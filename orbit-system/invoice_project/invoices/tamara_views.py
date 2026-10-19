"""Tamara checkout-link creation, the webhook that keeps order/invoice status in step, and
admin-only capture/cancel/refund actions. The browser redirect (merchant_url) is only ever
a landing page - Tamara's own docs say notifications are server-to-server and the redirect
must never be trusted to confirm payment, so tamara_checkout_return() shows a generic message
and nothing more."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import tamara_gateway as gw
from .models import AuditLog, Invoice, TamaraOrder, TamaraWebhookEvent
from .trainer_schedule import can_manage

logger = logging.getLogger(__name__)


@login_required
@require_POST
def tamara_create_link(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if not can_manage(request.user):
        messages.error(request, 'Only admins and sales managers can create a Tamara link.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[invoice.registration_id]))
    base = request.build_absolute_uri('/')[:-1]
    success = base + reverse('tamara_checkout_return', args=['success', invoice.pk])
    failure = base + reverse('tamara_checkout_return', args=['failure', invoice.pk])
    cancel = base + reverse('tamara_checkout_return', args=['cancel', invoice.pk])
    try:
        data = gw.create_checkout_session(invoice, success, failure, cancel)
        TamaraOrder.objects.create(
            invoice=invoice, order_id=data['order_id'], checkout_id=data.get('checkout_id', ''),
            checkout_url=data.get('checkout_url', ''), order_reference_id=invoice.invoice_number,
            status=data.get('status', 'new'), amount=invoice.total_amount,
            raw_create_response=data, created_by=request.user,
        )
        messages.success(request, f'Tamara link created: {data.get("checkout_url", "")}')
    except gw.TamaraError as e:
        messages.error(request, f'Could not create a Tamara link: {e}')
    return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[invoice.registration_id]))


def tamara_checkout_return(request, outcome, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    msg = {'success': 'Thank you - your payment is being confirmed. You will be notified once it clears.',
          'failure': 'The payment could not be completed. Please contact Orbit Training Centre.',
          'cancel': 'The payment was cancelled.'}.get(outcome, 'Thank you.')
    return render(request, 'invoices/tamara_return.html', {'message': msg, 'invoice': invoice})


@csrf_exempt
@require_POST
def tamara_webhook(request):
    """Tamara calls this server-to-server on every order status change. The tamaraToken is
    sent both as a query param and an Authorization header - we accept either."""
    token = request.GET.get('tamaraToken') or request.META.get('HTTP_AUTHORIZATION', '').removeprefix('Bearer ').strip()
    import json
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        payload = {}
    order_id = payload.get('order_id', '')
    event_type = payload.get('event_type', '')
    event = TamaraWebhookEvent.objects.create(order_id=order_id, event_type=event_type, payload=payload)
    try:
        gw.verify_webhook_token(token)
        event.signature_valid = True
        event.save(update_fields=['signature_valid'])
    except gw.TamaraError as e:
        event.error = str(e)[:500]
        event.save(update_fields=['error'])
        logger.warning('Tamara webhook rejected (bad signature): %s', e)
        return HttpResponse(status=401)

    order = TamaraOrder.objects.filter(order_id=order_id).first()
    if not order:
        event.error = f'No TamaraOrder for order_id={order_id}'[:500]
        event.save(update_fields=['error'])
        return HttpResponse(status=200)  # acknowledge anyway - nothing to retry

    status_map = {'order_approved': 'approved', 'order_authorised': 'authorised', 'order_captured': 'fully_captured'}
    new_status = status_map.get(event_type)
    if new_status:
        order.status = new_status
        if event_type == 'order_captured':
            captured = payload.get('data', {}).get('captured_amount', {})
            if captured.get('amount') is not None:
                order.captured_amount = captured['amount']
        order.save()
        # Only ever raise the invoice's recorded payment to match what Tamara confirms -
        # never re-add on a repeated/duplicate webhook delivery for the same order.
        if new_status in ('authorised', 'fully_captured', 'partially_captured'):
            paid_equiv = order.captured_amount if order.captured_amount else order.amount
            invoice = order.invoice
            if paid_equiv > invoice.amount_paid:
                invoice.amount_paid = paid_equiv
                invoice.save(update_fields=['amount_paid'])
                AuditLog.objects.create(action='payment', model_name='Invoice', object_id=str(invoice.pk),
                                        object_repr=str(invoice), changes=f'Tamara {new_status}: {paid_equiv} AED (order {order_id})')
    event.processed = True
    event.save(update_fields=['processed'])
    return HttpResponse(status=200)


@login_required
@require_POST
def tamara_capture(request, pk):
    order = get_object_or_404(TamaraOrder, pk=pk)
    if not can_manage(request.user):
        messages.error(request, 'Only admins and sales managers can capture a Tamara order.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))
    try:
        data = gw.capture_order(order)
        order.capture_id, order.status = data.get('capture_id', ''), data.get('status', order.status)
        captured = data.get('captured_amount', {})
        if captured.get('amount') is not None:
            order.captured_amount = captured['amount']
        order.save()
        invoice = order.invoice
        if order.captured_amount > invoice.amount_paid:
            invoice.amount_paid = order.captured_amount
            invoice.save(update_fields=['amount_paid'])
        messages.success(request, f'Captured: {order.captured_amount} AED.')
    except gw.TamaraError as e:
        messages.error(request, f'Capture failed: {e}')
    return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))


@login_required
@require_POST
def tamara_cancel(request, pk):
    order = get_object_or_404(TamaraOrder, pk=pk)
    if not can_manage(request.user):
        messages.error(request, 'Only admins and sales managers can cancel a Tamara order.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))
    try:
        data = gw.cancel_order(order)
        order.status = data.get('status', 'canceled')
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Tamara order cancelled.')
    except gw.TamaraError as e:
        messages.error(request, f'Cancel failed: {e}')
    return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))


@login_required
@require_POST
def tamara_refund(request, pk):
    order = get_object_or_404(TamaraOrder, pk=pk)
    if not can_manage(request.user):
        messages.error(request, 'Only admins and sales managers can refund a Tamara order.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))
    amount = request.POST.get('amount', '').strip()
    comment = request.POST.get('comment', 'Refund').strip()
    try:
        amt = float(amount)
    except ValueError:
        messages.error(request, 'Enter a valid refund amount.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))
    try:
        data = gw.refund_order(order, amt, comment)
        order.status = data.get('status', order.status)
        refunded = data.get('refunded_amount', {})
        order.refunded_amount = (order.refunded_amount or 0) + (refunded.get('amount') or amt)
        order.save()
        messages.success(request, f'Refunded {amt} AED.')
    except gw.TamaraError as e:
        messages.error(request, f'Refund failed: {e}')
    return redirect(request.META.get('HTTP_REFERER') or reverse('registration_invoice_detail', args=[order.invoice.registration_id]))
