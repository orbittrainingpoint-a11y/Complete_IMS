from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('invoices', '0069_certificationrequest_class_feedback')]
    operations = [
        migrations.AddField(
            model_name='certificationrequest',
            name='class_starting_date',
            field=models.DateField(null=True, blank=True),
        ),
    ]
