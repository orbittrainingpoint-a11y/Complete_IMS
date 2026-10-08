"""Payroll views (admin + accounts roles only, same access as the rest of Accounting).
Employees -> monthly payroll runs -> payslips with bonus/deduction line items. Marking a run
paid posts one expense transaction into the existing Accounting module."""
import datetime
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import accounting as acc
from . import accounting_engine as eng
from .models import AccSetting, Employee, FinAccount, FinCategory, FinTxn, PayrollRun, Payslip, PayslipLineItem

MONTH_NAMES = [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)]


# ── employees ────────────────────────────────────────────────────────────
@acc.acc_required
def employee_list(request):
    rows = Employee.objects.all()
    return render(request, 'payroll/employees.html', acc._ctx(
        request, 'payroll', nav='employees', employees=rows,
        active_total=sum((e.monthly_salary for e in rows if e.status == 'active'), Decimal('0'))))


@acc.acc_required
@require_POST
def employee_save(request):
    pk = request.POST.get('id')
    try:
        name = request.POST.get('name', '').strip()
        if not name:
            raise ValueError('Name is required.')
        e = get_object_or_404(Employee, pk=pk) if pk else Employee()
        e.name = name[:150]
        e.designation = request.POST.get('designation', '').strip()[:100]
        e.phone = request.POST.get('phone', '').strip()[:30]
        e.email = request.POST.get('email', '').strip()[:254]
        jd = request.POST.get('join_date', '').strip()
        e.join_date = datetime.date.fromisoformat(jd) if jd else None
        e.monthly_salary = acc._dec(request.POST.get('monthly_salary', '0'), 'Monthly salary', allow_zero=True)
        e.bank_name = request.POST.get('bank_name', '').strip()[:120]
        e.account_number = request.POST.get('account_number', '').strip()[:60]
        e.status = request.POST.get('status', 'active') if request.POST.get('status') in dict(Employee.STATUS_CHOICES) else 'active'
        e.notes = request.POST.get('notes', '').strip()[:300]
        e.save()
        acc._audit(request, 'update' if pk else 'create', e, f'salary {e.monthly_salary}')
        messages.success(request, 'Employee saved.')
    except ValueError as ex:
        messages.error(request, str(ex))
    return redirect('payroll_employees')


# ── payroll runs ─────────────────────────────────────────────────────────
@acc.acc_required
def run_list(request):
    runs = PayrollRun.objects.all()
    return render(request, 'payroll/runs.html', acc._ctx(request, 'payroll', nav='runs', runs=runs))


@acc.acc_required
def run_create(request):
    today = datetime.date.today()
    active_employees = Employee.objects.filter(status='active')
    if request.method == 'POST':
        try:
            try:
                year, month = int(request.POST.get('year')), int(request.POST.get('month'))
            except (TypeError, ValueError):
                raise ValueError('Choose a valid month and year.')
            if not (1 <= month <= 12):
                raise ValueError('Choose a valid month.')
            if PayrollRun.objects.filter(year=year, month=month).exists():
                raise ValueError('A payroll run for that month already exists.')
            ids = [int(i) for i in request.POST.getlist('employee_ids') if i.isdigit()]
            employees = list(active_employees.filter(pk__in=ids))
            if not employees:
                raise ValueError('Select at least one employee.')
            run = PayrollRun.objects.create(year=year, month=month, created_by=request.user)
            for e in employees:
                Payslip.objects.create(run=run, employee=e, basic_salary=e.monthly_salary, net_pay=e.monthly_salary)
            acc._audit(request, 'create', run, f'{len(employees)} employee(s)')
            messages.success(request, f'Payroll run created for {run.label()}.')
            return redirect('payroll_run_detail', pk=run.pk)
        except ValueError as ex:
            messages.error(request, str(ex))
    return render(request, 'payroll/run_form.html', acc._ctx(
        request, 'payroll', nav='runs', employees=active_employees, month_names=MONTH_NAMES,
        default_year=today.year, default_month=today.month))


@acc.acc_required
def run_detail(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk)
    payslips = run.payslips.select_related('employee').prefetch_related('line_items')
    return render(request, 'payroll/run_detail.html', acc._ctx(
        request, 'payroll', nav='runs', run=run, payslips=payslips, total=run.total_net(),
        accounts=FinAccount.objects.filter(is_active=True), today=datetime.date.today()))


