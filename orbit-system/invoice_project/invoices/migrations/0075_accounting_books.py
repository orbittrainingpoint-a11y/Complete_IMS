import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CATS_EXP = ['Rent', 'Salaries & wages', 'Utilities (DEWA, internet, phone)', 'Marketing & ads', 'Software & subscriptions',
            'Visa & government fees', 'Office supplies', 'Travel & transport', 'Instructor / trainer fees',
            'Training materials', 'Bank charges', 'Gateway & POS fees', 'Repairs & maintenance', 'Professional fees', 'Other expense']
CATS_INC = ['Other income', 'Interest received']
ACCOUNTS = [
    ('Cash in hand', 'cash', 'cash'),
    ('Main bank account', 'bank', 'bank_transfer,cheque,payment_link,other,payout,refund'),
    ('Card machine (POS)', 'pos', 'card'),
    ('Tabby wallet', 'gateway', 'tabby'),
    ('Tamara wallet', 'gateway', 'tamara'),
]


def seed(apps, schema_editor):
    Cat = apps.get_model('invoices', 'FinCategory')
    Acc = apps.get_model('invoices', 'FinAccount')
    Set = apps.get_model('invoices', 'AccSetting')
    for n in CATS_EXP:
        Cat.objects.get_or_create(name=n, kind='expense')
    for n in CATS_INC:
        Cat.objects.get_or_create(name=n, kind='income')
    for name, kind, rec in ACCOUNTS:
        Acc.objects.get_or_create(name=name, defaults={'kind': kind, 'receives': rec})
    Set.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    """General accounting: money accounts, categories, settings, bills, manual transactions. Additive only;
    every FK to users/accounts/courses is SET_NULL or PROTECT so financial history can never cascade away."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invoices', '0074_schedule_rules_occurrences'),
    ]

    operations = [
        migrations.CreateModel(name='FinAccount', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=80, unique=True)),
            ('kind', models.CharField(choices=[('cash', 'Cash in hand'), ('bank', 'Bank'), ('pos', 'Card machine / POS'), ('gateway', 'Gateway wallet (Tabby/Tamara)'), ('other', 'Other')], default='bank', max_length=10)),
            ('opening_balance', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
            ('receives', models.CharField(blank=True, max_length=200, help_text='Comma list of what lands here: payment methods (cash, card, bank_transfer, cheque, payment_link, tabby, tamara, other) plus payout (gateway payouts) and refund (refunds paid from here)')),
            ('is_active', models.BooleanField(default=True)),
            ('notes', models.CharField(blank=True, max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'ordering': ['kind', 'name']}),
        migrations.CreateModel(name='FinCategory', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=80)),
            ('kind', models.CharField(choices=[('expense', 'Expense'), ('income', 'Income')], default='expense', max_length=10)),
            ('is_active', models.BooleanField(default=True)),
        ], options={'ordering': ['kind', 'name'], 'unique_together': {('name', 'kind')}}),
        migrations.CreateModel(name='AccSetting', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('books_start_date', models.DateField(blank=True, null=True, help_text='Opening balances are as at this date; earlier data is ignored')),
            ('vat_rate', models.DecimalField(decimal_places=2, default=5, max_digits=5)),
            ('approval_threshold', models.DecimalField(decimal_places=2, default=2000, max_digits=12, help_text='Entries above this by the accounts role wait for admin approval. 0 = off')),
            ('locked_until', models.DateField(blank=True, null=True, help_text='Nothing can be added/changed on or before this date')),
            ('trn', models.CharField(blank=True, max_length=40, verbose_name='VAT registration number')),
        ]),
        migrations.CreateModel(name='Bill', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('vendor', models.CharField(max_length=200)),
            ('bill_number', models.CharField(blank=True, max_length=60)),
            ('bill_date', models.DateField()),
            ('due_date', models.DateField()),
            ('amount', models.DecimalField(decimal_places=2, max_digits=12, help_text='Total including VAT')),
            ('vat_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('description', models.CharField(blank=True, max_length=300)),
            ('attachment', models.FileField(blank=True, null=True, upload_to='accounting/bills/%Y/%m/')),
            ('status', models.CharField(choices=[('open', 'Open'), ('void', 'Void')], default='open', max_length=10)),
            ('void_reason', models.CharField(blank=True, max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bills', to='invoices.fincategory')),
            ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-bill_date', '-id']}),
        migrations.CreateModel(name='FinTxn', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('date', models.DateField()),
            ('txn_type', models.CharField(choices=[('expense', 'Expense paid'), ('income', 'Other income received'), ('transfer', 'Transfer between accounts'), ('bill_payment', 'Pay a vendor bill'), ('owner_in', 'Owner / partner put money in'), ('owner_out', 'Owner / partner took money out'), ('vat_payment', 'VAT paid to the tax authority')], max_length=15)),
            ('amount', models.DecimalField(decimal_places=2, max_digits=14, help_text='Total including VAT')),
            ('vat_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
            ('party', models.CharField(blank=True, max_length=200)),
            ('description', models.CharField(blank=True, max_length=300)),
            ('reference', models.CharField(blank=True, max_length=100)),
            ('attachment', models.FileField(blank=True, null=True, upload_to='accounting/%Y/%m/')),
            ('status', models.CharField(choices=[('posted', 'Posted'), ('pending', 'Waiting for approval'), ('rejected', 'Rejected'), ('void', 'Void')], default='posted', max_length=10)),
            ('approved_at', models.DateTimeField(blank=True, null=True)),
            ('void_reason', models.CharField(blank=True, max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('account', models.ForeignKey(help_text='Account the money moved out of / into', on_delete=django.db.models.deletion.PROTECT, related_name='txns', to='invoices.finaccount')),
            ('to_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='txns_in', to='invoices.finaccount')),
            ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='txns', to='invoices.fincategory')),
            ('bill', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='invoices.bill')),
            ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='invoices.course')),
            ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-date', '-id'], 'indexes': [models.Index(fields=['date', 'status'], name='invoices_fi_date_st_idx')]}),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
