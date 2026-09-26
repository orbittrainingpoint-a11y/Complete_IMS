"""Trainer scheduling: trainers, day board, batches, one-off sessions, waiting students, free-trainer finder.

Recurring schedules, the calendar and the create-schedule flow live in schedule_views.py; the
rules (individual rotation vs batch blocks, conflicts, capacity) live in schedule_engine.py.
"""
import datetime as dt
from collections import defaultdict
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import schedule_engine as eng
from .models import (
    WEEKDAY_CHOICES, Batch, BatchSkipDate, BatchStudent, ClassSession, Course, Registration, RegistrationCourse,
    ScheduleOccurrence, ScheduleRule, Trainer, TrainerLeave, TrainerWorkingHours,
)
from .schedule_engine import hhmm, mins

TRAINER_COLORS = ['#2563eb', '#7c3aed', '#db2777', '#ea580c', '#059669', '#0891b2', '#ca8a04', '#4f46e5']


# ── permissions ─────────────────────────────────────────────────────────────

def role_of(user):
    if user.is_superuser:
        return 'admin'
    p = getattr(user, 'profile', None)
    return p.role if p else ''


def can_manage(user):
    """Admin + sales manager (centre manager): create, edit, pause, resume, reschedule."""
    return role_of(user) in ('admin', 'sales_manager')


def can_create(user):
    """Everyone can VIEW trainer schedules; only admin and sales manager can create or edit."""
    return can_manage(user)


def is_admin_role(user):
    return role_of(user) == 'admin'


def own_trainer(user):
    return getattr(user, 'trainer_record', None)


def manage_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_manage(request.user):
            messages.error(request, 'Only admins and centre managers can change trainer schedules.')
            return redirect('trainer_list')
        return view(request, *args, **kwargs)
    return wrapper


def create_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_create(request.user):
            messages.error(request, 'You do not have permission to create schedules.')
            return redirect('trainer_list')
        return view(request, *args, **kwargs)
    return wrapper


def safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next') or ''
    return nxt if nxt.startswith('/') and not nxt.startswith('//') else default


def parse_time(s):
    return dt.datetime.strptime(s[:5], '%H:%M').time()


