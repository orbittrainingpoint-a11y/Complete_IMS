import sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import User, AttendanceSession, AttendanceBreak
from werkzeug.security import generate_password_hash
import attendance as att

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

app.config['WTF_CSRF_ENABLED'] = False
with app.app_context():
    u = User(username='zz_idle', email='zz_idle@x.test', password_hash=generate_password_hash('pw'), role='consultant'); db.session.add(u); db.session.commit(); uid = u.id
try:
    c = app.test_client(); c.post('/login', data={'username': 'zz_idle', 'password': 'pw'})
    c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    def session():
        return AttendanceSession.query.filter_by(user_id=uid, status='open').order_by(AttendanceSession.id.desc()).first()
    def set_last(minutes):
        with app.app_context():
            s = session(); s.last_activity_at = dt.datetime.utcnow() - dt.timedelta(minutes=minutes)
            AttendanceBreak.query.filter_by(session_id=s.id).delete(); db.session.commit()
    def breaks():
        with app.app_context():
            return [(b.break_type, round(((b.end_at or dt.datetime.utcnow()) - b.start_at).total_seconds() / 60)) for b in AttendanceBreak.query.filter_by(session_id=session().id)]

    print('1. 20-minute rule')
    check('idle limit is 20 minutes', att.IDLE_LIMIT == dt.timedelta(minutes=20))
    c.post('/attendance/heartbeat', json={'active': True})
    set_last(19); c.post('/attendance/heartbeat', json={'active': True})
    check('a 19 minute gap is NOT a break', breaks() == [], breaks())
    set_last(25); c.post('/attendance/heartbeat', json={'active': True})
    b = breaks(); check('a 25 minute silent gap becomes a break', len(b) == 1 and b[0][0] == 'auto_idle' and 24 <= b[0][1] <= 26, b)

    print('\n2. System-wide idle (browser reports idle_seconds)')
    set_last(60)   # heartbeats stopped an hour ago in the DB, but the browser says: idle for exactly 20 min
    c.post('/attendance/break/start', json={'type': 'auto_idle', 'idle_seconds': 1200})
    b = breaks(); check('break starts 20 min ago (not 60)', len(b) == 1 and 19 <= b[0][1] <= 21, b)
    c.post('/attendance/break/end', json={})
    set_last(5); c.post('/attendance/break/start', json={'type': 'auto_idle', 'idle_seconds': 1200})
    b = breaks(); check('break never starts before the last real activity (5 min ago)', len(b) == 1 and b[0][1] <= 6, b)
    c.post('/attendance/break/end', json={})

    print('\n3. ERP -> CRM heartbeat (cross-origin)')
    pre = c.open('/attendance/heartbeat', method='OPTIONS', headers={'Origin': 'https://orbittraining.online', 'Access-Control-Request-Method': 'POST'})
    check('preflight from the ERP is allowed', pre.status_code == 204 and pre.headers.get('Access-Control-Allow-Origin') == 'https://orbittraining.online' and pre.headers.get('Access-Control-Allow-Credentials') == 'true', (pre.status_code, dict(pre.headers)))
    r = c.post('/attendance/heartbeat', json={'active': True, 'source': 'erp'}, headers={'Origin': 'https://orbittraining.online'})
    check('ERP heartbeat accepted with CORS headers', r.status_code == 200 and r.headers.get('Access-Control-Allow-Origin') == 'https://orbittraining.online', r.status_code)
    r = c.post('/attendance/heartbeat', json={'active': True}, headers={'Origin': 'https://evil.example'})
    check('other origins get no CORS access', 'Access-Control-Allow-Origin' not in r.headers)
    pre = c.open('/leads', method='OPTIONS', headers={'Origin': 'https://orbittraining.online'})
    check('no CORS on any other endpoint', 'Access-Control-Allow-Origin' not in pre.headers)
    set_last(3); c.post('/attendance/heartbeat', json={'active': True, 'source': 'erp'}, headers={'Origin': 'https://orbittraining.online'})
    with app.app_context():
        s = session(); age = (dt.datetime.utcnow() - s.last_activity_at).total_seconds()
    check('ERP activity refreshes the last-activity time', age < 20, age)
finally:
    with app.app_context():
        AttendanceBreak.query.filter_by(user_id=uid).delete(); AttendanceSession.query.filter_by(user_id=uid).delete(); User.query.filter_by(id=uid).delete(); db.session.commit()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
