from django.db import migrations, models


class Migration(migrations.Migration):
    """Fields backing automated fee-overdue and repeated-absence pause/cancel. Additive only;
    every existing rule defaults to pause_kind='manual' (no behavior change) and
    consecutive_absences=0 / attendance_warned=False."""

    dependencies = [
        ('invoices', '0084_schedulerule_weekday_times'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedulerule',
            name='pause_kind',
            field=models.CharField(choices=[('manual', 'Manual'), ('fee', 'Fee overdue'), ('attendance', 'Repeated absence')],
                                   default='manual', max_length=10,
                                   help_text='Why this rule is paused - manual (staff action) vs the two automated reasons.'),
        ),
        migrations.AddField(
            model_name='schedulerule',
            name='fee_pause_date',
            field=models.DateField(blank=True, null=True,
                                   help_text='Anchor for the 14-day auto-deactivation clock; only set for fee pauses.'),
        ),
        migrations.AddField(
            model_name='schedulerule',
            name='consecutive_absences',
            field=models.PositiveIntegerField(default=0,
                                              help_text='Resets to 0 on any completed session; drives the attendance auto-pause/cancel.'),
        ),
        migrations.AddField(
            model_name='schedulerule',
            name='attendance_warned',
            field=models.BooleanField(default=False,
                                      help_text='Already auto-paused once for absences - the next streak cancels the registration instead of pausing again.'),
        ),
    ]
