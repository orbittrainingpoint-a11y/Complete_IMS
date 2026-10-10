"""Weekly schedule reminder email: every Monday, each active student with at least one
class this week gets an email listing the week's sessions, reusing the exact same
ScheduleOccurrence/Batch/ClassSession data the trainer schedule and student check-in use.
Covers individual-rule sessions (mode from Registration.class_type), batch sessions (mode
from Batch.mode), one-off ClassSession rows, the Monday-Sunday window boundary, and the
management command's idempotent re-run behaviour."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.conf import settings
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'  # never send real email from this test
from django.test.utils import setup_test_environment
setup_test_environment()  # creates mail.outbox, since this script runs outside `manage.py test`
from django.core import mail
from django.core.management import call_command
from invoices.models import *
from invoices.weekly_schedule import week_range, week_sessions, group_by_day

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

made = []
try:
    print('1. week_range: Monday..Sunday containing a given date')
    monday, sunday = week_range(dt.date(2026, 10, 14))  # a Wednesday
    check('Wed 14 Oct -> Mon 12..Sun 18 Oct', (monday, sunday) == (dt.date(2026, 10, 12), dt.date(2026, 10, 18)), (monday, sunday))

    trainer = Trainer.objects.create(name='ZZ Weekly Trainer'); made.append(trainer)
    course_a = Course.objects.create(name='ZZ Weekly Course A', code='ZWA1'); made.append(course_a)
    course_b = Course.objects.create(name='ZZ Weekly Course B', code='ZWB1'); made.append(course_b)

    reg_online = Registration.objects.create(first_name='Zara', last_name='Online', phone_no='1', email='zara.online@example.com',
                                             country='UAE', consultant_name='x', student_status='active', class_type='online')
    made.append(reg_online)
    reg_offline = Registration.objects.create(first_name='Zane', last_name='Offline', phone_no='2', email='zane.offline@example.com',
                                              country='UAE', consultant_name='x', student_status='active', class_type='offline')
    made.append(reg_offline)
    reg_inactive = Registration.objects.create(first_name='Zed', last_name='Inactive', phone_no='3', email='zed.inactive@example.com',
                                               country='UAE', consultant_name='x', student_status='inactive')
    made.append(reg_inactive)

    monday, sunday = week_range()  # the real current week, for the actual email flow below

    print('\n2. Individual session this week -> mode comes from the registration')
    rule_ind = ScheduleRule.objects.create(trainer=trainer, schedule_type='individual', registration=reg_online,
                                           course=course_a, start_date=monday, weekdays='0,2,4', start_time=dt.time(10, 0))
    made.append(rule_ind)
    occ_ind = ScheduleOccurrence.objects.create(rule=rule_ind, trainer=trainer, date=monday,
                                                start_time=dt.time(10, 0), end_time=dt.time(11, 0), status='scheduled')
    made.append(occ_ind)
    sessions = week_sessions(reg_online, monday, sunday)
    check('one session found', len(sessions) == 1, sessions)
    check('mode is online (from registration.class_type)', sessions[0]['mode'] == 'online', sessions[0])
    check('course name resolved', sessions[0]['course_name'] == 'ZZ Weekly Course A', sessions[0])

    print('\n3. Batch session -> mode comes from the batch, not the registration')
    batch = Batch.objects.create(name='ZZ Weekly Batch', course=course_b, trainer=trainer,
                                 start_date=monday, end_date=sunday, weekdays='1,3',
                                 start_time=dt.time(14, 0), end_time=dt.time(15, 30), mode='offline')
    made.append(batch)
    bs = BatchStudent.objects.create(batch=batch, registration=reg_online, course=course_b, status='active')
    made.append(bs)
    rule_batch = ScheduleRule.objects.create(trainer=trainer, schedule_type='batch', batch=batch,
                                             start_date=monday, weekdays='1,3', start_time=dt.time(14, 0))
    made.append(rule_batch)
    tuesday = monday + dt.timedelta(days=1)
    occ_batch = ScheduleOccurrence.objects.create(rule=rule_batch, trainer=trainer, date=tuesday,
                                                  start_time=dt.time(14, 0), end_time=dt.time(15, 30), status='scheduled')
    made.append(occ_batch)
    sessions = week_sessions(reg_online, monday, sunday)
    check('now two sessions (individual + batch)', len(sessions) == 2, sessions)
    batch_row = next(s for s in sessions if s['course_name'] == 'ZZ Weekly Course B')
    check('batch session mode is offline (from Batch.mode, overriding student class_type=online)',
          batch_row['mode'] == 'offline', batch_row)

    print('\n4. One-off ClassSession also included')
    friday = monday + dt.timedelta(days=4)
    cs = ClassSession.objects.create(trainer=trainer, course=course_a, date=friday, start_time=dt.time(16, 0),
                                     end_time=dt.time(17, 0), registration=reg_offline, mode='offline', status='scheduled')
    made.append(cs)
    sessions_offline = week_sessions(reg_offline, monday, sunday)
    check('class session found for the offline student', len(sessions_offline) == 1, sessions_offline)
    check('class session mode is its own mode field', sessions_offline[0]['mode'] == 'offline')

    print('\n5. Cancelled occurrence and a session outside the week are excluded')
    occ_cancelled = ScheduleOccurrence.objects.create(rule=rule_ind, trainer=trainer, date=monday + dt.timedelta(days=2),
                                                      start_time=dt.time(10, 0), end_time=dt.time(11, 0), status='cancelled')
    made.append(occ_cancelled)
    occ_next_week = ScheduleOccurrence.objects.create(rule=rule_ind, trainer=trainer, date=sunday + dt.timedelta(days=1),
                                                       start_time=dt.time(10, 0), end_time=dt.time(11, 0), status='scheduled')
    made.append(occ_next_week)
    sessions = week_sessions(reg_online, monday, sunday)
    check('still only 2 sessions (cancelled + next-week excluded)', len(sessions) == 2, len(sessions))

    print('\n6. group_by_day groups and labels correctly, only days with sessions')
    days = group_by_day(sessions)
    check('2 distinct days (Mon + Tue), not 7', len(days) == 2, [d['label'] for d in days])
    check('days are in date order', days[0]['date'] < days[1]['date'])

    print('\n7. End-to-end: management command sends, logs, and is idempotent')
    WeeklyScheduleNotice.objects.filter(registration__in=[reg_online, reg_offline, reg_inactive]).delete()
    mail.outbox.clear()
    call_command('send_weekly_schedule_emails')
    check('email sent to the online student', any('zara.online@example.com' in m.to for m in mail.outbox), [m.to for m in mail.outbox])
    check('email sent to the offline student', any('zane.offline@example.com' in m.to for m in mail.outbox))
    check('inactive student not emailed', not any('zed.inactive@example.com' in m.to for m in mail.outbox))
    online_mail = next(m for m in mail.outbox if 'zara.online@example.com' in m.to)
    check('subject mentions schedule', 'Schedule' in online_mail.subject)
    check('body mentions the online course', 'ZZ Weekly Course A' in online_mail.body)
    notice = WeeklyScheduleNotice.objects.get(registration=reg_online, week_start=monday)
    check('notice recorded with the right session count', notice.session_count == 2, notice.session_count)

    sent_count_before = len(mail.outbox)
    call_command('send_weekly_schedule_emails')
    check('re-running the same week sends nothing new (idempotent)', len(mail.outbox) == sent_count_before, len(mail.outbox))

finally:
    # The management command runs over every real active student in this (local dev) DB too —
    # clear every notice for the test week so a real local run isn't left thinking it already sent.
    WeeklyScheduleNotice.objects.filter(week_start=monday).delete()
    ClassSession.objects.filter(course__code__startswith='ZW').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ Weekly Trainer').delete()
    BatchStudent.objects.filter(batch__name='ZZ Weekly Batch').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ Weekly Trainer').delete()
    Batch.objects.filter(name='ZZ Weekly Batch').delete()
    Registration.objects.filter(last_name__in=('Online', 'Offline', 'Inactive')).delete()
    Course.objects.filter(code__startswith='ZW').delete()
    Trainer.objects.filter(name='ZZ Weekly Trainer').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
