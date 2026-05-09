"""
RSS SOC Middleware - Security Middleware for Django banking apps
==================================================================
Detects: SQLi, XSS, Path traversal, Brute force, Login success/failure
Pushes events to central SOC (Loki) via HTTP.

Usage:
    1. Copy this file into your Django project (e.g. apps/core/security_middleware.py)
    2. Add to MIDDLEWARE in settings.py:
          'apps.core.security_middleware.SecurityMiddleware'
    3. Set environment variables in your .env:
          RSS_SOC_APP_NAME=your-bank-name
          RSS_SOC_URL=http://198.199.70.48:3100
          RSS_SOC_TOKEN=your-token
          RSS_SOC_LOCAL_LOGS=/app/logs   (for fail2ban)
    4. Restart Django.

Author: Sidatt Belkhair - RSS Bank PFE 2025-2026
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from queue import Queue, Empty

try:
    import requests
except ImportError:
    raise ImportError("rss-soc requires 'requests'. Install with: pip install requests")

try:
    from django.core.cache import cache
except ImportError:
    cache = None  # fallback if Django cache not configured


# =============================================================================
# CONFIGURATION (via environment variables)
# =============================================================================
APP_NAME   = os.getenv('RSS_SOC_APP_NAME',   'unknown-app')
SOC_URL    = os.getenv('RSS_SOC_URL',        'http://198.199.70.48:3100')
SOC_TOKEN  = os.getenv('RSS_SOC_TOKEN',      '')
ENV_NAME   = os.getenv('RSS_SOC_ENV',        'production')
LOCAL_LOGS = os.getenv('RSS_SOC_LOCAL_LOGS', '/app/logs')


# =============================================================================
# THREAT DETECTION PATTERNS
# =============================================================================
SQL_RE = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|CAST|CONVERT)\b"
    r"|('|\")(\s)*(OR|AND)(\s)*(('|\")|\d)"
    r"|--(\s*$|\s+\w)"
    r"|\bOR\s+1\s*=\s*1\b"
    r"|SLEEP\s*\(|BENCHMARK\s*\()",
    re.IGNORECASE,
)
XSS_RE = re.compile(
    r"(<script|</script|javascript:|on\w+\s*=|<iframe|<object|<embed"
    r"|<img[^>]+onerror|alert\s*\(|document\.cookie)",
    re.IGNORECASE,
)
TRAVERSAL_RE = re.compile(r"\.\./|\.\.\\|/etc/passwd|%2e%2e", re.IGNORECASE)


# =============================================================================
# ASYNC LOKI PUSHER (non-blocking background thread)
# =============================================================================
_log_queue: Queue = Queue(maxsize=2000)
_worker_started = False
_worker_lock = threading.Lock()


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _loki_worker():
    """Background thread: drains queue and pushes batches to Loki."""
    session = requests.Session()
    endpoint = f"{SOC_URL.rstrip('/')}/loki/api/v1/push"
    headers = {'Content-Type': 'application/json'}
    if SOC_TOKEN:
        headers['X-Scope-OrgID'] = SOC_TOKEN

    while True:
        batch = []
        try:
            batch.append(_log_queue.get(timeout=5))
            for _ in range(99):  # drain up to 100 events at once
                try:
                    batch.append(_log_queue.get_nowait())
                except Empty:
                    break
        except Empty:
            continue

        # Group events by labels (Loki streams)
        streams_by_labels = {}
        for ev in batch:
            key = tuple(sorted(ev['labels'].items()))
            streams_by_labels.setdefault(key, []).append(ev)

        streams = []
        for key, events in streams_by_labels.items():
            labels = dict(key)
            values = [
                [str(int(ev['ts_unix'] * 1e9)), json.dumps(ev['data'])]
                for ev in events
            ]
            streams.append({'stream': labels, 'values': values})

        try:
            session.post(endpoint, json={'streams': streams},
                         headers=headers, timeout=5)
        except Exception:
            # SOC unreachable? We silently drop - never crash the app
            pass


def _ensure_worker():
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            t = threading.Thread(target=_loki_worker, daemon=True, name='rss-soc-loki-pusher')
            t.start()
            _worker_started = True


def _push_event(event_type, data, job):
    """Queue an event for async push to Loki + write locally for fail2ban."""
    _ensure_worker()

    # 1. Push to Loki (remote SOC)
    labels = {'app': APP_NAME, 'env': ENV_NAME, 'job': job}
    if event_type and job == 'django-security':
        labels['event'] = event_type

    try:
        _log_queue.put_nowait({
            'ts_unix': time.time(),
            'data': data,
            'labels': labels,
        })
    except Exception:
        pass  # queue full - drop

    # 2. Write locally (for fail2ban to read)
    try:
        os.makedirs(LOCAL_LOGS, exist_ok=True)
        fname = 'security.log' if job == 'django-security' else 'access.log'
        with open(os.path.join(LOCAL_LOGS, fname), 'a') as f:
            f.write(json.dumps(data) + '\n')
    except Exception:
        pass


# =============================================================================
# HELPERS
# =============================================================================
def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _detect(value):
    if not isinstance(value, str):
        return []
    threats = []
    if SQL_RE.search(value):
        threats.append('SQL_INJECTION')
    if XSS_RE.search(value):
        threats.append('XSS')
    if TRAVERSAL_RE.search(value):
        threats.append('PATH_TRAVERSAL')
    return threats


def _scan_request(request):
    threats = []
    try:
        for k, v in request.GET.items():
            threats += _detect(f"{k}={v}")

        if request.content_type and 'json' in request.content_type:
            try:
                body = request.body.decode('utf-8', errors='ignore')
                threats += _detect(body)
            except Exception:
                pass
        else:
            try:
                for k, v in request.POST.items():
                    threats += _detect(f"{k}={v}")
            except Exception:
                pass

        threats += _detect(request.path)
    except Exception:
        pass
    return list(set(threats))


# =============================================================================
# MIDDLEWARE CLASS
# =============================================================================
class SecurityMiddleware:
    """Add to Django MIDDLEWARE in settings.py."""

    def __init__(self, get_response):
        self.get_response = get_response
        print(f"[rss-soc] SOC middleware active: app={APP_NAME}, soc={SOC_URL}")

    def __call__(self, request):
        start = time.time()
        ip = _get_client_ip(request)

        # ─── 1. Threat detection BEFORE processing ──────────────
        threats = _scan_request(request)
        for threat in threats:
            _push_event(threat, {
                'ts': _now_iso(), 'event': threat, 'ip': ip,
                'method': request.method, 'path': request.path,
                'app': APP_NAME,
            }, job='django-security')

        # ─── 2. Normal processing ───────────────────────────────
        response = self.get_response(request)
        duration_ms = int((time.time() - start) * 1000)

        # ─── 3. Identify user ───────────────────────────────────
        user_email = 'anonymous'
        try:
            u = getattr(request, 'user', None)
            if u and hasattr(u, 'email') and u.is_authenticated:
                user_email = u.email
        except Exception:
            pass

        # ─── 4. Access log (every request) ──────────────────────
        _push_event('', {
            'ts': _now_iso(), 'method': request.method,
            'path': request.path, 'status': response.status_code,
            'ip': ip, 'user': user_email,
            'duration_ms': duration_ms, 'app': APP_NAME,
        }, job='django-access')

        # ─── 5. Login events detection ──────────────────────────
        is_login = ('login' in request.path.lower() or
                    'auth' in request.path.lower()) and request.method == 'POST'

        if is_login:
            if response.status_code in (200, 201):
                _push_event('LOGIN_SUCCESS', {
                    'ts': _now_iso(), 'event': 'LOGIN_SUCCESS',
                    'ip': ip, 'user': user_email, 'app': APP_NAME,
                }, job='django-security')
            elif response.status_code in (400, 401, 403):
                _push_event('LOGIN_FAILURE', {
                    'ts': _now_iso(), 'event': 'LOGIN_FAILURE',
                    'ip': ip, 'status': response.status_code, 'app': APP_NAME,
                }, job='django-security')

                # Brute force counter
                if cache is not None:
                    try:
                        key = f'rss_soc_bf:{ip}'
                        count = cache.get(key, 0) + 1
                        cache.set(key, count, timeout=300)
                        if count >= 5:
                            _push_event('BRUTE_FORCE', {
                                'ts': _now_iso(), 'event': 'BRUTE_FORCE',
                                'ip': ip, 'attempts': count, 'app': APP_NAME,
                            }, job='django-security')
                    except Exception:
                        pass

        # ─── 6. Other 401/403 events ────────────────────────────
        elif response.status_code == 401:
            _push_event('UNAUTHORIZED', {
                'ts': _now_iso(), 'event': 'UNAUTHORIZED',
                'ip': ip, 'path': request.path, 'app': APP_NAME,
            }, job='django-security')

        return response
