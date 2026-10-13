"""Online-class attendance via the LMS's own login tracker (lms.orbittraining.online — a
separate Node/Postgres app on the same VPS, with no prior link to the ERP). For each online
session that has just ended, a student counts as attended if they logged into the LMS at any
point between (scheduled start - grace) and scheduled end. Matched to the ERP's Registration
by email (the one ID both systems already collect). Recorded as a StudentCheckIn, same table
the in-person Wi-Fi check-in uses, so admins see both in one place (/schedule-checkins/).

Read-only against the LMS database; never writes to it. Configured via settings.LMS_DB — unset
in local dev (no LMS Postgres exists there), so sync_online_attendance() is a clean no-op until
production's .env.erp sets LMS_DB_USER/LMS_DB_PASSWORD.
"""
import datetime as dt
import logging

from django.conf import settings
from django.utils import timezone

from .models import BatchStudent, ClassSession, Registration, ScheduleOccurrence, StudentCheckIn

logger = logging.getLogger(__name__)

DUBAI = dt.timezone(dt.timedelta(hours=4))
LOGIN_GRACE_MINUTES = 15  # a login up to this long before the scheduled start still counts


def _lms_connect():
    """A connection to the LMS's Postgres, or None if not configured / unreachable. Caller
    is responsible for closing it."""
    cfg = getattr(settings, 'LMS_DB', {})
    if not cfg.get('user'):
        return None
    try:
        import psycopg2
        return psycopg2.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                                password=cfg['password'], dbname=cfg['database'], connect_timeout=5)
    except Exception:
        logger.exception('Could not connect to the LMS database')
        return None


def _lms_logged_in_during(conn, email, start_utc, end_utc):
    """True if this email's LMS account has a 'login' activity_logs row in [start_utc, end_utc]."""
    if not email:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM activity_logs al JOIN users u ON u.id = al.user_id
                   WHERE lower(u.email) = lower(%s) AND al.action = 'login'
                     AND al.created_at >= %s AND al.created_at <= %s LIMIT 1""",
                (email.strip(), start_utc, end_utc))
            return cur.fetchone() is not None
    except Exception:
        logger.exception('LMS login lookup failed for %s', email)
        return False


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


def _ended_candidates(window_start, window_end):
    """(kind, obj, registration) for every session ending in [window_start, window_end] —
    individual occurrences, batch occurrences (expanded per enrolled student), and one-off
    ClassSessions. Mirrors checkin._today_candidates / weekly_schedule.week_sessions, widened
    to a date range of ended sessions instead of "today" or "this week"."""
    out = []
    occs = (ScheduleOccurrence.objects.filter(
                date__gte=window_start.date(), date__lte=window_end.date(),
                status__in=('scheduled', 'rescheduled'))
            .select_related('rule', 'rule__course', 'rule__registration', 'rule__batch', 'rule__batch__course', 'trainer'))
    for occ in occs:
        rule = occ.rule
        end_dt = dt.datetime.combine(occ.date, occ.end_time, tzinfo=DUBAI)
        if not (window_start <= end_dt <= window_end):
            continue
        if rule.schedule_type == 'individual' and rule.registration:
            out.append(('occurrence', occ, rule.registration))
        elif rule.schedule_type == 'batch' and rule.batch:
            for bs in BatchStudent.objects.filter(batch=rule.batch, status='active').select_related('registration'):
                out.append(('occurrence', occ, bs.registration))
    for cs in (ClassSession.objects.filter(date__gte=window_start.date(), date__lte=window_end.date(),
                                           status='scheduled', registration__isnull=False)
               .select_related('course', 'trainer', 'registration')):
        end_dt = dt.datetime.combine(cs.date, cs.end_time, tzinfo=DUBAI)
        if window_start <= end_dt <= window_end:
            out.append(('class_session', cs, cs.registration))
    return out


def sync_online_attendance(now=None):
    """Check every online session that ended in the last 2 hours (and hasn't already been
    checked) against the LMS login tracker. Returns (checked, confirmed, skipped_no_lms)."""
    conn = _lms_connect()
    if conn is None:
        return 0, 0, 0
    checked = confirmed = skipped_no_email = 0
    now = now or timezone.now().astimezone(DUBAI)
    window_end = now
    window_start = now - dt.timedelta(hours=2)
    try:
        for kind, obj, reg in _ended_candidates(window_start, window_end):
            if _mode_of(kind, obj, reg) != 'online':
                continue
            existing = (StudentCheckIn.objects.filter(registration=reg, occurrence=obj).exists() if kind == 'occurrence'
                       else StudentCheckIn.objects.filter(registration=reg, class_session=obj).exists())
            if existing:
                continue
            checked += 1
            if not reg.email:
                skipped_no_email += 1
                continue
            start_dt = dt.datetime.combine(obj.date, obj.start_time, tzinfo=DUBAI) - dt.timedelta(minutes=LOGIN_GRACE_MINUTES)
            end_dt = dt.datetime.combine(obj.date, obj.end_time, tzinfo=DUBAI)
            if not _lms_logged_in_during(conn, reg.email, start_dt, end_dt):
                continue
            StudentCheckIn.objects.create(
                registration=reg, occurrence=obj if kind == 'occurrence' else None,
                class_session=obj if kind == 'class_session' else None,
                course=_course_of(kind, obj), trainer=obj.trainer,
                scheduled_date=obj.date, scheduled_start=obj.start_time, scheduled_end=obj.end_time,
                status='confirmed', confirmed_at=timezone.now(), user_agent='LMS auto-detected login')
            confirmed += 1
        return checked, confirmed, skipped_no_email
    finally:
        conn.close()
