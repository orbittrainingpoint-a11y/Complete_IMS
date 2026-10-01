from decimal import Decimal

from django.db import migrations


def recompute(apps, schema_editor):
    """Every InvoicePurchase.save() used to recompute total_amount from the legacy single
    `course` field on every save — never set once an invoice uses real line items (the normal
    workflow), so it silently reset total_amount to 0 every time, including right after the
    create/edit views tried to fix it. Backfill every existing row the same way models.py now
    computes it going forward: from its real purchase items when it has any."""
    InvoicePurchase = apps.get_model('invoices', 'InvoicePurchase')
    fixed = 0
    for pi in InvoicePurchase.objects.prefetch_related('purchaseitems').all():
        items = list(pi.purchaseitems.all())
        if not items:
            continue
        subtotal = Decimal('0.00')
        for item in items:
            item_total = item.unit_price * max(item.quantity, 1) * pi.number_of_person
            subtotal += item_total * (1 - Decimal(pi.discount) / 100)
        vat = subtotal * Decimal('0.05')
        total = (subtotal + vat).quantize(Decimal('0.01'))
        if pi.total_amount != total:
            pi.total_amount = total
            pi.save(update_fields=['total_amount'])
            fixed += 1
    if fixed:
        print(f'  fixed total_amount on {fixed} purchase invoice(s)')


class Migration(migrations.Migration):
    """Data-only fix: recompute InvoicePurchase.total_amount for every existing invoice that
    has real line items, undoing the effect of the save() bug fixed in this same change."""

    dependencies = [
        ('invoices', '0077_min_individual_gap'),
    ]

    operations = [
        migrations.RunPython(recompute, migrations.RunPython.noop),
    ]
