from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_trusteddevice_ip_ua'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='identitydocument',
            name='expiry_date',
        ),
    ]
