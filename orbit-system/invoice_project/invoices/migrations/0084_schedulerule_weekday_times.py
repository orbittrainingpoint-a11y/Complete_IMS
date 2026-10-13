from django.db import migrations, models


class Migration(migrations.Migration):
    """Optional per-day time override for a schedule, blank = every day uses start_time
    (identical to today's behavior for every existing rule). Additive only."""

    dependencies = [
        ('invoices', '0083_team_sales_target'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedulerule',
            name='weekday_times',
            field=models.CharField(blank=True, max_length=100,
                help_text='Optional per-day time override, "weekday:HHMM,weekday:HHMM" e.g. "0:1000,2:1400,4:1600" '
                          '- for students/batches taking different timing on different days. A day not listed here '
                          'uses start_time. Blank (the default) means every day uses start_time, same as before this '
                          'field existed. Parsed by schedule_engine.parse_day_times/format_day_times.'),
        ),
    ]
