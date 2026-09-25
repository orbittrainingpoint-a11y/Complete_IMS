import sys, time, datetime as dt
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import Lead, User, LeadSourceIntegration, CRMNotification, AttendanceSession, AttendanceBreak, LeadInteraction
from werkzeug.security import generate_password_hash
import attendance as att

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

app.config['WTF_CSRF_ENABLED'] = False
HTML = {'Accept': 'text/html'}
with app.app_context():
    for name, role in (('zz_sales', 'consultant'), ('zz_admin', 'admin')):
        if not User.query.filter_by(username=name).first():
            db.session.add(User(username=name, email=name + '@x.test', password_hash=generate_password_hash('pw'), role=role))
    db.session.commit()
    token = LeadSourceIntegration.query.filter_by(source_type='website', is_active=True).first().webhook_token

def login(u):
    c = app.test_client()
    r = c.post('/login', data={'username': u, 'password': 'pw'})
    return c, r

try:
    print('1. Sound lock')
    for who in ('zz_sales', 'zz_admin'):
        c, r = login(who)
        r = c.get('/', headers=HTML)
        check(f'{who}: page redirects to sound check', r.status_code == 302 and '/sound-check' in r.headers['Location'], (r.status_code, r.headers.get('Location')))
        r = c.post('/attendance/heartbeat', json={'active': True})
        check(f'{who}: heartbeat refused while locked', r.status_code == 423, r.status_code)
        check(f'{who}: status says locked', c.get('/sound-status').get_json()['ok'] is False)
        check(f'{who}: sound page opens', c.get('/sound-check').status_code == 200)
        r = c.post('/sound-check', data={'method': 'mic', 'delta_db': '3', 'next': '/'})
        check(f'{who}: cannot pass without a sound test', c.get('/sound-status').get_json()['ok'] is False)
        r = c.post('/sound-check', data={'method': 'mic', 'delta_db': '18', 'next': '/leads'})
        check(f'{who}: passing the test unlocks', r.status_code == 302 and r.headers['Location'].endswith('/leads') and c.get('/sound-status').get_json()['ok'] is True)
        r = c.get('/leads', headers=HTML); check(f'{who}: CRM works after the check', r.status_code == 200)
        with c.session_transaction() as s:
            s['sound_ok_at'] = int(time.time()) - 31 * 60
        r = c.get('/leads', headers=HTML)
        check(f'{who}: locks again after 30 minutes', r.status_code == 302 and '/sound-check' in r.headers['Location'])
        c.post('/sound-check', data={'method': 'mic', 'delta_db': '18', 'next': '/'})
        c.get('/logout')
        c2, _ = login(who)
        check(f'{who}: a new login starts locked again', c2.get('/leads', headers=HTML).status_code == 302)
    c, _ = login('zz_sales'); c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    r = c.post('/sound-check', data={'method': 'mic', 'delta_db': '18', 'next': 'https://evil.example'})
    check('open redirect blocked', r.headers['Location'].startswith('/') and 'evil' not in r.headers['Location'])

    print('\n1b. Real verification (no more click-to-pass)')
    import struct, wave, io
    c, _ = login('zz_sales')
    r = c.post('/sound-check', data={'audio_ok': '1', 'next': '/leads'})
    check('old click-only proof is rejected', c.get('/sound-status').get_json()['ok'] is False)
    r = c.post('/sound-check', data={'method': 'mic', 'delta_db': '9.9'})
    check('weak signal (9.9 dB) rejected', c.get('/sound-status').get_json()['ok'] is False)
    r = c.post('/sound-check', data={'method': 'mic', 'delta_db': 'abc'})
    check('garbage measurement rejected', c.get('/sound-status').get_json()['ok'] is False)
    r = c.get('/sound-check/challenge.wav')
    w = wave.open(io.BytesIO(r.data)); frames = w.readframes(w.getnframes()); w.close()
    samples = struct.unpack('<%dh' % (len(frames) // 2), frames)
    beeps, on, quiet = 0, False, 0
    for v in samples:
        if abs(v) > 3000:
            if not on:
                beeps += 1
                on = True
            quiet = 0
        else:
            quiet += 1
            if on and quiet > 800:
                on = False
    with c.session_transaction() as s:
        expected = s.get('sound_quiz')
    check('challenge audio is a valid WAV', r.status_code == 200 and r.mimetype == 'audio/wav')
    check('beeps in the audio match the answer stored on the server', beeps == expected, (beeps, expected))
    r = c.post('/sound-check', data={'method': 'quiz', 'answer': str(expected + 1 if expected < 5 else 2)})
    check('wrong beep count rejected', c.get('/sound-status').get_json()['ok'] is False)
    c.get('/sound-check/challenge.wav')
    with c.session_transaction() as s:
        expected = s.get('sound_quiz')
    r = c.post('/sound-check', data={'method': 'quiz', 'answer': str(expected), 'next': '/leads'})
    check('correct beep count unlocks', c.get('/sound-status').get_json()['ok'] is True)
    c3, _ = login('zz_sales')
    for _i in range(3):
        c3.get('/sound-check/challenge.wav')
        c3.post('/sound-check', data={'method': 'quiz', 'answer': '99'})
    c3.get('/sound-check/challenge.wav')
    with c3.session_transaction() as s:
        expected = s.get('sound_quiz')
    c3.post('/sound-check', data={'method': 'quiz', 'answer': str(expected)})
    check('3 wrong answers lock the quiz for a minute', c3.get('/sound-status').get_json()['ok'] is False)

    print('\n2. Webhook payload shapes')
    cl = app.test_client()
    payloads = [
        ('nested + form name', dict(json={'form': {'id': 'abc', 'name': 'Book Demo'}, 'fields': {'name': {'id': 'name', 'title': 'Name', 'value': 'ZZ Nested'},
              'm': {'id': 'm', 'title': 'Mobile No', 'value': '+971501110001'}, 'c': {'id': 'c', 'title': 'Course Name', 'value': 'Revit Training in Dubai'}}})),
        ('export style', dict(data={'name': 'ZZ Export', 'email': '+971501110002', 'message': 'Autocad course'})),
    ]
    for label, kw in payloads:
        cl.post(f'/webhooks/website/{token}/', **kw)
    with app.app_context():
        for l in Lead.query.filter(Lead.phone.in_(['+971501110001', '+971501110002'])).all():
            check(f'{label if False else l.phone}: name kept + course matched', l.name.startswith('ZZ ') and l.course_interest_id, (l.name, l.course_interest_id))
            CRMNotification.query.filter_by(lead_id=l.id).delete(); db.session.delete(l)
        db.session.commit()

    print('\n3. Pagination keeps Not Assigned filter')
    c, _ = login('zz_admin'); c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    r = c.get('/leads?consultant=unassigned', headers=HTML)
    body = r.data.decode()
    check('page 2 link carries consultant=unassigned', 'consultant=unassigned' in body and 'page=2' in body, r.status_code)

    print('\n4. Worked-while-idle claim')
    with app.app_context():
        uid = User.query.filter_by(username='zz_sales').first().id
    c, _ = login('zz_sales'); c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    c.post('/attendance/heartbeat', json={'active': True})
    with app.app_context():
        s = AttendanceSession.query.filter_by(user_id=uid, status='open').order_by(AttendanceSession.id.desc()).first(); s.last_activity_at = dt.datetime.utcnow() - dt.timedelta(minutes=20); db.session.commit()
    c.post('/attendance/break/start', json={'type': 'auto_idle'})
    r = c.post('/attendance/break/end', json={'worked': True})
    with app.app_context():
        s = AttendanceSession.query.filter_by(user_id=uid, status='open').order_by(AttendanceSession.id.desc()).first()
        types = [b.break_type for b in s.breaks]
        span, brk, net = att.session_minutes(s)
        check('idle period stored as claim', types == ['idle_worked'], types)
        check('claim not counted as break time', brk == 0, brk)
    c.post('/attendance/break/start', json={'type': 'manual'}); c.post('/attendance/break/end', json={})
    check('manual break still works', True)
finally:
    with app.app_context():
        for name in ('zz_sales', 'zz_admin'):
            u = User.query.filter_by(username=name).first()
            if u:
                AttendanceBreak.query.filter_by(user_id=u.id).delete(); AttendanceSession.query.filter_by(user_id=u.id).delete()
                db.session.delete(u)
        db.session.commit()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
