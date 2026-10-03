"""Student ID card generation: verify info, upload a photo, composite onto the official
template, view/download/print. Covers the compositor directly (layout math, missing data,
display overrides) and the full HTTP flow (permissions, validation, regenerate, editing what's
printed on the card without touching the registration)."""
import os, sys, datetime as dt
from io import BytesIO
sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client as DjClient
from PIL import Image
from invoices.models import *
from invoices import id_cards as compositor
import invoices.middleware as mw
mw._is_after_dubai_curfew = lambda: False

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

su = User.objects.filter(is_superuser=True).first()
admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

users = {}
for role in ('sales_manager', 'sales_executive'):
    u = User.objects.create_user('zz_idc_' + role, password='x'); UserProfile.objects.update_or_create(user=u, defaults={'role': role}); users[role] = u
def cl(role):
    c = DjClient(); c.force_login(users[role]); c.defaults['HTTP_HOST'] = 'localhost'; return c

def fake_photo_bytes(size=(300, 300), fmt='JPEG'):
    buf = BytesIO(); Image.new('RGB', size, (180, 160, 140)).save(buf, format=fmt); return buf.getvalue()

def gen(client, reg_id, extra=None, with_photo=True):
    data = {'valid_until': (dt.date.today() + dt.timedelta(days=365)).isoformat()}
    data.update(extra or {})
    if with_photo:
        data['photo'] = SimpleUploadedFile('p.jpg', fake_photo_bytes(), content_type='image/jpeg')
    return client.post(f'/id-cards/{reg_id}/generate/', data)

