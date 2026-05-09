import requests
from django.shortcuts import render, redirect

REDIRECT_URI = 'http://localhost:8000/demo/callback/'
SCOPE = 'openid profile email'


def _get_app():
    try:
        from oauth2_provider.models import Application
        return Application.objects.get(name='NovaGard Demo Client')
    except Exception:
        return None


def index(request):
    app = _get_app()
    if app is None:
        return render(request, 'demo_client/setup_needed.html')

    if request.session.get('demo_user'):
        return render(request, 'demo_client/profile.html', {
            'user': request.session['demo_user'],
            'access_token': request.session.get('demo_access_token', ''),
        })

    return render(request, 'demo_client/index.html', {
        'client_id': app.client_id,
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
    })


def callback(request):
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error or not code:
        return render(request, 'demo_client/error.html', {
            'error': error or 'Code manquant',
            'description': "L'autorisation a été refusée ou une erreur s'est produite.",
        })

    app = _get_app()
    if app is None:
        return render(request, 'demo_client/setup_needed.html')

    token_url = request.build_absolute_uri('/o/token/')
    try:
        resp = requests.post(token_url, data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': app.client_id,
            'client_secret': app.client_secret,
        }, timeout=10)

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
