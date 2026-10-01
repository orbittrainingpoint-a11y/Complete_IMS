"""InvoicePurchase.total_amount used to be recomputed from a legacy single `course` field on
EVERY save() - never set once an invoice uses real line items, which is the normal workflow
today - so it silently reset back to 0 every time, including the exact line the create/edit
views used to try to fix it (AED 0.00 on the dashboard/corporate portal while the Corporate Tax
Invoice flow, which recomputes from items itself, showed the real number). Covers: create, edit
(items changed), a legacy course-only PI with no items, and that the tax-invoice flow's number
now matches pi.total_amount exactly (closing the original complaint)."""
import os, sys, datetime as dt
from decimal import Decimal
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from invoices.models import *
from django.test import Client as DjClient
import invoices.middleware as mw
mw._is_after_dubai_curfew = lambda: False

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

su = User.objects.filter(is_superuser=True).first()
admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'
today = dt.date.today()
made = []
try:
    course = Course.objects.create(name='ZZ PI Course', code='ZZPI1', rate=Decimal('1000'))
    made.append(course)

    print('1. Create: total_amount reflects real item prices, not 0')
    r = admin.post('/create_purchase_invoice/', {
        'date': today.isoformat(), 'due_date': (today + dt.timedelta(days=14)).isoformat(),
        'advance_amount': '0', 'discount': '0', 'number_of_person': '1', 'payment': 'Account Transfer',
        'po_number': '', 'client_name': 'ZZ PI Client', 'client_emirates': 'Dubai', 'client_country': 'UAE',
        'client_trn': '', 'registration_number': '',
        'course_%d' % course.pk: str(course.pk), 'quantity_%d' % course.pk: '1', 'unit_price_%d' % course.pk: '2980.00',
    })
    check('create redirected (saved ok)', r.status_code == 302, r.status_code)
    pi = InvoicePurchase.objects.filter(client__name='ZZ PI Client').order_by('-id').first()
    made.append(pi)
    check('PI was created', pi is not None)
    check('total_amount is 3129.00 (2980 + 5% VAT), not 0', pi.total_amount == Decimal('3129.00'), pi.total_amount)

    print('\n2. Create-tax-invoice-from-PI flow now matches pi.total_amount exactly (the original complaint)')
    rv = admin.get(f'/corporate-tax-invoice/from-pi/{pi.pk}/')
    check('page loads', rv.status_code == 200)
    body = rv.content.decode()
    check('shown total matches the PI\'s own total_amount', '3,129.00' in body or '3129.00' in body, pi.total_amount)
    r2 = admin.post(f'/corporate-tax-invoice/from-pi/{pi.pk}/', {
        'date': today.isoformat(), 'due_date': (today + dt.timedelta(days=14)).isoformat(),
        'amount_paid': '0', 'payment': 'Account Transfer', 'status': 'Full Payment', 'po_number': '',
    })
    check('tax invoice created', r2.status_code == 302, r2.status_code)
    tax_inv = Invoice.objects.filter(client=pi.client).order_by('-id').first()
    made.append(tax_inv)
    check('tax invoice total EQUALS the purchase invoice total (no more mismatch)',
          tax_inv.total_amount == pi.total_amount == Decimal('3129.00'), (tax_inv.total_amount, pi.total_amount))

    print('\n3. Edit: changing items updates total_amount correctly (not reset to 0)')
    course2 = Course.objects.create(name='ZZ PI Course 2', code='ZZPI2', rate=Decimal('500'))
    made.append(course2)
    r3 = admin.post(f'/invoice_purchase/{pi.pk}/edit/', {
        'date': today.isoformat(), 'due_date': (today + dt.timedelta(days=14)).isoformat(),
        'advance_amount': '0', 'discount': '10', 'number_of_person': '1', 'payment': 'Account Transfer',
        'po_number': '', 'client_name': 'ZZ PI Client', 'client_emirates': 'Dubai', 'client_country': 'UAE',
        'client_trn': '', 'registration_number': '',
        'course_%d' % course2.pk: str(course2.pk), 'quantity_%d' % course2.pk: '2',
    })
    check('edit redirected (saved ok)', r3.status_code == 302, r3.status_code)
    pi.refresh_from_db()
    # 2 x 500 rate = 1000, 10% discount = 900, +5% VAT = 945.00
    check('total_amount reflects the NEW items (945.00), not 0 and not the old value', pi.total_amount == Decimal('945.00'), pi.total_amount)

    print('\n4. Legacy single-course PI with no items still uses the course-rate formula')
    legacy = InvoicePurchase.objects.create(
        client=pi.client, course=course, date=today, due_date=today + dt.timedelta(days=14),
        advance_amount=Decimal('0'), number_of_person=Decimal('2') if False else 2, discount=Decimal('0'),
        status='Full Payment', payment='Account Transfer',
    )
    made.append(legacy)
    # course.rate=1000 * number_of_person=2 * (1-0%) = 2000, NOT run through calculate_total_amount (no items)
    check('legacy course-rate total used when there are no items', legacy.total_amount == Decimal('2000'), legacy.total_amount)

    print('\n5. Brand new PI with neither course nor items yet stays at 0 (no crash on first save)')
    blank = InvoicePurchase.objects.create(
        client=pi.client, date=today, due_date=today + dt.timedelta(days=14),
        advance_amount=Decimal('0'), number_of_person=1, discount=Decimal('0'),
        status='Full Payment', payment='Account Transfer',
    )
    made.append(blank)
    check('no items, no course -> total_amount 0, no crash', blank.total_amount == Decimal('0'), blank.total_amount)
    InvoicePurchaseItem.objects.create(invoice=blank, course=course, quantity=1, unit_price=Decimal('100.00'))
    blank.save()
    check('adding an item and re-saving now picks it up', blank.total_amount == Decimal('105.00'), blank.total_amount)

finally:
    InvoiceItem.objects.filter(invoice__client__name='ZZ PI Client').delete()
    Invoice.objects.filter(client__name='ZZ PI Client').delete()
    InvoicePurchaseItem.objects.filter(invoice__client__name='ZZ PI Client').delete()
    InvoicePurchase.objects.filter(client__name='ZZ PI Client').delete()
    Client.objects.filter(name='ZZ PI Client').delete()
    Course.objects.filter(code__in=('ZZPI1', 'ZZPI2')).delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
