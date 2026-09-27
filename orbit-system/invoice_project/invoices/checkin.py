"""Student Wi-Fi check-in — phase 1 (software only, no captive portal yet).

Public pages (no login): a student types their registration number, the CRM matches it
against today's schedule (ScheduleOccurrence for individual/batch rules, or a one-off
ClassSession) using the exact same data the trainer schedule module already maintains,
shows a review screen, and records a StudentCheckIn once they confirm. Nothing here
duplicates the trainer's own present/absent mark — see the models.py docstring.
"""
import datetime as dt
import re

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from . import schedule_engine as eng
from .models import (Batch, BatchStudent, CheckInAttempt, CheckInSetting, ClassSession, Registration,
                     ScheduleOccurrence, StudentCheckIn)
from .trainer_schedule import can_manage

TOKEN_SALT = 'orbit-student-checkin-v1'
DUBAI = dt.timezone(dt.timedelta(hours=4))


def _now():
    return timezone.now().astimezone(DUBAI)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _normalize_id(raw):
    """Forgiving of spacing/case/dashes: 'ot 26 003' or 'ot-26-3' -> 'OT/26/003'."""
    s = re.sub(r'[\s_-]+', '/', (raw or '').strip().upper())
    s = re.sub(r'/+', '/', s).strip('/')
    m = re.match(r'^(OT|OC)/?(\d{2})/?(\d{1,3})$', s)
    if m:
        return f'{m.group(1)}/{m.group(2)}/{int(m.group(3)):03d}'
    return s


def _rate_limited(request):
    """Guards against Student-ID guessing (spec §45) — a real student whose class hasn't
    started yet, or who checks an already-confirmed session, is not an abuse signal and
    must never be locked out for it. Only wrong-ID guesses count."""
    s = CheckInSetting.get()
    since = timezone.now() - dt.timedelta(minutes=s.rate_limit_minutes)
    bad = CheckInAttempt.objects.filter(ip_address=_client_ip(request), created_at__gte=since, result='invalid_student').count()
    return bad >= s.rate_limit_attempts


