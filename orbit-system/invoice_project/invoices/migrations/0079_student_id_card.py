import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import invoices.models


class Migration(migrations.Migration):
    """Student ID cards: one per registration, additive only. PROTECT-equivalent via SET_NULL
    on course/generated_by so a deleted course or staff account never takes a card down with it."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0078_fix_purchase_invoice_totals'),
    ]

    operations = [
        migrations.CreateModel(name='StudentIDCard', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('photo', models.ImageField(upload_to=invoices.models.student_id_photo_path)),
            ('valid_until', models.DateField()),
            ('card_image', models.ImageField(blank=True, null=True, upload_to=invoices.models.student_id_card_path)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('registration', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='id_card', to='invoices.registration')),
            ('course', models.ForeignKey(blank=True, help_text="Which of the student's courses to print on the card", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.course')),
            ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ]),
    ]
