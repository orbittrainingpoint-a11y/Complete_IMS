from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Deleting a staff account must never delete the invoices/clients/
    quotations/purchase invoices they created — that's real revenue history,
    not login data. These four FKs were previously CASCADE, which silently
    destroyed hundreds of real invoices when departed staff accounts were
    removed. Switched to SET_NULL to match the pattern already used
    elsewhere (recorded_by, initiated_by, etc.)."""

    dependencies = [('invoices', '0070_certificationrequest_class_starting_date')]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='invoicepurchase',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='quotation',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
