import json
import base64
import secrets
import math
import datetime
from difflib import SequenceMatcher
from django.urls import reverse

import requests
from django.conf import settings
from django.core.cache import cache          # uses Redis in prod, LocMemCache in dev
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet
from users.models import UserActivity
from django.utils import timezone
from .models import PasswordResetToken

# ── OTP functions ─────────────────────────────────────────────────────────────
# OTPs are stored via Django's cache framework, which is already configured in
# settings.py: Redis when REDIS_URL is set, LocMemCache otherwise.
# This means email/SMS MFA works in both production and development.

def generate_otp(length=6):
    """Génère un code OTP numérique (cryptographically secure)."""
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))

def store_otp(key, otp, ttl=300):
    """Stocke un OTP dans le cache Django (Redis en prod, LocMemCache en dev)."""
    cache.set(key, otp, timeout=ttl)

def verify_otp(key, otp):
    """Vérifie un OTP et le supprime si valide."""
    stored = cache.get(key)
    if stored and stored == otp:
        cache.delete(key)
        return True
    return False


def generate_password_reset_token(user):
    token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(user=user, token=token)
    return token

_EMAIL_MICROSERVICE_URL = "https://bmnext.pythonanywhere.com/senders/send-email"
_EMAIL_SENDER = {"name": "NovaGard", "color": "#1A73E8"}

def _send_email(to, subject, message):
    """Sends an email via the Email Microservice API."""
    import logging
    api_key = getattr(settings, 'EMAIL_MICROSERVICE_API_KEY', None)
    if not api_key:
        logging.getLogger(__name__).error(
            "EMAIL_MICROSERVICE_API_KEY is not set — email to %s was not sent.", to
        )
        return
    payload = {
        "api_key": api_key,
        "to": to,
        "subject": subject,
        "message": message,
        "sender": _EMAIL_SENDER,
    }
    try:
        response = requests.post(_EMAIL_MICROSERVICE_URL, json=payload, timeout=10)
        if not response.ok:
            logging.getLogger(__name__).error(
                "Email microservice error %s: %s", response.status_code, response.text
            )
    except requests.RequestException as exc:
        logging.getLogger(__name__).error("Email microservice unreachable: %s", exc)


def send_password_reset_email(user, request):
    token = generate_password_reset_token(user)
    reset_url = request.build_absolute_uri(f'/api/password-reset/confirm/?token={token}')
    _send_email(
        to=user.email,
        subject="Password Reset Request",
        message=f"Click the link to reset your password: {reset_url}\nThis link expires in 1 hour.",
    )

def send_email_otp(email, otp):
    """Envoie un OTP par email."""
    _send_email(
        to=email,
        subject="Votre code de vérification",
        message=f"Votre code de vérification est : {otp}\nCe code est valable 5 minutes.",
    )

def send_verification_email(user):
    """Génère et envoie un OTP de vérification d'email après l'inscription."""
    otp = generate_otp()
    store_otp(f'email_verify:{user.id}', otp, ttl=600)
    _send_email(
        to=user.email,
        subject="Vérifiez votre adresse email — NovaGard",
        message=(
            f"Bienvenue sur NovaGard !\n\n"
            f"Votre code de vérification est : {otp}\n"
            f"Ce code est valable 10 minutes.\n\n"
            f"Si vous n'avez pas créé de compte, ignorez cet email."
        ),
    )

def send_sms_otp(phone, otp):
    """
    Envoie un OTP par SMS.
    TODO: Integrate a real SMS provider (Twilio, Vonage, etc.) for production.
    Until then, SMS OTP is logged to the console only — do NOT enable SMS MFA in prod.
    """
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "SMS OTP requested for %s but no SMS provider is configured. "
        "Code: %s — integrate Twilio or similar before enabling SMS MFA in production.",
        phone, otp
    )

# ── Activity logging ─────────────────────────────────────────────────────────
def log_user_activity(user, event_type, description, request=None):
    ip = None
    user_agent = None
    if request:
        ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    UserActivity.objects.create(
        user=user,
        event_type=event_type,
        description=description,
        ip_address=ip,
        user_agent=user_agent
    )

# ── AI Service client ────────────────────────────────────────────────────────
AI_SERVICE_URL = getattr(settings, 'AI_SERVICE_URL', None)
if not AI_SERVICE_URL:
    raise ImproperlyConfigured("AI_SERVICE_URL must be defined in settings (e.g., 'http://localhost:5001')")

