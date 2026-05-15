from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_remove_biometricprofile_liveness_score_enrollment'),
    ]

    operations = [
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_first_name_fl',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_last_name_fl',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_first_name_ar',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_last_name_ar',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_birth_date',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_doc_number',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_birth_place_fl',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_birth_place_ar',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_gender',
            field=models.CharField(blank=True, default='', max_length=5),
        ),
        migrations.AddField(
            model_name='identitydocument',
            name='ocr_nationality',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]
