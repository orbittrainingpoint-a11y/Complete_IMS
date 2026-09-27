from django.db import migrations, models


class Migration(migrations.Migration):
    """Minimum stagger between two individual students' start times for the same trainer.
    Overlapping windows are still the whole point of individual rotation; only starting two
    students at (near enough) the same instant is now a real conflict."""

    dependencies = [
        ('invoices', '0076_student_checkin'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedulingsetting', name='min_individual_gap_minutes',
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Two individual students' sessions may overlap (that's the rotation), but their "
                          'start times must be at least this many minutes apart - the trainer cannot start '
                          'two students at the exact same time.'),
        ),
    ]
