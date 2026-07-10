import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0062_add_consultant_to_corporatecompany'),
    ]

    operations = [
        migrations.AddField(
            model_name='corporatecompany',
            name='dashboard_token',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
