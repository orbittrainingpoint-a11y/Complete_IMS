from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0067_registration_is_refunded_refund'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificationrequest',
            name='class_rating',
            field=models.CharField(
                blank=True,
                choices=[
                    ('excellent', 'Excellent'),
                    ('good', 'Good'),
                    ('average', 'Average'),
                    ('poor', 'Poor'),
                ],
                max_length=20,
            ),
        ),
    ]
