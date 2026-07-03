from django.db import migrations

# All course codes present in the official price list
VALID_CODES = {
    'CC', 'IP', 'DS', 'DA', 'PP', 'SM', 'SE', 'DM', 'DC', 'ME', 'EX', 'MO', 'MB',
    'PY', 'BD', 'FD', 'BP', 'FH', 'PD', 'CN', 'CA', 'RO', 'DI', 'ST', 'SS', 'SPS',
    'SC', 'CV', 'VE', 'GD', 'GA', 'GP', 'MP', 'P6', 'TS', 'STP', 'FU', 'IN', 'SW',
    'LU', 'VR', '3D', 'RH', 'NW', 'RBT', 'RBC', 'RI', 'RM', 'AC', 'ACE', 'RS', 'RA',
    'AU', 'FS', 'CP', 'WF', 'ID', 'SU', 'AM', 'REE', 'B36', 'DIL', 'CRE', 'COR',
    'ID1', 'M36', 'OUT', 'ID3', 'PS', 'AID', 'MRN', 'ECM', 'PVS', 'ILL', 'FEX',
    'RHM', 'MEC', 'AGI', 'PLN', 'MSC', 'FED', 'SPP', 'ARC', 'FCP', 'CAT', 'ENS',
}


def remove_unlisted(apps, schema_editor):
    Course = apps.get_model('invoices', 'Course')
    InvoiceItem = apps.get_model('invoices', 'InvoiceItem')
    RegistrationCourse = apps.get_model('invoices', 'RegistrationCourse')
    QuotationItem = apps.get_model('invoices', 'QuotationItem')
    CourseContent = apps.get_model('invoices', 'CourseContent')

    for course in Course.objects.exclude(code__in=VALID_CODES):
        has_refs = (
            InvoiceItem.objects.filter(course_id=course.pk).exists()
            or RegistrationCourse.objects.filter(course_id=course.pk).exists()
            or QuotationItem.objects.filter(course_id=course.pk).exists()
        )
        if not has_refs:
            CourseContent.objects.filter(course_id=course.pk).delete()
            course.delete()
        # Courses with existing invoices/registrations/quotations are left untouched


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0056_course_prices_data'),
    ]

    operations = [
        migrations.RunPython(remove_unlisted, noop),
    ]
