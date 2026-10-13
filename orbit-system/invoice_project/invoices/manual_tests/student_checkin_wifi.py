"""In-person check-in now also requires the training centre WiFi, checked against the exact
same office-network ranges the CRM manages for staff attendance (one shared source of truth,
via _is_on_office_wifi -> CRM's /api/internal/office-check). Online sessions skip this check
entirely — their attendance comes from the LMS login tracker instead. The CRM call is mocked
here (no real network dependency); a separate concern (CRM reachable, correct answer) is the
CRM's own test for that endpoint."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.test import Client as DjClient
from invoices.models import *
from invoices import schedule_engine as eng
import invoices.checkin as checkin_mod
import invoices.middleware as mw_mod

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = eng.dubai_today()
_FAKE_NOW = dt.datetime.combine(today, dt.time(14, 0), tzinfo=checkin_mod.DUBAI)
_orig_now = checkin_mod._now
_orig_curfew = mw_mod._is_after_dubai_curfew
_orig_wifi = checkin_mod._is_on_office_wifi
checkin_mod._now = lambda: _FAKE_NOW
mw_mod._is_after_dubai_curfew = lambda: False
now_min = 14 * 60

def within(delta_min):
    m = max(0, min(23 * 60, now_min + delta_min))
    return dt.time(m // 60, m % 60)

made = []
try:
    course = Course.objects.create(name='ZZ Wifi Course', code='ZZWF1')
    trainer = Trainer.objects.create(name='ZZ Wifi Trainer')
    made += [course, trainer]

    def mk_session(class_type='offline'):
        reg = Registration.objects.create(first_name='ZZ', last_name='Wifi', phone_no='1', email='zzwifi@x.test',
                                          country='UAE', consultant_name='x', student_status='active', class_type=class_type)
        rule = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg, course=course,
                                           start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-30),
                                           session_minutes=120, teaching_interval=30)
        occ = ScheduleOccurrence.objects.create(rule=rule, trainer=trainer, date=today, start_time=within(-30),
                                                end_time=within(90), status='scheduled')
        made.extend([reg, rule, occ])
        return reg

    print('1. Offline session, NOT on office WiFi -> blocked, no check-in created')
    checkin_mod._is_on_office_wifi = lambda request: False
    reg_off = mk_session('offline')
    anon = DjClient()
    r = anon.post('/checkin/lookup/', {'student_id': reg_off.registration_number}, **HTML)
    check('blocked with the WiFi message', r.status_code == 200 and b'training centre WiFi' in r.content, r.content[:300])
    check('no StudentCheckIn row created', not StudentCheckIn.objects.filter(registration=reg_off).exists())
    check('logged as not_on_wifi', CheckInAttempt.objects.filter(registration=reg_off, result='not_on_wifi').exists())

    print('\n2. Same offline session, ON office WiFi -> proceeds normally')
    checkin_mod._is_on_office_wifi = lambda request: True
    r = anon.post('/checkin/lookup/', {'student_id': reg_off.registration_number}, **HTML)
    check('review page shown', r.status_code == 200 and b'Agree' in r.content, r.content[:300])
    check('StudentCheckIn row created', StudentCheckIn.objects.filter(registration=reg_off).exists())

    print('\n3. Online session, NOT on office WiFi -> still proceeds (check only applies to offline)')
    checkin_mod._is_on_office_wifi = lambda request: False
    reg_on = mk_session('online')
    r = anon.post('/checkin/lookup/', {'student_id': reg_on.registration_number}, **HTML)
    check('online session is not blocked by the WiFi check', r.status_code == 200 and b'Agree' in r.content, r.content[:300])
    check('StudentCheckIn row created for the online session', StudentCheckIn.objects.filter(registration=reg_on).exists())

    print('\n4. CRM unreachable -> fails open (does not block check-in)')
    def _raises(request):
        raise RuntimeError('simulated CRM outage')
    # _is_on_office_wifi itself is what catches the real urlopen exception and fails open; here
    # we exercise the real function (not a stub) against a CRM that cannot be reached, by
    # pointing it at a port nothing listens on, to prove the fail-open path for real.
    import invoices.views as views_mod
    _orig_crm_url = views_mod._CRM_URL
    views_mod._CRM_URL = 'http://127.0.0.1:1'  # nothing listens here -> connection refused fast
    checkin_mod._is_on_office_wifi = _orig_wifi
    reg_outage = mk_session('offline')
    r = anon.post('/checkin/lookup/', {'student_id': reg_outage.registration_number}, **HTML)
    check('CRM outage does not block an in-person check-in', r.status_code == 200 and b'Agree' in r.content, r.content[:300])
    views_mod._CRM_URL = _orig_crm_url

finally:
    checkin_mod._now = _orig_now
    mw_mod._is_after_dubai_curfew = _orig_curfew
    checkin_mod._is_on_office_wifi = _orig_wifi
    StudentCheckIn.objects.filter(trainer__name='ZZ Wifi Trainer').delete()
    CheckInAttempt.objects.filter(registration__last_name='Wifi').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ Wifi Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ Wifi Trainer').delete()
    Registration.objects.filter(last_name='Wifi').delete()
    Course.objects.filter(code='ZZWF1').delete()
    Trainer.objects.filter(name='ZZ Wifi Trainer').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
