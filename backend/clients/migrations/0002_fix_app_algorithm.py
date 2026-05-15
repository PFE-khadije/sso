from django.db import migrations


def set_rs256_on_apps(apps, schema_editor):
    from oauth2_provider.models import Application
    Application.objects.filter(algorithm='').update(algorithm='RS256')


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_rs256_on_apps, migrations.RunPython.noop),
    ]
