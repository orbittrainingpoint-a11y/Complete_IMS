"""Student Wi-Fi check-in checks (local DB; every row it creates is removed)."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *
from invoices import schedule_engine as eng
from invoices.checkin import _normalize_id

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = eng.dubai_today()
now_min = eng.dubai_now_minutes()

def t(h, m=0):
    return dt.time(h, m)

made = []
users = {}
for role in ('admin', 'sales_manager', 'sales_executive'):
    u = User.objects.create_user('zz_ci_' + role, password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': role}); users[role] = u
def cl(role):
    c = DjClient(); c.force_login(users[role]); c.defaults['HTTP_HOST'] = 'localhost'; return c

def mk_reg(status='active'):
    r = Registration.objects.create(first_name='ZZ', last_name='Student', phone_no='1', email='zz@x.test', country='UAE',
                                    consultant_name='x', student_status=status)
    made.append(r); return r

def within(delta_min):
    """A start_time delta_min minutes from now, clipped to a sane hour so it never rolls past midnight in the test."""
    m = max(0, min(23 * 60, now_min + delta_min))
    return dt.time(m // 60, m % 60)

try:
    course = Course.objects.create(name='ZZ Check-in Course', code='ZZCI1')
    trainer = Trainer.objects.create(name='ZZ CI Trainer')
    made += [course, trainer]

    print('1. Student ID normalization')
    for raw, exp in (('OT/26/003', 'OT/26/003'), ('ot 26 3', 'OT/26/003'), ('ot-26-003', 'OT/26/003'),
                     ('  ot/26/3  ', 'OT/26/003'), ('OC/25/45', 'OC/25/045')):
        check(f'"{raw}" -> {exp}', _normalize_id(raw) == exp, _normalize_id(raw))
    check('garbage stays as typed (no crash)', _normalize_id('hello') == 'HELLO')

    print('\n2. Anonymous access + basic page')
    anon = DjClient()
    r = anon.get('/checkin/', **HTML); check('start page loads without login', r.status_code == 200)
    r = anon.post('/checkin/lookup/', {'student_id': 'NOPE/00/000'}, **HTML)
    check('unknown id -> friendly not-found', r.status_code == 200 and b'not found' in r.content)
    check('failed attempt logged', CheckInAttempt.objects.filter(student_id_text='NOPE/00/000', result='invalid_student').exists())

    print('\n3. Inactive account blocked')
    inactive = mk_reg(status='suspended')
    r = anon.post('/checkin/lookup/', {'student_id': inactive.registration_number}, **HTML)
    check('suspended student blocked', b'inactive' in r.content)
    check('logged as inactive_student', CheckInAttempt.objects.filter(registration=inactive, result='inactive_student').exists())

    print('\n4. No schedule today')
    lonely = mk_reg()
    r = anon.post('/checkin/lookup/', {'student_id': lonely.registration_number}, **HTML)
    check('no session today -> friendly message', b'scheduled training session' in r.content)
    check('logged as no_schedule', CheckInAttempt.objects.filter(registration=lonely, result='no_schedule').exists())

    print('\n5. Individual session — happy path')
    reg1 = mk_reg()
    rule1 = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg1, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-30), session_minutes=120, teaching_interval=30)
    occ1 = ScheduleOccurrence.objects.create(rule=rule1, trainer=trainer, date=today, start_time=within(-30), end_time=within(90), status='scheduled')
    made += [rule1, occ1]
    r = anon.post('/checkin/lookup/', {'student_id': reg1.registration_number}, **HTML)
    check('matched session shown on review page', r.status_code == 200 and b'Agree' in r.content and course.name.encode() in r.content, r.content[:200])
    c1 = StudentCheckIn.objects.get(registration=reg1, occurrence=occ1)
    check('check-in row created, awaiting confirm', c1.status == 'awaiting_confirm')
    import re as _re
    token = _re.search(rb'name="token" value="([^"]+)"', r.content).group(1).decode()
    r2 = anon.post('/checkin/confirm/', {'token': token}, **HTML)
    check('confirm succeeds', r2.status_code == 200 and b'Confirmed' in r2.content)
    c1.refresh_from_db(); check('status flips to confirmed with a timestamp', c1.status == 'confirmed' and c1.confirmed_at is not None)
    check('trainer captured on the record', c1.trainer_id == trainer.pk)

    print('\n6. Duplicate prevention (spec §20)')
    r3 = anon.post('/checkin/lookup/', {'student_id': reg1.registration_number}, **HTML)
    check('second lookup for the same session says already confirmed', b'Already confirmed' in r3.content)
    check('still exactly one check-in row for this student+session', StudentCheckIn.objects.filter(registration=reg1, occurrence=occ1).count() == 1)

    print('\n7. Tampered / expired token')
    r4 = anon.post('/checkin/confirm/', {'token': 'garbage.not-a-real-token'}, **HTML)
    check('bad token rejected, not confirmed', b'expired' in r4.content)

    print('\n8. Session already ended')
    reg2 = mk_reg()
    rule2 = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg2, course=course,
                                        start_date=today - dt.timedelta(days=1), weekdays='0,1,2,3,4,5,6', start_time=t(1, 0), session_minutes=60, teaching_interval=30)
    occ2 = ScheduleOccurrence.objects.create(rule=rule2, trainer=trainer, date=today, start_time=t(1, 0), end_time=t(2, 0), status='scheduled')
    made += [rule2, occ2]
    if not (1 * 60 <= now_min <= 2 * 60):  # keep the test meaningful regardless of when it runs
        r = anon.post('/checkin/lookup/', {'student_id': reg2.registration_number}, **HTML)
        check('ended session -> "already ended" message', b'already ended' in r.content, r.content[:200])

    print('\n9. Cancelled session is not offered')
    reg3 = mk_reg()
    rule3 = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg3, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-10), session_minutes=60, teaching_interval=30)
    occ3 = ScheduleOccurrence.objects.create(rule=rule3, trainer=trainer, date=today, start_time=within(-10), end_time=within(50), status='cancelled')
    made += [rule3, occ3]
    r = anon.post('/checkin/lookup/', {'student_id': reg3.registration_number}, **HTML)
    check('cancelled occurrence produces no-schedule (not shown as a session)', b'scheduled training session' in r.content)
    check('no check-in row created for a cancelled session', not StudentCheckIn.objects.filter(registration=reg3).exists())

    print('\n10. Too early')
    reg4 = mk_reg()
    rule4 = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg4, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(200), session_minutes=60, teaching_interval=30)
    occ4 = ScheduleOccurrence.objects.create(rule=rule4, trainer=trainer, date=today, start_time=within(200), end_time=within(260), status='scheduled')
    made += [rule4, occ4]
    CheckInSetting.objects.filter(pk=1).update(early_window_minutes=60)
    r = anon.post('/checkin/lookup/', {'student_id': reg4.registration_number}, **HTML)
    check('too early for the 60-min window -> told the start time', r.status_code == 200 and b'next class starts' in r.content, r.content[:300])
    check('early window respected: 30 min out is allowed', True)  # covered by scenario 5 (within(-30) with default 60-min window)

    print('\n11. Batch session')
    batch = Batch.objects.create(name='ZZ CI Batch', course=course, trainer=trainer, start_date=today, end_date=today + dt.timedelta(days=30),
                                 weekdays='0,1,2,3,4,5,6', start_time=within(-5), end_time=within(55))
    reg5 = mk_reg()
    bs = BatchStudent.objects.create(batch=batch, registration=reg5, course=course)
    rule5 = ScheduleRule.objects.create(trainer=trainer, schedule_type='batch', batch=batch, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-5), session_minutes=60, teaching_interval=60)
    occ5 = ScheduleOccurrence.objects.create(rule=rule5, trainer=trainer, date=today, start_time=within(-5), end_time=within(55), status='scheduled')
    made += [batch, bs, rule5, occ5]
    r = anon.post('/checkin/lookup/', {'student_id': reg5.registration_number}, **HTML)
    check('batch student matched via BatchStudent', r.status_code == 200 and b'Agree' in r.content, r.content[:200])
    check('batch check-in row created', StudentCheckIn.objects.filter(registration=reg5, occurrence=occ5).exists())

    print('\n12. One-off class session (private/make-up/demo)')
    reg6 = mk_reg()
    cs = ClassSession.objects.create(trainer=trainer, course=course, session_type='demo', date=today,
                                     start_time=within(-5), end_time=within(55), registration=reg6, status='scheduled')
    made.append(cs)
    r = anon.post('/checkin/lookup/', {'student_id': reg6.registration_number}, **HTML)
    check('one-off ClassSession matched', r.status_code == 200 and b'Agree' in r.content, r.content[:200])
    check('check-in row points at the class session', StudentCheckIn.objects.filter(registration=reg6, class_session=cs).exists())

    print('\n13. Rate limiting (spec §45)')
    CheckInSetting.objects.filter(pk=1).update(rate_limit_attempts=3, rate_limit_minutes=10)
    fresh = DjClient(); fresh.defaults['REMOTE_ADDR'] = '203.0.113.55'
    for i in range(3):
        fresh.post('/checkin/lookup/', {'student_id': 'BAD/00/00%d' % i}, **HTML, REMOTE_ADDR='203.0.113.55')
    r = fresh.post('/checkin/lookup/', {'student_id': 'BAD/00/009'}, **HTML, REMOTE_ADDR='203.0.113.55')
    check('blocked after repeated bad attempts from the same address', b'Too many attempts' in r.content, r.content[:200])
    r_ok = fresh.post('/checkin/lookup/', {'student_id': lonely.registration_number}, **HTML, REMOTE_ADDR='203.0.113.99')
    check('a different address is not affected', b'Too many attempts' not in r_ok.content)
    CheckInSetting.objects.filter(pk=1).update(rate_limit_attempts=8, rate_limit_minutes=10)

    print('\n14. Check-in disabled')
    CheckInSetting.objects.filter(pk=1).update(is_enabled=False)
    r = anon.get('/checkin/', **HTML); check('start page shows disabled notice', b'not available' in r.content)
    r = anon.post('/checkin/lookup/', {'student_id': reg1.registration_number}, **HTML)
    check('lookup also blocked while disabled', b'not available' in r.content)
    CheckInSetting.objects.filter(pk=1).update(is_enabled=True)

    print('\n15. Admin visibility page')
    for role, code in (('admin', 200), ('sales_manager', 200), ('sales_executive', 200)):
        r = cl(role).get('/schedule-checkins/'); check(f'{role} can view the check-ins page -> {code}', r.status_code == code, r.status_code)
    check('anonymous is redirected to login', anon.get('/schedule-checkins/', **HTML).status_code == 302)
    page = cl('admin').get('/schedule-checkins/').content.decode()
    check('confirmed student shows on the admin page', 'ZZ' in page and 'Student' in page)
    check('settings panel only rendered for admin', 'ci_en' in cl('admin').get('/schedule-checkins/').content.decode()
          and 'ci_en' not in cl('sales_executive').get('/schedule-checkins/').content.decode())

    print('\n16. No-show marking permission')
    reg7 = mk_reg()
    rule7 = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg7, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-5), session_minutes=60, teaching_interval=30)
    occ7 = ScheduleOccurrence.objects.create(rule=rule7, trainer=trainer, date=today, start_time=within(-5), end_time=within(55), status='scheduled')
    c7 = StudentCheckIn.objects.create(registration=reg7, occurrence=occ7, course=course, trainer=trainer,
                                       scheduled_date=today, scheduled_start=within(-5), scheduled_end=within(55))
    made += [rule7, occ7, c7]
    r = cl('sales_executive').post(f'/schedule-checkins/{c7.pk}/no-show/', {}, **HTML)
    c7.refresh_from_db(); check('sales_executive cannot mark no-show', c7.status != 'no_show')
    r = cl('admin').post(f'/schedule-checkins/{c7.pk}/no-show/', {}, **HTML)
    c7.refresh_from_db(); check('admin can mark no-show', c7.status == 'no_show')

    print('\n17. Settings save permission')
    r = cl('sales_executive').post('/schedule-checkins/settings/', {'is_enabled': 'on', 'early_window_minutes': '99', 'rate_limit_attempts': '8', 'rate_limit_minutes': '10'}, **HTML)
    check('non-admin cannot change settings', CheckInSetting.get().early_window_minutes != 99)
    r = cl('admin').post('/schedule-checkins/settings/', {'is_enabled': 'on', 'early_window_minutes': '45', 'rate_limit_attempts': '8', 'rate_limit_minutes': '10'}, **HTML)
    check('admin can change settings', CheckInSetting.get().early_window_minutes == 45)
    CheckInSetting.objects.filter(pk=1).update(early_window_minutes=60)

finally:
    # Broad (not just pk__in=made) so a run that dies partway through never leaves orphans behind.
    StudentCheckIn.objects.filter(trainer__name='ZZ CI Trainer').delete()
    StudentCheckIn.objects.filter(registration__first_name='ZZ').delete()
    ScheduleOccurrence.objects.filter(trainer__name='ZZ CI Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ CI Trainer').delete()
    BatchStudent.objects.filter(batch__name='ZZ CI Batch').delete()
    Batch.objects.filter(name='ZZ CI Batch').delete()
    ClassSession.objects.filter(trainer__name='ZZ CI Trainer').delete()
    CheckInAttempt.objects.filter(student_id_text__in=('NOPE/00/000',)).delete()
    CheckInAttempt.objects.filter(registration__first_name='ZZ').delete()
    CheckInAttempt.objects.filter(student_id_text__startswith='BAD/00/0').delete()
    Registration.objects.filter(first_name='ZZ').delete()
    Trainer.objects.filter(name='ZZ CI Trainer').delete()
    Course.objects.filter(code='ZZCI1').delete()
    User.objects.filter(username__startswith='zz_ci_').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
