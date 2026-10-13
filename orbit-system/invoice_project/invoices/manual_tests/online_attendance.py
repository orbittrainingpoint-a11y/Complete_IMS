"""Online-class attendance via LMS login tracking. No local LMS Postgres exists, so
_lms_connect/_lms_logged_in_during are stubbed with an in-memory fake login list — the real
SQL query against activity_logs/users is exercised only in production, where the LMS actually
runs. This test covers the decision logic: which sessions get checked, the match-by-email,
the login-window math, and that it never double-processes or touches offline sessions."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from invoices.models import *
from invoices import schedule_engine as eng
import invoices.online_attendance as oa

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

DUBAI = oa.DUBAI
today = eng.dubai_today()

# Fake "LMS": a set of (email, login_at_utc) pairs, checked by a stub replacing the real
# Postgres-backed lookup. A non-None sentinel connection makes sync_online_attendance proceed
# past its "LMS not configured" early-out.
fake_logins = []
class _FakeConn:
    def close(self): pass
_orig_connect = oa._lms_connect
_orig_lookup = oa._lms_logged_in_during
oa._lms_connect = lambda: _FakeConn()
def _stub_lookup(conn, email, start_utc, end_utc):
    return any(e.lower() == (email or '').lower() and start_utc <= at <= end_utc for e, at in fake_logins)
oa._lms_logged_in_during = _stub_lookup

made = []
try:
    course = Course.objects.create(name='ZZ Online Course', code='ZZOA1')
    trainer = Trainer.objects.create(name='ZZ Online Trainer')
    made += [course, trainer]

    def mk_reg(email, class_type='online'):
        r = Registration.objects.create(first_name='ZZ', last_name='Online', phone_no='1', email=email,
                                        country='UAE', consultant_name='x', student_status='active', class_type=class_type)
        made.append(r)
        return r

    def mk_individual_session(reg, start_time, end_time, date=today):
        rule = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg, course=course,
                                           start_date=date, weekdays='0,1,2,3,4,5,6', start_time=start_time, session_minutes=60)
        occ = ScheduleOccurrence.objects.create(rule=rule, trainer=trainer, date=date, start_time=start_time,
                                                end_time=end_time, status='scheduled')
        made.extend([rule, occ])
        return occ

    # Frozen "now" (mid-afternoon), not the real wall clock: every offset below assumes room on
    # both sides of it, which a run close to midnight would break via date rollover — same
    # reasoning as student_checkin.py's _FAKE_NOW.
    now = dt.datetime.combine(today, dt.time(14, 0), tzinfo=DUBAI)
    ended_30_ago_start = (now - dt.timedelta(minutes=90)).time().replace(microsecond=0)
    ended_30_ago_end = (now - dt.timedelta(minutes=30)).time().replace(microsecond=0)

    print('1. Online session, student logged into the LMS during the window -> confirmed')
    reg1 = mk_reg('zz.online1@example.com')
    occ1 = mk_individual_session(reg1, ended_30_ago_start, ended_30_ago_end)
    login_time = dt.datetime.combine(today, ended_30_ago_start, tzinfo=DUBAI) + dt.timedelta(minutes=5)
    fake_logins.append(('zz.online1@example.com', login_time))
    checked, confirmed, skipped = oa.sync_online_attendance(now=now)
    check('one session checked, one confirmed', checked >= 1 and confirmed >= 1, (checked, confirmed, skipped))
    c1 = StudentCheckIn.objects.filter(registration=reg1, occurrence=occ1).first()
    check('StudentCheckIn created and confirmed', c1 is not None and c1.status == 'confirmed', c1)
    check('marked as LMS auto-detected', c1.user_agent == 'LMS auto-detected login')

    print('\n2. Online session, no LMS login at all -> nothing created')
    reg2 = mk_reg('zz.online2@example.com')
    occ2 = mk_individual_session(reg2, ended_30_ago_start, ended_30_ago_end)
    oa.sync_online_attendance(now=now)
    check('no check-in created without a login', not StudentCheckIn.objects.filter(registration=reg2, occurrence=occ2).exists())

    print('\n3. Login happened, but AFTER the session ended -> not counted')
    reg3 = mk_reg('zz.online3@example.com')
    occ3 = mk_individual_session(reg3, ended_30_ago_start, ended_30_ago_end)
    late_login = dt.datetime.combine(today, ended_30_ago_end, tzinfo=DUBAI) + dt.timedelta(minutes=20)
    fake_logins.append(('zz.online3@example.com', late_login))
    oa.sync_online_attendance(now=now)
    check('a login after class ended does not count as attendance', not StudentCheckIn.objects.filter(registration=reg3, occurrence=occ3).exists())

    print('\n4. Login a few minutes BEFORE the scheduled start -> still counts (grace window)')
    reg4 = mk_reg('zz.online4@example.com')
    occ4 = mk_individual_session(reg4, ended_30_ago_start, ended_30_ago_end)
    early_login = dt.datetime.combine(today, ended_30_ago_start, tzinfo=DUBAI) - dt.timedelta(minutes=10)
    fake_logins.append(('zz.online4@example.com', early_login))
    oa.sync_online_attendance(now=now)
    c4 = StudentCheckIn.objects.filter(registration=reg4, occurrence=occ4).first()
    check('login just before start (within grace) still counts', c4 is not None and c4.status == 'confirmed', c4)

    print('\n5. Offline session is never checked against the LMS, even with a matching login')
    reg5 = mk_reg('zz.online5@example.com', class_type='offline')
    occ5 = mk_individual_session(reg5, ended_30_ago_start, ended_30_ago_end)
    fake_logins.append(('zz.online5@example.com', dt.datetime.combine(today, ended_30_ago_start, tzinfo=DUBAI)))
    oa.sync_online_attendance(now=now)
    check('offline session untouched by the LMS sync', not StudentCheckIn.objects.filter(registration=reg5, occurrence=occ5).exists())

    print('\n6. Already has a check-in (e.g. manual) -> never double-processed')
    reg6 = mk_reg('zz.online6@example.com')
    occ6 = mk_individual_session(reg6, ended_30_ago_start, ended_30_ago_end)
    existing = StudentCheckIn.objects.create(registration=reg6, occurrence=occ6, course=course, trainer=trainer,
                                             scheduled_date=today, scheduled_start=occ6.start_time, scheduled_end=occ6.end_time,
                                             status='no_show')
    made.append(existing)
    fake_logins.append(('zz.online6@example.com', dt.datetime.combine(today, ended_30_ago_start, tzinfo=DUBAI)))
    oa.sync_online_attendance(now=now)
    existing.refresh_from_db()
    check('existing record left untouched, not overwritten', existing.status == 'no_show')
    check('still exactly one check-in row', StudentCheckIn.objects.filter(registration=reg6, occurrence=occ6).count() == 1)

    print('\n7. Session still in progress (not ended yet) -> not checked')
    reg7 = mk_reg('zz.online7@example.com')
    future_start = (now + dt.timedelta(minutes=10)).time().replace(microsecond=0)
    future_end = (now + dt.timedelta(minutes=70)).time().replace(microsecond=0)
    occ7 = mk_individual_session(reg7, future_start, future_end)
    fake_logins.append(('zz.online7@example.com', now))
    oa.sync_online_attendance(now=now)
    check('session not yet ended is skipped entirely', not StudentCheckIn.objects.filter(registration=reg7, occurrence=occ7).exists())

    print('\n8. LMS not configured (no connection) -> clean no-op, nothing raised')
    oa._lms_connect = lambda: None
    checked8, confirmed8, skipped8 = oa.sync_online_attendance(now=now)
    check('returns (0, 0, 0) when LMS is unreachable/unconfigured', (checked8, confirmed8, skipped8) == (0, 0, 0), (checked8, confirmed8, skipped8))
    oa._lms_connect = lambda: _FakeConn()

finally:
    oa._lms_connect = _orig_connect
    oa._lms_logged_in_during = _orig_lookup
    StudentCheckIn.objects.filter(trainer__name='ZZ Online Trainer').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ Online Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ Online Trainer').delete()
    Registration.objects.filter(last_name='Online').delete()
    Course.objects.filter(code='ZZOA1').delete()
    Trainer.objects.filter(name='ZZ Online Trainer').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
