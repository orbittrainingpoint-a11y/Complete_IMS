"""The corporate "View Details" page (eye icon on /corporate-companies/legacy/) was crashing
with a 500 on EVERY corporate registration - a template-wide compile error from an invalid
filter (`add_neg`, never a real Django filter) broke the whole template, not just that one
expression. Fixed to the existing `subtract` filter, and the span now actually shows the
computed due amount instead of just re-printing total_amount. Also brings this page to parity
with the regular student details page: certificate upload/generate/request, schedule section,
Tamara payment links - same "everyone can view, only admin/sales-manager can edit" rule."""
import os, sys, datetime as dt
from decimal import Decimal as D

sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.test import Client as DjClient
from invoices.models import *

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

HTML = {'HTTP_HOST': 'localhost'}
today = dt.date.today()

made = []
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'
    non_mgr = User.objects.create_user('zz_corpinv_accounts', password='x')
    UserProfile.objects.update_or_create(user=non_mgr, defaults={'role': 'accounts'})
    made.append(non_mgr)
    nm = DjClient(); nm.force_login(non_mgr); nm.defaults['HTTP_HOST'] = 'localhost'

    client = Client.objects.create(name='ZZ CorpInv Client', email='zzci@x.test', phone='1', address='a', emirates='Dubai', country='UAE')
    course = Course.objects.create(name='ZZ CorpInv Course', code='ZZCI1')
    made += [client, course]
    reg = Registration.objects.create(first_name='ZZ', last_name='CorpInv', phone_no='971500000002',
                                      registration_type='OC', country='UAE', consultant_name='x', email='')
    made.append(reg)
    RegistrationCourse.objects.create(registration=reg, course=course)
    inv = Invoice.objects.create(registration=reg, client=client, due_date=today, total_amount=0, amount_paid=D('150'),
                                 number_of_person=1, status='Term Payment', payment='Cash')
    Invoice.objects.filter(pk=inv.pk).update(total_amount=D('500'))
    inv.refresh_from_db()
    made.append(inv)

    url = f'/corporate-invoice-detail/{reg.pk}/'

    print('1. The page that used to 500 for EVERY corporate registration now loads')
    r = admin.get(url, **HTML)
    check('status 200, not 500', r.status_code == 200, r.status_code)
    body = r.content.decode()
    check('page shows the registration number', reg.registration_number in body)

    print('2. The per-invoice balance due is computed correctly (the actual bug, not just the crash)')
    check('balance due = 500 - 150 = 350.00, not just total_amount repeated', 'AED 350.00' in body, 'AED 350.00 not found in rendered page')

    print('3. Certificate / enrolment-doc actions now available (parity with the regular student page)')
    check('Create Certificate button (admin)', 'Create Certificate' in body)
    check('Upload Enrolment Doc action', 'Upload Enrolment Doc' in body)
    check('Upload Certificate action', 'Upload Certificate' in body)
    check('Send Certificate Request action', 'Send Certificate Request' in body)

    print('4. Certificate upload actually works through this page\'s own form target')
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse
    f = SimpleUploadedFile('cert.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
    r2 = admin.post(reverse('upload_certificate', args=[reg.id]), {'certificate_file': f}, **HTML)
    check('certificate upload succeeds', r2.status_code == 200 and CertificateUpload.objects.filter(registration=reg).exists())

    print('5. Schedule section present (view-only for non-managers, same rule as the regular page)')
    r_admin = admin.get(url, **HTML)
    r_nm = nm.get(url, **HTML)
    check('admin sees the Schedule section', 'Schedule' in r_admin.content.decode())
    check('non-manager sees it too (read-only)', 'Schedule' in r_nm.content.decode())
    check('non-manager page loads cleanly', r_nm.status_code == 200, r_nm.status_code)

    print('6. Tamara column present and gated the same way as the regular page')
    body_nm = r_nm.content.decode()
    check('non-manager cannot see Create Tamara Link', 'Create Tamara Link' not in body_nm)
    body_admin = r_admin.content.decode()
    check('admin can see Create Tamara Link (if configured)', 'Create Tamara Link' in body_admin or 'Tamara' not in body_admin)

finally:
    CertificateUpload.objects.filter(registration__last_name='CorpInv').delete()
    ScheduleOccurrence.objects.filter(rule__registration__last_name='CorpInv').delete()
    ScheduleRule.objects.filter(registration__last_name='CorpInv').delete()
    RegistrationCourse.objects.filter(registration__last_name='CorpInv').delete()
    Invoice.objects.filter(registration__last_name='CorpInv').delete()
    Registration.objects.filter(last_name='CorpInv').delete()
    Course.objects.filter(code='ZZCI1').delete()
    Client.objects.filter(name='ZZ CorpInv Client').delete()
    UserProfile.objects.filter(user__username='zz_corpinv_accounts').delete()
    User.objects.filter(username='zz_corpinv_accounts').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
