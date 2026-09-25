import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

POLICY = [('block', 'Block (admin override only)'), ('confirm', 'Warn and require confirmation'), ('allow', 'Allow silently')]


class Migration(migrations.Migration):
    """Recurring schedule rules, generated occurrences, audit trail and scheduling settings.
    Additive only. Rules/occurrences point at Trainer with PROTECT (a schedule can never lose
    its trainer); links to students/batches/courses are SET_NULL so history survives deletes."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0073_trainer_schedule_batches'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainer', name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                       related_name='trainer_record', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='SchedulingSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_interval', models.PositiveSmallIntegerField(default=30, help_text='Individual teaching interval (minutes): 15/30/45/60')),
                ('max_concurrent_individuals', models.PositiveSmallIntegerField(default=3, help_text='Students a trainer can rotate between at the same time')),
                ('batch_batch_policy', models.CharField(choices=POLICY, default='block', max_length=8)),
                ('batch_individual_policy', models.CharField(choices=POLICY, default='confirm', max_length=8)),
                ('working_hours_policy', models.CharField(choices=POLICY, default='confirm', max_length=8)),
                ('auto_extend', models.BooleanField(default=True, help_text='Add make-up sessions at the end when a session is cancelled or missed')),
                ('low_hours_threshold', models.PositiveSmallIntegerField(default=120, help_text='Alert when remaining training is at or below this many minutes')),
                ('absence_alert_count', models.PositiveSmallIntegerField(default=3, help_text='Flag a student after this many missed sessions')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('schedule_type', models.CharField(choices=[('individual', 'Individual'), ('batch', 'Batch')], default='individual', max_length=10)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('end_date_manual', models.BooleanField(default=False)),
                ('weekdays', models.CharField(max_length=20)),
                ('start_time', models.TimeField()),
                ('session_minutes', models.PositiveIntegerField(default=60)),
                ('teaching_interval', models.PositiveSmallIntegerField(default=30)),
                ('total_minutes', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('cancelled', 'Cancelled'), ('completed', 'Completed')], default='active', max_length=10)),
                ('auto_extend', models.BooleanField(default=True)),
                ('pause_date', models.DateField(blank=True, null=True)),
                ('pause_reason', models.CharField(blank=True, max_length=200)),
                ('pause_notes', models.TextField(blank=True)),
                ('expected_resume', models.DateField(blank=True, null=True)),
                ('resume_date', models.DateField(blank=True, null=True)),
                ('cancel_date', models.DateField(blank=True, null=True)),
                ('cancel_reason', models.CharField(blank=True, max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rules', to='invoices.batch')),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedule_rules', to='invoices.course')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rules_created', to=settings.AUTH_USER_MODEL)),
                ('paused_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('registration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedule_rules', to='invoices.registration')),
                ('trainer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rules', to='invoices.trainer')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ScheduleOccurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('completed', 'Completed'), ('absent', 'Absent'), ('cancelled', 'Cancelled'), ('paused', 'Paused'), ('rescheduled', 'Rescheduled')], db_index=True, default='scheduled', max_length=12)),
                ('delivered_minutes', models.PositiveIntegerField(default=0)),
                ('actual_start', models.TimeField(blank=True, null=True)),
                ('actual_end', models.TimeField(blank=True, null=True)),
                ('attendance', models.CharField(blank=True, max_length=10)),
                ('note', models.TextField(blank=True)),
                ('is_exception', models.BooleanField(default=False)),
                ('original_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='occurrences', to='invoices.schedulerule')),
                ('trainer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='occurrences', to='invoices.trainer')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['date', 'start_time']},
        ),
        migrations.AddIndex(
            model_name='scheduleoccurrence',
            index=models.Index(fields=['trainer', 'date'], name='invoices_sc_trainer_2c1a7e_idx'),
        ),
        migrations.CreateModel(
            name='ScheduleAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=30)),
                ('detail', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('occurrence', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.scheduleoccurrence')),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit', to='invoices.schedulerule')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
    ]