def _ai_headers():
    return {}

def _ai_error(response):
    """Extracts a human-readable error from an AI service error response."""
    try:
        body = response.json()
        return body.get('error') or body.get('detail') or body.get('message') or f"Service IA: HTTP {response.status_code}"
    except Exception:
        return f"Service IA indisponible (HTTP {response.status_code})"

class AIServiceError(Exception):
    pass

def health_check():
    """Vérifie si le service IA est disponible."""
    try:
        response = requests.get(f"{AI_SERVICE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def detect_face(image_bytes):
    """Détecte le plus grand visage dans une image."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/detect", files=files, headers=_ai_headers(), timeout=10)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.exceptions.Timeout:
        return {'error': 'Service IA: timeout'}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def extract_embedding(image_bytes):
    """Extrait l'embedding du visage (512 dimensions)."""
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/embed", files=files, headers=_ai_headers(), timeout=30)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.exceptions.Timeout:
        return {'error': 'Le service de reconnaissance faciale est temporairement indisponible. Réessayez dans quelques secondes.'}
    except requests.exceptions.ConnectionError:
        return {'error': 'Impossible de joindre le service de reconnaissance faciale.'}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def verify_face(image_bytes, reference_embedding):
    """Compare une image avec un embedding stocké."""
    payload = {'image': base64.b64encode(image_bytes).decode('utf-8'), 'embedding': reference_embedding}
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify", json=payload, headers=_ai_headers(), timeout=15)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def compare_two_faces(image_bytes1, image_bytes2):
    """Compare deux images et retourne la similarité."""
    payload = {
        'image1': base64.b64encode(image_bytes1).decode('utf-8'),
        'image2': base64.b64encode(image_bytes2).decode('utf-8'),
    }
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify", json=payload, headers=_ai_headers(), timeout=15)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}

def verify_id_card(id_card_bytes, selfie_bytes):
    """Vérifie que le selfie correspond à la photo de la pièce d'identité."""
    files = {
        'id_card': ('id_card.jpg', id_card_bytes, 'image/jpeg'),
        'selfie': ('selfie.jpg', selfie_bytes, 'image/jpeg'),
    }
    try:
        response = requests.post(f"{AI_SERVICE_URL}/verify-id", files=files, headers=_ai_headers(), timeout=30)
        if response.ok:
            return response.json()
        return {'error': _ai_error(response)}
    except requests.RequestException as e:
        return {'error': f"Erreur réseau: {str(e)}"}


# ── Encryption utilities (Fernet) ────────────────────────────────────────────
def get_encryption_key():
    """Récupère la clé de chiffrement depuis les settings. Lève une erreur si absente."""
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            "ENCRYPTION_KEY must be set in environment (e.g., .env file). "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return key

_cipher = None

def get_cipher():
    """Singleton Fernet instance."""
    global _cipher
    if _cipher is None:
        key = get_encryption_key()
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher

def encrypt_value(value):
    """Chiffre une chaîne et retourne en base64."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode('utf-8')
    cipher = get_cipher()
    encrypted = cipher.encrypt(value)
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_value(encrypted_value):
    """Déchiffre une valeur base64."""
    if encrypted_value is None:
        return None
    cipher = get_cipher()
    encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
    decrypted = cipher.decrypt(encrypted_bytes)
    return decrypted.decode('utf-8')

def encrypt_json(data):
    """Chiffre un objet JSON."""
    json_str = json.dumps(data)
    return encrypt_value(json_str)

def decrypt_json(encrypted_value):
    """Déchiffre et retourne un objet JSON."""
    decrypted_str = decrypt_value(encrypted_value)
    return json.loads(decrypted_str)


# ── Face identification helpers ───────────────────────────────────────────────
def cosine_sim(a, b):
    """Pure-Python cosine similarity between two embedding lists."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── OCR helpers ───────────────────────────────────────────────────────────────
_OCR_SERVICE_URL = "https://cheikhabdelkader.pythonanywhere.com/ocr"

def extract_card_text(image_bytes):
    """Extracts raw text from an ID card image via the NovaID OCR service.
    Handles both the new nested {"data": {...}} shape and older flat shapes."""
    try:
        response = requests.post(
            _OCR_SERVICE_URL,
            files={'image': ('document.jpg', image_bytes, 'image/jpeg')},
            timeout=30,
        )
        if response.ok:
            payload = response.json()
            if isinstance(payload, dict):
                data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
                # Prefer an explicit text blob if the service provides one;
                # otherwise stitch one together from the structured fields so
                # downstream fuzzy-search code still has content to match on.
                explicit = data.get('text') or data.get('raw_text')
                if explicit:
                    return explicit
                parts = [
                    data.get('first_name_fl'), data.get('last_name_fl'),
                    data.get('first_name_ll'), data.get('last_name_ll'),
                    data.get('birth_place_fl'), data.get('birth_place_ll'),
                    data.get('birth_date'), data.get('nni'),
                ]
                return ' '.join(str(p) for p in parts if p)
            return str(payload)
    except Exception:
        pass
    return ''


def extract_document_info(image_bytes):
    """Extracts structured info from an ID document.
    Priority: NovaID OCR service → regex fallback on raw OCR text.

    The NovaID OCR currently returns:
        {
          "data": {
            "first_name_fl": "Khadija",   "first_name_ll": "خديج",
            "last_name_fl":  "Abdellahi", "last_name_ll":  "عبد الله",
            "birth_date":    "YYYY-MM-DD",
            "birth_place_fl": "...",      "birth_place_ll": "...",
            "gender":         "F" | "M",
            "nationality_iso": "MRT",
            "nni":            "..."
          },
          "images": { "base64": "..." }
        }
    Returns a flat dict consumable by the verification flow:
        {first_name, last_name, first_name_ar, last_name_ar,
         birth_date, doc_number, raw_text, source}
    """
    import re

    # 1. NovaID OCR service — may return structured fields directly
    try:
        ocr_resp = requests.post(
            _OCR_SERVICE_URL,
            files={'image': ('document.jpg', image_bytes, 'image/jpeg')},
            timeout=30,
        )
        if ocr_resp.ok:
            payload = ocr_resp.json()
            if isinstance(payload, dict):
                # NovaID nests the structured fields inside a "data" key;
                # fall back to top-level for older / alternate response shapes.
                data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
                # Latin / French spelling — primary match target
                first_name = (
                    data.get('first_name_fl')
                    or data.get('first_name')
                    or data.get('prenom')
                )
                last_name = (
                    data.get('last_name_fl')
                    or data.get('last_name')
                    or data.get('nom')
                )
                # Arabic spelling — used as a secondary match target
                first_name_ar = data.get('first_name_ll') or data.get('first_name_ar')
                last_name_ar = data.get('last_name_ll') or data.get('last_name_ar')
                birth_date = data.get('birth_date') or data.get('date_naissance')
                doc_number = (
                    data.get('nni')
                    or data.get('doc_number')
                    or data.get('numero')
                )
                raw_text = data.get('text') or data.get('raw_text') or ''
                # If the service didn't include a flat text blob, build one
                # from every known field so legacy fuzzy-on-text fallbacks
                # still have something meaningful to search.
                if not raw_text:
                    parts = [
                        first_name, last_name, first_name_ar, last_name_ar,
                        data.get('birth_place_fl'), data.get('birth_place_ll'),
                        str(birth_date) if birth_date else '',
                        str(doc_number) if doc_number else '',
                    ]
                    raw_text = ' '.join(p for p in parts if p)
                if any([first_name, last_name, first_name_ar, last_name_ar,
                        birth_date, doc_number, raw_text]):
                    return {
                        'first_name': first_name,
                        'last_name': last_name,
                        'first_name_ar': first_name_ar,
                        'last_name_ar': last_name_ar,
                        'birth_date': birth_date,
                        'doc_number': doc_number,
                        'raw_text': raw_text,
                        'source': 'ocr',
                    }
    except requests.RequestException:
        pass

    # 2. Parse whatever raw text we have from OCR
    raw_text = extract_card_text(image_bytes)

    date_pattern = r'\b(\d{2}[./]\d{2}[./]\d{4})\b'
    dates = re.findall(date_pattern, raw_text)
    birth_date = dates[0] if len(dates) >= 1 else None

    doc_number = None
    num_match = re.search(r'\b([A-Z0-9]{8,12})\b', raw_text)
    if num_match:
        doc_number = num_match.group(1)

    return {
        'first_name': None,
        'last_name': None,
        'first_name_ar': None,
        'last_name_ar': None,
        'birth_date': birth_date,
        'doc_number': doc_number,
        'raw_text': raw_text,
        'source': 'ocr',
    }


def compare_names(registered_name, ocr_text, threshold=0.65):
    """Checks whether registered_name appears (fuzzy) in OCR text.
    Returns True if found, False if clearly absent, None if text is too short to judge."""
    if not registered_name or not ocr_text:
        return None
    if len(ocr_text.strip()) < 20:
        return None
    name = registered_name.lower().strip()
    text = ocr_text.lower()
    if name in text:
        return True
    n = len(name)
    for i in range(len(text) - n + 1):
        if SequenceMatcher(None, name, text[i:i + n]).ratio() >= threshold:
            return True
    return False


# ── Device auto-registration ──────────────────────────────────────────────────
def auto_register_device(user, request):
    """Creates or updates a TrustedDevice after any successful authentication."""
    import hashlib
    from .models import TrustedDevice
    fingerprint = request.META.get('HTTP_X_DEVICE_FINGERPRINT')
    if not fingerprint:
        return
    device_name = request.META.get('HTTP_X_DEVICE_NAME', 'Mobile Device')
    expires_at = timezone.now() + datetime.timedelta(days=30)
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    last_ip = (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', ''))[:45] or None
    ua_raw = request.META.get('HTTP_USER_AGENT', '')
    ua_hash = hashlib.sha256(ua_raw.encode()).hexdigest()[:64] if ua_raw else None
    TrustedDevice.objects.update_or_create(
        user=user,
        device_fingerprint=fingerprint,
        defaults={
            'device_name': device_name,
            'expires_at': expires_at,
            'last_ip': last_ip,
            'ua_hash': ua_hash,
        },
    )
last_name_ar,
                        birth_date, doc_number, raw_text]):
                    return {
                        'first_name': first_name,
                        'last_name': last_name,
                        'first_name_ar': first_name_ar,
                        'last_name_ar': last_name_ar,
                        'birth_date': birth_date,
                        'doc_number': doc_number,
                        'raw_text': raw_text,
                        'source': 'ocr',
                    }
    except requests.RequestException:
        pass

    # 2. Parse whatever raw text we have from OCR
    raw_text = extract_card_text(image_bytes)

    date_pattern = r'\b(\d{2}[./]\d{2}[./]\d{4})\b'
    dates = re.findall(date_pattern, raw_text)
    birth_date = dates[0] if len(dates) >= 1 else None

    doc_number = None
    num_match = re.search(r'\b([A-Z0-9]{8,12})\b', raw_text)
    if num_match:
        doc_number = num_match.group(1)

    return {
        'first_name': None,
        'last_name': None,
        'first_name_ar': None,
        'last_name_ar': None,
        'birth_date': birth_date,
        'doc_number': doc_number,
        'raw_text': raw_text,
        'source': 'ocr',
    }


