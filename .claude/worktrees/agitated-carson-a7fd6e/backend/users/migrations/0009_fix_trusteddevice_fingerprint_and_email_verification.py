from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_remove_user_email_verification_sent_at_and_more'),
    ]

    operations = [
        # 1. Replace global unique on device_fingerprint with per-user unique_together
        migrations.AlterField(
            model_name='trusteddevice',
            name='device_fingerprint',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='trusteddevice',
            unique_together={('user', 'device_fingerprint')},
        ),

        # 2. Re-add email verification fields (removed in 0008)
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_token',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
