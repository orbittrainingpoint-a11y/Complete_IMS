"""Accounting views (admin + accounts roles only). Logic lives in accounting_engine.py."""
import csv
import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import accounting_engine as eng
from .models import (AccSetting, AuditLog, Bill, Course, FinAccount, FinCategory, FinTxn)

ZERO = Decimal('0.00')


# ── access ────────────────────────────────────────────────────────────────
def _role(user):
    try:
        return user.profile.role
    except Exception:
        return ''


def is_admin(user):
    return user.is_superuser or user.is_staff or _role(user) == 'admin'


def can_use(user):
    return is_admin(user) or _role(user) == 'accounts'


def acc_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *a, **kw):
        if not can_use(request.user):
            return HttpResponseForbidden('Accounting is available to Admin and Accounts only.')
        return view(request, *a, **kw)
    return wrapper


def admin_only(view):
    @wraps(view)
    @acc_required
    def wrapper(request, *a, **kw):
        if not is_admin(request.user):
            messages.error(request, 'Only an admin can do that.')
            return redirect('accounting_home')
        return view(request, *a, **kw)
    return wrapper


# ── small helpers ─────────────────────────────────────────────────────────
def _audit(request, action, obj, changes=''):
    AuditLog.objects.create(user=request.user, action=action, model_name=obj.__class__.__name__,
                            object_id=str(obj.pk), object_repr=str(obj)[:300], changes=changes[:2000],
                            ip_address=request.META.get('REMOTE_ADDR') or None)


def _dec(v, field='Amount', allow_zero=False):
    try:
        d = Decimal(str(v).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f'{field} is not a valid number.')
    if d < 0 or (d == 0 and not allow_zero):
        raise ValueError(f'{field} must be greater than zero.')
    return eng.q(d)


def _date(v, field='Date'):
    try:
        return datetime.date.fromisoformat((v or '').strip())
    except ValueError:
        raise ValueError(f'{field} is required (YYYY-MM-DD).')


def _check_open_period(setting, d):
    if setting.locked_until and d <= setting.locked_until:
        raise ValueError(f'The books are closed up to {setting.locked_until:%d %b %Y}. Nothing can be added or changed on or before that date.')
    if setting.books_start_date and d < setting.books_start_date:
        raise ValueError(f'Date is before the books start date ({setting.books_start_date:%d %b %Y}).')


def _vat(request, gross, setting):
    mode = request.POST.get('vat_mode', 'none')
    if mode == 'incl':
        return eng.vat_from_amount(gross, setting.vat_rate)
    if mode == 'custom':
        v = _dec(request.POST.get('vat_amount', '0'), 'VAT amount', allow_zero=True)
        if v > gross:
            raise ValueError('VAT cannot be more than the total.')
        return v
    return ZERO


def _month_range(text):
    today = datetime.date.today()
    try:
        y, m = (int(x) for x in (text or '').split('-'))
        first = datetime.date(y, m, 1)
    except Exception:
        first = today.replace(day=1)
    last = datetime.date(first.year + (first.month == 12), (first.month % 12) + 1, 1) - datetime.timedelta(days=1)
    return first, last


def _range(request):
    """?from=&to= (custom) or ?month=YYYY-MM (default this month)."""
    f, t = request.GET.get('from'), request.GET.get('to')
    if f and t:
        try:
            return datetime.date.fromisoformat(f), datetime.date.fromisoformat(t)
        except ValueError:
            pass
    return _month_range(request.GET.get('month'))


def _ctx(request, active, **extra):
    s = AccSetting.get()
    base = {'active': active, 'acc_is_admin': is_admin(request.user), 'setting': s,
            'pending_count': FinTxn.objects.filter(status='pending').count()}
    base.update(extra)
    return base


def _needs_approval(user, setting, amount):
    return (not is_admin(user)) and setting.approval_threshold > 0 and amount > setting.approval_threshold


