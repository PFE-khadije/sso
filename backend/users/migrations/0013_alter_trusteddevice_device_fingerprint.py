from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_user_email_verified'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='trusteddevice',
            name='device_fingerprint',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='trusteddevice',
            unique_together={('user', 'device_fingerprint')},
        ),
    ]
