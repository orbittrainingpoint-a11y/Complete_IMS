"""Per-day time overrides: a student or batch taking different timing on different days
(e.g. Mon 10:00, Wed 14:00, Fri 16:00) instead of one shared time for every day. Covers the
parse/format helpers, plan_occurrences' day_times param, the full create-schedule HTTP flow
for both individual and batch, that make-up sessions (after absence) keep using each day's
own time, that editing/resuming with the plain single-time form cleanly resets to one time
rather than silently leaving stale per-day overrides, and that the ordinary "same time every
day" case still stores nothing in weekday_times (unchanged display/behavior)."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *
from invoices import schedule_engine as eng

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = dt.date.today()
mon = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)  # next Monday, clear of today's own data

made = []
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

    print('1. parse_day_times / format_day_times round-trip')
    s = eng.format_day_times({0: 600, 2: 840, 4: 960})
    check('formats as weekday:HHMM pairs', s == '0:1000,2:1400,4:1600', s)
    back = eng.parse_day_times(s)
    check('parses back to the same map', back == {0: 600, 2: 840, 4: 960}, back)
    check('blank string -> empty map (the no-override default)', eng.parse_day_times('') == {})
    check('garbage is skipped, not raised', eng.parse_day_times('not valid,9:9999,2:1400') == {2: 840})

    print('\n2. plan_occurrences: day_times overrides win, omitted days fall back to start_min')
    rows = eng.plan_occurrences(mon, [0, 2, 4], 600, 120, 360, day_times={2: 840})  # Wed at 14:00, others at 10:00
    check('3 sessions planned', len(rows) == 3, rows)
    by_day = {d.weekday(): s for d, s, e in rows}
    check('Monday uses the shared start_min (10:00)', by_day[0] == 600, by_day)
    check('Wednesday uses its own override (14:00)', by_day[2] == 840, by_day)
    check('Friday (not in the override map) falls back to start_min too', by_day[4] == 600, by_day)
    check('day_times=None behaves exactly like before (no crash, same as omitted)',
          eng.plan_occurrences(mon, [0], 600, 120, 120) == eng.plan_occurrences(mon, [0], 600, 120, 120, day_times=None))

    print('\n3. Full create-schedule flow (individual): different time per day, end to end')
    course = Course.objects.create(name='ZZ DayTime Course', code='ZZDT1')
    trainer = Trainer.objects.create(name='ZZ DayTime Trainer')
    made += [course, trainer]
    reg = Registration.objects.create(first_name='ZZ', last_name='DayTime', phone_no='1', email='zzdt@x.test',
                                      country='UAE', consultant_name='x', student_status='active')
    made.append(reg)
    RegistrationCourse.objects.create(registration=reg, course=course)

    def submit(stage, extra):
        data = {'stage': stage, 'trainer': trainer.pk, 'schedule_type': 'individual', 'registration': reg.pk,
                'course': course.pk, 'start_date': mon.isoformat(), 'weekdays': ['0', '2', '4'],
                'start_time': '10:00', 'time_0': '10:00', 'time_2': '14:00', 'time_4': '16:00',
                'session_hours': '2', 'total_hours': '12', 'teaching_interval': '30', 'confirm_ok': '1'}
        data.update(extra)
        return admin.post('/schedules/new/', data, **HTML)

    r = submit('confirm', {})
    check('schedule created (redirect)', r.status_code == 302, r.status_code)
    rule = ScheduleRule.objects.filter(trainer=trainer, registration=reg).first()
    made.append(rule)
    check('rule exists', rule is not None)
    check('weekday_times stores the two days that differ from the representative start_time',
          rule.weekday_times in ('2:1400,4:1600',), rule.weekday_times)
    check('start_time is the earliest day\'s time (Monday 10:00)', rule.start_time == dt.time(10, 0), rule.start_time)
    occs = {o.date.weekday(): o.start_time for o in rule.occurrences.all()}
    check('Monday occurrence really starts at 10:00', occs.get(0) == dt.time(10, 0), occs)
    check('Wednesday occurrence really starts at 14:00', occs.get(2) == dt.time(14, 0), occs)
    check('Friday occurrence really starts at 16:00', occs.get(4) == dt.time(16, 0), occs)
    check('has_day_times is true', rule.has_day_times is True)
    check('day_times_display shows each day with its own time',
          rule.day_times_display() == 'Mon 10:00, Wed 14:00, Fri 16:00', rule.day_times_display())

    print('\n4. Make-up session after an absence keeps using that weekday\'s own time')
    occ_wed = rule.occurrences.filter(date__week_day=4).first()  # Django week_day: Wed=4 (Sun=1)
    if not occ_wed:
        occ_wed = next(o for o in rule.occurrences.all() if o.date.weekday() == 2)
    eng.set_occurrence_status(occ_wed, 'absent', su)
    new_occs = {o.date.weekday(): o.start_time for o in rule.occurrences.exclude(pk=occ_wed.pk)}
    # Whatever day the make-up landed on, it must carry THAT day's own time, not a copy of
    # Wednesday's old 14:00 or a generic fallback.
    makeups_ok = all(new_occs[wd] == (dt.time(14, 0) if wd == 2 else dt.time(16, 0) if wd == 4 else dt.time(10, 0))
                    for wd in new_occs)
    check('every occurrence (incl. any new make-up) still has its own weekday\'s correct time',
          makeups_ok, new_occs)

    print('\n5. Editing via the plain single-time form clears the per-day overrides (no stale mix)')
    r = admin.post(f'/schedules/{rule.pk}/edit/', {
        'stage': 'confirm', 'effective': mon.isoformat(), 'weekdays': ['0', '2', '4'], 'start_time': '11:00',
        'session_hours': '2', 'total_hours': '12', 'teaching_interval': '30', 'trainer': trainer.pk,
        'confirm_ok': '1',
    }, **HTML)
    rule.refresh_from_db()
    check('weekday_times cleared by the single-time edit', rule.weekday_times == '', rule.weekday_times)
    check('rule start_time updated to the new single time', rule.start_time == dt.time(11, 0), rule.start_time)
    fresh_occs = {o.start_time for o in rule.occurrences.filter(status='scheduled')}
    check('every remaining scheduled occurrence now uses the one new time', fresh_occs <= {dt.time(11, 0)}, fresh_occs)

    print('\n6. Ordinary "same time every day" submission stores nothing in weekday_times (unchanged behavior)')
    reg2 = Registration.objects.create(first_name='ZZ', last_name='DayTime2', phone_no='2', email='zzdt2@x.test',
                                       country='UAE', consultant_name='x', student_status='active')
    made.append(reg2)
    RegistrationCourse.objects.create(registration=reg2, course=course)
    r = admin.post('/schedules/new/', {
        'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual', 'registration': reg2.pk,
        'course': course.pk, 'start_date': mon.isoformat(), 'weekdays': ['0', '2', '4'], 'start_time': '10:00',
        'session_hours': '2', 'total_hours': '12', 'teaching_interval': '30', 'confirm_ok': '1',
    }, **HTML)
    rule2 = ScheduleRule.objects.filter(trainer=trainer, registration=reg2).first()
    made.append(rule2)
    check('plain same-time submission -> weekday_times stays blank', rule2 is not None and rule2.weekday_times == '', rule2 and rule2.weekday_times)
    check('has_day_times is false -> old "Days" + "Start time" display, not the new combined one', rule2.has_day_times is False)

    print('\n7. Batch schedule with different times per day')
    batch = Batch.objects.create(name='ZZ DayTime Batch', course=course, trainer=trainer,
                                 start_date=mon, end_date=mon + dt.timedelta(days=60),
                                 weekdays='0,2', start_time=dt.time(10, 0), end_time=dt.time(12, 0), mode='offline')
    made.append(batch)
    r = admin.post('/schedules/new/', {
        'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'batch', 'batch': batch.pk,
        'start_date': mon.isoformat(), 'weekdays': ['0', '2'], 'start_time': '09:00',
        'time_0': '09:00', 'time_2': '13:00', 'session_hours': '2', 'total_hours': '8', 'teaching_interval': '30',
        'confirm_ok': '1',
    }, **HTML)
    check('batch schedule created', r.status_code == 302, r.status_code)
    brule = ScheduleRule.objects.filter(batch=batch).exclude(status='cancelled').first()
    made.append(brule)
    check('batch rule has the per-day override', brule is not None and brule.weekday_times == '2:1300', brule and brule.weekday_times)
    bocc = {o.date.weekday(): o.start_time for o in brule.occurrences.all()}
    check('batch Monday session at 09:00', bocc.get(0) == dt.time(9, 0), bocc)
    check('batch Wednesday session at 13:00', bocc.get(2) == dt.time(13, 0), bocc)
    check('a second schedule for the SAME batch is still blocked (uniqueness unaffected)',
          admin.post('/schedules/new/', {'stage': 'review', 'trainer': trainer.pk, 'schedule_type': 'batch', 'batch': batch.pk,
                                         'start_date': mon.isoformat(), 'weekdays': ['1'], 'start_time': '09:00',
                                         'session_hours': '2', 'total_hours': '8'}, **HTML).status_code == 200)

finally:
    StudentCheckIn.objects.filter(trainer__name='ZZ DayTime Trainer').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ DayTime Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ DayTime Trainer').delete()
    BatchStudent.objects.filter(batch__name='ZZ DayTime Batch').delete()
    Batch.objects.filter(name='ZZ DayTime Batch').delete()
    Registration.objects.filter(last_name__startswith='DayTime').delete()
    Course.objects.filter(code='ZZDT1').delete()
    Trainer.objects.filter(name='ZZ DayTime Trainer').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