# ── dashboard ─────────────────────────────────────────────────────────────
@acc_required
def accounting_home(request):
    s = AccSetting.get()
    if not s.books_start_date:
        return render(request, 'accounting/setup.html', _ctx(request, 'home', accounts=FinAccount.objects.all()))
    d1, d2 = _range(request)
    today = datetime.date.today()
    books = eng.Books(end=max(d2, today))
    p = books.period(d1, d2)
    bal = books.balances(today)
    accounts = [(a, bal.get(a.id, ZERO)) for a in books.accounts if a.is_active]
    rec_rows, rec_ages, rec_total = eng.receivables(today)
    pay_rows, pay_ages, pay_total = eng.payables(today)
    recent = FinTxn.objects.select_related('account', 'category').exclude(status='void')[:8]
    alerts = list(books.warnings)
    pend = FinTxn.objects.filter(status='pending').count()
    if pend and is_admin(request.user):
        alerts.append(f'{pend} entr{"y is" if pend == 1 else "ies are"} waiting for your approval.')
    overdue = sum(1 for r in pay_rows if r['days_late'] > 0)
    if overdue:
        alerts.append(f'{overdue} vendor bill(s) are overdue.')
    return render(request, 'accounting/home.html', _ctx(
        request, 'home', d1=d1, d2=d2, p=p, accounts=accounts, cash_total=sum((b for _a, b in accounts), ZERO),
        rec_total=rec_total, rec_ages=rec_ages, pay_total=pay_total, pay_ages=pay_ages,
        vat_position=books.vat_position(), recent=recent, alerts=alerts, monthly=books.monthly(6),
        month_value=d1.strftime('%Y-%m')))


# ── transactions ──────────────────────────────────────────────────────────
@acc_required
def txn_list(request):
    d1, d2 = _range(request)
    if not (request.GET.get('from') or request.GET.get('month')):
        d1 = datetime.date.today().replace(day=1) - datetime.timedelta(days=60)
        d2 = datetime.date.today()
    qs = FinTxn.objects.select_related('account', 'to_account', 'category', 'created_by').filter(date__gte=d1, date__lte=d2)
    f = {k: request.GET.get(k, '') for k in ('type', 'account', 'status', 'q')}
    if f['type']:
        qs = qs.filter(txn_type=f['type'])
    if f['account']:
        qs = qs.filter(Q(account_id=f['account']) | Q(to_account_id=f['account']))
    if f['status']:
        qs = qs.filter(status=f['status'])
    if f['q']:
        qs = qs.filter(Q(description__icontains=f['q']) | Q(party__icontains=f['q']) | Q(reference__icontains=f['q']))
    if request.GET.get('export') == 'csv':
        r = HttpResponse(content_type='text/csv')
        r['Content-Disposition'] = f'attachment; filename="transactions_{d1}_{d2}.csv"'
        w = csv.writer(r)
        w.writerow(['Date', 'Type', 'Account', 'To account', 'Category', 'Party', 'Description', 'Reference', 'Total', 'VAT', 'Status'])
        for t in qs:
            w.writerow([t.date, t.get_txn_type_display(), t.account, t.to_account or '', t.category or '', t.party,
                        t.description, t.reference, t.amount, t.vat_amount, t.get_status_display()])
        return r
    return render(request, 'accounting/transactions.html', _ctx(
        request, 'txns', txns=qs[:500], d1=d1, d2=d2, f=f, types=FinTxn.TYPE_CHOICES,
        statuses=FinTxn.STATUS_CHOICES, accounts=FinAccount.objects.all()))


def _txn_form_ctx(request, kind, values=None, error=None):
    return _ctx(request, 'txns', kind=kind, types=FinTxn.TYPE_CHOICES, accounts=FinAccount.objects.filter(is_active=True),
                exp_cats=FinCategory.objects.filter(kind='expense', is_active=True),
                inc_cats=FinCategory.objects.filter(kind='income', is_active=True),
                courses=Course.objects.all().order_by('name'),
                open_bills=[b for b in Bill.objects.filter(status='open') if b.balance() > 0],
                v=values or {}, error=error, today=datetime.date.today())


