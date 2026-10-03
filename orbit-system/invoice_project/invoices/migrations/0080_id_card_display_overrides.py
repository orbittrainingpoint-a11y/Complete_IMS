from django.db import migrations, models


class Migration(migrations.Migration):
    """Lets staff correct what's printed on an ID card (name/phone/email) without touching the
    student's actual registration record. Blank = still uses the live registration value."""

    dependencies = [
        ('invoices', '0079_student_id_card'),
    ]

    operations = [
        migrations.AddField(model_name='studentidcard', name='display_name', field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name='studentidcard', name='display_phone', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='studentidcard', name='display_email', field=models.EmailField(blank=True, max_length=254)),
    ]
