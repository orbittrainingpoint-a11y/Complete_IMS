from django.db import migrations, models
import invoices.models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0065_certificationrequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstituteSetting',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(default='Orbit Training Centre', max_length=255)),
                ('tagline', models.CharField(blank=True, max_length=255)),
                ('address', models.TextField(blank=True)),
                ('po_box', models.CharField(blank=True, max_length=50)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(blank=True, default='UAE', max_length=100)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True)),
                ('website', models.URLField(blank=True)),
                ('trn_number', models.CharField(blank=True, max_length=50, verbose_name='TRN Number')),
                ('license_number', models.CharField(blank=True, max_length=100)),
                ('license_authority', models.CharField(blank=True, help_text='e.g. KHDA, DED', max_length=200)),
                ('company_logo', models.ImageField(blank=True, help_text='Main logo used on invoices/emails (PNG recommended)', null=True, upload_to=invoices.models._setting_upload('logo'))),
                ('stamp', models.ImageField(blank=True, help_text='Official company stamp for certificates/documents', null=True, upload_to=invoices.models._setting_upload('stamp'))),
                ('authorization_logo', models.ImageField(blank=True, help_text='Accreditation / authorization badge', null=True, upload_to=invoices.models._setting_upload('auth_logo'))),
                ('signature', models.ImageField(blank=True, help_text='Authorized signatory signature image', null=True, upload_to=invoices.models._setting_upload('signature'))),
                ('invoice_prefix', models.CharField(blank=True, default='ORB', help_text='Prefix for invoice numbers', max_length=20)),
                ('invoice_footer', models.TextField(blank=True, help_text='Text printed at bottom of invoices')),
                ('bank_name', models.CharField(blank=True, max_length=200)),
                ('bank_account_name', models.CharField(blank=True, max_length=200)),
                ('bank_account_no', models.CharField(blank=True, max_length=50)),
                ('bank_iban', models.CharField(blank=True, max_length=50)),
                ('bank_swift', models.CharField(blank=True, max_length=20)),
                ('social_instagram', models.URLField(blank=True)),
                ('social_linkedin', models.URLField(blank=True)),
                ('social_facebook', models.URLField(blank=True)),
                ('social_twitter', models.URLField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Institute Setting'},
        ),
    ]
