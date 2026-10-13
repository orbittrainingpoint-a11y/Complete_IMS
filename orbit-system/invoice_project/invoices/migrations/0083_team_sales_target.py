import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """A sales manager's team target, separate from her own personal target (SalesTarget,
    reused as-is for her individual number). Additive only."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0082_weekly_schedule_notice'),
    ]

    operations = [
        migrations.CreateModel(name='TeamSalesTarget', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('month', models.DateField()),
            ('target_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('target_registrations', models.IntegerField(default=0)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='team_targets_created', to=settings.AUTH_USER_MODEL)),
            ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_sales_targets', to=settings.AUTH_USER_MODEL)),
        ], options={'unique_together': {('manager', 'month')}}),
    ]
