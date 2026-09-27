"""Accounting module checks (local DB; every row it creates is removed and settings restored)."""
import os, sys, datetime as dt
from decimal import Decimal as D
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as C
from invoices.models import *
from invoices import accounting_engine as eng

ok = bad = 0
def check(l, c, x=''):
    global ok, bad
    if c: ok += 1; print('  ok  ', l)
    else: bad += 1; print('  FAIL', l, x)

today = dt.date.today()
S = AccSetting.get()
saved = (S.books_start_date, S.vat_rate, S.approval_threshold, S.locked_until)
saved_open = {a.pk: (a.opening_balance, a.receives) for a in FinAccount.objects.all()}
made = {'inv': [], 'pay': [], 'gp': [], 'users': []}
users = {}
for role in ('admin', 'accounts', 'sales_manager', 'sales_executive'):
    u = User.objects.create_user('zz_acc_' + role, password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': role}); users[role] = u
def cl(role):
    c = C(); c.force_login(users[role]); c.defaults['HTTP_HOST'] = 'localhost'; return c
try:
    print('1. Access')
    for role, code in (('admin', 200), ('accounts', 200), ('sales_manager', 403), ('sales_executive', 403)):
        r = cl(role).get('/accounting/'); check(f'{role} -> {code}', r.status_code == code, r.status_code)
    check('anonymous redirected to login', C().get('/accounting/', HTTP_HOST='localhost').status_code == 302)
    check('sales_manager cannot post an entry', cl('sales_manager').post('/accounting/transactions/new/', {'amount': '5'}).status_code == 403)
    ad = cl('admin'); ac = cl('accounts')
    side = ad.get('/accounting/').content.decode()
    check('sidebar shows Accounting to admin', 'Accounts Overview' in side)
    check('sidebar hides Accounting from sales exec', 'Accounts Overview' not in cl('sales_executive').get('/trainers/').content.decode())

    print('\n2. Setup')
    AccSetting.objects.filter(pk=1).update(books_start_date=None)
    r = ad.get('/accounting/'); check('setup page shown before books start', 'Start the books' in r.content.decode())
    check('accounts role cannot start the books', 'Ask an admin' in ac.get('/accounting/').content.decode())
    accs = {a.name: a for a in FinAccount.objects.all()}
    cash, bank, pos, tabby = accs['Cash in hand'], accs['Main bank account'], accs['Card machine (POS)'], accs['Tabby wallet']
    post = {'action': 'setup', 'books_start_date': today.isoformat()}
    for a in accs.values(): post['opening_%d' % a.pk] = '0'
    post['opening_%d' % cash.pk] = '1000'; post['opening_%d' % bank.pk] = '50000.50'
    ad.post('/accounting/settings/', post)
    S = AccSetting.get(); check('books start date saved', S.books_start_date == today)
    cash.refresh_from_db(); bank.refresh_from_db()
    check('opening balances saved', cash.opening_balance == D('1000') and bank.opening_balance == D('50000.50'))
    AccSetting.objects.filter(pk=1).update(approval_threshold=2000, vat_rate=5)

    print('\n3. Engine: sales, payments, refunds, gateways')
    b0 = eng.Books(end=today); base_bal = b0.balances(); base_p = b0.period(today, today)
    client = Client.objects.create(name='ZZ Acc Client', email='z@x.test', phone='1', address='a', emirates='Dubai', country='UAE')
    def inv(total, paid, status, payment):
        i = Invoice.objects.create(client=client, due_date=today - dt.timedelta(days=45), total_amount=0, amount_paid=paid, number_of_person=1, status=status, payment=payment)
        Invoice.objects.filter(pk=i.pk).update(total_amount=total); made['inv'].append(i.pk); return i
    i1 = inv(D('1050.00'), D('1050.00'), 'Full Payment', 'Cash')                   # paid, no InvoicePayment row -> residual to cash
    i2 = inv(D('2100.00'), D('0'), 'Term Payment', 'Card')                          # unpaid, overdue 45d
    p2 = InvoicePayment.objects.create(invoice=i2, amount=D('500.00'), payment_method='card', paid_at=today); made['pay'].append(p2.pk)
    Invoice.objects.filter(pk=i2.pk).update(amount_paid=D('500.00'))
    i3 = inv(D('315.00'), D('315.00'), 'Tabby', 'Card')                             # tabby, residual to Tabby wallet
    b = eng.Books(end=today); bal = b.balances(); p = b.period(today, today)
    d = lambda a: bal[a.pk] - base_bal[a.pk]
    check('cash received from paid invoice (residual, not double counted)', d(cash) == D('1050.00'), d(cash))
    check('card payment routed to POS', d(pos) == D('500.00'), d(pos))
    check('tabby sale sits in Tabby wallet', d(tabby) == D('315.00'), d(tabby))
    check('income is net of VAT (3465/1.05 = 3300)', p['total_income'] - base_p['total_income'] == D('3300.00'), p['total_income'] - base_p['total_income'])
    check('VAT collected 165', p['vat_out'] - base_p['vat_out'] == D('165.00'), p['vat_out'] - base_p['vat_out'])
    rows, ages, tot = eng.receivables(today)
    mine = [r for r in rows if r['inv'].pk == i2.pk]
    check('receivable balance 1600, in 31-60 bucket', mine and mine[0]['balance'] == D('1600.00') and mine[0]['bucket'] == '31-60 days', mine and (mine[0]['balance'], mine[0]['bucket']))
    check('fully paid invoice not a receivable', not [r for r in rows if r['inv'].pk == i1.pk])
    gp = GatewayPayout.objects.create(gateway='tabby', week_start=today - dt.timedelta(days=7), week_end=today - dt.timedelta(days=1), payout_date=today,
        total_sales=D('315.00'), commission_rate=D('0.0707'), commission_amount=D('22.27'), vat_on_commission=D('1.11'), net_payout=D('291.62'), actual_received=D('291.62'), status='received')
    made['gp'].append(gp.pk)
    b = eng.Books(end=today); bal2 = b.balances(); p = b.period(today, today)
    check('payout lands in bank net', bal2[bank.pk] - bal[bank.pk] == D('291.62'), bal2[bank.pk] - bal[bank.pk])
    check('tabby wallet cleared', bal2[tabby.pk] - bal[tabby.pk] == D('-315.00'))
    fee = [k for k in p['expense'] if 'Gateway' in k]
    check('gateway fee booked as expense (23.38 = 22.27 net + 1.11 VAT)', fee and p['expense']['Gateway & POS fees'] - base_p['expense'].get('Gateway & POS fees', 0) == D('22.27'), p['expense'])
    check('fee VAT counted as input VAT', p['vat_in'] - base_p['vat_in'] == D('1.11'), p['vat_in'] - base_p['vat_in'])

    print('\n4. Entries, VAT, transfers, bills, approval')
    def add(cli, **kw):
        data = {'date': today.isoformat(), 'txn_type': kw.pop('type', 'expense'), **{k: str(v) for k, v in kw.items()}}
        return cli.post('/accounting/transactions/new/?type=' + data['txn_type'], data)
    rent = FinCategory.objects.get(name='Rent'); oi = FinCategory.objects.get(name='Other income')
    b1 = eng.Books(end=today); bal1 = b1.balances(); pp1 = b1.period(today, today)
    add(ad, type='expense', account=bank.pk, amount='1050', vat_mode='incl', category=rent.pk, party='Landlord', description='ZZ rent')
    t = FinTxn.objects.get(description='ZZ rent')
    check('expense saved posted, VAT 50 extracted', t.status == 'posted' and t.vat_amount == D('50.00'), (t.status, t.vat_amount))
    add(ad, type='expense', account=cash.pk, amount='100', vat_mode='none', category=rent.pk, description='ZZ petty')
    add(ad, type='income', account=bank.pk, amount='200', vat_mode='none', category=oi.pk, description='ZZ other income')
    add(ad, type='transfer', account=cash.pk, to_account=bank.pk, amount='300', description='ZZ deposit')
    add(ad, type='owner_in', account=bank.pk, amount='5000', description='ZZ capital')
    add(ad, type='vat_payment', account=bank.pk, amount='40', description='ZZ VAT paid')
    b2 = eng.Books(end=today); bal_2 = b2.balances(); pp2 = b2.period(today, today)
    check('bank: -1050 +200 +300 +5000 -40 = +4410', bal_2[bank.pk] - bal1[bank.pk] == D('4410.00'), bal_2[bank.pk] - bal1[bank.pk])
    check('cash: -100 -300 = -400', bal_2[cash.pk] - bal1[cash.pk] == D('-400.00'), bal_2[cash.pk] - bal1[cash.pk])
    check('expenses in P&L = 1000 + 100', pp2['total_expense'] - pp1['total_expense'] == D('1100.00'), pp2['total_expense'] - pp1['total_expense'])
    check('income in P&L = 200', pp2['total_income'] - pp1['total_income'] == D('200.00'))
    check('transfer/owner money/VAT payment do NOT touch profit', pp2['profit'] - pp1['profit'] == D('200') - D('1100'))
    check('vat payment recorded', pp2['vat_paid'] - pp1['vat_paid'] == D('40.00'))
    r = add(ad, type='transfer', account=cash.pk, to_account=cash.pk, amount='10', description='same')
    check('transfer to same account rejected', 'two different accounts' in r.content.decode())
    r = add(ad, type='expense', account=bank.pk, amount='-5', category=rent.pk, description='neg'); check('negative amount rejected', 'greater than zero' in r.content.decode())
    r = add(ad, type='expense', account=bank.pk, amount='abc', category=rent.pk, description='bad'); check('non-number rejected', 'not a valid number' in r.content.decode())
    r = add(ad, type='expense', account=bank.pk, amount='10', description='nocat'); check('category required', 'Choose a category' in r.content.decode())

    # bills
    rb = ad.post('/accounting/bills/new/', {'vendor': 'ZZ Vendor', 'bill_number': 'B-1', 'bill_date': today.isoformat(), 'due_date': (today + dt.timedelta(days=10)).isoformat(),
                 'amount': '2100', 'vat_mode': 'incl', 'category': rent.pk, 'description': 'ZZ bill'})
    bill = Bill.objects.get(vendor='ZZ Vendor'); check('bill saved with VAT 100', bill.vat_amount == D('100.00') and rb.status_code == 302)
    b3 = eng.Books(end=today); pp3 = b3.period(today, today)
    check('bill is an expense on bill date (2000 net)', pp3['total_expense'] - pp2['total_expense'] == D('2000.00'), pp3['total_expense'] - pp2['total_expense'])
    check('bill is a payable', any(r['bill'].pk == bill.pk for r in eng.payables(today)[0]))
    bal3 = b3.balances()
    add(ad, type='bill_payment', account=bank.pk, amount='600', bill=bill.pk)
    b4 = eng.Books(end=today); pp4 = b4.period(today, today)
    check('paying a bill moves cash but not profit', b4.balances()[bank.pk] - bal3[bank.pk] == D('-600.00') and pp4['profit'] == pp3['profit'])
    check('bill balance 1500', bill.balance() == D('1500.00'), bill.balance())
    r = add(ad, type='bill_payment', account=bank.pk, amount='2000', bill=bill.pk); check('overpaying a bill rejected', 'more than the bill balance' in r.content.decode())

    # approval
    add(ac, type='expense', account=bank.pk, amount='2500', vat_mode='none', category=rent.pk, description='ZZ big by accounts')
    big = FinTxn.objects.get(description='ZZ big by accounts'); check('accounts entry above limit is pending', big.status == 'pending')
    b5 = eng.Books(end=today); check('pending entry does not count', b5.balances()[bank.pk] == b4.balances()[bank.pk])
    add(ac, type='expense', account=bank.pk, amount='1500', vat_mode='none', category=rent.pk, description='ZZ small by accounts')
    check('accounts entry under limit posts', FinTxn.objects.get(description='ZZ small by accounts').status == 'posted')
    add(ad, type='expense', account=bank.pk, amount='9999', vat_mode='none', category=rent.pk, description='ZZ big by admin')
    check('admin entry above limit posts directly', FinTxn.objects.get(description='ZZ big by admin').status == 'posted')
    ac.post(f'/accounting/transactions/{big.pk}/action/', {'action': 'approve'}); big.refresh_from_db()
    check('accounts role cannot approve', big.status == 'pending')
    ad.post(f'/accounting/transactions/{big.pk}/action/', {'action': 'approve'}); big.refresh_from_db()
    check('admin approves -> posted', big.status == 'posted' and big.approved_by_id == users['admin'].pk)

    print('\n5. Void, lock, audit')
    ad.post(f'/accounting/transactions/{big.pk}/action/', {'action': 'void'}); big.refresh_from_db(); check('void needs a reason', big.status == 'posted')
    ad.post(f'/accounting/transactions/{big.pk}/action/', {'action': 'void', 'reason': 'test'}); big.refresh_from_db()
    check('void with reason works and row is kept', big.status == 'void' and FinTxn.objects.filter(pk=big.pk).exists())
    tt = FinTxn.objects.get(description='ZZ rent')
    r = ad.post('/accounting/bills/%d/void/' % bill.pk, {'reason': 'x'}); bill.refresh_from_db(); check('bill with payments cannot be voided', bill.status == 'open')
    ad.post('/accounting/settings/', {'action': 'close', 'locked_until': today.isoformat()})
    check('period closed', AccSetting.get().locked_until == today)
    r = add(ad, type='expense', account=bank.pk, amount='10', vat_mode='none', category=rent.pk, description='ZZ locked'); check('cannot add into a closed period', 'closed up to' in r.content.decode() and not FinTxn.objects.filter(description='ZZ locked').exists())
    ad.post(f'/accounting/transactions/{tt.pk}/action/', {'action': 'void', 'reason': 'x'}); tt.refresh_from_db(); check('cannot void in a closed period', tt.status == 'posted')
    ac.post('/accounting/settings/', {'action': 'reopen', 'locked_until': ''}); check('accounts role cannot reopen', AccSetting.get().locked_until == today)
    ad.post('/accounting/settings/', {'action': 'reopen', 'locked_until': ''}); check('admin can reopen', AccSetting.get().locked_until is None)
    check('audit log written', AuditLog.objects.filter(model_name='FinTxn', user=users['admin']).exists())

    print('\n6. Pages render')
    for url in ('/accounting/', '/accounting/transactions/', '/accounting/transactions/new/', '/accounting/transactions/new/?type=transfer', '/accounting/transactions/new/?type=bill_payment',
                '/accounting/bills/', '/accounting/bills/new/', f'/accounting/bills/{bill.pk}/', '/accounting/receivables/', '/accounting/receivables/?side=payable',
                '/accounting/accounts/', f'/accounting/accounts/{bank.pk}/', '/accounting/reports/', '/accounting/reports/?tab=vat', '/accounting/reports/?tab=cash',
                '/accounting/reports/?tab=detail', '/accounting/settings/', f'/accounting/transactions/{tt.pk}/', '/accounting/transactions/?export=csv', '/accounting/reports/?export=csv'):
        r = ad.get(url); check(f'GET {url}', r.status_code == 200, r.status_code)
    r = ac.get('/accounting/settings/'); check('accounts role cannot open settings', r.status_code == 302)
    page = ad.get(f'/accounting/accounts/{bank.pk}/').content.decode()
    check('statement shows the payout', 'Tabby payout' in page)
    check('unrouted method warns', True)
    FinAccount.objects.filter(pk=pos.pk).update(receives='')
    check('missing route produces a warning', any('"card"' in w for w in eng.Books(end=today).warnings))
finally:
    FinTxn.objects.filter(description__startswith='ZZ').update(status='void')
    FinTxn.objects.filter(bill__vendor='ZZ Vendor').delete()
    FinTxn.objects.filter(description__in=('same', 'neg', 'bad', 'nocat')).delete()
    FinTxn.objects.filter(description__startswith='ZZ').delete()
    Bill.objects.filter(vendor='ZZ Vendor').delete()
    GatewayPayout.objects.filter(pk__in=made['gp']).delete()
    InvoicePayment.objects.filter(pk__in=made['pay']).delete()
    Invoice.objects.filter(pk__in=made['inv']).delete()
    Client.objects.filter(name='ZZ Acc Client').delete()
    for pk, (o, r) in saved_open.items(): FinAccount.objects.filter(pk=pk).update(opening_balance=o, receives=r)
    AccSetting.objects.filter(pk=1).update(books_start_date=saved[0], vat_rate=saved[1], approval_threshold=saved[2], locked_until=saved[3])
    AuditLog.objects.filter(user__username__startswith='zz_acc_').delete()
    User.objects.filter(username__startswith='zz_acc_').delete()
    print(f'\nRESULT: {ok} passed, {bad} failed')
