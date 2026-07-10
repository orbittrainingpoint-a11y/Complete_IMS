from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0063_corporatecompany_dashboard_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='registration',
            name='welcome_email_sent',
            field=models.BooleanField(default=False),
        ),
    ]
