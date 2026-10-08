"""Payroll: employees -> monthly run -> payslips with bonus/deduction line items -> finalize ->
mark paid (posts one expense transaction into Accounting). Covers the full HTTP flow plus the
draft-lock on finalize."""
import datetime as dt
import os, sys
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *
import invoices.middleware as mw
mw._is_after_dubai_curfew = lambda: False

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

su = User.objects.filter(is_superuser=True).first()
admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

sales_exec = User.objects.create_user('zz_pay_sx', password='x')
UserProfile.objects.update_or_create(user=sales_exec, defaults={'role': 'sales_executive'})
sx = DjClient(); sx.force_login(sales_exec); sx.defaults['HTTP_HOST'] = 'localhost'

s = AccSetting.get()
if not s.books_start_date:
    s.books_start_date = dt.date.today() - dt.timedelta(days=365)
    s.save()
account, _ = FinAccount.objects.get_or_create(name='ZZ Payroll Bank', defaults={'kind': 'bank'})

made_ids = {'employee': [], 'run': []}
try:
    print('1. Permissions: sales_executive is blocked, admin is not')
    check('sales_executive blocked from employee list', sx.get('/accounting/payroll/employees/').status_code == 403)
    check('admin can see employee list', admin.get('/accounting/payroll/employees/').status_code == 200)

    print('\n2. Create employees')
    r = admin.post('/accounting/payroll/employees/save/', {'name': 'ZZ Employee One', 'monthly_salary': '5000', 'status': 'active'})
    check('employee 1 saved -> redirect', r.status_code == 302)
    r = admin.post('/accounting/payroll/employees/save/', {'name': 'ZZ Employee Two', 'monthly_salary': '3000', 'status': 'active'})
    check('employee 2 saved -> redirect', r.status_code == 302)
    e1 = Employee.objects.get(name='ZZ Employee One'); e2 = Employee.objects.get(name='ZZ Employee Two')
    made_ids['employee'] = [e1.pk, e2.pk]
    check('salary stored correctly', e1.monthly_salary == 5000 and e2.monthly_salary == 3000)

    print('\n3. Create a payroll run with both employees')
    today = dt.date.today()
    # pick a month/year with no existing run
    y, m = today.year, today.month
    while PayrollRun.objects.filter(year=y, month=m).exists():
        m = m - 1 if m > 1 else (m, y := y - 1)[0] or 12
    r = admin.post('/accounting/payroll/new/', {'year': y, 'month': m, 'employee_ids': [e1.pk, e2.pk]})
    check('run created -> redirect to detail', r.status_code == 302, r.headers.get('Location'))
    run = PayrollRun.objects.get(year=y, month=m)
    made_ids['run'] = [run.pk]
    check('run is draft', run.status == 'draft')
    check('two payslips created, net = basic (no line items yet)',
          run.payslips.count() == 2 and run.total_net() == 8000, run.total_net())

    print('\n4. Duplicate month is rejected')
    r = admin.post('/accounting/payroll/new/', {'year': y, 'month': m, 'employee_ids': [e1.pk]})
    check('duplicate month rejected, no second run',
          r.status_code == 200 and PayrollRun.objects.filter(year=y, month=m).count() == 1,
          (r.status_code, PayrollRun.objects.filter(year=y, month=m).count()))

    print('\n5. Add a bonus and a deduction to one payslip; net recomputes')
    slip1 = run.payslips.get(employee=e1)
    r = admin.post(f'/accounting/payroll/payslip/{slip1.pk}/item/add/', {'kind': 'bonus', 'label': 'Performance bonus', 'amount': '500'})
    check('bonus added -> redirect', r.status_code == 302)
    r = admin.post(f'/accounting/payroll/payslip/{slip1.pk}/item/add/', {'kind': 'deduction', 'label': 'Unpaid leave - 1 day', 'amount': '200'})
    check('deduction added -> redirect', r.status_code == 302)
    slip1.refresh_from_db()
    check('net pay = basic + bonus - deduction', slip1.net_pay == 5000 + 500 - 200, slip1.net_pay)
    check('run total reflects the change', run.total_net() == 5300 + 3000, run.total_net())

    print('\n6. Removing a line item recomputes net pay')
    item = slip1.line_items.get(label='Unpaid leave - 1 day')
    r = admin.post(f'/accounting/payroll/payslip/{slip1.pk}/item/{item.pk}/delete/')
    check('item removed -> redirect', r.status_code == 302)
    slip1.refresh_from_db()
    check('net pay back up', slip1.net_pay == 5500, slip1.net_pay)

    print('\n7. Finalize locks the run; line items can no longer be edited')
    r = admin.post(f'/accounting/payroll/{run.pk}/finalize/')
    check('finalize -> redirect', r.status_code == 302)
    run.refresh_from_db()
    check('run is finalized', run.status == 'finalized')
    r = admin.post(f'/accounting/payroll/payslip/{slip1.pk}/item/add/', {'kind': 'bonus', 'label': 'late add', 'amount': '10'})
    check('adding a line item after finalize is refused', not slip1.line_items.filter(label='late add').exists())

    print('\n8. Mark paid posts one expense transaction into Accounting')
    total_before = FinTxn.objects.filter(party='Payroll').count()
    r = admin.post(f'/accounting/payroll/{run.pk}/mark-paid/', {'date': today.isoformat(), 'account': account.pk})
    check('mark paid -> redirect', r.status_code == 302)
    run.refresh_from_db()
    check('run is paid', run.status == 'paid')
    check('one payroll expense transaction created', FinTxn.objects.filter(party='Payroll').count() == total_before + 1)
    check('transaction linked back to the run, amount matches total net',
          run.txn is not None and run.txn.amount == run.total_net() and run.txn.txn_type == 'expense',
          (run.txn, run.txn.amount if run.txn else None))
    check('transaction category is Salaries & wages', run.txn.category and run.txn.category.name == 'Salaries & wages')

    print('\n9. A paid run cannot be deleted or finalized again')
    r = admin.post(f'/accounting/payroll/{run.pk}/delete/')
    check('delete on a non-draft run is refused, run still exists', PayrollRun.objects.filter(pk=run.pk).exists())
    r = admin.post(f'/accounting/payroll/{run.pk}/finalize/')
    run2 = PayrollRun.objects.get(pk=run.pk)
    check('re-finalize is a no-op', run2.status == 'paid')

    print('\n10. Payslip detail / print page renders')
    r = admin.get(f'/accounting/payroll/payslip/{slip1.pk}/')
    check('payslip page -> 200', r.status_code == 200 and b'ZZ Employee One' in r.content)

finally:
    for pk in made_ids['run']:
        run = PayrollRun.objects.filter(pk=pk).first()
        if run and run.txn_id:
            FinTxn.objects.filter(pk=run.txn_id).delete()
        PayrollRun.objects.filter(pk=pk).delete()
    Employee.objects.filter(pk__in=made_ids['employee']).delete()
    FinAccount.objects.filter(name='ZZ Payroll Bank').delete()
    User.objects.filter(username='zz_pay_sx').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
