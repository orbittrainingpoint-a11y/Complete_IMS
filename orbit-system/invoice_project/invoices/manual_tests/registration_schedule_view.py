"""The registration 'View Details' page now shows the student's schedule(s) - visible to
everyone who can open that page, but with a "Manage" link (not an edit control of its own)
that only takes effect on the schedule's own page, where admin/sales-manager gating already
lives. A non-manager sees "View" instead and the page never exposes an edit action directly."""
import os, sys, datetime as dt
from decimal import Decimal as D

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
today = eng.dubai_today()
mon = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)

made = []
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

    non_mgr = User.objects.create_user('zz_regview_accounts', password='x')
    UserProfile.objects.update_or_create(user=non_mgr, defaults={'role': 'accounts'})
    nm = DjClient(); nm.force_login(non_mgr); nm.defaults['HTTP_HOST'] = 'localhost'
    made.append(non_mgr)

    course = Course.objects.create(name='ZZ RegView Course', code='ZZRV1')
    trainer = Trainer.objects.create(name='ZZ RegView Trainer')
    client = Client.objects.create(name='ZZ RegView Client', email='zzrv@x.test', phone='1', address='a', emirates='Dubai', country='UAE')
    made += [course, trainer, client]
    reg = Registration.objects.create(first_name='ZZ', last_name='RegView', phone_no='1', email='zzrv@x.test',
                                      country='UAE', consultant_name='x', student_status='active')
    made.append(reg)
    RegistrationCourse.objects.create(registration=reg, course=course)
    inv = Invoice.objects.create(registration=reg, client=client, due_date=today, total_amount=0,
                                 amount_paid=1000, number_of_person=1, status='Full Payment', payment='Cash')
    Invoice.objects.filter(pk=inv.pk).update(total_amount=1000)
    made.append(inv)

    url = f'/registrations/{reg.pk}/invoice-detail/' if False else None
    # Find the real URL by reversing the name instead of guessing the path.
    from django.urls import reverse
    url = reverse('registration_invoice_detail', args=[reg.pk])

    print('1. No schedule yet')
    r = admin.get(url, **HTML)
    check('admin page loads', r.status_code == 200, r.status_code)
    check('shows "No schedule yet"', b'No schedule yet' in r.content)
    check('admin sees a create-schedule link', b'Create one.' in r.content)
    r_nm = nm.get(url, **HTML)
    check('non-manager page loads too', r_nm.status_code == 200, r_nm.status_code)
    check('non-manager does NOT see a create-schedule link', b'Create one.' not in r_nm.content)

    print('\n2. With an active schedule')
    r = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                       'registration': reg.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                       'weekdays': ['0'], 'start_time': '10:00', 'session_hours': '2',
                                       'total_hours': '12', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule = ScheduleRule.objects.filter(trainer=trainer, registration=reg).first()
    made.append(rule)
    check('schedule created', rule is not None)

    r = admin.get(url, **HTML)
    check('admin page shows the course name', course.name.encode() in r.content)
    check('admin page shows the trainer name', trainer.name.encode() in r.content)
    check('admin sees "Manage" (can edit on the schedule page)', b'>Manage<' in r.content, None)

    r_nm = nm.get(url, **HTML)
    check('non-manager also sees the schedule', course.name.encode() in r_nm.content)
    check('non-manager sees "View" not "Manage"', b'>View<' in r_nm.content and b'>Manage<' not in r_nm.content)

    print('\n3. The actual edit action on the linked schedule page is still gated (regression)')
    r = nm.post(f'/schedules/{rule.pk}/pause/', {'pause_date': today.isoformat(), 'reason': 'test'}, **HTML)
    rule.refresh_from_db()
    check('non-manager cannot actually pause the schedule from its own page', rule.status == 'active', rule.status)

finally:
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ RegView Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ RegView Trainer').delete()
    Invoice.objects.filter(registration__last_name='RegView').delete()
    RegistrationCourse.objects.filter(registration__last_name='RegView').delete()
    Registration.objects.filter(last_name='RegView').delete()
    Course.objects.filter(code='ZZRV1').delete()
    Trainer.objects.filter(name='ZZ RegView Trainer').delete()
    Client.objects.filter(name='ZZ RegView Client').delete()
    UserProfile.objects.filter(user__username='zz_regview_accounts').delete()
    User.objects.filter(username='zz_regview_accounts').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
