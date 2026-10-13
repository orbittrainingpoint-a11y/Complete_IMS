"""Trainer schedule link: a public, no-login, durable link per trainer showing only their own
sessions (not other trainers'). Plus: confirming a student check-in emails only that session's
own trainer, not every trainer in the system."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.conf import settings
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
from django.test.utils import setup_test_environment
setup_test_environment()
from django.core import mail
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *
from invoices import schedule_engine as eng
from invoices import trainer_link as tl
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
checkin_mod._is_on_office_wifi = lambda request: True
now_min = 14 * 60

def within(delta_min):
    m = max(0, min(23 * 60, now_min + delta_min))
    return dt.time(m // 60, m % 60)

made = []
try:
    course = Course.objects.create(name='ZZ Link Course', code='ZZTL1')
    t1 = Trainer.objects.create(name='ZZ Link Trainer One', email='zz.trainer1@example.com')
    t2 = Trainer.objects.create(name='ZZ Link Trainer Two', email='zz.trainer2@example.com')
    made += [course, t1, t2]

    print('1. Token round-trips to the right trainer')
    tok1 = tl.make_trainer_token(t1.pk)
    check('token resolves back to trainer 1', tl._read_trainer_token(tok1) == t1.pk)
    check('garbage token resolves to nothing', tl._read_trainer_token('not-a-real-token') is None)

    print('\n2. Public page needs no login and shows only this trainer\'s sessions')
    monday = today - dt.timedelta(days=today.weekday())
    reg = Registration.objects.create(first_name='ZZ', last_name='LinkStudent', phone_no='1', email='zz.link@x.test',
                                      country='UAE', consultant_name='x', student_status='active')
    made.append(reg)
    rule1 = ScheduleRule.objects.create(trainer=t1, schedule_type='individual', registration=reg, course=course,
                                        start_date=monday, weekdays='0,1,2,3,4,5,6', start_time=dt.time(10, 0), session_minutes=60)
    occ1 = ScheduleOccurrence.objects.create(rule=rule1, trainer=t1, date=monday, start_time=dt.time(10, 0),
                                             end_time=dt.time(11, 0), status='scheduled')
    rule2 = ScheduleRule.objects.create(trainer=t2, schedule_type='individual', registration=reg, course=course,
                                        start_date=monday, weekdays='0,1,2,3,4,5,6', start_time=dt.time(15, 0), session_minutes=60)
    occ2 = ScheduleOccurrence.objects.create(rule=rule2, trainer=t2, date=monday, start_time=dt.time(15, 0),
                                             end_time=dt.time(16, 0), status='scheduled')
    made += [rule1, occ1, rule2, occ2]

    anon = DjClient()
    r = anon.get(f'/trainer-link/{tok1}/', **HTML)
    check('loads without login -> 200', r.status_code == 200)
    check("shows trainer one's own student", b'ZZ LinkStudent' in r.content)
    check("does NOT show trainer two's session", b'15:00' not in r.content and b'3:00 PM' not in r.content)

    r2 = anon.get(f'/trainer-link/{tl.make_trainer_token(t2.pk)}/', **HTML)
    check("trainer two's own link shows their own session", r2.status_code == 200 and b'3:00 PM' in r2.content, r2.content[:200])

    print('\n3. Invalid/tampered token -> friendly 404, not a crash')
    r3 = anon.get('/trainer-link/garbage-token-xyz/', **HTML)
    check('invalid token -> 404 with a friendly message', r3.status_code == 404 and b"isn't valid" in r3.content)

    print('\n4. Confirming a check-in emails only that session\'s own trainer')
    mail.outbox.clear()
    occ_today = ScheduleOccurrence.objects.create(rule=rule1, trainer=t1, date=today, start_time=within(-15),
                                                   end_time=within(45), status='scheduled')
    made.append(occ_today)
    r4 = anon.post('/checkin/lookup/', {'student_id': reg.registration_number}, **HTML)
    check('matched today\'s session', r4.status_code == 200 and b'Agree' in r4.content, r4.content[:200])
    import re as _re
    token = _re.search(rb'name="token" value="([^"]+)"', r4.content).group(1).decode()
    r5 = anon.post('/checkin/confirm/', {'token': token}, **HTML)
    check('confirm succeeds', r5.status_code == 200 and b'Confirmed' in r5.content)
    check('exactly one email sent', len(mail.outbox) == 1, len(mail.outbox))
    if mail.outbox:
        sent = mail.outbox[0]
        check('sent to trainer 1 only, not trainer 2', sent.to == ['zz.trainer1@example.com'])
        check('subject mentions the student', 'ZZ LinkStudent' in sent.subject, sent.subject)

    print('\n5. Trainer with no email on file -> no crash, nothing sent')
    t3 = Trainer.objects.create(name='ZZ Link Trainer NoEmail', email='')
    made.append(t3)
    rule3 = ScheduleRule.objects.create(trainer=t3, schedule_type='individual', registration=reg, course=course,
                                        start_date=today, weekdays='0,1,2,3,4,5,6', start_time=within(-15), session_minutes=60)
    occ3 = ScheduleOccurrence.objects.create(rule=rule3, trainer=t3, date=today, start_time=within(-15),
                                             end_time=within(45), status='scheduled')
    made += [rule3, occ3]
    c3 = StudentCheckIn.objects.create(registration=reg, occurrence=occ3, course=course, trainer=t3,
                                       scheduled_date=today, scheduled_start=occ3.start_time, scheduled_end=occ3.end_time,
                                       status='awaiting_confirm')
    made.append(c3)
    mail.outbox.clear()
    checkin_mod._notify_trainer_of_checkin(c3)
    check('no email attempted for a trainer with no address on file', len(mail.outbox) == 0)

    print('\n6. Admin trainer list offers a copy-link button with the right token')
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'
    r6 = admin.get('/trainers/', **HTML)
    check('trainer list loads', r6.status_code == 200)
    check("includes trainer one's real link token", tok1.encode() in r6.content)

finally:
    checkin_mod._now = _orig_now
    mw_mod._is_after_dubai_curfew = _orig_curfew
    checkin_mod._is_on_office_wifi = _orig_wifi
    StudentCheckIn.objects.filter(trainer__name__startswith='ZZ Link').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name__startswith='ZZ Link').delete()
    ScheduleRule.objects.filter(trainer__name__startswith='ZZ Link').delete()
    Registration.objects.filter(last_name='LinkStudent').delete()
    Course.objects.filter(code='ZZTL1').delete()
    Trainer.objects.filter(name__startswith='ZZ Link').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
