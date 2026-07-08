from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0059_corporate_company_and_candidate_link'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuotationLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(
                    choices=[
                        ('intermediate', 'Intermediate'),
                        ('professional', 'Professional'),
                        ('advanced', 'Advanced'),
                    ],
                    default='intermediate',
                    max_length=20,
                )),
                ('quotation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='level_info',
                    to='invoices.quotation',
                )),
            ],
        ),
    ]
