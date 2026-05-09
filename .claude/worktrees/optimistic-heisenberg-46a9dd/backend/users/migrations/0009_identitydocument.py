from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_remove_user_email_verification_sent_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdentityDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(choices=[('id_card', 'National ID Card'), ('passport', 'Passport')], max_length=20)),
                ('front_image', models.ImageField(upload_to='identity/front/')),
                ('back_image', models.ImageField(blank=True, null=True, upload_to='identity/back/')),
                ('selfie_image', models.ImageField(upload_to='identity/selfies/')),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('rejection_reason', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='identity_document', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
