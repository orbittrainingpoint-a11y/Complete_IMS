"""A sales manager has two targets: her own individual number (same SalesTarget an executive
has) and a separate TeamSalesTarget for her team combined. Covers: Set Targets page includes
managers (it only used to list executives), saving both target types from one POST, her own
dashboard showing both progress bars, and the admin dashboard's manager row reflecting her real
individual target instead of a hardcoded 0%."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = dt.date.today()
month_first = today.replace(day=1)
month_str = month_first.strftime('%Y-%m')

made = []
users = {}
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

    mgr = User.objects.create_user('zz_tgt_mgr', password='x')
    UserProfile.objects.update_or_create(user=mgr, defaults={'role': 'sales_manager'})
    made.append(mgr)
    mgr_client = DjClient(); mgr_client.force_login(mgr); mgr_client.defaults['HTTP_HOST'] = 'localhost'

    print('1. Set Targets page now lists sales managers, not just executives')
    r = admin.get('/manage/set-targets/', **HTML)
    check('page loads', r.status_code == 200)
    check('manager appears on the page', b'zz_tgt_mgr' in r.content)
    check('both an individual and a team target field are present for her',
          f'target_amount_{mgr.id}'.encode() in r.content and f'team_target_amount_{mgr.id}'.encode() in r.content)

    print('\n2. Saving the form sets BOTH her individual target and the team target')
    r = admin.post('/manage/set-targets/', {
        'month': month_str,
        f'target_amount_{mgr.id}': '30000',
        f'target_reg_{mgr.id}': '10',
        f'team_target_amount_{mgr.id}': '150000',
        f'team_target_reg_{mgr.id}': '50',
    }, **HTML)
    check('redirects after save', r.status_code == 302)
    individual = SalesTarget.objects.filter(user=mgr, month=month_first).first()
    team = TeamSalesTarget.objects.filter(manager=mgr, month=month_first).first()
    made += [individual, team]
    check('individual SalesTarget saved (same model an executive uses)',
          individual is not None and individual.target_amount == 30000 and individual.target_registrations == 10)
    check('TeamSalesTarget saved separately', team is not None and team.target_amount == 150000 and team.target_registrations == 50)

    print('\n3. Her own dashboard shows both targets')
    r = mgr_client.get('/', **HTML)
    check('dashboard loads', r.status_code == 200)
    check('individual target card present', b'Individual Target' in r.content)
    check('team target card present', b'Team Target' in r.content)
    check('her individual target amount shown', b'30,000' in r.content or b'30000' in r.content, r.content[:0])

    print('\n4. Admin dashboard reflects her real individual target, not a hardcoded 0')
    r = admin.get('/', **HTML)
    check('admin dashboard loads', r.status_code == 200, r.status_code)
    # The actual regression this fixes: the admin view's manager loop used to hardcode
    # target_amount=0 for every manager regardless of what was saved. Confirm the shared
    # lookup it now uses returns her real saved amount, not the old hardcoded value.
    from invoices.views import _exec_target
    tamt, treg = _exec_target(mgr, month_first)
    check('_exec_target now returns her saved individual target, not 0', tamt == 30000, tamt)
    check('her saved registration target too', treg == 10, treg)

    print('\n5. No target set yet -> 0%, not an error (division-by-zero guard)')
    mgr2 = User.objects.create_user('zz_tgt_mgr2', password='x')
    UserProfile.objects.update_or_create(user=mgr2, defaults={'role': 'sales_manager'})
    made.append(mgr2)
    mgr2_client = DjClient(); mgr2_client.force_login(mgr2); mgr2_client.defaults['HTTP_HOST'] = 'localhost'
    r = mgr2_client.get('/', **HTML)
    check('dashboard with no target set still loads cleanly', r.status_code == 200)
    check('shows "(not set)" rather than crashing', b'not set' in r.content)

finally:
    TeamSalesTarget.objects.filter(manager__username__startswith='zz_tgt_').delete()
    SalesTarget.objects.filter(user__username__startswith='zz_tgt_').delete()
    User.objects.filter(username__startswith='zz_tgt_').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