@acc.acc_required
@require_POST
def run_delete(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk)
    if run.status != 'draft':
        messages.error(request, 'Only a draft run can be deleted.')
        return redirect('payroll_run_detail', pk=run.pk)
    acc._audit(request, 'delete', run, 'deleted draft run')
    run.delete()
    messages.success(request, 'Draft payroll run deleted.')
    return redirect('payroll_runs')


@acc.acc_required
@require_POST
def run_finalize(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk)
    try:
        if run.status != 'draft':
            raise ValueError('This run is not a draft.')
        if not run.payslips.exists():
            raise ValueError('There are no payslips on this run.')
        run.status = 'finalized'
        run.finalized_at = datetime.datetime.now()
        run.save()
        acc._audit(request, 'status_change', run, 'finalized')
        messages.success(request, 'Run finalized. Payslips are now locked; you can mark it paid.')
    except ValueError as ex:
        messages.error(request, str(ex))
    return redirect('payroll_run_detail', pk=run.pk)


@acc.acc_required
@require_POST
def run_mark_paid(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk)
    s = AccSetting.get()
    try:
        if run.status != 'finalized':
            raise ValueError('Finalize the run before marking it paid.')
        if not s.books_start_date:
            raise ValueError('Set up the books (Accounting > Settings) before posting payroll.')
        d = acc._date(request.POST.get('date'), 'Payment date')
        acc._check_open_period(s, d)
        account = get_object_or_404(FinAccount, pk=request.POST.get('account'), is_active=True)
        total = run.total_net()
        if total <= 0:
            raise ValueError('Total net pay must be greater than zero.')
        cat = FinCategory.objects.filter(name='Salaries & wages', kind='expense').first()
        txn = FinTxn.objects.create(
            date=d, txn_type='expense', account=account, amount=eng.q(total), category=cat,
            party='Payroll', description=f'Payroll - {run.label()}', created_by=request.user)
        run.txn = txn
        run.status = 'paid'
        run.paid_at = datetime.datetime.now()
        run.save()
        acc._audit(request, 'status_change', run, f'paid AED {total} from {account}')
        messages.success(request, f'Marked paid. AED {total} posted as an expense in Accounting.')
    except ValueError as ex:
        messages.error(request, str(ex))
    return redirect('payroll_run_detail', pk=run.pk)


# ── payslips ─────────────────────────────────────────────────────────────
@acc.acc_required
def payslip_detail(request, pk):
    slip = get_object_or_404(Payslip.objects.select_related('employee', 'run'), pk=pk)
    return render(request, 'payroll/payslip.html', acc._ctx(
        request, 'payroll', nav='runs', slip=slip, items=slip.line_items.all(),
        editable=(slip.run.status == 'draft')))


@acc.acc_required
@require_POST
def payslip_item_add(request, pk):
    slip = get_object_or_404(Payslip.objects.select_related('run'), pk=pk)
    try:
        if slip.run.status != 'draft':
            raise ValueError('This payroll run is no longer a draft; line items are locked.')
        kind = request.POST.get('kind')
        if kind not in dict(PayslipLineItem.KIND_CHOICES):
            raise ValueError('Choose bonus or deduction.')
        label = request.POST.get('label', '').strip()
        if not label:
            raise ValueError('Give the line item a label.')
        amount = acc._dec(request.POST.get('amount'), 'Amount')
        PayslipLineItem.objects.create(payslip=slip, kind=kind, label=label[:150], amount=amount)
        slip.recompute()
        slip.save()
        messages.success(request, 'Added.')
    except ValueError as ex:
        messages.error(request, str(ex))
    return redirect('payroll_payslip_detail', pk=slip.pk)


@acc.acc_required
@require_POST
def payslip_item_delete(request, pk, item_id):
    slip = get_object_or_404(Payslip.objects.select_related('run'), pk=pk)
    if slip.run.status != 'draft':
        messages.error(request, 'This payroll run is no longer a draft; line items are locked.')
        return redirect('payroll_payslip_detail', pk=slip.pk)
    PayslipLineItem.objects.filter(pk=item_id, payslip=slip).delete()
    slip.recompute()
    slip.save()
    messages.success(request, 'Removed.')
    return redirect('payroll_payslip_detail', pk=slip.pk)
