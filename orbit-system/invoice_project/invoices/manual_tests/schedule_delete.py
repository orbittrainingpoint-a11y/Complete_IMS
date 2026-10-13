"""Delete a mistakenly-created schedule — different from Cancel, which keeps everything as
history. Hard delete is admin-only and blocked automatically if anything real happened on it
(a completed occurrence, or a student check-in, which is PROTECTed at the DB level). The
deletion itself is logged to AuditLog, not ScheduleAudit (which would cascade-delete along
with the rule — the point is a record that survives the thing it's about). Covers rule
delete, single-occurrence delete, and one-off ClassSession delete."""
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

made = []
users = {}
for role in ('admin', 'sales_manager'):
    u = User.objects.create_user('zz_del_' + role, password='x')
    UserProfile.objects.update_or_create(user=u, defaults={'role': role})
    users[role] = u
def cl(role):
    c = DjClient(); c.force_login(users[role]); c.defaults['HTTP_HOST'] = 'localhost'; return c

try:
    course = Course.objects.create(name='ZZ Delete Course', code='ZZDL1')
    trainer = Trainer.objects.create(name='ZZ Delete Trainer')
    made += [course, trainer]

    def mk_rule(reg):
        return eng.create_rule(users['admin'], trainer=trainer, schedule_type='individual', registration=reg,
                               course=course, start_date=today, weekdays='0,1,2,3,4,5,6',
                               start_time=dt.time(10, 0), session_minutes=60, total_minutes=120)

    print('1. A manager (not admin) cannot hard-delete -- told to use Cancel instead')
    reg1 = Registration.objects.create(first_name='ZZ', last_name='Del1', phone_no='1', email='zz1@x.test',
                                       country='UAE', consultant_name='x', student_status='active')
    made.append(reg1)
    rule1 = mk_rule(reg1); made.append(rule1)
    r = cl('sales_manager').post(f'/schedules/{rule1.pk}/delete/', {'reason': 'wrong student'}, **HTML)
    check('manager blocked', ScheduleRule.objects.filter(pk=rule1.pk).exists())

    print('\n2. Admin, no reason given -- blocked')
    r = cl('admin').post(f'/schedules/{rule1.pk}/delete/', {}, **HTML)
    check('blocked without a reason', ScheduleRule.objects.filter(pk=rule1.pk).exists())

    print('\n3. Admin, with a reason, no real history -- deleted, occurrences gone too, logged')
    occ_count = rule1.occurrences.count()
    check('rule actually has occurrences to begin with', occ_count > 0, occ_count)
    # Exactly what the real template's delete modal submits: a "next" pointing back at this
    # rule's own detail page (every other action's modal does this, since the page still
    # exists afterward — the bug was copying that pattern onto delete, where it doesn't).
    r = cl('admin').post(f'/schedules/{rule1.pk}/delete/',
                        {'reason': 'created for the wrong student', 'next': f'/schedules/{rule1.pk}/'}, **HTML)
    check('redirects after delete', r.status_code == 302)
    check('rule gone', not ScheduleRule.objects.filter(pk=rule1.pk).exists())
    check('its occurrences gone too (cascade)', not ScheduleOccurrence.objects.filter(rule_id=rule1.pk).exists())
    check('redirect does NOT send the browser back to the now-deleted rule\'s own page',
          r.headers.get('Location') != f'/schedules/{rule1.pk}/', r.headers.get('Location'))
    check('redirect target actually resolves (no 404 after a successful delete)',
          cl('admin').get(r.headers.get('Location'), **HTML).status_code == 200, r.headers.get('Location'))
    log = AuditLog.objects.filter(model_name='ScheduleRule', object_id=str(rule1.pk), action='delete').first()
    check('AuditLog entry survives (not cascaded away with the rule)', log is not None and 'wrong student' in log.changes, log)

    print('\n4. A completed occurrence blocks the delete -- real history is protected')
    reg2 = Registration.objects.create(first_name='ZZ', last_name='Del2', phone_no='2', email='zz2@x.test',
                                       country='UAE', consultant_name='x', student_status='active')
    made.append(reg2)
    rule2 = mk_rule(reg2); made.append(rule2)
    occ2 = rule2.occurrences.first()
    occ2.status, occ2.delivered_minutes = 'completed', 60
    occ2.save()
    r = cl('admin').post(f'/schedules/{rule2.pk}/delete/', {'reason': 'try anyway'}, **HTML)
    check('blocked: rule with a completed session is not deleted', ScheduleRule.objects.filter(pk=rule2.pk).exists())

    print('\n5. A student check-in (PROTECTed) blocks the delete even with nothing "completed"')
    reg3 = Registration.objects.create(first_name='ZZ', last_name='Del3', phone_no='3', email='zz3@x.test',
                                       country='UAE', consultant_name='x', student_status='active')
    made.append(reg3)
    rule3 = mk_rule(reg3); made.append(rule3)
    occ3 = rule3.occurrences.first()  # still 'scheduled', not completed
    checkin = StudentCheckIn.objects.create(registration=reg3, occurrence=occ3, course=course, trainer=trainer,
                                            scheduled_date=occ3.date, scheduled_start=occ3.start_time,
                                            scheduled_end=occ3.end_time, status='awaiting_confirm')
    made.append(checkin)
    r = cl('admin').post(f'/schedules/{rule3.pk}/delete/', {'reason': 'try anyway'}, **HTML)
    check('blocked: a protected check-in stops the delete', ScheduleRule.objects.filter(pk=rule3.pk).exists())
    checkin.delete()  # clean up so the occurrence can be removed in teardown

    print('\n6. Single-occurrence delete: removes just that one session, not the whole rule')
    reg4 = Registration.objects.create(first_name='ZZ', last_name='Del4', phone_no='4', email='zz4@x.test',
                                       country='UAE', consultant_name='x', student_status='active')
    made.append(reg4)
    rule4 = mk_rule(reg4); made.append(rule4)
    occs4 = list(rule4.occurrences.all())
    check('rule4 has multiple occurrences', len(occs4) > 1, len(occs4))
    target = occs4[0]
    r = cl('admin').post(f'/schedule-sessions/{target.pk}/delete/', {'reason': 'duplicate slot'}, **HTML)
    check('that one occurrence is gone', not ScheduleOccurrence.objects.filter(pk=target.pk).exists())
    check('the rest of the schedule is untouched', ScheduleRule.objects.filter(pk=rule4.pk).exists()
          and rule4.occurrences.count() == len(occs4) - 1)

    print('\n7. One-off ClassSession delete')
    cs = ClassSession.objects.create(trainer=trainer, course=course, date=today, start_time=dt.time(14, 0),
                                     end_time=dt.time(15, 0), registration=reg4, status='scheduled')
    made.append(cs)
    r = cl('sales_manager').post(f'/sessions/{cs.pk}/delete/', {'reason': 'try'}, **HTML)
    check('non-admin blocked from deleting a class session', ClassSession.objects.filter(pk=cs.pk).exists())
    r = cl('admin').post(f'/sessions/{cs.pk}/delete/', {'reason': 'duplicate booking'}, **HTML)
    check('admin deletes the one-off session', not ClassSession.objects.filter(pk=cs.pk).exists())

finally:
    StudentCheckIn.objects.filter(trainer__name='ZZ Delete Trainer').delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ Delete Trainer').delete()
    ClassSession.objects.filter(trainer__name='ZZ Delete Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ Delete Trainer').delete()
    AuditLog.objects.filter(model_name__in=('ScheduleRule', 'ScheduleOccurrence', 'ClassSession'),
                            changes__icontains='mistaken').delete()
    Registration.objects.filter(last_name__startswith='Del').delete()
    Course.objects.filter(code='ZZDL1').delete()
    Trainer.objects.filter(name='ZZ Delete Trainer').delete()
    User.objects.filter(username__startswith='zz_del_').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
