from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0068_certificationrequest_class_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificationrequest',
            name='class_feedback',
            field=models.TextField(blank=True),
        ),
    ]
