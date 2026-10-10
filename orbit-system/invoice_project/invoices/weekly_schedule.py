"""Weekly schedule reminder — every Monday, each active student with at least one class
this week gets an email listing the week's sessions (date/time/course/trainer/mode), pulled
from the exact same ScheduleOccurrence/Batch/ClassSession data the trainer schedule and the
student check-in system already use. See management command send_weekly_schedule_emails."""
import datetime as dt

from .models import BatchStudent, ClassSession, ScheduleOccurrence

DUBAI = dt.timezone(dt.timedelta(hours=4))
SITE_URL = 'https://orbittraining.online'


def dubai_today():
    return dt.datetime.now(DUBAI).date()


def week_range(today=None):
    """Monday..Sunday for the week containing `today` (defaults to Dubai-local today)."""
    today = today or dubai_today()
    monday = today - dt.timedelta(days=today.weekday())
    return monday, monday + dt.timedelta(days=6)


def _mode_of(kind, obj, registration):
    if kind == 'class_session':
        return obj.mode
    rule = obj.rule
    if rule.schedule_type == 'batch' and rule.batch:
        return rule.batch.mode
    return registration.class_type


def _course_of(kind, obj):
    if kind == 'class_session':
        return obj.course
    rule = obj.rule
    return rule.course or (rule.batch.course if rule.batch else None)


def week_sessions(registration, monday, sunday):
    """Every session this student has Monday..Sunday, as plain dicts (no live model
    objects crossing into the email template)."""
    rows = []
    for occ in (ScheduleOccurrence.objects.filter(date__range=(monday, sunday), status__in=('scheduled', 'rescheduled'))
                .filter(rule__registration=registration, rule__schedule_type='individual')
                .select_related('rule', 'rule__course', 'trainer')):
        rows.append(('occurrence', occ))
    batch_ids = list(BatchStudent.objects.filter(registration=registration, status='active').values_list('batch_id', flat=True))
    if batch_ids:
        for occ in (ScheduleOccurrence.objects.filter(date__range=(monday, sunday), status__in=('scheduled', 'rescheduled'),
                                                       rule__batch_id__in=batch_ids, rule__schedule_type='batch')
                    .select_related('rule', 'rule__batch', 'rule__batch__course', 'trainer')):
            rows.append(('occurrence', occ))
    for cs in ClassSession.objects.filter(registration=registration, date__range=(monday, sunday), status='scheduled').select_related('course', 'trainer'):
        rows.append(('class_session', cs))

    out = []
    for kind, obj in rows:
        course = _course_of(kind, obj)
        out.append({
            'date': obj.date,
            'start_time': obj.start_time,
            'end_time': obj.end_time,
            'course_name': course.name if course else 'Training session',
            'trainer_name': obj.trainer.name if obj.trainer else '',
            'mode': _mode_of(kind, obj, registration),
        })
    out.sort(key=lambda r: (r['date'], r['start_time']))
    return out


def group_by_day(sessions):
    """[{'date', 'label', 'sessions'}] in date order — only days that actually have a
    session, so the email doesn't show empty days."""
    by_date = {}
    for s in sessions:
        by_date.setdefault(s['date'], []).append(s)
    return [{'date': d, 'label': d.strftime('%A, %d %b'), 'sessions': by_date[d]} for d in sorted(by_date)]
