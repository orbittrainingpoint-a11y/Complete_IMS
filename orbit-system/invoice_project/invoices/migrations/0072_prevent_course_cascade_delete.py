import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Deleting a Course row (e.g. cleaning up a duplicate) must never delete
    the records that reference it. This already happened once: 65+ student
    registrations lost their course link with no way to recover it, because
    RegistrationCourse.course was CASCADE. Switched to PROTECT there (force
    an explicit reassignment before a Course can be deleted) and to SET_NULL
    for the others, matching the pattern already used for Invoice.course."""

    dependencies = [('invoices', '0071_prevent_user_cascade_delete')]

    operations = [
        migrations.AlterField(
            model_name='quotationitem',
            name='course',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='invoices.course'),
        ),
        migrations.AlterField(
            model_name='registrationcourse',
            name='course',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='invoices.course'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='course',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='invoices.course'),
        ),
        migrations.AlterField(
            model_name='trainingschedule',
            name='course',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedules', to='invoices.course'),
        ),
    ]
