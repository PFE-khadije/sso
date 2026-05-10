import os
from django.core.management.base import BaseCommand

REDIRECT_URI = os.getenv(
    'DEMO_REDIRECT_URI',
    'http://localhost:8000/demo/callback/',
)


class Command(BaseCommand):
    help = 'Create or update the NovaGard Demo OAuth2 client application in the database'

    def handle(self, *args, **options):
        from oauth2_provider.models import Application

        app, created = Application.objects.update_or_create(
            name='NovaGard Demo Client',
            defaults={
                'client_type': Application.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
                'redirect_uris': REDIRECT_URI,
                'skip_authorization': False,
            },
        )

        verb = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(
            f'Demo app {verb}.\n'
            f'  Client ID:     {app.client_id}\n'
            f'  Client Secret: {app.client_secret}\n'
            f'  Redirect URI:  {REDIRECT_URI}'
        ))
