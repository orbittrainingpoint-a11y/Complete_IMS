"""Tamara API client: Create Checkout Session, Capture, Cancel, Simplified Refund, and webhook
signature verification. Training courses aren't physically shipped, so the required
shipping_address/shipping_info fields in Tamara's schema get sensible service-delivery
placeholders rather than real shipping details. Request/response field names match Tamara's
published reference docs (docs.tamara.co/reference/...) as of this integration."""
import datetime as dt
from decimal import Decimal

import jwt
import requests
from django.conf import settings


class TamaraError(Exception):
    """Raised with the actual message Tamara's API returned, so the UI can show something
    useful instead of a generic failure."""


def _headers():
    return {'Authorization': f'Bearer {settings.TAMARA_API_TOKEN}', 'Content-Type': 'application/json'}


def _money(amount, currency='AED'):
    return {'amount': float(amount), 'currency': currency}


def _post(path, body):
    url = settings.TAMARA_API_URL.rstrip('/') + path
    try:
        r = requests.post(url, json=body, headers=_headers(), timeout=20)
    except requests.RequestException as e:
        raise TamaraError(f'Could not reach Tamara: {e}')
    if r.status_code >= 400:
        try:
            data = r.json()
            msg = data.get('message') or str(data)
        except ValueError:
            msg = r.text[:300]
        raise TamaraError(f'Tamara {r.status_code}: {msg}')
    return r.json()


def _risk_assessment(registration):
    from .models import Invoice
    past = Invoice.objects.filter(registration=registration).exclude(pk=None).order_by('date')
    paid_dates = [i.date for i in past if i.amount_paid and i.amount_paid > 0]
    return {
        'is_premium_customer': False,
        'account_creation_date': (registration.created_at or registration.date).strftime('%d-%m-%Y'),
        'total_order_count': past.count(),
        'date_first_paid': paid_dates[0].strftime('%d-%m-%Y') if paid_dates else None,
        'date_last_paid': paid_dates[-1].strftime('%d-%m-%Y') if paid_dates else None,
    }


def create_checkout_session(invoice, success_url, failure_url, cancel_url):
    """Create a Tamara checkout session for the full outstanding amount on this invoice.
    Returns the created TamaraOrder (not yet saved by the caller - this just builds and
    sends the request; tamara_views.py persists the result)."""
    reg = invoice.registration
    if not reg:
        raise TamaraError('This invoice has no registration - Tamara needs a customer.')
    items = list(invoice.items.all())
    line_items = [{
        'reference_id': str(it.pk), 'type': 'Digital',
        'name': (it.course.name if it.course else it.description or 'Training course')[:255],
        'sku': f'INV-{invoice.invoice_number}-{it.pk}'[:128],
        'quantity': it.quantity, 'total_amount': _money(it.get_total()),
    } for it in items] or [{
        'reference_id': invoice.invoice_number, 'type': 'Digital', 'name': 'Training course',
        'sku': f'INV-{invoice.invoice_number}', 'quantity': 1, 'total_amount': _money(invoice.total_amount),
    }]
    address = {
        'first_name': reg.first_name, 'last_name': reg.last_name,
        'line1': reg.address or 'N/A', 'city': reg.emirates or 'Dubai',
        'country_code': 'AE', 'phone_number': reg.phone_no,
    }
    body = {
        'order_reference_id': invoice.invoice_number,
        'total_amount': _money(invoice.total_amount),
        'shipping_amount': {'amount': '0', 'currency': 'AED'},
        'tax_amount': {'amount': '0', 'currency': 'AED'},
        'items': line_items,
        'consumer': {'first_name': reg.first_name, 'last_name': reg.last_name,
                     'phone_number': reg.phone_no, 'email': reg.email or ''},
        'country_code': 'AE',
        'description': f'Orbit Training - Invoice {invoice.invoice_number}'[:256],
        'merchant_url': {'success': success_url, 'failure': failure_url, 'cancel': cancel_url},
        'shipping_address': address,
        'billing_address': address,
        'platform': 'Orbit ERP',
        'locale': 'en_US',
        'risk_assessment': _risk_assessment(reg),
    }
    return _post('/checkout', body)


def capture_order(tamara_order, shipping_company='Orbit Training Centre (service delivery)'):
    body = {
        'order_id': tamara_order.order_id,
        'total_amount': _money(tamara_order.amount, tamara_order.currency),
        'shipping_info': {
            'shipped_at': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'shipping_company': shipping_company,
        },
    }
    return _post('/payments/capture', body)


def cancel_order(tamara_order):
    body = {'total_amount': _money(tamara_order.amount, tamara_order.currency)}
    return _post(f'/orders/{tamara_order.order_id}/cancel', body)


def refund_order(tamara_order, amount, comment):
    body = {'total_amount': _money(amount, tamara_order.currency), 'comment': comment[:500]}
    return _post(f'/payments/simplified-refund/{tamara_order.order_id}', body)


def verify_webhook_token(token):
    """Decode+verify the tamaraToken JWT (HS256, signed with our Notification Token) sent on
    every webhook call. Returns the decoded claims, or raises TamaraError if it doesn't check
    out - never trust a webhook payload without this."""
    if not token:
        raise TamaraError('Missing tamaraToken.')
    try:
        return jwt.decode(token, settings.TAMARA_NOTIFICATION_TOKEN, algorithms=['HS256'],
                          options={'verify_exp': True})
    except jwt.PyJWTError as e:
        raise TamaraError(f'Invalid tamaraToken: {e}')
