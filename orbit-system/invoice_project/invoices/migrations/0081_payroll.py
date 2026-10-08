import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Payroll: employee records, monthly payroll runs, and payslips with bonus/deduction line
    items. Mark-paid posts one expense transaction per run into the existing Accounting module
    (Salaries & wages category, seeded in 0075). Additive only."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0080_id_card_display_overrides'),
    ]

    operations = [
        migrations.CreateModel(name='Employee', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=150)),
            ('designation', models.CharField(blank=True, max_length=100)),
            ('phone', models.CharField(blank=True, max_length=30)),
            ('email', models.EmailField(blank=True, max_length=254)),
            ('join_date', models.DateField(blank=True, null=True)),
            ('monthly_salary', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('bank_name', models.CharField(blank=True, max_length=120)),
            ('account_number', models.CharField(blank=True, max_length=60, verbose_name='Account number / IBAN')),
            ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=10)),
            ('notes', models.CharField(blank=True, max_length=300)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'ordering': ['name']}),
        migrations.CreateModel(name='PayrollRun', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('year', models.PositiveSmallIntegerField()),
            ('month', models.PositiveSmallIntegerField()),
            ('status', models.CharField(choices=[('draft', 'Draft'), ('finalized', 'Finalized'), ('paid', 'Paid')], default='draft', max_length=10)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('finalized_at', models.DateTimeField(blank=True, null=True)),
            ('paid_at', models.DateTimeField(blank=True, null=True)),
            ('txn', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.fintxn')),
            ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-year', '-month'], 'unique_together': {('year', 'month')}}),
        migrations.CreateModel(name='Payslip', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('basic_salary', models.DecimalField(decimal_places=2, max_digits=12)),
            ('net_pay', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payslips', to='invoices.payrollrun')),
            ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payslips', to='invoices.employee')),
        ], options={'ordering': ['employee__name'], 'unique_together': {('run', 'employee')}}),
        migrations.CreateModel(name='PayslipLineItem', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('kind', models.CharField(choices=[('bonus', 'Bonus / addition'), ('deduction', 'Deduction')], max_length=10)),
            ('label', models.CharField(max_length=150)),
            ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
            ('payslip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='invoices.payslip')),
        ]),
    ]
