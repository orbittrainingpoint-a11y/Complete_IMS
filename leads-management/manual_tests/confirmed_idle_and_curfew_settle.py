"""Two bug fixes, tested directly against attendance.py (no HTTP/login — after the real
9:30 PM Dubai curfew, the curfew hook itself would log a fresh test session straight back
out again, which is unrelated to what's being tested here):

1. A background tab's own heartbeat timer can be throttled by the browser for 20+ minutes;
   an unconfirmed ("assumed elsewhere") heartbeat must not retroactively turn that silent gap
   into a break, or ordinary tab-switching gets punished as idle time.
2. A session left open into the next day is only "unpaid leave" if the last real activity was
   at/after the 9:30 PM curfew. Someone who simply forgot to click Logout after a normal day
   (last activity well before curfew) must be closed as a normal Present day instead.
"""
import sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import User, AttendanceSession, AttendanceBreak
import attendance as att

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

def dubai_dt(date, hour, minute):
    """A naive UTC datetime whose Dubai-local clock reads date hour:minute."""
    return dt.datetime(date.year, date.month, date.day, hour, minute) - dt.timedelta(hours=4)

def breaks(sid):
    return [(b.break_type, round(((b.end_at or dt.datetime.utcnow()) - b.start_at).total_seconds() / 60))
            for b in AttendanceBreak.query.filter_by(session_id=sid)]

with app.app_context():
    User.query.filter_by(username='zz_curfew').delete()
    db.session.commit()
    u = User(username='zz_curfew', email='zz_curfew@x.test', password_hash='x', role='consultant')
    db.session.add(u); db.session.commit(); uid = u.id

try:
    with app.app_context():
        print('1. Unconfirmed (background-tab) heartbeat never creates a break')
        now = dt.datetime.utcnow()
        s = AttendanceSession(user_id=uid, work_date=att.dubai_today(), login_at=now - dt.timedelta(hours=2),
                              last_activity_at=now - dt.timedelta(minutes=35), status='open')
        db.session.add(s); db.session.commit(); sid = s.id
        att.record_activity(s, confirmed=False)
        check('a 35-minute gap explained by "assumed elsewhere" creates NO break', breaks(sid) == [], breaks(sid))
        s = AttendanceSession.query.get(sid)
        check('last_activity_at still moves forward (not stuck)', (dt.datetime.utcnow() - s.last_activity_at).total_seconds() < 20)

        print('\n2. Confirmed heartbeat after a real gap (e.g. laptop woke up) still counts')
        s.last_activity_at = dt.datetime.utcnow() - dt.timedelta(minutes=35)
        db.session.commit()
        att.record_activity(s, confirmed=True)
        b = breaks(sid)
        check('a confirmed 35-minute gap IS logged as a break', len(b) == 1 and b[0][0] == 'auto_idle' and 34 <= b[0][1] <= 36, b)
        AttendanceBreak.query.filter_by(session_id=sid).delete(); db.session.commit()

        print('\n3. Legacy callers (no "confirmed" argument, e.g. ERP heartbeat) default to confirmed')
        s.last_activity_at = dt.datetime.utcnow() - dt.timedelta(minutes=30)
        db.session.commit()
        att.record_activity(s)  # positional/default call, exactly as any pre-existing caller would
        check('default behaves as before (break logged)', len(breaks(sid)) == 1, breaks(sid))
        AttendanceBreak.query.filter_by(user_id=uid).delete()
        AttendanceSession.query.filter_by(user_id=uid).delete(); db.session.commit()

        print('\n4. Curfew-aware next-day settle')
        yesterday = att.dubai_today() - dt.timedelta(days=1)

        def make_stale(hour, minute):
            AttendanceSession.query.filter_by(user_id=uid, status='open').delete(); db.session.commit()
            login = dubai_dt(yesterday, 9, 0)
            last = dubai_dt(yesterday, hour, minute)
            row = AttendanceSession(user_id=uid, work_date=yesterday, login_at=login, last_activity_at=last, status='open')
            db.session.add(row); db.session.commit()
            return row.id

        sid = make_stale(19, 30)
        att.settle_stale_sessions(uid)
        s = AttendanceSession.query.get(sid)
        check('last activity well before curfew (19:30) -> closed normally, no warning',
              s.status == 'closed' and s.logout_type == 'forgot_logout' and s.warning_pending is False,
              (s.status, s.logout_type, s.warning_pending))
        check('logout time = last real activity, not settle time', s.logout_at == s.last_activity_at)

        sid2 = make_stale(21, 45)
        att.settle_stale_sessions(uid)
        s2 = AttendanceSession.query.get(sid2)
        check('last activity AT/after curfew (21:45) -> unpaid leave with a warning',
              s2.status == 'unpaid_leave' and s2.logout_type == 'forced_next_day' and s2.warning_pending is True,
              (s2.status, s2.logout_type, s2.warning_pending))

        sid3 = make_stale(21, 30)
        att.settle_stale_sessions(uid)
        s3 = AttendanceSession.query.get(sid3)
        check('exactly 9:30 PM counts as at-curfew -> unpaid leave (boundary is inclusive)', s3.status == 'unpaid_leave', s3.status)

        sid4 = make_stale(21, 29)
        att.settle_stale_sessions(uid)
        s4 = AttendanceSession.query.get(sid4)
        check('9:29 PM (one minute before curfew) -> closed normally', s4.status == 'closed', s4.status)

        print('\n5. Report row reflects the real ending, not whichever session the DB returns first')
        AttendanceSession.query.filter_by(user_id=uid).delete(); db.session.commit()
        early = AttendanceSession(user_id=uid, work_date=yesterday,
                                  login_at=dubai_dt(yesterday, 6, 14), last_activity_at=dubai_dt(yesterday, 6, 15),
                                  logout_at=dubai_dt(yesterday, 6, 15), status='closed', logout_type='manual')
        real = AttendanceSession(user_id=uid, work_date=yesterday,
                                 login_at=dubai_dt(yesterday, 6, 16), last_activity_at=dubai_dt(yesterday, 19, 33),
                                 status='open')
        db.session.add_all([early, real]); db.session.commit()
        att.settle_stale_sessions(uid)
        from routes import _attendance_rows
        sessions = AttendanceSession.query.filter_by(user_id=uid, work_date=yesterday).all()
        rows = _attendance_rows(sessions)
        check('one merged row for the day', len(rows) == 1, len(rows))
        row = rows[0]
        last_out_dubai = row['last_out'] + dt.timedelta(hours=4)
        check("last_out is the LATER session's logout (19:33 Dubai), not the mistaken 06:15", last_out_dubai.hour == 19 and last_out_dubai.minute == 33, row['last_out'])
        check('logout_type reflects the real session that actually ended the day', row['logout_type'] == 'forgot_logout', row['logout_type'])
        check('status is closed (normal Present day), not unpaid leave', row['status'] == 'closed', row['status'])

finally:
    with app.app_context():
        AttendanceBreak.query.filter_by(user_id=uid).delete()
        AttendanceSession.query.filter_by(user_id=uid).delete()
        User.query.filter_by(id=uid).delete()
        db.session.commit()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
