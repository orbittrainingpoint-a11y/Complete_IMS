import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed(apps, schema_editor):
    apps.get_model('invoices', 'CheckInSetting').objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    """Student Wi-Fi check-in (phase 1, software-only): per-student attendance records
    matched against the existing trainer schedule. Additive only; every FK to schedule
    rows is PROTECT so a check-in can never silently disappear."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0075_accounting_books'),
    ]

    operations = [
        migrations.CreateModel(name='CheckInSetting', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('is_enabled', models.BooleanField(default=True)),
            ('early_window_minutes', models.PositiveSmallIntegerField(default=60, help_text='How early before the scheduled start a student may check in. Check-in stays open for the whole session and closes at the scheduled end.')),
            ('rate_limit_attempts', models.PositiveSmallIntegerField(default=8, help_text='Failed attempts allowed from one address before a short block')),
            ('rate_limit_minutes', models.PositiveSmallIntegerField(default=10)),
        ]),
        migrations.CreateModel(name='CheckInAttempt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('student_id_text', models.CharField(blank=True, max_length=50)),
            ('result', models.CharField(choices=[('success', 'Matched a session'), ('invalid_student', 'Student ID not found'), ('inactive_student', 'Student account inactive'), ('no_schedule', 'No session today'), ('session_completed', 'Session already ended'), ('session_cancelled', 'Session cancelled'), ('already_confirmed', 'Already confirmed'), ('rate_limited', 'Too many attempts'), ('system_error', 'System error')], max_length=20)),
            ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
            ('user_agent', models.CharField(blank=True, max_length=300)),
            ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ('registration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.registration')),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel(name='StudentCheckIn', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('scheduled_date', models.DateField()),
            ('scheduled_start', models.TimeField()),
            ('scheduled_end', models.TimeField()),
            ('login_at', models.DateTimeField(auto_now_add=True, help_text='When the student reached the review page')),
            ('confirmed_at', models.DateTimeField(blank=True, null=True)),
            ('status', models.CharField(choices=[('awaiting_confirm', 'Shown, not yet confirmed'), ('confirmed', 'Confirmed'), ('no_show', 'No show'), ('cancelled', 'Session cancelled after check-in')], default='awaiting_confirm', max_length=20)),
            ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
            ('user_agent', models.CharField(blank=True, max_length=300)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('registration', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='wifi_checkins', to='invoices.registration')),
            ('occurrence', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='wifi_checkins', to='invoices.scheduleoccurrence')),
            ('class_session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='wifi_checkins', to='invoices.classsession')),
            ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.course')),
            ('trainer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wifi_checkins', to='invoices.trainer')),
            ('marked_no_show_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-scheduled_date', '-scheduled_start'], 'unique_together': {('registration', 'occurrence'), ('registration', 'class_session')}}),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
