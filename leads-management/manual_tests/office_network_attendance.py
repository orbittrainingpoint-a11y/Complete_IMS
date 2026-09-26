import sys, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import User, AttendanceSession, AttendanceBreak, OfficeNetwork
from werkzeug.security import generate_password_hash
import attendance as att

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

app.config['WTF_CSRF_ENABLED'] = False
OFFICE, HOME = '217.165.113.138', '2.51.71.141'
HTML = {'Accept': 'text/html'}
with app.app_context():
    OfficeNetwork.query.delete(); db.session.commit(); att.office_networks(force=True)
    ids = {}
    for name, role in (('zz_off_sales', 'consultant'), ('zz_off_admin', 'admin')):
        u = User(username=name, email=name + '@x.test', password_hash=generate_password_hash('pw'), role=role); db.session.add(u); db.session.commit(); ids[name] = u.id

def client(user, ip):
    c = app.test_client()
    c.environ_base['HTTP_X_FORWARDED_FOR'] = ip
    c.post('/login', data={'username': user, 'password': 'pw'})
    c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    return c
def sessions(uid):
    with app.app_context():
        return AttendanceSession.query.filter_by(user_id=uid).order_by(AttendanceSession.id).all()
def wipe(uid):
    with app.app_context():
        for s in AttendanceSession.query.filter_by(user_id=uid).all():
            AttendanceBreak.query.filter_by(session_id=s.id).delete(); db.session.delete(s)
        db.session.commit()

try:
    sid = ids['zz_off_sales']
    print('1. No office network configured -> works everywhere (nobody locked out)')
    c = client('zz_off_sales', HOME); check('session recorded from any IP', len(sessions(sid)) == 1)
    c.get('/logout'); wipe(sid)

    print('\n2. Admin sets the office network from the office WiFi')
    a = client('zz_off_admin', OFFICE)
    r = a.get('/attendance/office-network'); check('admin page opens and shows the IP', r.status_code == 200 and OFFICE in r.data.decode())
    a.post('/attendance/office-network', data={'action': 'add_current', 'label': 'Office WiFi'})
    with app.app_context(): nets = [n.cidr for n in OfficeNetwork.query.all()]
    check('current IP saved as the office network', nets == [OFFICE], nets)
    r = a.post('/attendance/office-network', data={'action': 'add_manual', 'cidr': 'not-an-ip'});
    with app.app_context(): check('invalid address rejected', OfficeNetwork.query.count() == 1)
    a.post('/attendance/office-network', data={'action': 'add_manual', 'cidr': '198.51.100.0/28', 'label': 'Branch'})
    with app.app_context(): check('range can be added', OfficeNetwork.query.count() == 2)
    s_ = client('zz_off_sales', OFFICE); r = s_.get('/attendance/office-network'); check('non-admin cannot open the page', r.status_code == 302)
    s_.get('/logout'); wipe(sid)

    print('\n3. Login away from the office')
    h = client('zz_off_sales', HOME)
    check('login works', h.get('/leads', headers={**HTML}).status_code == 200)
    check('NO attendance session recorded', len(sessions(sid)) == 0, len(sessions(sid)))
    page = h.get('/leads', headers=HTML).data.decode()
    check('"You are out of office" banner rendered on the page', page.count('id="oooBanner"') == 2, page.count('id="oooBanner"'))
    r = h.post('/attendance/heartbeat', json={'active': True}).get_json()
    check('heartbeat says out_of_office and records nothing', r.get('out_of_office') is True and len(sessions(sid)) == 0, r)
    h.post('/attendance/break/start', json={'type': 'manual'})
    check('break cannot be started away from the office', len(sessions(sid)) == 0)

    print('\n4. Range match + arriving at the office later the same day')
    o = client('zz_off_sales', '198.51.100.9')   # inside the /28
    check('address inside the office range counts as office', len(sessions(sid)) >= 1)
    check('no banner in the office', o.get('/leads', headers=HTML).data.decode().count('id="oooBanner"') == 1)
    r = o.post('/attendance/heartbeat', json={'active': True}).get_json(); check('heartbeat normal in office', r.get('out_of_office') is False, r)
    o.get('/logout'); wipe(sid)
    h2 = client('zz_off_sales', HOME); check('still nothing recorded away', len(sessions(sid)) == 0)
    h2.environ_base['HTTP_X_FORWARDED_FOR'] = OFFICE
    h2.get('/leads', headers=HTML)
    check('first request from the office starts the session', len(sessions(sid)) == 1)
    print('\n5. Logging out from outside keeps the office end time')
    with app.app_context():
        s = AttendanceSession.query.filter_by(user_id=sid, status='open').first(); s.last_activity_at = dt.datetime.utcnow() - dt.timedelta(hours=2); s.login_at = s.last_activity_at - dt.timedelta(hours=6); db.session.commit(); last = s.last_activity_at
    h2.environ_base['HTTP_X_FORWARDED_FOR'] = HOME
    h2.get('/logout')
    with app.app_context():
        s = AttendanceSession.query.filter_by(user_id=sid).order_by(AttendanceSession.id.desc()).first()
        check('day closed at last office activity, not at home logout time', s.status == 'closed' and abs((s.logout_at - last).total_seconds()) < 2, (s.status, s.logout_at, last))
    print('\n6. Admins are not affected')
    ah = client('zz_off_admin', HOME); r = ah.get('/leads', headers=HTML)
    check('admin from anywhere: no banner, no session', r.status_code == 200 and 'id="oooBanner"' not in r.data.decode() and len(sessions(ids['zz_off_admin'])) == 0)
    print('\n7. Remove network')
    with app.app_context(): nid = OfficeNetwork.query.first().id
    a.post('/attendance/office-network', data={'action': 'delete', 'id': nid})
    with app.app_context(): check('network removed', OfficeNetwork.query.count() == 1)
finally:
    with app.app_context():
        OfficeNetwork.query.delete()
        for name in ('zz_off_sales', 'zz_off_admin'):
            u = User.query.filter_by(username=name).first()
            if u:
                for s in AttendanceSession.query.filter_by(user_id=u.id).all():
                    AttendanceBreak.query.filter_by(session_id=s.id).delete(); db.session.delete(s)
                db.session.delete(u)
        db.session.commit(); att.office_networks(force=True)
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
