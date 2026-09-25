"""Attendance rules for salespeople: login -> mandatory logout, idle/manual breaks,
and next-day "did not log out" handling (day becomes unpaid leave unless an admin excuses it).

Rules live here (not in routes.py) so the request hooks and the background scheduler
apply exactly the same logic.
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import AttendanceSession, AttendanceBreak

IDLE_LIMIT = timedelta(minutes=15)
TRACKED_ROLES = ('consultant', 'sales_manager')
DUBAI_TZ = timezone(timedelta(hours=4))


def is_tracked(user):
    return bool(user and user.is_authenticated and user.role in TRACKED_ROLES)


def dubai_today():
    return datetime.now(DUBAI_TZ).date()


def _open_break(session_id):
    return AttendanceBreak.query.filter_by(session_id=session_id, end_at=None).first()


def _close_open_break(session_id, at):
    br = _open_break(session_id)
    if br:
        br.end_at = max(at, br.start_at)
    return br


def settle_stale_sessions(user_id=None):
    """Any session still open from a previous Dubai date was never logged out:
    the day becomes unpaid leave and the user gets a one-time warning. Returns count."""
    q = AttendanceSession.query.filter(
        AttendanceSession.status == 'open',
        AttendanceSession.work_date < dubai_today(),
    )
    if user_id is not None:
        q = q.filter(AttendanceSession.user_id == user_id)
    count = 0
    for s in q.all():
        _close_open_break(s.id, s.last_activity_at)
        s.status = 'unpaid_leave'
        s.logout_type = 'forced_next_day'
        s.logout_at = s.last_activity_at
        s.warning_pending = True
        count += 1
    if count:
        db.session.commit()
    return count


def ensure_session(user):
    """Today's open session for this user, creating one if needed (after settling stale ones)."""
    settle_stale_sessions(user.id)
    today = dubai_today()
    now = datetime.utcnow()
    s = AttendanceSession.query.filter_by(user_id=user.id, work_date=today, status='open').first()
    if s:
        return s
    s = AttendanceSession(user_id=user.id, work_date=today, login_at=now, last_activity_at=now, status='open')
    db.session.add(s)
    db.session.commit()
    return s


def dubai_day_start_utc():
    """Start of today's Dubai calendar day as a naive UTC datetime."""
    today = dubai_today()
    return datetime(today.year, today.month, today.day) - timedelta(hours=4)


def pending_comment_leads(user_id):
    """Leads this person added, or was assigned, today that still have no comment from them
    today. They cannot log out until this list is empty."""
    from sqlalchemy import or_
    from models import Lead, LeadInteraction, LeadReassignment
    start = dubai_day_start_utc()
    ids = {r.lead_id for r in LeadReassignment.query.filter(
        LeadReassignment.to_user_id == user_id, LeadReassignment.assigned_at >= start)}
    ids = {l.id for l in Lead.query.filter(Lead.id.in_(ids), Lead.assigned_to == user_id)} if ids else set()
    ids |= {l.id for l in Lead.query.filter(
        or_(Lead.added_by == user_id, Lead.created_by_id == user_id), Lead.created_at >= start)}
    if not ids:
        return []
    done = {i.lead_id for i in LeadInteraction.query.filter(
        LeadInteraction.lead_id.in_(ids), LeadInteraction.created_by_id == user_id,
        LeadInteraction.interaction_date >= start)}
    return Lead.query.filter(Lead.id.in_(ids - done)).order_by(Lead.created_at).all()


def close_session(user_id, logout_type='manual', note=None):
    now = datetime.utcnow()
    s = AttendanceSession.query.filter_by(user_id=user_id, status='open').order_by(AttendanceSession.id.desc()).first()
    if not s:
        return None
    _close_open_break(s.id, now)
    s.logout_at = now
    s.status = 'closed'
    s.logout_type = logout_type
    if note:
        s.admin_note = note[:300]
    db.session.commit()
    return s


def record_activity(session):
    """Human activity heartbeat. If the user was silent for more than the idle limit
    (laptop asleep, walked away with the tab closed) the silent gap counts as a break."""
    now = datetime.utcnow()
    if _open_break(session.id):
        return
    if now - session.last_activity_at > IDLE_LIMIT:
        db.session.add(AttendanceBreak(
            session_id=session.id, user_id=session.user_id,
            start_at=session.last_activity_at, end_at=now, break_type='auto_idle',
        ))
    session.last_activity_at = now
    db.session.commit()


def start_break(session, break_type):
    """Manual breaks start now; idle breaks start from the last real activity so the
    15 idle minutes are counted as break time."""
    if _open_break(session.id):
        return _open_break(session.id)
    now = datetime.utcnow()
    start = session.last_activity_at if break_type == 'auto_idle' else now
    br = AttendanceBreak(session_id=session.id, user_id=session.user_id,
                         start_at=min(start, now), break_type=break_type)
    db.session.add(br)
    db.session.commit()
    return br


def end_break(session, worked=False):
    """End the running break. `worked` = the person says they were actually working (on a
    call / with a lead) while the CRM saw no activity: the time is not counted as a break,
    but it is kept and shown to managers as a claim."""
    now = datetime.utcnow()
    br = _close_open_break(session.id, now)
    if br and worked and br.break_type == 'auto_idle':
        br.break_type = 'idle_worked'
    session.last_activity_at = now
    db.session.commit()
    return br


def session_minutes(s, now=None):
    """(span, break, net) minutes for one session."""
    now = now or datetime.utcnow()
    end = s.logout_at or (s.last_activity_at if s.status != 'open' else now)
    span = max(0.0, (end - s.login_at).total_seconds() / 60)
    brk = 0.0
    for b in s.breaks:
        if b.break_type == 'idle_worked':
            continue
        b_end = b.end_at or end
        brk += max(0.0, (b_end - b.start_at).total_seconds() / 60)
    brk = min(brk, span)
    return round(span), round(brk), round(span - brk)


def fmt_minutes(m):
    m = int(m or 0)
    return f'{m // 60}h {m % 60:02d}m'
