from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the NovaGard Demo OAuth2 client application in the database'

    def handle(self, *args, **options):
        from oauth2_provider.models import Application

        app, created = Application.objects.get_or_create(
            name='NovaGard Demo Client',
            defaults={
                'client_type': Application.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
                'redirect_uris': 'http://localhost:8000/demo/callback/',
                'skip_authorization': False,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'Demo app created.\n  Client ID:     {app.client_id}\n  Client Secret: {app.client_secret}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'Demo app already exists.\n  Client ID: {app.client_id}'
            ))
