"""Tamara checkout-session integration: creating a link (gated to admin/sales-manager, visible
to everyone), the webhook that keeps order/invoice status in step (signature verification is
the real security boundary here - anyone can POST to that URL), and capture/cancel/refund
actions. Network calls to Tamara are mocked (deterministic, no sandbox dependency); the JWT
webhook-signature check uses the real notification token and real PyJWT, since that's pure
local crypto with no network involved."""
import os, sys, datetime as dt
from decimal import Decimal as D
from unittest.mock import patch

sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
import jwt as pyjwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *
from invoices import tamara_gateway as gw

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = dt.date.today()

CREATE_RESPONSE = {'order_id': 'f56a3123-9e23-45e4-87a2-95366d3b0bca', 'checkout_id': '5ccbe4b1-890d-40b3-8a88-0b489ba8ed01',
                   'status': 'new', 'checkout_url': 'https://checkout-sandbox.tamara.co/checkout/5ccbe4b1'}
CAPTURE_RESPONSE = {'capture_id': 'cap-1', 'order_id': 'f56a3123-9e23-45e4-87a2-95366d3b0bca', 'status': 'fully_captured',
                    'captured_amount': {'amount': 500.0, 'currency': 'AED'}}
CANCEL_RESPONSE = {'cancel_id': 'can-1', 'order_id': 'f56a3123-9e23-45e4-87a2-95366d3b0bca', 'status': 'canceled',
                   'canceled_amount': {'amount': 500.0, 'currency': 'AED'}}
REFUND_RESPONSE = {'order_id': 'f56a3123-9e23-45e4-87a2-95366d3b0bca', 'comment': 'test', 'refund_id': 'ref-1',
                   'status': 'fully_refunded', 'refunded_amount': {'amount': 100.0, 'currency': 'AED'}}

