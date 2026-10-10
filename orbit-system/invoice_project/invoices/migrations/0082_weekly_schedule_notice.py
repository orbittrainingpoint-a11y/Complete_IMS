import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Weekly schedule-reminder email: one row per registration per week sent, so the
    Monday cron job never double-sends. Additive only."""

    dependencies = [
        ('invoices', '0081_payroll'),
    ]

    operations = [
        migrations.CreateModel(name='WeeklyScheduleNotice', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('week_start', models.DateField(help_text='The Monday this notice covers')),
            ('session_count', models.PositiveIntegerField(default=0)),
            ('sent_at', models.DateTimeField(auto_now_add=True)),
            ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weekly_schedule_notices', to='invoices.registration')),
        ], options={'ordering': ['-week_start'], 'unique_together': {('registration', 'week_start')}}),
    ]
