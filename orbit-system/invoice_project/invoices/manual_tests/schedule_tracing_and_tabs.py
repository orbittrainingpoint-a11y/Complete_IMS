import os, sys, re, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client as C
from invoices.models import *
from invoices import schedule_engine as eng

ok = bad = 0
def check(l, c, x=''):
    global ok, bad
    if c: ok += 1; print('  ok  ', l)
    else: bad += 1; print('  FAIL', l, x)

adm = User.objects.filter(is_superuser=True).first()
c = C(); c.force_login(adm); c.defaults['HTTP_HOST'] = 'localhost'
today = eng.dubai_today()
t1 = Trainer.objects.create(name='ZZ Trace A'); t2 = Trainer.objects.create(name='ZZ Trace B')
for t in (t1, t2):
    for d in range(7): TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=dt.time(10), end_time=dt.time(21))
rcs = list(RegistrationCourse.objects.select_related('registration', 'course').order_by('id')[:3])
r1 = eng.create_rule(None, trainer=t1, schedule_type='individual', registration=rcs[0].registration, course=rcs[0].course, start_date=today - dt.timedelta(days=4),
                     weekdays=','.join(str(i) for i in range(7)), start_time=dt.time(10), session_minutes=60, total_minutes=600, teaching_interval=30)
r2 = eng.create_rule(None, trainer=t2, schedule_type='individual', registration=rcs[1].registration, course=rcs[1].course, start_date=today + dt.timedelta(days=1),
                     weekdays='0,1,2,3,4,5,6', start_time=dt.time(12), session_minutes=60, total_minutes=300, teaching_interval=30)
occs = list(r1.occurrences.order_by('date')[:3])
eng.set_occurrence_status(occs[0], 'completed', None); eng.set_occurrence_status(occs[1], 'absent', None)   # occs[2] stays unmarked (past)
eng.pause_rule(r2, today + dt.timedelta(days=3), 'test', '', None, None)
cache.clear()

try:
    print('1. All Schedules page')
    r = c.get('/schedules/?status=all'); body = r.content.decode()
    check('page loads', r.status_code == 200, r.status_code)
    check('both test schedules listed', rcs[0].registration.first_name in body and rcs[1].registration.first_name in body)
    check('session strip dots drawn', body.count('ts-dot') > 10)
    check('completed + absent dots present', 'ts-dot completed' in body and 'ts-dot absent' in body)
    check('"to mark" flag for the unmarked past session', 'to mark' in body)
    for label, url, expect_in, expect_out in [
        ('search by student name', f'/schedules/?status=all&q={rcs[0].registration.first_name}', rcs[0].registration.first_name, None),
        ('search by registration number', f'/schedules/?status=all&q={rcs[0].registration.registration_number}', rcs[0].registration.registration_number, None),
        ('search by trainer', '/schedules/?status=all&q=ZZ+Trace+B', rcs[1].registration.first_name, 'ZZ Trace A'),
        ('filter paused', '/schedules/?status=paused', rcs[1].registration.first_name, None),
        ('filter by trainer', f'/schedules/?status=all&trainer={t1.pk}', 'ZZ Trace A', 'ZZ Trace B'),
        ('sort by progress', '/schedules/?status=all&sort=progress', 'ZZ Trace', None)]:
        rr = c.get(url); b = rr.content.decode(); b = b[b.find('<tbody>'):] if '<tbody>' in b else b
        check(label, rr.status_code == 200 and expect_in in b and (expect_out is None or expect_out not in b), rr.status_code)
    check('CSV export works for admin', 'text/csv' in c.get('/schedules/?status=all&export=1')['Content-Type'])
    print('\n2. Tab bar')
    home = c.get('/trainers/').content.decode()
    for t in ('All Schedules', 'Trainers', 'Daily Board', 'Batches', 'One-off', 'Find Free Trainer', 'Students Waiting', 'To Mark', 'Utilization', 'Create Schedule', 'Trace a student'):
        check(f'tab "{t}" present', t in home)
    check('To Mark badge shows a count', re.search(r'To Mark <span class="ts-badge red">\d+', home) is not None)
    check('Paused badge shows a count', re.search(r'Paused <span class="ts-badge warn">\d+', home) is not None)
    print('\n3. Detail page trace')
    d = c.get(f'/schedules/{r1.pk}/').content.decode()
    check('next / last / attention row', 'Next session' in d and 'Last session' in d and 'not marked' in d)
    check('strip on detail page', 'ts-dot' in d)
    check('back link to all schedules', 'All schedules' in d)
    print('\n4. Permissions')
    u = User.objects.create_user('zz_view', password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': 'sales_executive'})
    cv = C(); cv.force_login(u); cv.defaults['HTTP_HOST'] = 'localhost'
    rv = cv.get('/schedules/?status=all'); check('view-only user can trace schedules', rv.status_code == 200 and 'View only' in rv.content.decode())
    check('view-only user has no CSV export', 'text/csv' not in cv.get('/schedules/?status=all&export=1')['Content-Type'])
    check('view-only user has no To Mark tab', 'To Mark' not in rv.content.decode())
    for url in ('/trainers/', '/trainer-board/', '/batches/', '/sessions/', '/waiting-students/', '/find-trainer/', '/trainer-utilization/', f'/schedules/{r1.pk}/'):
        check(f'view-only can open {url}', cv.get(url).status_code == 200)
finally:
    ScheduleAudit.objects.filter(rule__trainer__name__startswith='ZZ').delete(); ScheduleOccurrence.objects.filter(trainer__name__startswith='ZZ').delete()
    ScheduleRule.objects.filter(trainer__name__startswith='ZZ').delete(); Trainer.objects.filter(name__startswith='ZZ').delete(); User.objects.filter(username__startswith='zz_').delete(); cache.clear()
    print(f'\nRESULT: {ok} passed, {bad} failed')
