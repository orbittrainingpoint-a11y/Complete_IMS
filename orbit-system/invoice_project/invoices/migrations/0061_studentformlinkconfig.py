from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0060_quotationlevel'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentFormLinkConfig',
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
                ('course_prices_json', models.TextField(blank=True, default='{}')),
                ('link', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='config',
                    to='invoices.studentformlink',
                )),
            ],
        ),
    ]
