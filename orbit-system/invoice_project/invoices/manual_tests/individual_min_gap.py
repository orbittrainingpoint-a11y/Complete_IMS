"""Two individual students on the same trainer may still overlap (that's the whole point of
rotation) but must not start within `min_individual_gap_minutes` (default 30) of each other -
starting two students at the exact same instant isn't a real rotation slot, the trainer can't
be in two places at once. Covers the engine check directly and the create-schedule HTTP flow."""
import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from invoices.models import *
from django.test import Client as DjClient
from invoices import schedule_engine as eng

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

su = User.objects.filter(is_superuser=True).first()
admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'
today = dt.date.today()
mon = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)

users = {}
for role in ('sales_manager', 'sales_executive'):
    u = User.objects.create_user('zz_gap_' + role, password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': role}); users[role] = u
def cl(role):
    c = DjClient(); c.force_login(users[role]); c.defaults['HTTP_HOST'] = 'localhost'; return c

regs = []
for rc in RegistrationCourse.objects.select_related('registration', 'course').order_by('id'):
    if rc.registration_id not in [r.registration_id for r in regs]:
        regs.append(rc)
    if len(regs) == 4:
        break

saved_setting = None
created = []
try:
    t = Trainer.objects.create(name='ZZ Gap Trainer', color='#2563eb'); created.append(t)
    for d in range(7): TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=dt.time(9), end_time=dt.time(21))

    setting = eng.settings_obj()
    saved_setting = setting.min_individual_gap_minutes
    setting.min_individual_gap_minutes = 30
    setting.save()

    def create(client, reg_rc, start='10:00', extra=None):
        data = dict(stage='confirm', trainer=t.pk, schedule_type='individual', registration=reg_rc.registration_id,
                    course=reg_rc.course_id, start_date=mon.isoformat(), weekdays=['0'], start_time=start,
                    session_hours='2', total_hours='20', teaching_interval='30')
        data.update(extra or {})
        return client.post('/schedules/new/', data)

    def review(client, reg_rc, start):
        return client.post('/schedules/new/', dict(stage='review', trainer=t.pk, schedule_type='individual',
            registration=reg_rc.registration_id, course=reg_rc.course_id, start_date=mon.isoformat(), weekdays=['0'],
            start_time=start, session_hours='2', total_hours='20', teaching_interval='30'))

    print('1. Engine-level: check_conflicts direct')
    base = ScheduleRule.objects.create(trainer=t, schedule_type='individual', registration=regs[0].registration,
                                       course=regs[0].course, start_date=mon, weekdays='0', start_time=dt.time(10, 0),
                                       session_minutes=120, teaching_interval=30, total_minutes=1200)
    eng._generate(base, mon, 1200, su)
    created.append(base)

    def res_for(start_time_str):
        h, m = (int(x) for x in start_time_str.split(':'))
        return eng.check_conflicts(t, [(mon, h * 60 + m, h * 60 + m + 120)], 'individual', registration=regs[1].registration)

    r = res_for('10:00')
    check('exact same start time -> blocking error', bool(r['errors']) and not r['confirms'], r)
    check('error message explains the gap requirement', r['errors'] and 'at least 30 minutes' in r['errors'][0], r['errors'])

    r = res_for('10:15')
    check('15 minutes apart -> still blocked (below the 30-min minimum)', bool(r['errors']), r)

    r = res_for('10:29')
    check('29 minutes apart -> still blocked', bool(r['errors']), r)

    r = res_for('10:30')
    check('exactly 30 minutes apart -> allowed (info, no error/confirm)', not r['errors'] and not r['confirms'] and bool(r['info']), r)

    r = res_for('10:31')
    check('31 minutes apart -> allowed', not r['errors'] and bool(r['info']), r)

    r = res_for('13:00')
    check('no time overlap at all -> no conflict noise', not r['errors'] and not r['confirms'] and not r['info'], r)

    print('\n2. HTTP create flow')
    # regs[0] already has "base" for this course from step 1 - reusing it here would trip the
    # unrelated "student already has a schedule for this course" confirms notice, which is not
    # what this section tests. regs[1]/regs[2] start clean.
    r1 = create(admin, regs[1], start='11:00')
    n_before = ScheduleRule.objects.filter(trainer=t, schedule_type='individual').count()
    check('setup: regs[1] booked at 11:00 without incident', n_before == 2, n_before)  # base + r1

    r2 = create(admin, regs[2], start='11:00')  # exact same time as regs[1]'s 11:00 rule
    n_after = ScheduleRule.objects.filter(trainer=t, schedule_type='individual').count()
    check('same-time booking NOT created (blocked without override)', n_after == n_before, (n_before, n_after))

    rv = review(admin, regs[2], '11:00')
    check('review stage surfaces the too-close conflict', b'at least 30 minutes' in rv.content, rv.content[:400])

    r3 = create(admin, regs[2], start='11:00', extra={'override': '1'})
    n_override = ScheduleRule.objects.filter(trainer=t, schedule_type='individual').count()
    check('admin override lets it through', n_override == n_before + 1, (n_before, n_override))
    check('override was actually recorded in the audit trail', ScheduleAudit.objects.filter(
        rule__trainer=t, action='override').exists())

    print('\n3. Non-admin cannot override')
    r4 = cl('sales_manager').post('/schedules/new/', dict(stage='confirm', trainer=t.pk, schedule_type='individual',
        registration=regs[3].registration_id, course=regs[3].course_id, start_date=mon.isoformat(), weekdays=['0'],
        start_time='11:00', session_hours='2', total_hours='20', teaching_interval='30', override='1'))
    n_sm = ScheduleRule.objects.filter(trainer=t, schedule_type='individual').count()
    check('sales_manager\'s "override=1" is ignored (still blocked)', n_sm == n_override, (n_override, n_sm))

    print('\n4. Setting is configurable and respected')
    admin.post('/scheduling/settings/', dict(default_interval='30', max_concurrent_individuals='3',
        min_individual_gap_minutes='45', batch_batch_policy='block', batch_individual_policy='confirm',
        working_hours_policy='confirm', low_hours_threshold='120', absence_alert_count='3'))
    setting.refresh_from_db()
    check('setting saved as 45', setting.min_individual_gap_minutes == 45)
    # Isolated at 17:00, away from the 10:00/11:00 cluster above, so this only tests the setting.
    isolated = ScheduleRule.objects.create(trainer=t, schedule_type='individual', registration=regs[3].registration,
                                           course=regs[3].course, start_date=mon, weekdays='0', start_time=dt.time(17, 0),
                                           session_minutes=60, teaching_interval=30, total_minutes=600)
    eng._generate(isolated, mon, 600, su)
    created.append(isolated)

    def res_isolated(start_time_str):
        h, m = (int(x) for x in start_time_str.split(':'))
        return eng.check_conflicts(t, [(mon, h * 60 + m, h * 60 + m + 60)], 'individual')

    r = res_isolated('17:44')
    check('44 minutes apart now blocked under the new 45-min setting', bool(r['errors']), r)
    r = res_isolated('17:45')
    check('45 minutes apart now allowed', not r['errors'], r)

    print('\n5. Batch policies unaffected (regression)')
    b1 = Batch.objects.create(name='ZZ Gap Batch A', trainer=t, start_date=mon, end_date=mon + dt.timedelta(days=28),
                              weekdays='0', start_time=dt.time(15), end_time=dt.time(17), capacity=5)
    b2 = Batch.objects.create(name='ZZ Gap Batch B', trainer=t, start_date=mon, end_date=mon + dt.timedelta(days=28),
                              weekdays='0', start_time=dt.time(15), end_time=dt.time(17), capacity=5)
    created += [b1, b2]
    admin.post('/schedules/new/', dict(stage='confirm', trainer=t.pk, schedule_type='batch', batch=b1.pk,
                                       start_date=mon.isoformat(), weekdays=['0'], start_time='15:00', session_hours='2', total_hours='20'))
    admin.post('/schedules/new/', dict(stage='confirm', trainer=t.pk, schedule_type='batch', batch=b2.pk,
                                       start_date=mon.isoformat(), weekdays=['0'], start_time='15:00', session_hours='2', total_hours='20'))
    check('batch vs batch still blocked exactly as before', not ScheduleRule.objects.filter(batch=b2).exists())

finally:
    ScheduleAudit.objects.filter(rule__trainer__name='ZZ Gap Trainer').delete()
    ScheduleOccurrence.objects.filter(trainer__name='ZZ Gap Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ Gap Trainer').delete()
    Batch.objects.filter(name__startswith='ZZ Gap Batch').delete()
    TrainerWorkingHours.objects.filter(trainer__name='ZZ Gap Trainer').delete()
    Trainer.objects.filter(name='ZZ Gap Trainer').delete()
    User.objects.filter(username__startswith='zz_gap_').delete()
    if saved_setting is not None:
        s = eng.settings_obj(); s.min_individual_gap_minutes = saved_setting; s.save()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