made = []
try:
    course = Course.objects.create(name='ZZ ID Card Course', code='ZZIDC1')
    made.append(course)
    reg = Registration.objects.create(first_name='Zahra', last_name='ZZTest', phone_no='+971500000000',
                                      email='zahra.zztest@example.com', country='UAE', consultant_name='x',
                                      student_status='active')
    made.append(reg)
    RegistrationCourse.objects.create(registration=reg, course=course)

    print('1. Compositor: layout + missing-data handling')
    card = StudentIDCard(registration=reg, course=course, valid_until=dt.date.today() + dt.timedelta(days=365))
    card.photo.save('t.jpg', ContentFile(fake_photo_bytes()), save=False)
    content, warnings = compositor.generate_card_image(card)
    check('card image produced', content is not None and len(content.read()) > 0)
    content.seek(0)
    out = Image.open(content)
    check('output is the right card size', out.size == (compositor.CARD_W, compositor.CARD_H), out.size)
    check('no warnings when phone/email are present', warnings == [], warnings)

    reg_blank = Registration.objects.create(first_name='NoContact', last_name='ZZTest', phone_no='', email='',
                                            country='UAE', consultant_name='x', student_status='active')
    made.append(reg_blank)
    card2 = StudentIDCard(registration=reg_blank, course=course, valid_until=dt.date.today())
    card2.photo.save('t2.jpg', ContentFile(fake_photo_bytes()), save=False)
    _, warnings2 = compositor.generate_card_image(card2)
    check('missing phone/email -> warnings, not a crash', len(warnings2) == 2, warnings2)

    print('\n2. Compositor: display overrides take priority over the live registration value')
    card3 = StudentIDCard(registration=reg, course=course, valid_until=dt.date.today(),
                          display_name='Zee (preferred)', display_phone='+971 50 OVERRIDE')
    check('name() uses the override', card3.name() == 'Zee (preferred)')
    check('phone() uses the override', card3.phone() == '+971 50 OVERRIDE')
    check('email() falls back to the live value when no override is set', card3.email() == reg.email)

    print('\n3. HTTP flow: list, permissions, generate')
    check('admin can view the ID card list -> 200', admin.get('/id-cards/').status_code == 200)
    for role in ('sales_manager', 'sales_executive'):
        r = cl(role).get('/id-cards/')
        check(f'{role} can view the ID card list -> 200', r.status_code == 200, r.status_code)
    check('anonymous redirected to login', DjClient().get('/id-cards/', HTTP_HOST='localhost').status_code == 302)

    r = cl('sales_executive').get(f'/id-cards/{reg.pk}/generate/')
    check('sales_executive blocked from the generate page', r.status_code == 302)
    page = admin.get(f'/id-cards/{reg.pk}/generate/')
    check('admin sees the generate form', page.status_code == 200 and reg.first_name.encode() in page.content)
    check('form is pre-filled with the live phone/email (editable, not read-only)',
          f'value="{reg.phone_no}"'.encode() in page.content and f'value="{reg.email}"'.encode() in page.content)

    r = gen(admin, reg.pk, {'name': 'Zahra ZZTest'}, with_photo=False)
    check('missing photo on first generation is rejected', r.status_code == 200 and b'upload a photo' in r.content.lower())
    r = gen(admin, reg.pk, {'name': ''})
    check('empty name is rejected', r.status_code == 200 and b'name cannot be empty' in r.content.lower())

    r = gen(admin, reg.pk, {'course': course.pk, 'name': 'Zahra ZZTest', 'phone': reg.phone_no, 'email': reg.email})
    check('generate redirects to the view page', r.status_code == 302 and f'/id-cards/{reg.pk}/' in r.headers.get('Location', ''), r.headers.get('Location'))
    db_card = StudentIDCard.objects.get(registration=reg)
    check('card saved with a photo and a generated image', bool(db_card.photo) and bool(db_card.card_image))
    check('generated_by recorded', db_card.generated_by_id == su.pk)
    check('name/phone/email left unchanged -> stored blank (still tracks the live registration)',
          db_card.display_name == '' and db_card.display_phone == '' and db_card.display_email == '')

    print('\n4. View / download / list reflects the generated card')
    r = admin.get(f'/id-cards/{reg.pk}/')
    check('view page shows the card image', r.status_code == 200 and b'idc-card-img' in r.content)
    r = admin.get(f'/id-cards/{reg.pk}/download/')
    check('download returns the PNG as an attachment', r.status_code == 200 and r['Content-Type'] == 'image/png'
          and 'attachment' in r.get('Content-Disposition', ''))
    listing = admin.get(f'/id-cards/?q={reg.registration_number}').content.decode()
    check('list shows "Generated" for this student', 'Generated' in listing)

    print('\n5. Editing name/phone/email on the card does NOT touch the registration')
    r = gen(admin, reg.pk, {'course': course.pk, 'name': 'Zee Printed Name', 'phone': '+971500000099', 'email': 'printed@example.com'}, with_photo=False)
    check('regenerate with edited info succeeds', r.status_code == 302, r.status_code)
    db_card.refresh_from_db(); reg.refresh_from_db()
    check('card now shows the edited name/phone/email', (db_card.name(), db_card.phone(), db_card.email()) ==
          ('Zee Printed Name', '+971500000099', 'printed@example.com'), (db_card.name(), db_card.phone(), db_card.email()))
    check('registration itself is untouched', reg.first_name == 'Zahra' and reg.phone_no == '+971500000000' and reg.email == 'zahra.zztest@example.com')
    check('generated card file is non-empty', db_card.card_image.size > 1000, db_card.card_image.size)

    print('\n6. Reverting the card fields back to match the registration clears the override')
    r = gen(admin, reg.pk, {'course': course.pk, 'name': 'Zahra ZZTest', 'phone': reg.phone_no, 'email': reg.email}, with_photo=False)
    check('revert succeeds', r.status_code == 302)
    db_card.refresh_from_db()
    check('override cleared -> back to tracking the live registration', db_card.display_name == '' and db_card.display_phone == '' and db_card.display_email == '')

    print('\n7. Regenerate keeps the photo if none is re-uploaded, updates validity')
    new_until = dt.date.today() + dt.timedelta(days=30)
    r = gen(admin, reg.pk, {'course': course.pk, 'name': 'Zahra ZZTest', 'phone': reg.phone_no, 'email': reg.email, 'valid_until': new_until.isoformat()}, with_photo=False)
    check('regenerate without a new photo succeeds', r.status_code == 302, r.status_code)
    db_card.refresh_from_db()
    check('valid_until updated', db_card.valid_until == new_until, db_card.valid_until)

    print('\n8. No course on registration is refused with a clear message')
    reg_nocourse = Registration.objects.create(first_name='NoCourse', last_name='ZZTest', phone_no='1',
                                               email='nc@example.com', country='UAE', consultant_name='x', student_status='active')
    made.append(reg_nocourse)
    r = gen(admin, reg_nocourse.pk, {'name': 'NoCourse ZZTest'})
    check('no course on file -> rejected with a clear message', r.status_code == 200 and b'no course on file' in r.content, r.status_code)

    print('\n9. Viewing before generation redirects to the generate page')
    reg_fresh = Registration.objects.create(first_name='Fresh', last_name='ZZTest', phone_no='1', email='f@example.com',
                                            country='UAE', consultant_name='x', student_status='active')
    made.append(reg_fresh)
    r = admin.get(f'/id-cards/{reg_fresh.pk}/', follow=True)
    check('redirected to generate (no card yet)', f'/id-cards/{reg_fresh.pk}/generate/' in [u for u, c in r.redirect_chain][0] if r.redirect_chain else False)

finally:
    StudentIDCard.objects.filter(registration__last_name='ZZTest').delete()
    RegistrationCourse.objects.filter(registration__last_name='ZZTest').delete()
    Registration.objects.filter(last_name='ZZTest').delete()
    Course.objects.filter(code='ZZIDC1').delete()
    User.objects.filter(username__startswith='zz_idc_').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
