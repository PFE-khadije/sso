from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0013_alter_trusteddevice_device_fingerprint'),
    ]

    operations = [
        migrations.AddField(
            model_name='trusteddevice',
            name='last_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='trusteddevice',
            name='ua_hash',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
