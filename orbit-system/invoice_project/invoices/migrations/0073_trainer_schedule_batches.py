import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

WEEKDAYS = [(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
            (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')]


class Migration(migrations.Migration):
    """Trainer schedule + batch management. Additive only - new tables, nothing altered.
    Foreign keys to Trainer/Course/User are SET_NULL so deleting one of them can never
    delete batches or sessions."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0072_prevent_course_cascade_delete'),
    ]

    operations = [
        migrations.CreateModel(
            name='Trainer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('specialization', models.CharField(blank=True, max_length=200)),
                ('color', models.CharField(default='#2563eb', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('courses', models.ManyToManyField(blank=True, related_name='trainers', to='invoices.course')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='TrainerWorkingHours',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(choices=WEEKDAYS)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('trainer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='working_hours', to='invoices.trainer')),
            ],
            options={'ordering': ['weekday'], 'unique_together': {('trainer', 'weekday')}},
        ),
        migrations.CreateModel(
            name='TrainerLeave',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_from', models.DateField()),
                ('date_to', models.DateField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('trainer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leaves', to='invoices.trainer')),
            ],
            options={'ordering': ['-date_from']},
        ),
        migrations.CreateModel(
            name='Batch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('weekdays', models.CharField(default='0,1,2,3,4', max_length=20)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('mode', models.CharField(choices=[('offline', 'Offline'), ('online', 'Online')], default='offline', max_length=10)),
                ('venue', models.CharField(blank=True, max_length=200)),
                ('capacity', models.PositiveIntegerField(default=10)),
                ('status', models.CharField(choices=[('upcoming', 'Upcoming'), ('ongoing', 'Ongoing'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='upcoming', max_length=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batches', to='invoices.course')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batches_created', to=settings.AUTH_USER_MODEL)),
                ('trainer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batches', to='invoices.trainer')),
            ],
            options={'ordering': ['start_date', 'start_time'], 'verbose_name_plural': 'batches'},
        ),
        migrations.CreateModel(
            name='BatchSkipDate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skip_dates', to='invoices.batch')),
            ],
            options={'ordering': ['date'], 'unique_together': {('batch', 'date')}},
        ),
        migrations.CreateModel(
            name='BatchStudent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('dropped', 'Dropped'), ('completed', 'Completed')], default='active', max_length=10)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='students', to='invoices.batch')),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='invoices.course')),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batch_links', to='invoices.registration')),
            ],
            options={'unique_together': {('batch', 'registration')}},
        ),
        migrations.CreateModel(
            name='ClassSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_type', models.CharField(choices=[('private', 'Private class'), ('makeup', 'Make-up class'), ('demo', 'Demo class'), ('workshop', 'Workshop'), ('other', 'Other')], default='private', max_length=10)),
                ('date', models.DateField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('student_name', models.CharField(blank=True, max_length=150)),
                ('mode', models.CharField(choices=[('offline', 'Offline'), ('online', 'Online')], default='offline', max_length=10)),
                ('venue', models.CharField(blank=True, max_length=200)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('no_show', 'No show')], default='scheduled', max_length=10)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='invoices.course')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions_created', to=settings.AUTH_USER_MODEL)),
                ('registration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='class_sessions', to='invoices.registration')),
                ('trainer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='invoices.trainer')),
            ],
            options={'ordering': ['date', 'start_time']},
        ),
    ]
