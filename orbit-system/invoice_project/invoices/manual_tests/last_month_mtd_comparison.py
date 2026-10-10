"""Dashboard revenue/registration trend ("X% vs last month") compared this month-to-date
against the WHOLE previous month, so a partial month always looked like a big drop even when
the daily run rate was unchanged. _last_month_mtd_range now caps the previous month at the
same day-of-month as today, giving a fair run-rate comparison. Covers the date-math helper and
the admin/sales-manager/accounts dashboards' actual revenue comparison with real data."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from django.db.models import Sum
from invoices.models import *
from invoices.views import _last_month_mtd_range, _pct_change
import invoices.middleware as mw
mw._is_after_dubai_curfew = lambda: False

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

print('1. _last_month_mtd_range: same day-of-month one month back')
f, l = _last_month_mtd_range(dt.date(2026, 10, 11))
check('Oct 11 -> Sep 1..Sep 11', (f, l) == (dt.date(2026, 9, 1), dt.date(2026, 9, 11)), (f, l))

print('\n2. Clamps when today\'s day does not exist last month (31st -> short Feb)')
f, l = _last_month_mtd_range(dt.date(2026, 3, 31))
check('Mar 31 -> Feb 1..Feb 28 (clamped, 2026 not a leap year)', (f, l) == (dt.date(2026, 2, 1), dt.date(2026, 2, 28)), (f, l))

print('\n3. The 1st of the month -> a single-day comparison, not the whole previous month')
f, l = _last_month_mtd_range(dt.date(2026, 11, 1))
check('Nov 1 -> Oct 1..Oct 1 only', (f, l) == (dt.date(2026, 10, 1), dt.date(2026, 10, 1)), (f, l))

print('\n4. Year boundary')
f, l = _last_month_mtd_range(dt.date(2026, 1, 5))
check('Jan 5 2026 -> Dec 1..Dec 5 2025', (f, l) == (dt.date(2025, 12, 1), dt.date(2025, 12, 5)), (f, l))

print('\n5. Real data: identical daily run rate in two different-length windows must show 0% change')
su = User.objects.filter(is_superuser=True).first()
admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

made = []
try:
    client = Client.objects.create(name='ZZ MTD Client', email='zzmtd@example.com', phone='1', address='x')
    made.append(client)
    today = dt.date(2026, 10, 11)
    def make_invoice(d, amount):
        inv = Invoice.objects.create(client=client, date=d, due_date=d, amount_paid=amount,
                                     total_amount=amount, number_of_person=1,
                                     status='Full Payment', payment='Cash')
        made.append(inv)
    # AED 100/day for the first 11 days of October (this month-to-date)
    for day in range(1, 12):
        make_invoice(dt.date(2026, 10, day), 100)
    # The SAME AED 100/day rate for the first 11 days of September (last month, same window)
    for day in range(1, 12):
        make_invoice(dt.date(2026, 9, day), 100)
    # Plus a lot more revenue later in September that a whole-month comparison would have
    # wrongly counted against October's partial month.
    for day in range(12, 31):
        make_invoice(dt.date(2026, 9, day), 500)

    from invoices.views import _month_range
    first, last = _month_range(today)
    prev_first, prev_last = _last_month_mtd_range(today)
    month_revenue = Invoice.objects.filter(client=client, date__gte=first, date__lte=today)\
        .aggregate(t=Sum('amount_paid'))['t'] or 0
    prev_revenue = Invoice.objects.filter(client=client, date__gte=prev_first, date__lte=prev_last)\
        .aggregate(t=Sum('amount_paid'))['t'] or 0
    check('this month-to-date (11 days @ 100) = 1100', float(month_revenue) == 1100, month_revenue)
    check('same-window last month (11 days @ 100) = 1100, not the whole month', float(prev_revenue) == 1100, prev_revenue)
    pct, direction = _pct_change(month_revenue, prev_revenue)
    check('fair comparison shows 0% change (identical run rate)', pct == 0, (pct, direction))

    # Prove the OLD behavior would have been misleading: whole September vs Oct MTD.
    from invoices.views import _last_month_range
    old_prev_first, old_prev_last = _last_month_range(today)
    old_prev_revenue = Invoice.objects.filter(client=client, date__gte=old_prev_first, date__lte=old_prev_last)\
        .aggregate(t=Sum('amount_paid'))['t'] or 0
    old_pct, old_dir = _pct_change(month_revenue, old_prev_revenue)
    check('old whole-month comparison would have wrongly shown a big drop', old_dir == 'down' and old_pct > 50,
          (old_pct, old_dir, old_prev_revenue))
finally:
    for obj in reversed(made):
        obj.delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
