from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import invoices.models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0066_institutesetting'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='is_refunded',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('document', models.FileField(blank=True, null=True, upload_to=invoices.models.refund_doc_upload_path)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('refund_reference', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Confirmation'),
                        ('confirmed', 'Confirmed & Processed'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('admin_notes', models.TextField(blank=True)),
                ('initiated_at', models.DateTimeField(auto_now_add=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('registration', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refund',
                    to='invoices.registration',
                )),
                ('initiated_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='refunds_initiated',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('confirmed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='refunds_confirmed',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
