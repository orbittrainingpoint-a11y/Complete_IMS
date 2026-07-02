import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0054_course_oo_advanced_course_oo_intermediate_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='coupon',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quotations',
                to='invoices.coupon',
            ),
        ),
    ]