@acc_required
def txn_add(request):
    kind = request.GET.get('type') or request.POST.get('txn_type') or 'expense'
    if kind not in dict(FinTxn.TYPE_CHOICES):
        kind = 'expense'
    s = AccSetting.get()
    if not s.books_start_date:
        messages.warning(request, 'Set the books start date and opening balances first.')
        return redirect('accounting_home')
    if request.method == 'POST':
        try:
            d = _date(request.POST.get('date'))
            _check_open_period(s, d)
            amount = _dec(request.POST.get('amount'))
            account = get_object_or_404(FinAccount, pk=request.POST.get('account'), is_active=True)
            t = FinTxn(date=d, txn_type=kind, account=account, amount=amount,
                       party=request.POST.get('party', '').strip()[:200],
                       description=request.POST.get('description', '').strip()[:300],
                       reference=request.POST.get('reference', '').strip()[:100], created_by=request.user)
            if kind in ('expense', 'income'):
                t.vat_amount = _vat(request, amount, s)
                cat = request.POST.get('category')
                t.category = FinCategory.objects.filter(pk=cat, kind=kind).first() if cat else None
                if not t.category:
                    raise ValueError('Choose a category.')
                if not (t.description or t.party):
                    raise ValueError('Add a description or who it was with.')
                cid = request.POST.get('course')
                t.course = Course.objects.filter(pk=cid).first() if cid else None
            elif kind == 'transfer':
                to = get_object_or_404(FinAccount, pk=request.POST.get('to_account'), is_active=True)
                if to.pk == account.pk:
                    raise ValueError('Choose two different accounts for a transfer.')
                t.to_account = to
            elif kind == 'bill_payment':
                bill = get_object_or_404(Bill, pk=request.POST.get('bill'), status='open')
                if amount > bill.balance():
                    raise ValueError(f'That is more than the bill balance (AED {bill.balance()}).')
                t.bill = bill
                t.party = bill.vendor
            elif kind == 'vat_payment':
                t.description = t.description or 'VAT payment'
            if _needs_approval(request.user, s, amount):
                t.status = 'pending'
            if request.FILES.get('attachment'):
                t.attachment = request.FILES['attachment']
            t.save()
            _audit(request, 'create', t, f'{t.get_txn_type_display()} AED {t.amount} ({t.get_status_display()})')
            if t.status == 'pending':
                messages.info(request, f'AED {amount} is above the approval limit - sent to an admin for approval.')
            else:
                messages.success(request, 'Saved.')
            return redirect('accounting_txn_list')
        except ValueError as e:
            return render(request, 'accounting/txn_form.html', _txn_form_ctx(request, kind, request.POST, str(e)))
    return render(request, 'accounting/txn_form.html', _txn_form_ctx(request, kind, {'date': datetime.date.today().isoformat(), 'bill': request.GET.get('bill', '')}))


@acc_required
def txn_detail(request, pk):
    t = get_object_or_404(FinTxn.objects.select_related('account', 'to_account', 'category', 'created_by', 'approved_by', 'bill'), pk=pk)
    return render(request, 'accounting/txn_detail.html', _ctx(request, 'txns', t=t))


