from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_remove_identitydocument_expiry_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='biometricprofile',
            name='liveness_score_enrollment',
        ),
    ]
