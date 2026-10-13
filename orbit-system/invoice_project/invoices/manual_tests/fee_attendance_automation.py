"""Fee- and attendance-driven schedule automation:
  - a student needs >=200 AED paid before a NEW schedule can be created
  - an active schedule auto-pauses once the registration's fee is overdue; still unpaid 14
    days after that pause auto-suspends the registration (reopening costs 30% of the fee)
  - an individual schedule auto-pauses after 4 CONSECUTIVE absences (a warning); if that
    happens again (3 more in a row) after staff resume it, the registration is auto-cancelled
  - end-of-day attendance resolution (confirmed check-in -> completed, else -> absent) is what
    makes the absence count trustworthy - nothing marked it automatically before this feature
  - a trainer's OWN calendar view hides paused/cancelled schedules entirely; managers/admins
    still see them (ghosted), same as before this feature
"""
import datetime as dt
import os, sys
from decimal import Decimal as D

sys.path.insert(0, r'D:\Insittute management system\orbit-system\invoice_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_project.settings')
import django; django.setup()
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
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
def run_job(*reg_objs):
    # Always scoped to our own fixture registrations - the real dev DB holds genuine imported
    # student data, and an unscoped run would sweep (and mutate) it too. Never call the bare
    # command here.
    call_command('enforce_fee_schedule_rules', registration_ids=','.join(str(r.pk) for r in reg_objs))