@acc_required
@require_POST
def txn_action(request, pk):
    t = get_object_or_404(FinTxn, pk=pk)
    act, s = request.POST.get('action'), AccSetting.get()
    try:
        if act in ('approve', 'reject'):
            if not is_admin(request.user):
                raise ValueError('Only an admin can approve or reject.')
            if t.status != 'pending':
                raise ValueError('This entry is not waiting for approval.')
            if act == 'approve':
                _check_open_period(s, t.date)
            t.status = 'posted' if act == 'approve' else 'rejected'
            t.approved_by, t.approved_at = request.user, datetime.datetime.now()
            t.save()
            _audit(request, 'status_change', t, act)
            messages.success(request, 'Approved and posted.' if act == 'approve' else 'Rejected.')
        elif act == 'void':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                raise ValueError('Give a reason for voiding.')
            if t.status not in ('posted', 'pending'):
                raise ValueError('Already voided or rejected.')
            _check_open_period(s, t.date)
            t.status, t.void_reason = 'void', reason[:200]
            t.save()
            _audit(request, 'delete', t, f'void: {reason}')
            messages.success(request, 'Voided. It stays visible in the history but no longer counts.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('accounting_txn_detail', pk=t.pk)


# ── bills ─────────────────────────────────────────────────────────────────
@acc_required
def bill_list(request):
    show = request.GET.get('show', 'unpaid')
    today = datetime.date.today()
    rows = []
    for b in Bill.objects.select_related('category').filter(status='open'):
        bal = b.balance()
        if show == 'unpaid' and bal <= 0:
            continue
        if show == 'paid' and bal > 0:
            continue
        rows.append({'b': b, 'paid': b.amount - bal, 'balance': bal, 'late': (today - b.due_date).days if bal > 0 and b.due_date < today else 0})
    return render(request, 'accounting/bills.html', _ctx(request, 'bills', rows=rows, show=show,
                                                       total=sum((r['balance'] for r in rows), ZERO)))


@acc_required
def bill_add(request):
    s = AccSetting.get()
    cats = FinCategory.objects.filter(kind='expense', is_active=True)
    ctx = lambda v=None, e=None: _ctx(request, 'bills', cats=cats, v=v or {}, error=e, today=datetime.date.today())
    if request.method == 'POST':
        try:
            bd, dd = _date(request.POST.get('bill_date'), 'Bill date'), _date(request.POST.get('due_date'), 'Due date')
            _check_open_period(s, bd)
            amount = _dec(request.POST.get('amount'))
            vendor = request.POST.get('vendor', '').strip()
            if not vendor:
                raise ValueError('Vendor is required.')
            if dd < bd:
                raise ValueError('Due date cannot be before the bill date.')
            b = Bill(vendor=vendor[:200], bill_number=request.POST.get('bill_number', '').strip()[:60], bill_date=bd, due_date=dd,
                     amount=amount, vat_amount=_vat(request, amount, s), description=request.POST.get('description', '').strip()[:300],
                     created_by=request.user)
            cid = request.POST.get('category')
            b.category = FinCategory.objects.filter(pk=cid, kind='expense').first() if cid else None
            if not b.category:
                raise ValueError('Choose a category.')
            if request.FILES.get('attachment'):
                b.attachment = request.FILES['attachment']
            b.save()
            _audit(request, 'create', b, f'AED {b.amount} due {b.due_date}')
            messages.success(request, 'Bill saved. It counts as an expense from the bill date; pay it from the bill page.')
            return redirect('accounting_bill_detail', pk=b.pk)
        except ValueError as e:
            return render(request, 'accounting/bill_form.html', ctx(request.POST, str(e)))
    return render(request, 'accounting/bill_form.html', ctx({'bill_date': datetime.date.today().isoformat(),
                                                             'due_date': (datetime.date.today() + datetime.timedelta(days=30)).isoformat()}))


@acc_required
def bill_detail(request, pk):
    b = get_object_or_404(Bill.objects.select_related('category', 'created_by'), pk=pk)
    return render(request, 'accounting/bill_detail.html', _ctx(
        request, 'bills', b=b, payments=b.payments.select_related('account').order_by('date'), balance=b.balance(),
        accounts=FinAccount.objects.filter(is_active=True), today=datetime.date.today()))


@acc_required
@require_POST
def bill_void(request, pk):
    b = get_object_or_404(Bill, pk=pk)
    reason = request.POST.get('reason', '').strip()
    try:
        if not reason:
            raise ValueError('Give a reason for voiding.')
        if b.payments.filter(status__in=('posted', 'pending')).exists():
            raise ValueError('Void the payments made against this bill first.')
        _check_open_period(AccSetting.get(), b.bill_date)
        b.status, b.void_reason = 'void', reason[:200]
        b.save()
        _audit(request, 'delete', b, f'void: {reason}')
        messages.success(request, 'Bill voided.')
        return redirect('accounting_bills')
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('accounting_bill_detail', pk=b.pk)


# ── receivables & payables ────────────────────────────────────────────────
@acc_required
def receivables_view(request):
    today = datetime.date.today()
    rec, rec_ages, rec_total = eng.receivables(today)
    pay, pay_ages, pay_total = eng.payables(today)
    side = request.GET.get('side', 'receivable')
    return render(request, 'accounting/receivables.html', _ctx(
        request, 'ar', side=side, rec=rec, rec_ages=rec_ages, rec_total=rec_total, pay=pay, pay_ages=pay_ages,
        pay_total=pay_total))


# ── accounts ──────────────────────────────────────────────────────────────
@acc_required
def account_list(request):
    s = AccSetting.get()
    books = eng.Books(end=datetime.date.today())
    bal = books.balances()
    return render(request, 'accounting/accounts.html', _ctx(
        request, 'accounts', rows=[(a, bal.get(a.id, ZERO)) for a in books.accounts], kinds=FinAccount.KIND_CHOICES,
        warnings=books.warnings, total=sum((bal.get(a.id, ZERO) for a in books.accounts if a.is_active), ZERO)))


@admin_only
@require_POST
def account_save(request):
    pk = request.POST.get('id')
    try:
        name = request.POST.get('name', '').strip()
        if not name:
            raise ValueError('Account name is required.')
        a = get_object_or_404(FinAccount, pk=pk) if pk else FinAccount()
        if FinAccount.objects.filter(name__iexact=name).exclude(pk=a.pk).exists():
            raise ValueError('An account with that name already exists.')
        a.name = name[:80]
        a.kind = request.POST.get('kind', 'bank') if request.POST.get('kind') in dict(FinAccount.KIND_CHOICES) else 'bank'
        a.opening_balance = eng.q(Decimal(request.POST.get('opening_balance', '0') or '0'))
        a.receives = ','.join(x.strip().lower() for x in request.POST.get('receives', '').split(',') if x.strip())
        a.is_active = request.POST.get('is_active') == 'on' if pk else True
        a.notes = request.POST.get('notes', '').strip()[:200]
        a.save()
        _audit(request, 'update' if pk else 'create', a, f'opening {a.opening_balance}')
        messages.success(request, 'Account saved.')
    except (ValueError, InvalidOperation) as e:
        messages.error(request, str(e) if isinstance(e, ValueError) else 'Opening balance is not a valid number.')
    return redirect('accounting_accounts')


@acc_required
def account_statement(request, pk):
    a = get_object_or_404(FinAccount, pk=pk)
    d1, d2 = _range(request)
    books = eng.Books(end=max(d2, datetime.date.today()))
    if not books.start:
        return redirect('accounting_home')
    opening, rows, closing = books.statement(a.pk, d1, d2)
    return render(request, 'accounting/statement.html', _ctx(request, 'accounts', a=a, d1=d1, d2=d2, opening=opening,
                                                           rows=rows, closing=closing, month_value=d1.strftime('%Y-%m')))


# ── reports ───────────────────────────────────────────────────────────────
@acc_required
def reports(request):
    tab = request.GET.get('tab', 'pl')
    d1, d2 = _range(request)
    s = AccSetting.get()
    if not s.books_start_date:
        return redirect('accounting_home')
    books = eng.Books(end=d2)
    p = books.period(d1, d2)
    if request.GET.get('export') == 'csv':
        r = HttpResponse(content_type='text/csv')
        r['Content-Disposition'] = f'attachment; filename="profit_loss_{d1}_{d2}.csv"'
        w = csv.writer(r)
        w.writerow(['Profit & Loss', d1, d2])
        w.writerow(['INCOME (excl. VAT)'])
        for k, v in p['income'].items():
            w.writerow([k, v])
        w.writerow(['Total income', p['total_income']])
        w.writerow(['EXPENSES (excl. VAT)'])
        for k, v in p['expense'].items():
            w.writerow([k, v])
        w.writerow(['Total expenses', p['total_expense']])
        w.writerow(['NET PROFIT', p['profit']])
        w.writerow([])
        w.writerow(['VAT collected', p['vat_out']])
        w.writerow(['VAT paid on costs', p['vat_in']])
        w.writerow(['Net VAT payable for period', p['vat_net']])
        return r
    kinds = dict(eng_kind_labels())
    flow = [(kinds.get(k, k), v['in'], v['out']) for k, v in p['flow'].items()]
    detail = [(d, k, l, n, v, g) for d, k, l, n, v, g in sorted(books.pnl, key=lambda x: x[0]) if d1 <= d <= d2]
    return render(request, 'accounting/reports.html', _ctx(
        request, 'reports', tab=tab, d1=d1, d2=d2, p=p, flow=flow, detail=detail, month_value=d1.strftime('%Y-%m'),
        vat_position=books.vat_position(), margin=(p['profit'] / p['total_income'] * 100) if p['total_income'] else None))


def eng_kind_labels():
    return [('sale_receipt', 'Customer payments'), ('income', 'Other income'), ('payout', 'Tabby/Tamara payouts'),
            ('expense', 'Expenses paid'), ('bill_payment', 'Vendor bills paid'), ('refund', 'Refunds'),
            ('owner_in', 'Owner money in'), ('owner_out', 'Owner withdrawals'), ('vat_payment', 'VAT paid')]


# ── settings ──────────────────────────────────────────────────────────────
@admin_only
def acc_settings(request):
    s = AccSetting.get()
    if request.method == 'POST':
        act = request.POST.get('action')
        try:
            if act == 'setup':
                if s.books_start_date:
                    raise ValueError('The books are already set up.')
                s.books_start_date = _date(request.POST.get('books_start_date'), 'Start date')
                s.save()
                for a in FinAccount.objects.all():
                    a.opening_balance = eng.q(Decimal(request.POST.get('opening_%d' % a.pk, '0') or '0'))
                    a.save()
                _audit(request, 'update', s, 'books started %s' % s.books_start_date)
                messages.success(request, 'Books started. Sales, payments, refunds and Tabby/Tamara payouts from that date are now included automatically.')
                return redirect('accounting_home')
            if act == 'save':
                if not s.books_start_date or request.POST.get('books_start_date'):
                    new = _date(request.POST.get('books_start_date'), 'Books start date')
                    if s.books_start_date and new != s.books_start_date and (FinTxn.objects.exists() or Bill.objects.exists()):
                        raise ValueError('The start date cannot be changed once entries exist.')
                    s.books_start_date = new
                s.vat_rate = _dec(request.POST.get('vat_rate', '5'), 'VAT rate', allow_zero=True)
                s.approval_threshold = _dec(request.POST.get('approval_threshold', '0'), 'Approval limit', allow_zero=True)
                s.trn = request.POST.get('trn', '').strip()[:40]
                s.save()
                _audit(request, 'update', s, 'settings')
                messages.success(request, 'Settings saved.')
            elif act == 'close':
                d = _date(request.POST.get('locked_until'), 'Close until')
                if d > datetime.date.today():
                    raise ValueError('You cannot close a period in the future.')
                if s.locked_until and d < s.locked_until:
                    raise ValueError('Periods can only be closed further forward here.')
                if FinTxn.objects.filter(status='pending', date__lte=d).exists():
                    raise ValueError('Approve or reject the pending entries in that period first.')
                s.locked_until = d
                s.save()
                _audit(request, 'update', s, f'closed until {d}')
                messages.success(request, f'Books closed up to {d:%d %b %Y}.')
            elif act == 'reopen':
                s.locked_until = _date(request.POST.get('locked_until'), 'Reopen from') if request.POST.get('locked_until') else None
                s.save()
                _audit(request, 'update', s, f'lock moved to {s.locked_until}')
                messages.success(request, 'Lock updated.')
            elif act == 'add_category':
                name, kind = request.POST.get('name', '').strip(), request.POST.get('kind', 'expense')
                if not name or kind not in ('expense', 'income'):
                    raise ValueError('Category name is required.')
                FinCategory.objects.get_or_create(name=name[:80], kind=kind, defaults={'is_active': True})
                messages.success(request, 'Category added.')
            elif act == 'toggle_category':
                c = get_object_or_404(FinCategory, pk=request.POST.get('id'))
                c.is_active = not c.is_active
                c.save()
        except (ValueError, InvalidOperation) as e:
            messages.error(request, str(e) if isinstance(e, ValueError) else 'A number is not valid.')
        return redirect('accounting_settings')
    return render(request, 'accounting/settings.html', _ctx(request, 'settings', cats=FinCategory.objects.all()))
