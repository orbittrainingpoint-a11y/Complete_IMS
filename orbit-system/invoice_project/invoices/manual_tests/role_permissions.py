import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as C
from invoices.models import *

t = Trainer.objects.create(name='ZZ Perm Trainer')
for d in range(6): TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=dt.time(10), end_time=dt.time(21))
users = {}
for role in ('admin', 'sales_manager', 'sales_executive', 'accounts'):
    u = User.objects.create_user('zz_' + role, password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': role}); users[role] = u
ok = bad = 0
def check(l, c, x=''):
    global ok, bad
    if c: ok += 1; print('  ok  ', l)
    else: bad += 1; print('  FAIL', l, x)
mon = dt.date.today() + dt.timedelta(days=(7 - dt.date.today().weekday()))
try:
    for role, u in users.items():
        c = C(); c.force_login(u); c.defaults['HTTP_HOST'] = 'localhost'
        edit = role in ('admin', 'sales_manager')
        print(f'\n{role} (edit={edit})')
        home = c.get('/trainers/').content.decode()
        check('sidebar shows Trainers & Batches', 'Trainers &amp; Batches' in home)
        for url in ('/trainers/', f'/trainers/{t.pk}/', f'/trainers/{t.pk}/?view=month', '/trainer-board/', '/batches/', '/sessions/', '/waiting-students/', '/find-trainer/', '/trainer-utilization/'):
            r = c.get(url); check(f'can VIEW {url}', r.status_code == 200, r.status_code)
        page = c.get(f'/trainers/{t.pk}/?view=day').content.decode()
        check('Create/Add buttons ' + ('shown' if edit else 'hidden'), ('Create Schedule' in page) == edit)
        check('settings page ' + ('open' if role == 'admin' else 'blocked'), (c.get('/scheduling/settings/').status_code == 200) == (role == 'admin'))
        r = c.get('/schedules/new/'); check('create form ' + ('open' if edit else 'blocked'), (r.status_code == 200) == edit, r.status_code)
        r = c.post('/trainers/new/', dict(name='ZZ Hacker', wd_0='1', ws_0='10:00', we_0='21:00'))
        check('add trainer ' + ('allowed' if edit else 'blocked'), Trainer.objects.filter(name='ZZ Hacker').exists() == edit)
        Trainer.objects.filter(name='ZZ Hacker').delete()
        r = c.post(f'/trainers/{t.pk}/leave/add/', dict(date_from=mon.isoformat(), date_to=mon.isoformat()))
        check('add leave ' + ('allowed' if edit else 'blocked'), TrainerLeave.objects.filter(trainer=t).exists() == edit)
        TrainerLeave.objects.filter(trainer=t).delete()
        r = c.get('/api/student-search/?q=ab'); check('student search ' + ('open' if edit else 'blocked'), (r.status_code == 200) == edit, r.status_code)
finally:
    Trainer.objects.filter(name__startswith='ZZ').delete(); User.objects.filter(username__startswith='zz_').delete()
    print(f'\nRESULT: {ok} passed, {bad} failed')
