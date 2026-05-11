import os
import json
import base64
import hashlib
import secrets as _secrets
from urllib.parse import urlencode, quote
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def _get_app():
    try:
        from oauth2_provider.models import Application
        return Application.objects.get(name='NovaGard Demo Client')
    except Exception:
        return None


def _pkce_pair():
    verifier = _secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return verifier, challenge


def _redirect_uri(request):
    """Always derives the callback URL from the current request host,
    so it works identically on localhost and on Render."""
    return request.build_absolute_uri('/demo/callback/')


def index(request):
    app = _get_app()
    if app is None:
        return render(request, 'demo_client/setup_needed.html')

    if request.session.get('demo_user'):
        return render(request, 'demo_client/profile.html', {
            'user': request.session['demo_user'],
            'access_token': request.session.get('demo_access_token', ''),
        })

    redirect_uri = _redirect_uri(request)
    verifier, challenge = _pkce_pair()
    request.session['pkce_verifier'] = verifier
    request.session['demo_redirect_uri'] = redirect_uri

    params = {
        'response_type': 'code',
        'client_id': app.client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid read',
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    authorize_url = '/o/authorize/?' + urlencode(params)

    return render(request, 'demo_client/index.html', {
        'authorize_url': authorize_url,
        'authorize_url_register': authorize_url + '&prompt=login',
        'redirect_uri': redirect_uri,
        'client_id': app.client_id,
    })


def callback(request):
    code = request.GET.get('code')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description', '')

    if error or not code:
        return render(request, 'demo_client/error.html', {
            'error': error or 'Code manquant',
            'description': error_description or "L'autorisation a été refusée ou une erreur s'est produite.",
        })

    app = _get_app()
    if app is None:
        return render(request, 'demo_client/setup_needed.html')

    redirect_uri = request.session.pop('demo_redirect_uri', _redirect_uri(request))
    code_verifier = request.session.pop('pkce_verifier', None)
    token_url = request.build_absolute_uri('/o/token/')

    try:
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': app.client_id,
            'client_secret': app.client_secret,
        }
        if code_verifier:
            token_data['code_verifier'] = code_verifier

        resp = requests.post(token_url, data=token_data, timeout=10)
        if not resp.ok:
            return render(request, 'demo_client/error.html', {
                'error': 'Échange de token échoué',
                'description': resp.text,
            })

        access_token = resp.json().get('access_token', '')
        userinfo_url = request.build_absolute_uri('/api/userinfo/')
        user_resp = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        user_data = user_resp.json() if user_resp.ok else {}
        request.session['demo_user'] = user_data
        request.session['demo_access_token'] = access_token
        return redirect('/demo/')

    except Exception as exc:
        return render(request, 'demo_client/error.html', {
            'error': 'Erreur de connexion',
            'description': str(exc),
        })


def logout_view(request):
    request.session.pop('demo_user', None)
    request.session.pop('demo_access_token', None)
    return redirect('/demo/')


def web_register(request):
    """Web registration for users without the mobile app."""
    next_url = request.GET.get('next', '/demo/')
    errors = {}

    if request.method == 'POST':
        next_url = request.POST.get('next', '/demo/')
        step = request.POST.get('step', 'register')

        # Step 2: verify email OTP
        if step == 'verify':
            email = request.POST.get('email', '').strip()
            code = request.POST.get('code', '').strip()
            api_url = request.build_absolute_uri('/api/verify-email/')
            try:
                resp = requests.post(api_url, json={'email': email, 'code': code}, timeout=10)
                if resp.status_code == 200:
                    return redirect(f'/accounts/login/?next={quote(next_url)}&verified=1')
                errors = resp.json()
            except Exception as exc:
                errors = {'__all__': [str(exc)]}
            return render(request, 'demo_client/register.html', {
                'errors': errors,
                'next': next_url,
                'pending_email': email,
                'step': 'verify',
            })

        # Step 1: create account
        payload = {
            'email': request.POST.get('email', '').strip(),
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name': request.POST.get('last_name', '').strip(),
            'password': request.POST.get('password', ''),
            'password2': request.POST.get('password2', ''),
        }
        api_url = request.build_absolute_uri('/api/signup/')
        try:
            resp = requests.post(api_url, json=payload, timeout=10)
            if resp.status_code == 201:
                return render(request, 'demo_client/register.html', {
                    'next': next_url,
                    'pending_email': payload['email'],
                    'step': 'verify',
                })
            errors = resp.json()
        except Exception as exc:
            errors = {'__all__': [str(exc)]}

    return render(request, 'demo_client/register.html', {
        'errors': errors,
        'next': next_url,
        'post': request.POST if request.method == 'POST' else {},
        'step': 'register',
    })


@csrf_exempt
def qr_session(request):
    """Called by JS after QR confirmation. Receives the JWT, fetches userinfo,
    and creates a demo session — same as the OAuth2 callback."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body)
        access = body.get('access')
        if not access:
            return JsonResponse({'error': 'access token required'}, status=400)
        userinfo_url = request.build_absolute_uri('/api/userinfo/')
        user_resp = requests.get(
            userinfo_url,
            headers={'Authorization': f'Bearer {access}'},
            timeout=10,
        )
        user_data = user_resp.json() if user_resp.ok else {}
        request.session['demo_user'] = user_data
        request.session['demo_access_token'] = access
        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)
