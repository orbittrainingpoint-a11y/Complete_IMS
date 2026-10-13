"""Public, no-login schedule link for trainers — one durable link per trainer (a signed
token, not a stored secret, so nothing new needs provisioning per trainer) showing only
their own sessions. Mirrors the student check-in page's "public link, no account needed"
design, scoped the other way around (by trainer instead of by student).
"""
import datetime as dt

from django.core import signing
from django.shortcuts import get_object_or_404, render

from .models import ClassSession, ScheduleOccurrence, Trainer

TOKEN_SALT = 'orbit-trainer-schedule-link-v1'
DUBAI = dt.timezone(dt.timedelta(hours=4))


def make_trainer_token(trainer_id):
    """Deterministic (not time-based) — the same trainer always gets the same link, so
    "Copy Schedule Link" shows a stable, bookmarkable URL every time, not a new one per
    click. signing.dumps()/loads() use TimestampSigner, which embeds the current time and
    so would produce a DIFFERENT string on every call — wrong for a durable link; plain
    Signer has no such expiry concept."""
    return signing.Signer(salt=TOKEN_SALT).sign(str(trainer_id))


def _read_trainer_token(token):
    try:
        return int(signing.Signer(salt=TOKEN_SALT).unsign(token))
    except (signing.BadSignature, ValueError, TypeError):
        return None


def _week_range(today):
    monday = today - dt.timedelta(days=today.weekday())
    return monday, monday + dt.timedelta(days=6)


def trainer_week_sessions(trainer, monday, sunday):
    """This trainer's own sessions in [monday, sunday], as plain dicts. ScheduleOccurrence
    already has a direct trainer FK, so this needs none of the student-matching logic
    checkin.py/weekly_schedule.py use — just filter by trainer."""
    rows = []
    occs = (ScheduleOccurrence.objects.filter(trainer=trainer, date__gte=monday, date__lte=sunday,
                                              status__in=('scheduled', 'rescheduled'))
            .select_related('rule', 'rule__course', 'rule__registration', 'rule__batch', 'rule__batch__course'))
    for occ in occs:
        rule = occ.rule
        if rule.schedule_type == 'batch' and rule.batch:
            student_label, course = rule.batch.name, (rule.course or rule.batch.course)
        elif rule.registration:
            student_label = f'{rule.registration.first_name} {rule.registration.last_name}'.strip()
            course = rule.course
        else:
            student_label, course = '-', rule.course
        rows.append({'date': occ.date, 'start_time': occ.start_time, 'end_time': occ.end_time,
                    'course_name': course.name if course else 'Training session',
                    'student_label': student_label, 'status': occ.status})
    for cs in (ClassSession.objects.filter(trainer=trainer, date__gte=monday, date__lte=sunday)
               .exclude(status='cancelled').select_related('course', 'registration')):
        student_label = (f'{cs.registration.first_name} {cs.registration.last_name}'.strip()
                         if cs.registration else (cs.student_name or '-'))
        rows.append({'date': cs.date, 'start_time': cs.start_time, 'end_time': cs.end_time,
                    'course_name': cs.course.name if cs.course else 'Training session',
                    'student_label': student_label, 'status': cs.status})
    rows.sort(key=lambda r: (r['date'], r['start_time']))
    return rows


def group_by_day(rows):
    by_date = {}
    for r in rows:
        by_date.setdefault(r['date'], []).append(r)
    return [{'date': d, 'label': d.strftime('%A, %d %b'), 'rows': by_date[d]} for d in sorted(by_date)]


def trainer_schedule_public(request, token):
    """Public page — no login. Shows this week's sessions for the trainer this token names."""
    tid = _read_trainer_token(token)
    if not tid:
        return render(request, 'trainer_schedule/public_link_invalid.html', status=404)
    trainer = get_object_or_404(Trainer, pk=tid)
    today = dt.datetime.now(DUBAI).date()
    monday, sunday = _week_range(today)
    rows = trainer_week_sessions(trainer, monday, sunday)
    return render(request, 'trainer_schedule/public_schedule.html', {
        'trainer': trainer, 'today': today, 'days': group_by_day(rows),
        'week_label': f"{monday.strftime('%d %b')} - {sunday.strftime('%d %b %Y')}",
    })