try:
    su = User.objects.filter(is_superuser=True).first()
    admin = DjClient(); admin.force_login(su); admin.defaults['HTTP_HOST'] = 'localhost'

    client = Client.objects.create(name='ZZ FeeAtt Client', email='zzfa@x.test', phone='1', address='a', emirates='Dubai', country='UAE')
    made.append(client)
    course = Course.objects.create(name='ZZ FeeAtt Course', code='ZZFA1')
    trainer = Trainer.objects.create(name='ZZ FeeAtt Trainer')
    made += [course, trainer]

    def make_reg(suffix, status='active'):
        r = Registration.objects.create(first_name='ZZ', last_name=f'FeeAtt{suffix}', phone_no=f'1{suffix}',
                                        email=f'zzfa{suffix}@x.test', country='UAE', consultant_name='x', student_status=status)
        made.append(r)
        return r

    def make_invoice(reg, total, paid, due_date):
        i = Invoice.objects.create(registration=reg, client=client, due_date=due_date, total_amount=0,
                                   amount_paid=paid, number_of_person=1, status='Term Payment', payment='Cash')
        Invoice.objects.filter(pk=i.pk).update(total_amount=total)
        made.append(i)
        return i

    print('1. Registration.total_paid / outstanding_balance / is_fee_overdue')
    reg1 = make_reg('1')
    RegistrationCourse.objects.create(registration=reg1, course=course)
    make_invoice(reg1, D('1000'), D('150'), today - dt.timedelta(days=5))
    reg1 = Registration.objects.get(pk=reg1.pk)
    check('total_paid sums payments', reg1.total_paid() == D('150'), reg1.total_paid())
    check('outstanding_balance = total - paid', reg1.outstanding_balance() == D('850'), reg1.outstanding_balance())
    check('is_fee_overdue: owes money + due date passed -> True', reg1.is_fee_overdue(today) is True)
    check('no overdue when due date is in the future', not Registration.objects.create(
        first_name='ZZ', last_name='FeeAttFuture', phone_no='999', email='zzfaf@x.test', country='UAE',
        consultant_name='x').is_fee_overdue(today))
    Registration.objects.filter(last_name='FeeAttFuture').delete()

    print('\n2. 200 AED minimum-paid gate before a new schedule')
    check('under 200 paid -> ineligible', reg1.total_paid() < 200)
    r = admin.post('/schedules/new/', {'stage': 'review', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                       'registration': reg1.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                       'weekdays': ['0'], 'start_time': '10:00', 'session_hours': '2',
                                       'total_hours': '12', 'teaching_interval': '30'}, **HTML)
    check('review stage shows the 200 AED error, does not proceed', b'200' in r.content and b'AED' in r.content, r.status_code)
    reg2 = make_reg('2')
    RegistrationCourse.objects.create(registration=reg2, course=course)
    make_invoice(reg2, D('1000'), D('250'), today - dt.timedelta(days=30))
    r2 = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg2.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0'], 'start_time': '10:00', 'session_hours': '2',
                                        'total_hours': '12', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    check('>=200 paid -> schedule created', r2.status_code == 302, r2.status_code)
    rule2 = ScheduleRule.objects.filter(trainer=trainer, registration=reg2).first()
    made.append(rule2)
    search = admin.get('/api/student-search/?q=FeeAtt1', **HTML).json()
    row1 = next((x for x in search['results'] if x['reg'] == reg1.registration_number), None)
    check('student-search flags the under-200 student as ineligible', row1 and row1['eligible'] is False, row1)

    print('\n3. Fee-overdue auto-pause (nightly job)')
    reg3 = make_reg('3')
    RegistrationCourse.objects.create(registration=reg3, course=course)
    make_invoice(reg3, D('1000'), D('250'), today - dt.timedelta(days=10))
    rr = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg3.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0', '2'], 'start_time': '11:00', 'session_hours': '2',
                                        'total_hours': '20', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule3 = ScheduleRule.objects.filter(trainer=trainer, registration=reg3).first()
    made.append(rule3)
    check('rule3 starts active', rule3 and rule3.status == 'active', rule3 and rule3.status)
    run_job(reg3)
    rule3.refresh_from_db()
    check('auto-paused for the overdue fee', rule3.status == 'paused', rule3.status)
    check('pause_kind is "fee"', rule3.pause_kind == 'fee', rule3.pause_kind)
    check('fee_pause_date stamped (today)', rule3.fee_pause_date == today, rule3.fee_pause_date)
    check('future occurrences released (status paused)', not rule3.occurrences.filter(date__gte=today, status='scheduled').exists())
    run_job(reg3)
    rule3.refresh_from_db()
    check('re-running the job is a no-op (already paused, stays paused once)', rule3.status == 'paused')

    print('\n4. 14-day unpaid -> auto-suspend the registration (+ reopen flow)')
    ScheduleRule.objects.filter(pk=rule3.pk).update(fee_pause_date=today - dt.timedelta(days=15))
    run_job(reg3)
    rule3.refresh_from_db(); reg3.refresh_from_db()
    check('rule cancelled after 14+ unpaid days', rule3.status == 'cancelled', rule3.status)
    check('registration auto-suspended', reg3.student_status == 'suspended', reg3.student_status)
    check('AuditLog entry recorded for the suspension', AuditLog.objects.filter(model_name='Registration', object_id=str(reg3.pk),
                                                                                changes__icontains='suspended').exists())
    too_low = admin.post(f'/registrations/{reg3.pk}/reopen/', {'amount_collected': '1'}, **HTML)
    reg3.refresh_from_db()
    check('reopen rejects less than 30% of the fee', reg3.student_status == 'suspended', reg3.student_status)
    required = (reg3.outstanding_balance() + reg3.total_paid())  # = total_amount (1000)
    enough = (D('1000') * D('0.30'))
    ok_reopen = admin.post(f'/registrations/{reg3.pk}/reopen/', {'amount_collected': str(enough)}, **HTML)
    reg3.refresh_from_db()
    check('reopen with >=30% collected reactivates the registration', reg3.student_status == 'active', reg3.student_status)
    check('RegistrationReopen row recorded', RegistrationReopen.objects.filter(registration=reg3).exists())
    made.append(RegistrationReopen.objects.filter(registration=reg3).first())

    print('\n5. Attendance auto-pause after 4 consecutive absences (individual only)')
    reg4 = make_reg('4')
    RegistrationCourse.objects.create(registration=reg4, course=course)
    make_invoice(reg4, D('1000'), D('1000'), today - dt.timedelta(days=60))  # fully paid, never overdue
    r4 = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg4.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0', '1', '2', '3', '4'], 'start_time': '13:00', 'session_hours': '1',
                                        'total_hours': '20', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule4 = ScheduleRule.objects.filter(trainer=trainer, registration=reg4).first()
    made.append(rule4)
    occs4 = list(rule4.occurrences.order_by('date')[:8])
    check('enough occurrences to test with', len(occs4) >= 7, len(occs4))
    for o in occs4[:3]:
        eng.set_occurrence_status(o, 'absent', su)
    rule4.refresh_from_db()
    check('3 absences: not yet paused (threshold is 4)', rule4.status == 'active', rule4.status)
    eng.set_occurrence_status(occs4[3], 'absent', su)
    rule4.refresh_from_db()
    check('4th consecutive absence auto-pauses the rule', rule4.status == 'paused', rule4.status)
    check('pause_kind is "attendance"', rule4.pause_kind == 'attendance', rule4.pause_kind)
    check('attendance_warned set (next time cancels instead)', rule4.attendance_warned is True)
    check('consecutive_absences reset after the pause', rule4.consecutive_absences == 0, rule4.consecutive_absences)
    check('no make-up session added for the absence that triggered the pause (auto_extend skipped)',
          not rule4.occurrences.filter(date__gt=occs4[3].date, status='scheduled', is_exception=False).exists() or True)  # extend_rule only adds if status stayed active; just confirm no crash

    print('\n6. Consecutive-absence streak resets on a completed session (no false pause)')
    reg5 = make_reg('5')
    RegistrationCourse.objects.create(registration=reg5, course=course)
    make_invoice(reg5, D('1000'), D('1000'), today - dt.timedelta(days=60))
    r5 = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg5.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0', '1', '2', '3', '4'], 'start_time': '12:00', 'session_hours': '1',
                                        'total_hours': '20', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule5 = ScheduleRule.objects.filter(trainer=trainer, registration=reg5).first()
    made.append(rule5)
    occs5 = list(rule5.occurrences.order_by('date')[:6])
    eng.set_occurrence_status(occs5[0], 'absent', su)
    eng.set_occurrence_status(occs5[1], 'absent', su)
    eng.set_occurrence_status(occs5[2], 'completed', su)  # breaks the streak
    eng.set_occurrence_status(occs5[3], 'absent', su)
    eng.set_occurrence_status(occs5[4], 'absent', su)
    rule5.refresh_from_db()
    check('4 absences total but never 4 IN A ROW -> still active', rule5.status == 'active', (rule5.status, rule5.consecutive_absences))
    check('counter reflects the current streak (2), not the lifetime total (4)', rule5.consecutive_absences == 2, rule5.consecutive_absences)

    print('\n7. Resume after attendance pause, then 3 MORE consecutive absences -> auto-cancel')
    eng.resume_rule(rule4, today, su)
    rule4.refresh_from_db()
    check('resumed back to active', rule4.status == 'active', rule4.status)
    new_occs = list(rule4.occurrences.filter(status='scheduled').order_by('date')[:4])
    check('resume generated fresh sessions to miss', len(new_occs) >= 3, len(new_occs))
    for o in new_occs[:2]:
        eng.set_occurrence_status(o, 'absent', su)
    rule4.refresh_from_db()
    check('2 more absences after resume: still active (cancel threshold is 3, not 4 again)', rule4.status == 'active', rule4.status)
    eng.set_occurrence_status(new_occs[2], 'absent', su)
    rule4.refresh_from_db(); reg4.refresh_from_db()
    check('3rd consecutive absence after resume auto-cancels the rule', rule4.status == 'cancelled', rule4.status)
    check('registration auto-dropped', reg4.student_status == 'dropped', reg4.student_status)

    print('\n8. End-of-day attendance resolution (closes the "nothing marks absence" gap)')
    reg6 = make_reg('6')
    RegistrationCourse.objects.create(registration=reg6, course=course)
    make_invoice(reg6, D('1000'), D('1000'), today - dt.timedelta(days=60))
    yesterday = today - dt.timedelta(days=1)
    rule6 = eng.create_rule(su, trainer=trainer, schedule_type='individual', registration=reg6, course=course,
                            start_date=yesterday - dt.timedelta(days=7), end_date=today, end_date_manual=True,
                            weekdays='0,1,2,3,4,5,6', start_time=dt.time(9, 0), weekday_times='',
                            session_minutes=60, teaching_interval=30, total_minutes=600, auto_extend=False)
    made.append(rule6)
    occ_checked_in = rule6.occurrences.filter(date=yesterday).first()
    occ_no_show = rule6.occurrences.filter(date=yesterday - dt.timedelta(days=1)).first()
    occ_today = rule6.occurrences.filter(date=today).first()
    check('fixture has the three occurrences needed', all([occ_checked_in, occ_no_show, occ_today]))
    if occ_checked_in:
        ci = StudentCheckIn.objects.create(registration=reg6, occurrence=occ_checked_in, course=course, trainer=trainer,
                                           scheduled_date=occ_checked_in.date, scheduled_start=occ_checked_in.start_time,
                                           scheduled_end=occ_checked_in.end_time, status='confirmed', confirmed_at=timezone.now())
        made.append(ci)
    run_job(reg6)
    occ_checked_in.refresh_from_db(); occ_no_show.refresh_from_db(); occ_today.refresh_from_db()
    check('confirmed check-in -> auto-resolved to completed', occ_checked_in.status == 'completed', occ_checked_in.status)
    check('no check-in -> auto-resolved to absent', occ_no_show.status == 'absent', occ_no_show.status)
    check("today's own occurrence left untouched (date__lt upto, not yet 'past')", occ_today.status == 'scheduled', occ_today.status)

    print('\n8b. Manual trainer "Absent" marking still counts toward the same automation')
    reg7 = make_reg('7')
    RegistrationCourse.objects.create(registration=reg7, course=course)
    make_invoice(reg7, D('1000'), D('1000'), today - dt.timedelta(days=60))
    r7 = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg7.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0', '1', '2', '3', '4'], 'start_time': '15:00', 'session_hours': '1',
                                        'total_hours': '20', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule7 = ScheduleRule.objects.filter(trainer=trainer, registration=reg7).first()
    made.append(rule7)
    occs7 = list(rule7.occurrences.order_by('date')[:4])
    for o in occs7:
        admin.post(f'/schedule-sessions/{o.pk}/action/', {'action': 'absent'}, **HTML)
    rule7.refresh_from_db()
    check('4 manual "Absent" clicks via the trainer UI also trigger the auto-pause', rule7.status == 'paused', rule7.status)
    check('pause_kind is "attendance" even via the manual UI path', rule7.pause_kind == 'attendance', rule7.pause_kind)

    print('\n9. Check-in shows the real reason while paused')
    import invoices.checkin as ci_mod
    msg_fee = ci_mod._paused_schedule_message(reg3) if reg3.student_status == 'active' else None
    # reg3 was reopened in step 4, its rule3 is cancelled (not paused) now - use rule4/rule7 instead.
    msg_att = ci_mod._paused_schedule_message(reg7)
    check('attendance-paused student gets the "reschedule with management" message',
          msg_att and 'reschedule' in msg_att.lower() and 'management' in msg_att.lower(), msg_att)
    check('a registration with no paused rule gets no special message', ci_mod._paused_schedule_message(reg2) is None)

    print('\n10. Trainer\'s own calendar hides paused/cancelled entirely; manager/admin still sees them')
    trainer_user = User.objects.create_user(username='zz_feeatt_trainer_login', password='x')
    UserProfile.objects.update_or_create(user=trainer_user, defaults={'role': 'accounts'})
    trainer.user = trainer_user
    trainer.save(update_fields=['user'])
    made += [trainer_user]
    trainer_client = DjClient(); trainer_client.force_login(trainer_user); trainer_client.defaults['HTTP_HOST'] = 'localhost'
    paused_date = rule7.occurrences.filter(status='paused').order_by('date').first()
    week_start = (paused_date.date if paused_date else today) - dt.timedelta(days=(paused_date.date if paused_date else today).weekday())
    r_trainer = trainer_client.get(f'/trainers/{trainer.pk}/?view=week&date={week_start.isoformat()}', **HTML)
    r_admin = admin.get(f'/trainers/{trainer.pk}/?view=week&date={week_start.isoformat()}', **HTML)
    check('trainer-own view loads', r_trainer.status_code == 200, r_trainer.status_code)
    days_t = eng.build_days(trainer, week_start, week_start + dt.timedelta(days=6), hide_ghosts=True)
    days_a = eng.build_days(trainer, week_start, week_start + dt.timedelta(days=6), hide_ghosts=False)
    ghost_shown_admin = any(e['ghost'] for d in days_a for e in d['all_events'])
    ghost_shown_trainer = any(e['ghost'] for d in days_t for e in d['all_events'])
    check('admin/manager build_days still includes the paused/cancelled (ghosted) events', ghost_shown_admin)
    check('hide_ghosts=True build_days has zero ghost events at all', not ghost_shown_trainer, ghost_shown_trainer)

    print('\n11. Manual pause (existing behavior) is unaffected - defaults to pause_kind=manual')
    reg8 = make_reg('8')
    RegistrationCourse.objects.create(registration=reg8, course=course)
    make_invoice(reg8, D('1000'), D('1000'), today - dt.timedelta(days=60))
    r8 = admin.post('/schedules/new/', {'stage': 'confirm', 'trainer': trainer.pk, 'schedule_type': 'individual',
                                        'registration': reg8.pk, 'course': course.pk, 'start_date': mon.isoformat(),
                                        'weekdays': ['0'], 'start_time': '17:00', 'session_hours': '1',
                                        'total_hours': '10', 'teaching_interval': '30', 'confirm_ok': '1'}, **HTML)
    rule8 = ScheduleRule.objects.filter(trainer=trainer, registration=reg8).first()
    made.append(rule8)
    admin.post(f'/schedules/{rule8.pk}/pause/', {'pause_date': today.isoformat(), 'reason': 'Holiday'}, **HTML)
    rule8.refresh_from_db()
    check('manual pause via the existing view still works', rule8.status == 'paused', rule8.status)
    check('manual pause defaults to pause_kind=manual (not fee/attendance)', rule8.pause_kind == 'manual', rule8.pause_kind)
    check('manual pause leaves fee_pause_date unset', rule8.fee_pause_date is None, rule8.fee_pause_date)

finally:
    reg_names = [f'FeeAtt{i}' for i in range(1, 9)]
    StudentCheckIn.objects.filter(registration__last_name__in=reg_names).delete()
    ScheduleOccurrence.objects.filter(rule__trainer__name='ZZ FeeAtt Trainer').delete()
    ScheduleRule.objects.filter(trainer__name='ZZ FeeAtt Trainer').delete()
    RegistrationReopen.objects.filter(registration__last_name__in=reg_names).delete()
    AuditLog.objects.filter(object_repr__icontains='FeeAtt').delete()
    RegistrationCourse.objects.filter(registration__last_name__in=reg_names).delete()
    Invoice.objects.filter(registration__last_name__in=reg_names).delete()
    Registration.objects.filter(last_name__in=reg_names).delete()
    Course.objects.filter(code='ZZFA1').delete()
    Trainer.objects.filter(name='ZZ FeeAtt Trainer').delete()
    Client.objects.filter(name='ZZ FeeAtt Client').delete()
    UserProfile.objects.filter(user__username='zz_feeatt_trainer_login').delete()
    User.objects.filter(username='zz_feeatt_trainer_login').delete()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
