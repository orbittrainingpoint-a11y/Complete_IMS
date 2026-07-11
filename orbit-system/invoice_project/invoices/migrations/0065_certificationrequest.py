import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0064_registration_createdat_welcomeemailsent'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificationRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_name', models.CharField(max_length=200)),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('completion_date', models.DateField(blank=True, null=True)),
                ('course_completed', models.BooleanField(blank=True, null=True)),
                ('client_notes', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Response'),
                        ('submitted', 'Submitted by Client'),
                        ('approved', 'Certificate Generated'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('registration', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cert_requests',
                    to='invoices.registration',
                )),
                ('sent_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('generated_certificate', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='invoices.certificate',
                )),
            ],
        ),
    ]
