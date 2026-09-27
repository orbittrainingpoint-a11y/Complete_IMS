"""Simple-books engine.

One rule: sales data is never copied. Invoices, InvoicePayment, Refund, GatewayPayout and the old
Expense table stay the source of truth and are read live; only things that exist nowhere else
(bills, manual transactions, accounts) are stored in the Fin* tables.

Basis:  sales are recognised on the invoice date, bills on the bill date, direct expenses/income on their
        date (so bills and receivables are proper payables/receivables); paying a bill or collecting a
        receipt is a cash movement with no profit effect. Transfers, owner money and VAT payments never
        touch profit.
Money:  everything is Decimal, AED. Balances = opening balance + posted movements on/after books_start_date.
"""
import datetime
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.urls import reverse

from .models import (AccSetting, Bill, FinAccount, FinTxn, Invoice, InvoicePayment, Refund, GatewayPayout,
                     Expense)

ZERO = Decimal('0.00')
CENT = Decimal('0.01')

_INVOICE_METHOD = {'Card': 'card', 'Cash': 'cash', 'Account Transfer': 'bank_transfer',
                   'Payment Link': 'payment_link', 'Cheque': 'cheque'}


def q(x):
    return Decimal(x or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def split_vat(gross, rate):
    """gross (VAT included) -> (net, vat)."""
    gross = q(gross)
    vat = q(gross - gross / (1 + Decimal(rate) / 100))
    return gross - vat, vat


def vat_from_amount(gross, rate):
    return split_vat(gross, rate)[1]


class Entry:
    """One cash movement on one account (in or out)."""
    __slots__ = ('date', 'kind', 'label', 'account_id', 'cash_in', 'cash_out', 'ref', 'link')

    def __init__(self, date, kind, label, account_id, cash_in=ZERO, cash_out=ZERO, ref='', link=''):
        self.date, self.kind, self.label, self.account_id = date, kind, label, account_id
        self.cash_in, self.cash_out, self.ref, self.link = q(cash_in), q(cash_out), ref, link


class Books:
    """Everything derived for [books_start_date, end]. Build once per request."""

    def __init__(self, end=None):
        self.s = AccSetting.get()
        self.end = end or datetime.date.today()
        self.start = self.s.books_start_date
        self.rate = Decimal(self.s.vat_rate)
        self.accounts = list(FinAccount.objects.all())
        self.by_id = {a.id: a for a in self.accounts}
        self.entries = []          # cash movements
        self.pnl = []              # (date, 'income'|'expense', label, net, vat, group)
        self.vat_paid = []         # (date, amount)
        self.warnings = []
        self._route_cache = {}
        if self.start:
            self._collect()

    # ── routing ────────────────────────────────────────────────────────────
    def route(self, token):
        if token in self._route_cache:
            return self._route_cache[token]
        found = None
        for a in self.accounts:
            if a.is_active and token in a.receives_list():
                found = a.id
                break
        if found is None and token in ('payout', 'refund'):
            for a in self.accounts:
                if a.is_active and a.kind == 'bank':
                    found = a.id
                    break
        if found is None:
            w = f'No account is set to receive "{token}" - those amounts are not in any balance. Fix it in Accounts.'
            if w not in self.warnings:
                self.warnings.append(w)
        self._route_cache[token] = found
        return found

    # ── collection ─────────────────────────────────────────────────────────
    def _in_range(self, d):
        return d is not None and self.start <= d <= self.end

    def _collect(self):
        self._sales()
        self._manual()
        self._payouts_refunds()
        self._legacy_expenses()

    def _sales(self):
        paid_by_inv = defaultdict(lambda: ZERO)
        for p in InvoicePayment.objects.filter(paid_at__gte=self.start, paid_at__lte=self.end).select_related('invoice'):
            self.entries.append(Entry(p.paid_at, 'sale_receipt', f'Payment {p.invoice.invoice_number}',
                                      self.route(p.payment_method), cash_in=p.amount, ref=p.reference,
                                      link=reverse('edit_invoice', args=[p.invoice_id])))
        # sums of every recorded payment (any date) so the "initial payment" residual isn't double counted
        for row in InvoicePayment.objects.values('invoice_id').annotate(t=Sum('amount')):
            paid_by_inv[row['invoice_id']] = row['t'] or ZERO
        for inv in Invoice.objects.filter(date__gte=self.start, date__lte=self.end).only(
                'id', 'invoice_number', 'date', 'total_amount', 'amount_paid', 'status', 'payment'):
            net, vat = split_vat(inv.total_amount, self.rate)
            self.pnl.append((inv.date, 'income', f'Invoice {inv.invoice_number}', net, vat, 'Course & training sales'))
            residual = q(inv.amount_paid) - q(paid_by_inv.get(inv.id, ZERO))
            if residual > 0:
                if inv.status in ('Tabby', 'Tamara'):
                    method = inv.status.lower()
                else:
                    method = _INVOICE_METHOD.get(inv.payment, 'other')
                self.entries.append(Entry(inv.date, 'sale_receipt', f'Initial payment {inv.invoice_number}',
                                          self.route(method), cash_in=residual, link=reverse('edit_invoice', args=[inv.id])))

    def _manual(self):
        cats = {}
        qs = (FinTxn.objects.filter(status='posted', date__gte=self.start, date__lte=self.end)
              .select_related('category', 'account', 'to_account', 'bill'))
        for t in qs:
            net, vat = q(t.amount - t.vat_amount), q(t.vat_amount)
            desc = t.description or t.party or t.get_txn_type_display()
            link = reverse('accounting_txn_detail', args=[t.id])
            if t.txn_type == 'expense':
                self.entries.append(Entry(t.date, 'expense', desc, t.account_id, cash_out=t.amount, ref=t.reference, link=link))
                self.pnl.append((t.date, 'expense', desc, net, vat, t.category.name if t.category else 'Uncategorised'))
            elif t.txn_type == 'income':
                self.entries.append(Entry(t.date, 'income', desc, t.account_id, cash_in=t.amount, ref=t.reference, link=link))
                self.pnl.append((t.date, 'income', desc, net, vat, t.category.name if t.category else 'Other income'))
            elif t.txn_type == 'bill_payment':
                self.entries.append(Entry(t.date, 'bill_payment', f'Bill payment - {t.bill}', t.account_id,
                                          cash_out=t.amount, ref=t.reference, link=link))
            elif t.txn_type == 'transfer' and t.to_account_id:
                self.entries.append(Entry(t.date, 'transfer', f'Transfer to {t.to_account.name}', t.account_id, cash_out=t.amount, ref=t.reference, link=link))
                self.entries.append(Entry(t.date, 'transfer', f'Transfer from {t.account.name}', t.to_account_id, cash_in=t.amount, ref=t.reference, link=link))
            elif t.txn_type == 'owner_in':
                self.entries.append(Entry(t.date, 'owner_in', desc, t.account_id, cash_in=t.amount, ref=t.reference, link=link))
            elif t.txn_type == 'owner_out':
                self.entries.append(Entry(t.date, 'owner_out', desc, t.account_id, cash_out=t.amount, ref=t.reference, link=link))
            elif t.txn_type == 'vat_payment':
                self.entries.append(Entry(t.date, 'vat_payment', desc or 'VAT payment', t.account_id, cash_out=t.amount, ref=t.reference, link=link))
                self.vat_paid.append((t.date, t.amount))
        for b in Bill.objects.filter(status='open', bill_date__gte=self.start, bill_date__lte=self.end).select_related('category'):
            net, vat = q(b.amount - b.vat_amount), q(b.vat_amount)
            self.pnl.append((b.bill_date, 'expense', f'Bill: {b.vendor} {b.bill_number}'.strip(), net, vat,
                             b.category.name if b.category else 'Uncategorised'))

    def _payouts_refunds(self):
        for r in Refund.objects.filter(status='confirmed', confirmed_at__isnull=False):
            d = r.confirmed_at.date()
            if not self._in_range(d) or not r.amount:
                continue
            net, vat = split_vat(r.amount, self.rate)
            self.entries.append(Entry(d, 'refund', f'Refund {r.registration.registration_number}', self.route('refund'),
                                      cash_out=r.amount, ref=r.refund_reference))
            self.pnl.append((d, 'income', f'Refund {r.registration.registration_number}', -net, -vat, 'Refunds given'))
        for p in GatewayPayout.objects.filter(status='received', payout_date__gte=self.start, payout_date__lte=self.end):
            got = q(p.actual_received if p.actual_received is not None else p.net_payout)
            sales = q(p.total_sales)
            gw = p.gateway
            label = f'{gw.title()} payout (week {p.week_start:%d %b})'
            self.entries.append(Entry(p.payout_date, 'payout', label, self.route('payout'), cash_in=got))
            self.entries.append(Entry(p.payout_date, 'payout', f'{gw.title()} settled', self.route(gw), cash_out=sales))
            fee_total = sales - got
            if fee_total > 0:
                vat = min(q(p.vat_on_commission), fee_total)
                self.pnl.append((p.payout_date, 'expense', f'{gw.title()} fees (week {p.week_start:%d %b})',
                                 fee_total - vat, vat, 'Gateway & POS fees'))

    def _legacy_expenses(self):
        """Old 'Expenses' page rows. Included in profit and VAT; they have no account so not in balances."""
        for e in Expense.objects.filter(expense_date__gte=self.start, expense_date__lte=self.end):
            self.pnl.append((e.expense_date, 'expense', e.description, q(e.amount), q(e.vat_amount),
                             e.get_category_display()))

    # ── queries ────────────────────────────────────────────────────────────
    def balances(self, as_of=None):
        as_of = as_of or self.end
        bal = {a.id: q(a.opening_balance) for a in self.accounts}
        for e in self.entries:
            if e.account_id in bal and e.date <= as_of:
                bal[e.account_id] += e.cash_in - e.cash_out
        return bal

    def period(self, d1, d2):
        """Profit & loss + VAT + cash flow for [d1, d2]."""
        inc, exp = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
        vat_out = vat_in = ZERO
        for d, kind, _l, net, vat, group in self.pnl:
            if d1 <= d <= d2:
                if kind == 'income':
                    inc[group] += net
                    vat_out += vat
                else:
                    exp[group] += net
                    vat_in += vat
        paid = sum((a for d, a in self.vat_paid if d1 <= d <= d2), ZERO)
        flow = defaultdict(lambda: {'in': ZERO, 'out': ZERO})
        for e in self.entries:
            if d1 <= e.date <= d2 and e.kind != 'transfer':
                flow[e.kind]['in'] += e.cash_in
                flow[e.kind]['out'] += e.cash_out
        income, expense = sum(inc.values(), ZERO), sum(exp.values(), ZERO)
        return {
            'income': dict(sorted(inc.items(), key=lambda kv: -kv[1])),
            'expense': dict(sorted(exp.items(), key=lambda kv: -kv[1])),
            'total_income': q(income), 'total_expense': q(expense), 'profit': q(income - expense),
            'vat_out': q(vat_out), 'vat_in': q(vat_in), 'vat_net': q(vat_out - vat_in), 'vat_paid': q(paid),
            'flow': dict(flow),
            'cash_in': q(sum((f['in'] for f in flow.values()), ZERO)),
            'cash_out': q(sum((f['out'] for f in flow.values()), ZERO)),
            'cash_net': q(sum((f['in'] - f['out'] for f in flow.values()), ZERO)),
        }

    def vat_position(self):
        """Cumulative VAT owed to the authority since books started (output - input - already paid)."""
        out = sum((v for d, k, _l, n, v, g in self.pnl if k == 'income'), ZERO)
        inn = sum((v for d, k, _l, n, v, g in self.pnl if k == 'expense'), ZERO)
        paid = sum((a for d, a in self.vat_paid), ZERO)
        return q(out - inn - paid)

    def monthly(self, months=6):
        """Income / expense / profit for the last N calendar months ending at self.end."""
        rows = []
        y, m = self.end.year, self.end.month
        for _ in range(months):
            first = datetime.date(y, m, 1)
            last = (datetime.date(y + (m == 12), (m % 12) + 1, 1) - datetime.timedelta(days=1))
            p = self.period(first, min(last, self.end))
            rows.append({'label': first.strftime('%b %Y'), 'income': p['total_income'],
                         'expense': p['total_expense'], 'profit': p['profit']})
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        return list(reversed(rows))

    def statement(self, account_id, d1, d2):
        """Ledger for one account with running balance."""
        opening = q(self.by_id[account_id].opening_balance) + sum(
            (e.cash_in - e.cash_out for e in self.entries if e.account_id == account_id and e.date < d1), ZERO)
        rows, run = [], opening
        for e in sorted((e for e in self.entries if e.account_id == account_id and d1 <= e.date <= d2),
                        key=lambda e: e.date):
            run += e.cash_in - e.cash_out
            rows.append({'e': e, 'balance': run})
        return opening, rows, run


AGE_BUCKETS = [('Not due', None), ('1-30 days', 30), ('31-60 days', 60), ('61-90 days', 90), ('90+ days', 10 ** 6)]


def _bucket(due, today):
    late = (today - due).days
    if late <= 0:
        return 'Not due'
    for name, top in AGE_BUCKETS[1:]:
        if late <= top:
            return name


def receivables(today=None):
    """Unpaid invoices (all time - money owed is owed whenever it was billed)."""
    today = today or datetime.date.today()
    rows, totals = [], defaultdict(lambda: ZERO)
    for inv in (Invoice.objects.select_related('client', 'course')
                .exclude(status='Full Payment').order_by('due_date')):
        bal = q(inv.total_amount) - q(inv.amount_paid)
        if bal <= 0:
            continue
        b = _bucket(inv.due_date, today)
        totals[b] += bal
        rows.append({'inv': inv, 'balance': bal, 'bucket': b, 'days_late': max((today - inv.due_date).days, 0)})
    return rows, {name: totals.get(name, ZERO) for name, _ in AGE_BUCKETS}, q(sum(totals.values(), ZERO))


def payables(today=None):
    today = today or datetime.date.today()
    rows, totals = [], defaultdict(lambda: ZERO)
    for b in Bill.objects.filter(status='open').select_related('category').order_by('due_date'):
        bal = b.balance()
        if bal <= 0:
            continue
        bk = _bucket(b.due_date, today)
        totals[bk] += bal
        rows.append({'bill': b, 'balance': bal, 'bucket': bk, 'days_late': max((today - b.due_date).days, 0)})
    return rows, {name: totals.get(name, ZERO) for name, _ in AGE_BUCKETS}, q(sum(totals.values(), ZERO))
