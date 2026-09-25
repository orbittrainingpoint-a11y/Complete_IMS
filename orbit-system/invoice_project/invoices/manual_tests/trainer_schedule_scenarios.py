import os, sys, re, datetime as dt, traceback
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
mon = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)   # next Monday

regs = []
for rc in RegistrationCourse.objects.select_related('registration', 'course').order_by('id'):
    if rc.registration_id not in [r.registration_id for r in regs]:
        regs.append(rc)
    if len(regs) == 4: break
print('registrations available:', len(regs))
created = []
try:
    t = Trainer.objects.create(name='ZZ Ahmed', color='#2563eb'); created.append(t)
    for d in range(6): TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=dt.time(10), end_time=dt.time(21))

    def create(client, reg_rc, start='10:00', days=('0', '2', '4'), win='2', total='20', stage='confirm', extra=None):
        data = dict(stage=stage, trainer=t.pk, schedule_type='individual', registration=reg_rc.registration_id, course=reg_rc.course_id,
                    start_date=mon.isoformat(), weekdays=list(days), start_time=start, session_hours=win, total_hours=total, teaching_interval='30')
        data.update(extra or {})
        return client.post('/schedules/new/', data)

    print('\n1. Individual recurring schedule (Mon/Wed/Fri 10:00, 2h window, 20h)')
    r = create(admin, regs[0])
    rule_a = ScheduleRule.objects.filter(trainer=t, registration=regs[0].registration).first()
    check('created and redirected', r.status_code == 302 and rule_a is not None, r.status_code)
    occ = list(rule_a.occurrences.order_by('date'))
    check('10 sessions of 2h generated', len(occ) == 10 and all(mins == 120 for mins in [eng.mins(o.end_time) - eng.mins(o.start_time) for o in occ]), len(occ))
    check('only Mon/Wed/Fri', {o.date.weekday() for o in occ} == {0, 2, 4})
    exp = eng.expected_completion(mon, [0, 2, 4], 600, 120, 1200)
    check('expected completion matches end date', rule_a.end_date == exp['last'] == occ[-1].date, (rule_a.end_date, exp['last']))
    h = eng.rule_hours(rule_a)
    check('hours: required 1200 scheduled 1200 delivered 0 remaining 1200', (h['required'], h['scheduled'], h['delivered'], h['remaining']) == (1200, 1200, 0, 1200), h)

    print('\n2. Rotating individual students overlap (10:30 and 11:00 windows)')
    if len(regs) >= 3:
        r2 = create(admin, regs[1], start='10:30'); r3 = create(admin, regs[2], start='11:00')
        check('second student created without confirmation', r2.status_code == 302 and ScheduleRule.objects.filter(trainer=t, registration=regs[1].registration).exists(), r2.status_code)
        check('third student created', ScheduleRule.objects.filter(trainer=t).count() == 3, r3.status_code)
        day = eng.build_days(t, mon, mon)[0]
        states = {(s['start'], s['state'], s['n']) for s in day['segments']}
        check('capacity shows partial rotation (3 students at 11:00 = full)', any(s['state'] == 'full' for s in day['segments']), states)
        check('10:00-10:30 one student => partial', any(s['start'] == 600 and s['state'] == 'partial' and s['n'] == 1 for s in day['segments']), states)
        check('rotation plan assigns a student per slot', day['rotation'][0]['who'] and day['rotation'][2]['who'], day['rotation'][:3])
        check('free window after windows end (13:00+)', any(f['start'] >= 780 for f in day['free']), day['free'])

    print('\n3. Batch conflicts')
    b1 = Batch.objects.create(name='ZZ Revit B1', start_date=mon, end_date=mon + dt.timedelta(days=28), weekdays='5,6', start_time=dt.time(11), end_time=dt.time(12), capacity=5)
    def batch_rule(client, batch, start, days, total='20', hours='1', trainer=None):
        return client.post('/schedules/new/', dict(stage='confirm', trainer=(trainer or t).pk, schedule_type='batch', batch=batch.pk, start_date=mon.isoformat(),
                                                   weekdays=days, start_time=start, session_hours=hours, total_hours=total, confirm_ok='1'))
    r = batch_rule(admin, b1, '14:00', ['5', '6'])
    br1 = ScheduleRule.objects.filter(batch=b1).first()
    check('batch schedule created', br1 is not None and br1.occurrences.count() == 20, r.status_code)
    b2 = Batch.objects.create(name='ZZ B2', start_date=mon, end_date=mon + dt.timedelta(days=28), weekdays='5,6', start_time=dt.time(11), end_time=dt.time(12), capacity=5)
    r = batch_rule(admin, b2, '14:30', ['5', '6'])
    check('batch vs batch overlap blocked', not ScheduleRule.objects.filter(batch=b2).exists())
    r = admin.post('/schedules/new/', dict(stage='review', trainer=t.pk, schedule_type='batch', batch=b2.pk, start_date=mon.isoformat(), weekdays=['5', '6'],
                                           start_time='14:30', session_hours='1', total_hours='20'))
    check('review shows batch conflict message', b'Batch conflict' in r.content)
    # batch vs individual (individual on saturday over the batch)
    rr = create(admin, regs[0], start='14:15', days=('5',), total='4', win='1')
    check('individual over a batch needs confirmation (blocked without it)', ScheduleRule.objects.filter(trainer=t, registration=regs[0].registration).count() == 1)
    rr = create(admin, regs[0], start='14:15', days=('5',), total='4', win='1', extra={'confirm_ok': '1'})
    check('admin confirms exception -> created', ScheduleRule.objects.filter(trainer=t, registration=regs[0].registration).count() == 2)

    print('\n4. Pause / resume keeps hours, frees slots')
    # complete two sessions first
    o0, o1 = occ[0], occ[1]
    r = admin.post(f'/schedule-sessions/{o0.pk}/action/', dict(action='completed', delivered_hours='2'))
    r = admin.post(f'/schedule-sessions/{o1.pk}/action/', dict(action='absent'))
    rule_a.refresh_from_db(); h = eng.rule_hours(rule_a)
    check('completed delivers 120 min', h['delivered'] == 120, h)
    check('absent auto-added a make-up session (11 scheduled)', rule_a.occurrences.exclude(status__in=('cancelled', 'paused')).count() == 11 and h['unscheduled'] == 0, h)
    pause_from = occ[3].date
    r = admin.post(f'/schedules/{rule_a.pk}/pause/', dict(pause_date=pause_from.isoformat(), reason='Student not attending', notes='n', expected_resume=''))
    rule_a.refresh_from_db(); h2 = eng.rule_hours(rule_a)
    check('rule paused', rule_a.status == 'paused')
    check('future sessions paused (slots freed)', rule_a.occurrences.filter(status='paused').count() > 0)
    check('delivered/remaining unchanged after pause', (h2['delivered'], h2['remaining']) == (120, 1080), h2)
    check('history kept: completed + absent still there', rule_a.occurrences.filter(status='completed').count() == 1 and rule_a.occurrences.filter(status='absent').count() == 1)
    day = eng.build_days(t, pause_from, pause_from)[0]
    who = [e['title'] for e in day['events'] if not e['ghost']]
    check('paused student no longer occupies the calendar', regs[0].registration.first_name not in ' '.join(who), who)
    check('paused shown as ghost (visible, not booked)', any(e['ghost'] and e['status'] == 'paused' for e in day['all_events']))
    r = admin.post(f'/schedules/{rule_a.pk}/resume/', dict(start_date=(pause_from + dt.timedelta(days=14)).isoformat(), confirm_ok='1'))
    rule_a.refresh_from_db(); h3 = eng.rule_hours(rule_a)
    check('resumed -> active with remaining hours rescheduled', rule_a.status == 'active' and h3['unscheduled'] == 0 and h3['remaining'] == 1080, h3)
    check('audit trail has created/paused/resumed', {'created', 'paused', 'resumed'} <= set(rule_a.audit.values_list('action', flat=True)))

    print('\n5. Reschedule occurrence')
    nxt = rule_a.occurrences.filter(status='scheduled').order_by('date').first()
    new_date = nxt.date + dt.timedelta(days=1)
    r = admin.post(f'/schedule-sessions/{nxt.pk}/action/', dict(action='reschedule', new_date=new_date.isoformat(), new_start='16:00', scope='one', confirm_ok='1'))
    nxt.refresh_from_db()
    check('moved this occurrence only', nxt.date == new_date and nxt.start_time == dt.time(16, 0) and nxt.is_exception and nxt.status == 'rescheduled', (nxt.date, nxt.start_time))
    check('rule itself unchanged (start 10:00)', ScheduleRule.objects.get(pk=rule_a.pk).start_time == dt.time(10, 0))

    print('\n6. Edit rule keeps history')
    done_before = rule_a.occurrences.filter(status='completed').count()
    r = admin.post(f'/schedules/{rule_a.pk}/edit/', dict(stage='confirm', effective=(today + dt.timedelta(days=1)).isoformat(), start_time='13:00', session_hours='2', weekdays=['1', '3'],
                                                         total_hours='20', teaching_interval='30', confirm_ok='1', auto_extend='1'))
    rule_a.refresh_from_db()
    check('edit applied', rule_a.weekdays == '1,3' and rule_a.start_time == dt.time(13, 0), (rule_a.weekdays, rule_a.start_time, r.status_code))
    check('completed history intact', rule_a.occurrences.filter(status='completed').count() == done_before)
    fut = rule_a.occurrences.filter(status='scheduled', date__gte=today + dt.timedelta(days=1))
    check('future sessions regenerated on Tue/Thu 13:00', fut.exists() and {o.date.weekday() for o in fut} <= {1, 3})

    print('\n7. Pages render')
    urls = ['/trainers/', f'/trainers/{t.pk}/?view=day&date={mon}', f'/trainers/{t.pk}/?view=week&date={mon}', f'/trainers/{t.pk}/?view=month&date={mon}',
            f'/trainers/{t.pk}/?view=week&date={mon}&q=Ahmed&type=individual&status=scheduled', '/trainer-board/', f'/trainer-board/?mode=list&date={mon}',
            f'/schedules/{rule_a.pk}/', f'/schedules/{rule_a.pk}/edit/', f'/schedules/{br1.pk}/', f'/schedules/new/?trainer={t.pk}&date={mon}&start=660',
            f'/schedules/new/?trainer={t.pk}&registration={regs[0].registration_id}', f'/students/{regs[0].registration_id}/schedule-history/',
            '/trainer-utilization/', '/scheduling/settings/', '/find-trainer/', f'/find-trainer/?date={mon}&start_time=10:00&end_time=11:00&kind=individual',
            '/waiting-students/', '/batches/', f'/batches/{b1.pk}/', f'/batches/{b1.pk}/edit/', '/batches/new/', '/sessions/', '/sessions/new/',
            f'/schedules/preview/?trainer={t.pk}&schedule_type=individual&start_date={mon}&weekdays=0,2&start_time=10:00&session_hours=2&total_hours=10',
            '/api/student-search/?q=' + regs[0].registration.first_name[:3]]
    for u in urls:
        try:
            r = admin.get(u)
            check(f'GET {u[:80]}', r.status_code == 200, r.status_code)
        except Exception as e:
            check(f'GET {u[:80]}', False, repr(e)); traceback.print_exc()

    print('\n8. Permissions')
    sales = User.objects.create_user('zz_sales', password='x'); UserProfile.objects.update_or_create(user=sales, defaults={'role': 'sales_executive'})
    trainer_u = User.objects.create_user('zz_trainer', password='x'); UserProfile.objects.update_or_create(user=trainer_u, defaults={'role': 'accounts'})
    t.user = trainer_u; t.save()
    sc = DjClient(); sc.force_login(sales); sc.defaults['HTTP_HOST'] = 'localhost'
    tc = DjClient(); tc.force_login(trainer_u); tc.defaults['HTTP_HOST'] = 'localhost'
    check('sales can open create form', sc.get('/schedules/new/').status_code == 200)
    r = sc.post(f'/schedules/{rule_a.pk}/pause/', dict(pause_date=today.isoformat(), reason='x'))
    rule_a.refresh_from_db(); check('sales cannot pause', rule_a.status == 'active')
    r = sc.get('/scheduling/settings/'); check('sales cannot open settings', r.status_code == 302)
    nxt2 = rule_a.occurrences.filter(status='scheduled').order_by('date').first()
    r = tc.post(f'/schedule-sessions/{nxt2.pk}/action/', dict(action='completed', delivered_hours='2'))
    nxt2.refresh_from_db(); check('trainer marks own session completed', nxt2.status == 'completed')
    r = tc.post(f'/schedule-sessions/{nxt2.pk}/action/', dict(action='cancelled'))
    check('trainer cannot cancel', ScheduleOccurrence.objects.get(pk=nxt2.pk).status == 'completed')
    other = Trainer.objects.create(name='ZZ Other'); created.append(other)
    check('trainer blocked from another trainer calendar', tc.get(f'/trainers/{other.pk}/').status_code == 302)
    check('trainer opens own calendar', tc.get(f'/trainers/{t.pk}/').status_code == 200)
    # sales confirm needed exception blocked
    b3 = Batch.objects.create(name='ZZ B3', start_date=mon, end_date=mon + dt.timedelta(days=7), weekdays='5', start_time=dt.time(14), end_time=dt.time(15), capacity=3)
    r = sc.post('/schedules/new/', dict(stage='confirm', trainer=t.pk, schedule_type='batch', batch=b3.pk, start_date=mon.isoformat(), weekdays=['5'], start_time='14:00',
                                        session_hours='1', total_hours='2', confirm_ok='1'))
    check('sales cannot approve a conflicting batch', not ScheduleRule.objects.filter(batch=b3).exists())

    print('\n9. Alerts')
    for k, o in enumerate(rule_a.occurrences.filter(status='scheduled').order_by('date')[:3]):
        o.date = today - dt.timedelta(days=5 - k); o.save()
        admin.post(f'/schedule-sessions/{o.pk}/action/', dict(action='absent'))
    items = eng.attention_items()
    check('repeated absence flagged', any(a['rule'].pk == rule_a.pk for a in items['absences']), items['absences'])
finally:
    print('\ncleanup')
    ScheduleAudit.objects.filter(rule__trainer__name__startswith='ZZ').delete()
    ScheduleOccurrence.objects.filter(trainer__name__startswith='ZZ').delete()
    ScheduleRule.objects.filter(trainer__name__startswith='ZZ').delete()
    Batch.objects.filter(name__startswith='ZZ').delete()
    Trainer.objects.filter(name__startswith='ZZ').delete()
    User.objects.filter(username__startswith='zz_').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