def _log(request, student_text, registration, result):
    CheckInAttempt.objects.create(student_id_text=student_text[:50], registration=registration, result=result,
                                  ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', '')[:300])


def _today_candidates(registration):
    """Every session this student could plausibly be checking into today, earliest first."""
    today = eng.dubai_today()
    rows = []
    for occ in (ScheduleOccurrence.objects.filter(date=today, status__in=('scheduled', 'rescheduled'))
                .filter(rule__registration=registration, rule__schedule_type='individual')
                .select_related('rule', 'rule__course', 'trainer')):
        rows.append((occ.start_time, 'occurrence', occ))
    batch_ids = BatchStudent.objects.filter(registration=registration, status='active').values_list('batch_id', flat=True)
    if batch_ids:
        for occ in (ScheduleOccurrence.objects.filter(date=today, status__in=('scheduled', 'rescheduled'), rule__batch_id__in=list(batch_ids), rule__schedule_type='batch')
                    .select_related('rule', 'rule__batch', 'rule__batch__course', 'trainer')):
            rows.append((occ.start_time, 'occurrence', occ))
    for cs in ClassSession.objects.filter(registration=registration, date=today, status='scheduled').select_related('course', 'trainer'):
        rows.append((cs.start_time, 'class_session', cs))
    rows.sort(key=lambda r: r[0])
    return rows


def _course_of(kind, obj):
    if kind == 'class_session':
        return obj.course
    rule = obj.rule
    return rule.course or (rule.batch.course if rule.batch else None)


def _existing_checkin(registration, kind, obj):
    if kind == 'occurrence':
        return StudentCheckIn.objects.filter(registration=registration, occurrence=obj).first()
    return StudentCheckIn.objects.filter(registration=registration, class_session=obj).first()


def _make_token(checkin_id):
    return signing.dumps({'id': checkin_id}, salt=TOKEN_SALT)


def _read_token(token):
    try:
        return signing.loads(token, salt=TOKEN_SALT, max_age=30 * 60)['id']
    except (signing.BadSignature, KeyError, TypeError):
        return None


# ── student-facing pages (public, no login) ─────────────────────────────────

@csrf_protect
def checkin_start(request):
    setting = CheckInSetting.get()
    if not setting.is_enabled:
        return render(request, 'checkin/disabled.html')
    return render(request, 'checkin/start.html', {})


@csrf_protect
@require_POST
def checkin_lookup(request):
    setting = CheckInSetting.get()
    if not setting.is_enabled:
        return render(request, 'checkin/disabled.html')
    raw = request.POST.get('student_id', '')
    if _rate_limited(request):
        _log(request, raw, None, 'rate_limited')
        return render(request, 'checkin/error.html', {
            'message': 'Too many attempts from this device. Please wait a few minutes and try again, or ask reception for help.'})

    sid = _normalize_id(raw)
    if not sid:
        _log(request, raw, None, 'invalid_student')
        return render(request, 'checkin/error.html', {'message': 'Please enter your Student ID.', 'retry': True})

    reg = Registration.objects.filter(registration_number__iexact=sid).first()
    if not reg:
        _log(request, raw, None, 'invalid_student')
        return render(request, 'checkin/error.html', {
            'message': 'Student ID not found. Please check your Student ID.', 'retry': True})
    if reg.student_status not in ('active',):
        _log(request, raw, reg, 'inactive_student')
        return render(request, 'checkin/error.html', {
            'message': 'Your student account is currently inactive. Please contact Orbit Training Center.'})

    now = _now()
    candidates = _today_candidates(reg)
    early = dt.timedelta(minutes=setting.early_window_minutes)
    match = None
    all_ended = bool(candidates)
    for _t, kind, obj in candidates:
        start = dt.datetime.combine(now.date(), obj.start_time, tzinfo=DUBAI)
        end = dt.datetime.combine(now.date(), obj.end_time, tzinfo=DUBAI)
        if now <= end:
            all_ended = False
        # Early login is allowed from (start - early_window); once checked in, attendance
        # covers the full scheduled window regardless of when the student arrives, so the
        # cutoff for CHECKING IN is simply the scheduled end, not the start (spec §22-23).
        if (start - early) <= now <= end:
            match = (kind, obj)
            break
    if not match:
        if not candidates:
            _log(request, raw, reg, 'no_schedule')
            return render(request, 'checkin/error.html', {
                'message': 'You do not have a scheduled training session at this time.'})
        if all_ended:
            _log(request, raw, reg, 'session_completed')
            return render(request, 'checkin/error.html', {
                'message': 'Your scheduled class has already ended. Attendance cannot be started for this session.'})
        nxt = candidates[0][2]
        _log(request, raw, reg, 'no_schedule')
        return render(request, 'checkin/error.html', {
            'message': f'Your next class starts at {nxt.start_time:%I:%M %p}. You can check in from '
                       f'{(dt.datetime.combine(now.date(), nxt.start_time, tzinfo=DUBAI) - early).strftime("%I:%M %p")}.'})

    kind, obj = match
    existing = _existing_checkin(reg, kind, obj)
    if existing and existing.status == 'confirmed':
        _log(request, raw, reg, 'already_confirmed')
        return render(request, 'checkin/already.html', {'c': existing})

    trainer = obj.trainer
    course = _course_of(kind, obj)
    if existing:
        c = existing
    else:
        try:
            c = StudentCheckIn.objects.create(
                registration=reg, occurrence=obj if kind == 'occurrence' else None,
                class_session=obj if kind == 'class_session' else None, course=course, trainer=trainer,
                scheduled_date=obj.date if kind == 'occurrence' else obj.date,
                scheduled_start=obj.start_time, scheduled_end=obj.end_time,
                ip_address=_client_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', '')[:300])
        except IntegrityError:
            c = _existing_checkin(reg, kind, obj)
    _log(request, raw, reg, 'success')
    return render(request, 'checkin/review.html', {
        'c': c, 'token': _make_token(c.pk), 'trainer': trainer, 'course': course,
        'login_time': c.login_at.astimezone(DUBAI)})


@csrf_protect
@require_POST
def checkin_confirm(request):
    cid = _read_token(request.POST.get('token', ''))
    if not cid:
        return render(request, 'checkin/error.html', {
            'message': 'This confirmation has expired. Please enter your Student ID again.', 'retry': True})
    c = get_object_or_404(StudentCheckIn, pk=cid)
    if c.status == 'confirmed':
        return render(request, 'checkin/already.html', {'c': c})
    now = _now()
    end = dt.datetime.combine(c.scheduled_date, c.scheduled_end, tzinfo=DUBAI)
    if now > end:
        return render(request, 'checkin/error.html', {
            'message': 'Your scheduled class has already ended. Attendance cannot be started for this session.'})
    c.status, c.confirmed_at = 'confirmed', timezone.now()
    c.save(update_fields=['status', 'confirmed_at'])
    return render(request, 'checkin/success.html', {'c': c})


# ── admin visibility (Trainers & Batches area) ──────────────────────────────

@login_required
def checkin_admin_list(request):
    today = eng.dubai_today()
    date_str = request.GET.get('date', '') or today.isoformat()
    try:
        the_date = dt.date.fromisoformat(date_str)
    except ValueError:
        the_date = today
    qs = StudentCheckIn.objects.filter(scheduled_date=the_date).select_related('registration', 'course', 'trainer')
    if request.GET.get('trainer'):
        qs = qs.filter(trainer_id=request.GET['trainer'])
    rows = list(qs)
    for r in rows:
        r.disp = r.display_status()
    from .models import Trainer
    return render(request, 'checkin/admin_list.html', {
        'rows': rows, 'the_date': the_date, 'today': today, 'trainers': Trainer.objects.filter(is_active=True),
        'can_edit': can_manage(request.user), 'setting': CheckInSetting.get(),
        'confirmed': sum(1 for r in rows if r.status == 'confirmed'), 'total': len(rows)})


@login_required
@require_POST
def checkin_settings_save(request):
    from django.contrib import messages
    from django.contrib.auth.decorators import user_passes_test
    if not (request.user.is_superuser or request.user.is_staff or getattr(getattr(request.user, 'profile', None), 'role', '') == 'admin'):
        messages.error(request, 'Only an admin can change this.')
        return redirect('checkin_admin_list')
    s = CheckInSetting.get()
    s.is_enabled = request.POST.get('is_enabled') == 'on'
    try:
        s.early_window_minutes = max(0, int(request.POST.get('early_window_minutes', 60)))
        s.rate_limit_attempts = max(1, int(request.POST.get('rate_limit_attempts', 8)))
        s.rate_limit_minutes = max(1, int(request.POST.get('rate_limit_minutes', 10)))
    except (TypeError, ValueError):
        messages.error(request, 'Settings must be numbers.')
        return redirect('checkin_admin_list')
    s.save()
    messages.success(request, 'Check-in settings saved.')
    return redirect('checkin_admin_list')


@login_required
@require_POST
def checkin_mark_no_show(request, pk):
    if not can_manage(request.user):
        from django.contrib import messages
        messages.error(request, 'Only admins and the sales manager can do that.')
        return redirect('checkin_admin_list')
    c = get_object_or_404(StudentCheckIn, pk=pk)
    if c.status != 'confirmed':
        c.status, c.marked_no_show_by = 'no_show', request.user
        c.save(update_fields=['status', 'marked_no_show_by'])
    return redirect(request.META.get('HTTP_REFERER') or 'checkin_admin_list')
