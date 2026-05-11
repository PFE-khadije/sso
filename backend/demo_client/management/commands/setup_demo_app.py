import os
from django.core.management.base import BaseCommand

# Space-separated list accepted by django-oauth-toolkit.
# Always includes localhost for local development plus whatever is in env.
_PROD_URI = os.getenv('DEMO_REDIRECT_URI', '').strip()
REDIRECT_URIS = 'http://localhost:8000/demo/callback/'
if _PROD_URI and _PROD_URI != 'http://localhost:8000/demo/callback/':
    REDIRECT_URIS = f'{REDIRECT_URIS} {_PROD_URI}'


class Command(BaseCommand):
    help = 'Create or update the NovaGard Demo OAuth2 client application in the database'

    def handle(self, *args, **options):
        from oauth2_provider.models import Application

        app, created = Application.objects.update_or_create(
            name='NovaGard Demo Client',
            defaults={
                'client_type': Application.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
                'redirect_uris': REDIRECT_URIS,
                'skip_authorization': False,
            },
        )

        verb = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(
            f'Demo app {verb}.\n'
            f'  Client ID:     {app.client_id}\n'
            f'  Client Secret: {app.client_secret}\n'
            f'  Redirect URIs: {REDIRECT_URIS}'
        ))