def parse_date(s, default=None):
    try:
        return dt.datetime.strptime(s, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


def refresh_batch_statuses():
    today = eng.dubai_today()
    Batch.objects.filter(status='upcoming', start_date__lte=today, end_date__gte=today).update(status='ongoing')
    Batch.objects.filter(status__in=('upcoming', 'ongoing'), end_date__lt=today).update(status='completed')


def batch_occurrence_dates(start_date, end_date, weekdays):
    return [d for d, _, _ in eng.plan_occurrences(start_date, weekdays, 600, 60, 0, until=end_date)]


def find_conflicts(trainer, dates, start_min, end_min, kind='individual', exclude_batch=None, exclude_session=None, registration=None):
    """(errors, warnings) for the simple forms: warnings need a confirmation tick."""
    rule = ScheduleRule.objects.filter(batch_id=exclude_batch).first() if exclude_batch else None
    res = eng.check_conflicts(trainer, [(d, start_min, end_min) for d in dates], kind, exclude_rule=rule,
                              exclude_session=exclude_session, registration=registration)
    return res['errors'], res['confirms'] + res['warnings']


def trainers_free_for(dates, start_min, end_min, course=None, kind='individual'):
    result = []
    for t in Trainer.objects.filter(is_active=True).prefetch_related('courses'):
        res = eng.check_conflicts(t, [(d, start_min, end_min) for d in dates], kind)
        if res['errors']:
            continue
        teaches = bool(course and t.courses.filter(pk=course.pk).exists())
        result.append({'trainer': t, 'teaches': teaches, 'warnings': res['confirms'] + res['warnings'], 'info': res['info']})
    result.sort(key=lambda r: (not r['teaches'], bool(r['warnings']), r['trainer'].name.lower()))
    return result


def waiting_students(course=None, days=90):
    """Enrolled students (per course) with no batch and no active individual schedule yet."""
    since = eng.dubai_today() - dt.timedelta(days=days)
    rcs = (RegistrationCourse.objects.select_related('registration', 'course')
           .filter(registration__student_status__in=('active', 'pending'), registration__is_refunded=False,
                   registration__date__gte=since))
    if course:
        rcs = rcs.filter(course=course)
    assigned = set()
    for reg_id, c_id, b_course in BatchStudent.objects.filter(status='active').values_list('registration_id', 'course_id', 'batch__course_id'):
        assigned.add((reg_id, c_id or b_course))
    for reg_id, c_id in ScheduleRule.objects.filter(status__in=('active', 'paused'), schedule_type='individual',
                                                    registration__isnull=False).values_list('registration_id', 'course_id'):
        assigned.add((reg_id, c_id))
    return [rc for rc in rcs.order_by('course__name', 'registration__date') if (rc.registration_id, rc.course_id) not in assigned]


# ── trainers ────────────────────────────────────────────────────────────────

@login_required
def trainer_list(request):
    today = eng.dubai_today()
    now_min = eng.dubai_now_minutes()
    mine = own_trainer(request.user)
    qs = Trainer.objects.filter(is_active=True).prefetch_related('courses')
    if mine and not can_manage(request.user):
        qs = qs.filter(pk=mine.pk)
    week0 = today - dt.timedelta(days=today.weekday())
    setting = eng.settings_obj()
    rows = []
    for t in qs:
        week = eng.build_days(t, week0, week0 + dt.timedelta(days=6), setting=setting)
        day = next(d for d in week if d['date'] == today)
        snap = eng.trainer_snapshot(t, today, day=day, setting=setting)
        busy_now = any(e['start'] <= now_min < e['end'] and not e['ghost'] for e in day['events'])
        status = ('leave', 'On leave') if day['leave'] else ('off', 'Day off') if day['off'] else \
                 ('busy', 'Teaching now') if busy_now else ('free', 'Available now')
        w_working = sum(d['stats']['working'] for d in week)
        w_util = round(sum(d['stats']['util'] * d['stats']['working'] for d in week) / w_working) if w_working else 0
        rows.append({'t': t, 'status': status, 'snap': snap, 'util': w_util,
                     'hs': eng.fmt_hours(snap['hours_scheduled']), 'hd': eng.fmt_hours(snap['hours_delivered']),
                     'hr': eng.fmt_hours(snap['hours_remaining']),
                     'today_labels': [f'{e["label"]}  {e["title"]}' for e in day['events'] if not e['ghost']][:6],
                     'free_today': [s['label'] for s in day['free']][:6],
                     'booked_h': round(sum(d['stats']['occupied_min'] for d in week) / 60, 1)})
    return render(request, 'trainer_schedule/trainer_list.html', {
        'rows': rows, 'can_manage': can_manage(request.user), 'can_create': can_create(request.user), 'today': today,
        'inactive': Trainer.objects.filter(is_active=False).count(), 'fmt': eng.fmt_hours})


@manage_required
def trainer_form(request, pk=None):
    from django.contrib.auth.models import User
    trainer = get_object_or_404(Trainer, pk=pk) if pk else None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Trainer name is required.')
        else:
            t = trainer or Trainer()
            t.name = name
            t.phone = request.POST.get('phone', '').strip()
            t.email = request.POST.get('email', '').strip()
            t.specialization = request.POST.get('specialization', '').strip()
            t.color = request.POST.get('color') or TRAINER_COLORS[Trainer.objects.count() % len(TRAINER_COLORS)]
            t.notes = request.POST.get('notes', '').strip()
            t.is_active = request.POST.get('is_active', 'on') == 'on'
            uid = request.POST.get('user') or None
            t.user = User.objects.filter(pk=uid).first() if uid and not Trainer.objects.filter(user_id=uid).exclude(pk=t.pk).exists() else None
            t.save()
            t.courses.set(Course.objects.filter(pk__in=request.POST.getlist('courses')))
            t.working_hours.all().delete()
            for d in range(7):
                if request.POST.get(f'wd_{d}'):
                    try:
                        s, e = parse_time(request.POST.get(f'ws_{d}', '10:00')), parse_time(request.POST.get(f'we_{d}', '21:00'))
                    except ValueError:
                        continue
                    if e > s:
                        TrainerWorkingHours.objects.create(trainer=t, weekday=d, start_time=s, end_time=e)
            messages.success(request, f'Trainer "{t.name}" saved.')
            if not t.working_hours.exists():
                messages.warning(request, 'No working days were ticked - this trainer shows as "day off" everywhere until you set working hours.')
            return redirect('trainer_week', pk=t.pk)
    hours = {w.weekday: w for w in trainer.working_hours.all()} if trainer else {}
    rows = []
    for d, name in WEEKDAY_CHOICES:
        if trainer:
            w = hours.get(d)
            rows.append({'d': d, 'name': name, 'on': bool(w), 'start': w.start_time.strftime('%H:%M') if w else '10:00',
                         'end': w.end_time.strftime('%H:%M') if w else '21:00'})
        else:
            rows.append({'d': d, 'name': name, 'on': d < 6, 'start': '10:00', 'end': '21:00'})
    return render(request, 'trainer_schedule/trainer_form.html', {
        'trainer': trainer, 'courses': Course.objects.order_by('name'), 'hours': rows,
        'selected': set(trainer.courses.values_list('pk', flat=True)) if trainer else set(), 'colors': TRAINER_COLORS,
        'users': User.objects.filter(is_active=True).order_by('username')})


@manage_required
@require_POST
def trainer_deactivate(request, pk):
    t = get_object_or_404(Trainer, pk=pk)
    if t.is_active and ScheduleRule.objects.filter(trainer=t, status__in=('active', 'paused')).exists():
        messages.warning(request, f'{t.name} still has active schedules - move or cancel them first, or leave the trainer active.')
        return redirect('trainer_list')
    t.is_active = not t.is_active
    t.save(update_fields=['is_active'])
    messages.success(request, f'{t.name} {"re-activated" if t.is_active else "deactivated (history kept)"}.')
    return redirect('trainer_list')


@manage_required
@require_POST
def trainer_leave_add(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    d1 = parse_date(request.POST.get('date_from'))
    d2 = parse_date(request.POST.get('date_to'), d1)
    if not d1 or d2 < d1:
        messages.error(request, 'Please enter a valid leave date range.')
    else:
        TrainerLeave.objects.create(trainer=trainer, date_from=d1, date_to=d2, reason=request.POST.get('reason', '')[:200])
        n = ScheduleOccurrence.objects.filter(trainer=trainer, date__gte=d1, date__lte=d2, status__in=eng.ACTIVE_FUTURE).count()
        messages.success(request, 'Leave added.')
        if n:
            messages.warning(request, f'{n} scheduled session(s) fall in that period. Reschedule them from the trainer calendar '
                                      f'(they are listed under "Needs attention").')
    return redirect(safe_next(request, f'/trainers/{pk}/'))


@manage_required
@require_POST
def trainer_leave_delete(request, pk, leave_id):
    TrainerLeave.objects.filter(pk=leave_id, trainer_id=pk).delete()
    return redirect(safe_next(request, f'/trainers/{pk}/'))


# ── day board (all trainers) ────────────────────────────────────────────────

@login_required
def day_board(request):
    d = parse_date(request.GET.get('date'), eng.dubai_today())
    mode = request.GET.get('mode', 'timeline')
    rows = []
    setting = eng.settings_obj()
    for t in Trainer.objects.filter(is_active=True):
        day = eng.build_days(t, d, d, setting=setting)[0]
        listing = []
        for r in day['rotation']:
            key = (r['who'], r['kind'])
            if listing and listing[-1]['key'] == key and r['kind'] in ('batch', 'free'):
                listing[-1]['end'] = r['end']
            else:
                listing.append({'key': key, 'start': r['start'], 'end': r['end'], 'who': r['who'], 'kind': r['kind'], 'others': r['others']})
        for l in listing:
            l['label'] = f'{hhmm(l["start"])}-{hhmm(l["end"])}'
        rows.append({'t': t, 'day': day, 'st': day['stats'], 'listing': listing, 'free_label': ', '.join(s['label'] for s in day['free'])})
    return render(request, 'trainer_schedule/day_board.html', {
        'rows': rows, 'date': d, 'mode': mode, 'prev': d - dt.timedelta(days=1), 'next': d + dt.timedelta(days=1),
        'today': eng.dubai_today(), 'fmt': eng.fmt_hours,
        'hour_marks': [{'label': f'{h:02d}', 'left': eng.pct_top(h * 60)} for h in range(10, 21)],
        'can_create': can_create(request.user)})


# ── batches ─────────────────────────────────────────────────────────────────

def sync_batch_rule(batch, user):
    """Every batch with a trainer has one schedule rule that generates its calendar sessions."""
    rule = ScheduleRule.objects.filter(batch=batch).exclude(status='cancelled').first()
    if batch.status == 'cancelled':
        if rule:
            eng.cancel_rule(rule, eng.dubai_today(), 'Batch cancelled', user)
        return None
    if not batch.trainer:
        return None
    s = mins(batch.start_time)
    dur = mins(batch.end_time) - s
    plan = eng.plan_occurrences(batch.start_date, batch.weekday_list, s, dur, 0, until=batch.end_date)
    total = sum(e - st for _, st, e in plan)
    fields = dict(trainer=batch.trainer, course=batch.course, start_date=batch.start_date, end_date=batch.end_date,
                  end_date_manual=True, weekdays=batch.weekdays, start_time=batch.start_time, session_minutes=dur, total_minutes=total)
    if rule:
        changed = any(getattr(rule, k) != v for k, v in fields.items())
        for k, v in fields.items():
            setattr(rule, k, v)
        rule.updated_by = user
        rule.save()
        if changed:
            eng.regenerate_future(rule, max(eng.dubai_today(), batch.start_date), user, 'Batch details changed', keep_exceptions=True)
        return rule
    return eng.create_rule(user, schedule_type='batch', batch=batch, **fields)


@login_required
def batch_list(request):
    refresh_batch_statuses()
    qs = Batch.objects.select_related('course', 'trainer')
    status, trainer, course = request.GET.get('status', ''), request.GET.get('trainer', ''), request.GET.get('course', '')
    if status:
        qs = qs.filter(status=status)
    if trainer == 'none':
        qs = qs.filter(trainer__isnull=True)
    elif trainer:
        qs = qs.filter(trainer_id=trainer)
    if course:
        qs = qs.filter(course_id=course)
    batches = list(qs.order_by('-start_date'))
    for b in batches:
        b.active_students = b.students.filter(status='active').count()
    return render(request, 'trainer_schedule/batch_list.html', {
        'batches': batches, 'status': status, 'trainer_f': trainer, 'course_f': course,
        'trainers': Trainer.objects.filter(is_active=True), 'courses': Course.objects.order_by('name'),
        'can_manage': can_manage(request.user)})


def _batch_from_post(request, batch):
    p = request.POST
    weekdays = sorted({int(x) for x in p.getlist('weekdays') if x.isdigit() and 0 <= int(x) <= 6})
    batch.course = Course.objects.filter(pk=p.get('course') or None).first()
    batch.trainer = Trainer.objects.filter(pk=p.get('trainer') or None).first()
    batch.start_date = parse_date(p.get('start_date'))
    batch.end_date = parse_date(p.get('end_date'))
    batch.weekdays = ','.join(map(str, weekdays))
    batch.start_time = parse_time(p.get('start_time') or '10:00')
    batch.end_time = parse_time(p.get('end_time') or '12:00')
    batch.mode = p.get('mode') if p.get('mode') in ('online', 'offline') else 'offline'
    batch.venue = p.get('venue', '').strip()
    batch.capacity = int(p.get('capacity') or 10)
    batch.notes = p.get('notes', '').strip()
    if p.get('status') in dict(Batch.STATUS_CHOICES):
        batch.status = p.get('status')
    batch.name = p.get('name', '').strip() or (
        f'{batch.course.name if batch.course else "Batch"} - {batch.start_date:%d %b %Y} {batch.start_time:%H:%M}'
        if batch.start_date else 'Batch')
    return weekdays


@manage_required
def batch_form(request, pk=None):
    batch = get_object_or_404(Batch, pk=pk) if pk else None
    errors, warnings, prefill = [], [], {}
    if request.method == 'POST':
        target = batch or Batch()
        try:
            weekdays = _batch_from_post(request, target)
            valid = target.start_date and target.end_date and target.end_date >= target.start_date and weekdays and mins(target.end_time) > mins(target.start_time)
        except ValueError:
            valid = False
        if not valid:
            errors.append('Start date, end date (not before start), an end time after the start time, and at least one weekday are required.')
        else:
            if target.trainer:
                dates = batch_occurrence_dates(target.start_date, target.end_date, weekdays)
                errors, warnings = find_conflicts(target.trainer, dates, mins(target.start_time), mins(target.end_time),
                                                  kind='batch', exclude_batch=target.pk)
                if is_admin_role(request.user) and request.POST.get('override') and errors:
                    warnings, errors = errors + warnings, []
                if target.course and not target.trainer.courses.filter(pk=target.course.pk).exists():
                    warnings.append(f'{target.trainer.name} is not marked as teaching {target.course.name}.')
            if not errors and (not warnings or request.POST.get('confirm_warnings')):
                if not target.pk:
                    target.created_by = request.user
                target.save()
                sync_batch_rule(target, request.user)
                messages.success(request, f'Batch "{target.name}" saved.')
                return redirect(safe_next(request, f'/batches/{target.pk}/'))
        batch = target if target.pk else None
        prefill = request.POST
    if prefill:
        vals = {k: prefill.get(k, '') for k in ('name', 'course', 'trainer', 'start_date', 'end_date', 'start_time',
                                               'end_time', 'mode', 'venue', 'capacity', 'status', 'notes')}
    elif batch:
        vals = {'name': batch.name, 'course': batch.course_id or '', 'trainer': batch.trainer_id or '',
                'start_date': batch.start_date.isoformat(), 'end_date': batch.end_date.isoformat(),
                'start_time': batch.start_time.strftime('%H:%M'), 'end_time': batch.end_time.strftime('%H:%M'),
                'mode': batch.mode, 'venue': batch.venue, 'capacity': batch.capacity, 'status': batch.status, 'notes': batch.notes}
    else:
        vals = {'name': '', 'course': request.GET.get('course', ''), 'trainer': request.GET.get('trainer', ''),
                'start_date': '', 'end_date': '', 'start_time': '10:00', 'end_time': '12:00', 'mode': 'offline',
                'venue': '', 'capacity': 10, 'status': 'upcoming', 'notes': ''}
    return render(request, 'trainer_schedule/batch_form.html', {
        'batch': batch, 'errors': errors, 'warnings': warnings, 'v': vals,
        'next': request.POST.get('next') or request.GET.get('next') or '',
        'courses': Course.objects.order_by('name'), 'trainers': Trainer.objects.filter(is_active=True),
        'weekdays': WEEKDAY_CHOICES, 'is_admin': is_admin_role(request.user),
        'sel_days': (set(int(x) for x in prefill.getlist('weekdays') if x.isdigit()) if prefill else
                     (set(batch.weekday_list) if batch else {0, 1, 2, 3, 4})),
        'confirm': bool(warnings)})


@login_required
def batch_detail(request, pk):
    batch = get_object_or_404(Batch.objects.select_related('course', 'trainer'), pk=pk)
    roster = list(batch.students.select_related('registration').order_by('registration__first_name'))
    active = [s for s in roster if s.status == 'active']
    rule = ScheduleRule.objects.filter(batch=batch).exclude(status='cancelled').first()
    today = eng.dubai_today()
    occs = list(rule.occurrences.exclude(status__in=('cancelled', 'paused')).order_by('date')) if rule else []
    return render(request, 'trainer_schedule/batch_detail.html', {
        'batch': batch, 'roster': roster, 'active_count': len(active), 'seats_left': max(0, batch.capacity - len(active)),
        'rule': rule, 'upcoming': [o for o in occs if o.date >= today and o.status in eng.ACTIVE_FUTURE][:12],
        'total_sessions': len(occs), 'done_sessions': sum(1 for o in occs if o.status == 'completed'),
        'hours': eng.rule_hours(rule) if rule else None, 'fmt': eng.fmt_hours,
        'skip': list(batch.skip_dates.all()),
        'waiting': waiting_students(batch.course, days=180) if batch.course else [], 'can_manage': can_manage(request.user)})


@manage_required
@require_POST
def batch_add_students(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    room = batch.capacity - batch.students.filter(status='active').count()
    added = 0
    for reg in Registration.objects.filter(pk__in=request.POST.getlist('reg')):
        if room <= 0:
            messages.warning(request, f'Batch is full ({batch.capacity}); remaining students were not added.')
            break
        _, created = BatchStudent.objects.get_or_create(batch=batch, registration=reg, defaults={'course': batch.course, 'status': 'active'})
        if created:
            added += 1
            room -= 1
    if added:
        messages.success(request, f'{added} student(s) added to {batch.name}.')
    return redirect('batch_detail', pk=pk)


@manage_required
@require_POST
def batch_student_update(request, pk, link_id):
    link = get_object_or_404(BatchStudent, pk=link_id, batch_id=pk)
    action = request.POST.get('action')
    if action == 'remove':
        link.delete()
    elif action in ('dropped', 'completed', 'active'):
        link.status = action
        link.save(update_fields=['status'])
    return redirect('batch_detail', pk=pk)


@manage_required
@require_POST
def batch_skip(request, pk):
    """Holiday / no-class day: cancels that day's batch session and frees the trainer's slot."""
    batch = get_object_or_404(Batch, pk=pk)
    if request.POST.get('delete'):
        BatchSkipDate.objects.filter(batch=batch, pk=request.POST['delete']).delete()
    else:
        d = parse_date(request.POST.get('date'))
        if d:
            BatchSkipDate.objects.get_or_create(batch=batch, date=d, defaults={'reason': request.POST.get('reason', '')[:200]})
            for occ in ScheduleOccurrence.objects.filter(rule__batch=batch, date=d, status__in=eng.ACTIVE_FUTURE):
                eng.set_occurrence_status(occ, 'cancelled', request.user, note=request.POST.get('reason', 'Skipped')[:200])
    return redirect(safe_next(request, f'/batches/{pk}/'))


@manage_required
@require_POST
def batch_status(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if request.POST.get('status') in dict(Batch.STATUS_CHOICES):
        batch.status = request.POST['status']
        batch.save(update_fields=['status'])
        sync_batch_rule(batch, request.user)
    return redirect('batch_detail', pk=pk)


# ── one-off sessions (single date, outside any recurring schedule) ──────────

@login_required
def session_list(request):
    d1 = parse_date(request.GET.get('from'), eng.dubai_today() - dt.timedelta(days=7))
    d2 = parse_date(request.GET.get('to'), eng.dubai_today() + dt.timedelta(days=30))
    qs = ClassSession.objects.select_related('trainer', 'course').filter(date__gte=d1, date__lte=d2)
    if request.GET.get('trainer'):
        qs = qs.filter(trainer_id=request.GET['trainer'])
    return render(request, 'trainer_schedule/session_list.html', {
        'sessions': qs.order_by('date', 'start_time'), 'd1': d1, 'd2': d2, 'trainer_f': request.GET.get('trainer', ''),
        'trainers': Trainer.objects.filter(is_active=True), 'can_manage': can_manage(request.user)})


@manage_required
def session_form(request, pk=None):
    sess = get_object_or_404(ClassSession, pk=pk) if pk else None
    errors, warnings, prefill = [], [], {}
    if request.method == 'POST':
        p = request.POST
        target = sess or ClassSession()
        try:
            target.date = parse_date(p.get('date'))
            target.start_time = parse_time(p.get('start_time') or '10:00')
            target.end_time = parse_time(p.get('end_time') or '11:00')
        except ValueError:
            target.date = None
        target.trainer = Trainer.objects.filter(pk=p.get('trainer') or None).first()
        target.course = Course.objects.filter(pk=p.get('course') or None).first()
        target.session_type = p.get('session_type') if p.get('session_type') in dict(ClassSession.TYPE_CHOICES) else 'private'
        target.registration = Registration.objects.filter(pk=p.get('registration') or None).first()
        target.student_name = p.get('student_name', '').strip() or (
            f'{target.registration.first_name} {target.registration.last_name}' if target.registration else '')
        target.mode = p.get('mode') if p.get('mode') in ('online', 'offline') else 'offline'
        target.venue = p.get('venue', '').strip()
        target.notes = p.get('notes', '').strip()
        if p.get('status') in dict(ClassSession.STATUS_CHOICES):
            target.status = p.get('status')
        if not target.trainer:
            errors.append('A session must always have a trainer.')
        elif not target.date:
            errors.append('A valid date is required.')
        elif target.status != 'cancelled':
            errors, warnings = find_conflicts(target.trainer, [target.date], mins(target.start_time), mins(target.end_time),
                                              kind='individual', exclude_session=target.pk)
        if not errors and (not warnings or p.get('confirm_warnings')):
            if not target.pk:
                target.created_by = request.user
            target.save()
            messages.success(request, 'Session saved.')
            return redirect(safe_next(request, '/sessions/'))
        sess = target if target.pk else None
        prefill = p
    if prefill:
        vals = {k: prefill.get(k, '') for k in ('trainer', 'course', 'session_type', 'date', 'start_time', 'end_time',
                                               'student_name', 'mode', 'venue', 'status', 'notes')}
    elif sess:
        vals = {'trainer': sess.trainer_id or '', 'course': sess.course_id or '', 'session_type': sess.session_type,
                'date': sess.date.isoformat(), 'start_time': sess.start_time.strftime('%H:%M'),
                'end_time': sess.end_time.strftime('%H:%M'), 'student_name': sess.student_name, 'mode': sess.mode,
                'venue': sess.venue, 'status': sess.status, 'notes': sess.notes}
    else:
        vals = {'trainer': request.GET.get('trainer', ''), 'course': '', 'session_type': 'private',
                'date': request.GET.get('date', ''), 'start_time': request.GET.get('start_time', '10:00'),
                'end_time': request.GET.get('end_time', '11:00'), 'student_name': '', 'mode': 'offline',
                'venue': '', 'status': 'scheduled', 'notes': ''}
    return render(request, 'trainer_schedule/session_form.html', {
        'sess': sess, 'errors': errors, 'warnings': warnings, 'v': vals, 'confirm': bool(warnings),
        'next': request.POST.get('next') or request.GET.get('next') or '',
        'trainers': Trainer.objects.filter(is_active=True), 'courses': Course.objects.order_by('name'),
        'types': ClassSession.TYPE_CHOICES, 'statuses': ClassSession.STATUS_CHOICES})


@manage_required
@require_POST
def session_status(request, pk):
    s = get_object_or_404(ClassSession, pk=pk)
    if request.POST.get('status') in dict(ClassSession.STATUS_CHOICES):
        s.status = request.POST['status']
        s.save(update_fields=['status'])
    return redirect(safe_next(request, '/sessions/'))


# ── waiting students / free-trainer finder / live conflict API ──────────────

@login_required
def waiting_list(request):
    days = int(request.GET.get('days') or 90)
    course_id = request.GET.get('course')
    course = Course.objects.filter(pk=course_id).first() if course_id else None
    groups = defaultdict(list)
    for rc in waiting_students(course, days):
        groups[rc.course].append(rc)
    today = eng.dubai_today()
    cards = []
    for c, items in sorted(groups.items(), key=lambda kv: kv[0].name):
        open_batches = [b for b in Batch.objects.filter(course=c, status__in=('upcoming', 'ongoing')).select_related('trainer')
                        if b.students.filter(status='active').count() < b.capacity]
        for b in open_batches:
            b.seats = b.capacity - b.students.filter(status='active').count()
        trainers = []
        for t in c.trainers.filter(is_active=True):
            day = eng.build_days(t, today, today)[0]
            trainers.append({'t': t, 'free_today': [s['label'] for s in day['free']],
                             'partial_today': [s['label'] for s in day['partial']], 'util': day['stats']['util']})
        cards.append({'course': c, 'items': items, 'batches': open_batches, 'trainers': trainers})
    return render(request, 'trainer_schedule/waiting.html', {
        'cards': cards, 'days': days, 'course_f': course_id or '', 'courses': Course.objects.order_by('name'),
        'total': sum(len(c['items']) for c in cards), 'can_manage': can_manage(request.user), 'can_create': can_create(request.user)})


def _segs_in(day, s, e):
    return [seg for seg in day['segments'] if seg['start'] < e and s < seg['end']]


@login_required
def find_trainer(request):
    d = parse_date(request.GET.get('date'))
    course = Course.objects.filter(pk=request.GET.get('course') or None).first()
    kind = request.GET.get('kind') if request.GET.get('kind') in ('individual', 'batch') else 'individual'
    start, end = request.GET.get('start_time', ''), request.GET.get('end_time', '')
    results, error = [], ''
    if d and start and end:
        try:
            s, e = mins(parse_time(start)), mins(parse_time(end))
            if e <= s:
                error = 'End time must be after start time.'
            else:
                results = trainers_free_for([d], s, e, course, kind)
                for r in results:
                    day = eng.build_days(r['trainer'], d, d)[0]
                    r['util'] = day['stats']['util']
                    r['overlap'] = max([c['n'] for c in _segs_in(day, s, e)] or [0])
        except ValueError:
            error = 'Invalid time.'
    return render(request, 'trainer_schedule/find_trainer.html', {
        'results': results, 'error': error, 'courses': Course.objects.order_by('name'), 'kind': kind,
        'q': {'date': request.GET.get('date', ''), 'start_time': start, 'end_time': end, 'course': request.GET.get('course', '')},
        'searched': bool(d and start and end and not error), 'can_create': can_create(request.user)})


@login_required
def check_conflicts(request):
    g = request.GET
    trainer = Trainer.objects.filter(pk=g.get('trainer') or None).first()
    try:
        s, e = mins(parse_time(g.get('start_time', ''))), mins(parse_time(g.get('end_time', '')))
        if g.get('kind') == 'session':
            dates, kind = [parse_date(g.get('date'))], 'individual'
        else:
            wd = [int(x) for x in g.get('weekdays', '').split(',') if x.isdigit()]
            dates, kind = batch_occurrence_dates(parse_date(g.get('start_date')), parse_date(g.get('end_date')), wd), 'batch'
        dates = [x for x in dates if x]
    except (ValueError, TypeError):
        return JsonResponse({'errors': [], 'warnings': [], 'info': []})
    rule = ScheduleRule.objects.filter(batch_id=g.get('exclude_batch')).first() if g.get('exclude_batch') else None
    res = eng.check_conflicts(trainer, [(d, s, e) for d in dates], kind, exclude_rule=rule,
                              exclude_session=int(g['exclude_session']) if g.get('exclude_session') else None)
    return JsonResponse({'errors': res['errors'], 'warnings': res['confirms'] + res['warnings'], 'info': res['info']})