made = []
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'
    non_mgr = User.objects.create_user('zz_tam_accounts', password='x')
    UserProfile.objects.update_or_create(user=non_mgr, defaults={'role': 'accounts'})
    made.append(non_mgr)
    nm = DjClient(); nm.force_login(non_mgr); nm.defaults['HTTP_HOST'] = 'localhost'

    client = Client.objects.create(name='ZZ Tamara Client', email='zzt@x.test', phone='1', address='a', emirates='Dubai', country='UAE')
    course = Course.objects.create(name='ZZ Tamara Course', code='ZZTAM1')
    made += [client, course]
    reg = Registration.objects.create(first_name='ZZ', last_name='Tamara', phone_no='971500000001', email='zzt@x.test',
                                      country='UAE', consultant_name='x', address='Test St', emirates='Dubai')
    made.append(reg)
    inv = Invoice.objects.create(registration=reg, client=client, due_date=today, total_amount=0, amount_paid=0,
                                 number_of_person=1, status='Tamara', payment='Payment Link')
    Invoice.objects.filter(pk=inv.pk).update(total_amount=D('500.00'))
    inv.refresh_from_db()
    made.append(inv)
    item = InvoiceItem.objects.create(invoice=inv, course=course, quantity=1, unit_price=D('476.19'))
    made.append(item)

    print('1. create_checkout_session() builds a valid request and parses the response')
    with patch('invoices.tamara_gateway._post', return_value=CREATE_RESPONSE) as mock_post:
        data = gw.create_checkout_session(inv, 'https://x/success', 'https://x/failure', 'https://x/cancel')
        body = mock_post.call_args[0][1]
    check('checkout_url returned', data['checkout_url'] == CREATE_RESPONSE['checkout_url'])
    check('order_reference_id = invoice number', body['order_reference_id'] == inv.invoice_number, body.get('order_reference_id'))
    check('total_amount matches the invoice', body['total_amount']['amount'] == float(inv.total_amount), body['total_amount'])
    check('country_code is AE', body['country_code'] == 'AE')
    check('consumer built from the registration', body['consumer']['phone_number'] == reg.phone_no, body['consumer'])
    check('shipping_info-style address has a service placeholder, not real shipping', body['shipping_address']['city'] == 'Dubai')
    check('risk_assessment present with required sub-fields', 'account_creation_date' in body['risk_assessment'])

    print('\n2. Non-manager cannot create a link; the restriction is server-side, not just the UI')
    with patch('invoices.tamara_gateway.create_checkout_session', return_value=CREATE_RESPONSE):
        r = nm.post(f'/invoices/{inv.pk}/tamara/create/', {}, **HTML)
    check('non-manager blocked', not TamaraOrder.objects.filter(invoice=inv).exists())
    check('redirected, not a crash', r.status_code == 302, r.status_code)

    print('\n3. Admin creates a real Tamara link (mocked network call) via the actual view')
    with patch('invoices.tamara_gateway.create_checkout_session', return_value=CREATE_RESPONSE):
        r = admin.post(f'/invoices/{inv.pk}/tamara/create/', {}, **HTML)
    order = TamaraOrder.objects.filter(invoice=inv).first()
    made.append(order)
    check('TamaraOrder created', order is not None)
    check('order_id stored', order and order.order_id == CREATE_RESPONSE['order_id'], order and order.order_id)
    check('checkout_url stored', order and order.checkout_url == CREATE_RESPONSE['checkout_url'])
    check('status starts as "new"', order and order.status == 'new', order and order.status)

    print('\n4. Everyone (even non-managers) can SEE the created link on the registration page')
    url = f'/registration/{reg.pk}/'
    r_admin = admin.get(url, **HTML)
    r_nm = nm.get(url, **HTML)
    check('admin sees the Tamara section', b'Tamara' in r_admin.content)
    check('non-manager also sees it (view-only)', b'Tamara' in r_nm.content)
    cancel_action = f'/tamara/{order.pk}/cancel/'.encode()
    check("non-manager's page offers no Capture/Cancel/Refund action", cancel_action not in r_nm.content, cancel_action)

    print('\n5. Webhook signature verification (real JWT, real notification token, no network)')
    good_token = pyjwt.encode({'iss': 'Tamara', 'iat': 1234567890}, settings.TAMARA_NOTIFICATION_TOKEN, algorithm='HS256')
    bad_token = pyjwt.encode({'iss': 'Tamara'}, 'wrong-secret-entirely', algorithm='HS256')
    claims = gw.verify_webhook_token(good_token)
    check('a correctly-signed token verifies and decodes', claims.get('iss') == 'Tamara', claims)
    try:
        gw.verify_webhook_token(bad_token)
        check('a forged token is rejected', False, 'did not raise')
    except gw.TamaraError:
        check('a forged token is rejected', True)

    print('\n6. Webhook updates TamaraOrder + Invoice.amount_paid on "order_authorised"')
    import json
    payload = {'order_id': order.order_id, 'order_reference_id': inv.invoice_number, 'event_type': 'order_authorised', 'data': {}}
    r = admin.post(f'/tamara/webhook/?tamaraToken={good_token}', data=json.dumps(payload), content_type='application/json', **HTML)
    order.refresh_from_db(); inv.refresh_from_db()
    check('webhook accepted (200)', r.status_code == 200, r.status_code)
    check('order status -> authorised', order.status == 'authorised', order.status)
    check('invoice.amount_paid raised to match', inv.amount_paid == inv.total_amount, (inv.amount_paid, inv.total_amount))
    check('a WebhookEvent row was logged', TamaraWebhookEvent.objects.filter(order_id=order.order_id, signature_valid=True).exists())

    print('\n7. A forged webhook (bad signature) is rejected and does NOT touch the invoice')
    inv.amount_paid = D('0')
    inv.save(update_fields=['amount_paid'])
    order.status = 'new'; order.save(update_fields=['status'])
    r = admin.post(f'/tamara/webhook/?tamaraToken={bad_token}', data=json.dumps(payload), content_type='application/json', **HTML)
    order.refresh_from_db(); inv.refresh_from_db()
    check('forged webhook rejected (401)', r.status_code == 401, r.status_code)
    check('order status untouched', order.status == 'new', order.status)
    check('invoice.amount_paid untouched', inv.amount_paid == D('0'), inv.amount_paid)

    print('\n8. Capture / Cancel / Refund are gated to admin/sales-manager only')
    order.status = 'authorised'; order.save(update_fields=['status'])
    with patch('invoices.tamara_gateway.capture_order', return_value=CAPTURE_RESPONSE):
        r = nm.post(f'/tamara/{order.pk}/capture/', {}, **HTML)
    order.refresh_from_db()
    check('non-manager cannot capture', order.status == 'authorised', order.status)
    with patch('invoices.tamara_gateway.capture_order', return_value=CAPTURE_RESPONSE):
        r = admin.post(f'/tamara/{order.pk}/capture/', {}, **HTML)
    order.refresh_from_db(); inv.refresh_from_db()
    check('admin captures successfully', order.status == 'fully_captured', order.status)
    check('captured_amount recorded', order.captured_amount == D('500.0'), order.captured_amount)
    check('invoice.amount_paid reflects the capture', inv.amount_paid == D('500.0'), inv.amount_paid)

    print('\n9. Refund (admin only) records refunded_amount')
    with patch('invoices.tamara_gateway.refund_order', return_value=REFUND_RESPONSE):
        r = admin.post(f'/tamara/{order.pk}/refund/', {'amount': '100', 'comment': 'Customer request'}, **HTML)
    order.refresh_from_db()
    check('refund recorded', order.refunded_amount == D('100.0'), order.refunded_amount)
    check('status reflects partial/full refund', order.status == 'fully_refunded', order.status)

    print('\n10. Cancel (admin only)')
    order2 = TamaraOrder.objects.create(invoice=inv, order_id='order-2', order_reference_id=inv.invoice_number,
                                        status='new', amount=D('500.00'))
    made.append(order2)
    with patch('invoices.tamara_gateway.cancel_order', return_value=CANCEL_RESPONSE):
        r = admin.post(f'/tamara/{order2.pk}/cancel/', {}, **HTML)
    order2.refresh_from_db()
    check('admin cancels successfully', order2.status == 'canceled', order2.status)

finally:
    TamaraWebhookEvent.objects.filter(order_id__in=['f56a3123-9e23-45e4-87a2-95366d3b0bca', 'order-2']).delete()
    TamaraOrder.objects.filter(invoice__registration__last_name='Tamara').delete()
    InvoiceItem.objects.filter(invoice__registration__last_name='Tamara').delete()
    Invoice.objects.filter(registration__last_name='Tamara').delete()
    Registration.objects.filter(last_name='Tamara').delete()
    Course.objects.filter(code='ZZTAM1').delete()
    Client.objects.filter(name='ZZ Tamara Client').delete()
    UserProfile.objects.filter(user__username='zz_tam_accounts').delete()
    User.objects.filter(username='zz_tam_accounts').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
