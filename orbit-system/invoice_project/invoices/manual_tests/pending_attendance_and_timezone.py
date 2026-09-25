import os, sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as C
from invoices.models import *
from invoices import schedule_engine as eng
c = C(); c.force_login(User.objects.filter(is_superuser=True).first()); c.defaults['HTTP_HOST'] = 'localhost'
print('dubai today:', eng.dubai_today(), '| utc today:', dt.datetime.utcnow().date(), '| now(min):', eng.dubai_now_minutes())
t = Trainer.objects.create(name='ZZ Pend')
for d in range(7): TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=dt.time(10), end_time=dt.time(21))
reg = RegistrationCourse.objects.select_related('registration', 'course').first()
past = eng.dubai_today() - dt.timedelta(days=3)
rule = eng.create_rule(None, trainer=t, schedule_type='individual', registration=reg.registration, course=reg.course, start_date=past, weekdays=','.join(str(i) for i in range(7)),
                       start_time=dt.time(10), session_minutes=60, total_minutes=300, teaching_interval=30)
pend = eng.pending_attendance(t)
print('pending past sessions:', len(pend), '(expect >= 3)')
r = c.get(f'/schedule-pending/?trainer={t.pk}'); print('pending page', r.status_code, b'waiting for attendance' in r.content)
ids = [o.pk for o in pend]
r = c.post('/schedule-pending/bulk/', dict(action='completed', occ=ids)); print('bulk mark', r.status_code)
print('after bulk pending:', len(eng.pending_attendance(t)), '| delivered:', eng.rule_hours(ScheduleRule.objects.get(pk=rule.pk))['delivered'])
r = c.get(f'/trainers/{t.pk}/?view=week'); print('calendar', r.status_code)
# pause with a past date must not touch past sessions
eng.pause_rule(rule, past, 'test', '', None, None)
print('past statuses untouched by pause:', set(rule.occurrences.filter(date__lt=eng.dubai_today()).values_list('status', flat=True)))
# accounts-role user cannot use student search
u = User.objects.create_user('zz_acc', password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': 'accounts'})
ca = C(); ca.force_login(u); ca.defaults['HTTP_HOST'] = 'localhost'
print('accounts student-search:', ca.get('/api/student-search/?q=ab').status_code, '| preview:', ca.get('/schedules/preview/').status_code)
ScheduleAudit.objects.filter(rule=rule).delete(); ScheduleOccurrence.objects.filter(rule=rule).delete(); rule.delete(); t.delete(); u.delete()
print('cleaned')
