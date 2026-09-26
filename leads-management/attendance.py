"""Attendance rules for salespeople: login -> mandatory logout, idle/manual breaks,
and next-day "did not log out" handling (day becomes unpaid leave unless an admin excuses it).

Rules live here (not in routes.py) so the request hooks and the background scheduler
apply exactly the same logic.
"""
import ipaddress
import time
from datetime import datetime, timedelta, timezone

from extensions import db
from models import AttendanceSession, AttendanceBreak

IDLE_LIMIT = timedelta(minutes=20)   # no movement for this long counts as a break
TRACKED_ROLES = ('consultant', 'sales_manager')
DUBAI_TZ = timezone(timedelta(hours=4))


_net_cache = {'t': 0.0, 'nets': None}


def office_networks(force=False):
    """Parsed office networks (cached 30 s). Empty list = the office check is switched off."""
    if not force and _net_cache['nets'] is not None and time.time() - _net_cache['t'] < 30:
        return _net_cache['nets']
    nets = []
    try:
        from models import OfficeNetwork
        for n in OfficeNetwork.query.all():
            try:
                nets.append(ipaddress.ip_network((n.cidr or '').strip(), strict=False))
            except ValueError:
                continue
    except Exception:
        db.session.rollback()
    _net_cache.update({'t': time.time(), 'nets': nets})
    return nets


def client_ip(req):
    return (req.remote_addr or '').split(',')[0].strip()


def in_office(req):
    """True when the request comes from the office network. If no office network has been
    configured yet, attendance works from everywhere (so nobody is locked out by mistake)."""
    nets = office_networks()
    if not nets:
        return True
    try:
        ip = ipaddress.ip_address(client_ip(req))
    except ValueError:
        return False
    if getattr(ip, 'ipv4_mapped', None):
        ip = ip.ipv4_mapped
    return any(ip in n for n in nets)


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


def close_session(user_id, logout_type='manual', note=None, use_last_activity=False):
    """Close today's open session. Logging out from outside the office still closes it, but the
    end time stays at the last time the person was active on the office network."""
    now = datetime.utcnow()
    s = AttendanceSession.query.filter_by(user_id=user_id, status='open').order_by(AttendanceSession.id.desc()).first()
    if not s:
        return None
    if use_last_activity:
        now = max(s.login_at, s.last_activity_at)
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


def start_break(session, break_type, idle_seconds=None):
    """Manual breaks start now. Idle breaks start when the person stopped moving: the last
    real activity, or `idle_seconds` ago if the browser reported system-wide idleness."""
    if _open_break(session.id):
        return _open_break(session.id)
    now = datetime.utcnow()
    start = now
    if break_type == 'auto_idle':
        start = session.last_activity_at
        if idle_seconds:
            start = max(start, now - timedelta(seconds=int(idle_seconds)))
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