def compare_names(registered_name, ocr_text, threshold=0.65):
    """Checks whether registered_name appears (fuzzy) in OCR text.
    Returns True if found, False if clearly absent, None if text is too short to judge."""
    if not registered_name or not ocr_text:
        return None
    if len(ocr_text.strip()) < 20:
        return None
    name = registered_name.lower().strip()
    text = ocr_text.lower()
    if name in text:
        return True
    n = len(name)
    for i in range(len(text) - n + 1):
        if SequenceMatcher(None, name, text[i:i + n]).ratio() >= threshold:
            return True
    return False


# ââ Device auto-registration ââââââââââââââââââââââââââââââ
def auto_register_device(user, request):
    """Creates or updates a TrustedDevice after any successful authentication."""
    import hashlib
    from .models import TrustedDevice
    fingerprint = request.META.get('HTTP_X_DEVICE_FINGERPRINT')
    if not fingerprint:
        return
    device_name = request.META.get('HTTP_X_DEVICE_NAME', 'Mobile Device')
    expires_at = timezone.now() + datetime.timedelta(days=30)
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    last_ip = (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', ''))[:45] or None
    ua_raw = request.META.get('HTTP_USER_AGENT', '')
    ua_hash = hashlib.sha256(ua_raw.encode()).hexdigest()[:64] if ua_raw else None
    TrustedDevice.objects.update_or_create(
        user=user,
        device_fingerprint=fingerprint,
        defaults={
            'device_name': device_name,
            'expires_at': expires_at,
            'last_ip': last_ip,
            'ua_hash': ua_hash,
        },
    )
