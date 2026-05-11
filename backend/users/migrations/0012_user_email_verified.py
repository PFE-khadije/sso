from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_loginlockout_identitydocument_expiry_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            # preserve_default=False: existing rows get True (pre-verified),
            # but new signups use the model's default=False and must verify.
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]
