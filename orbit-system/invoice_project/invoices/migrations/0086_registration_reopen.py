import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """New table recording a registration being reopened after auto-deactivation (30% fee).
    Additive only - no changes to any existing table."""

    dependencies = [
        ('invoices', '0085_schedulerule_fee_attendance_automation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistrationReopen',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fee_required', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fee_collected', models.DecimalField(decimal_places=2, max_digits=10)),
                ('note', models.CharField(blank=True, max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reopens', to='invoices.registration')),
                ('reopened_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
