"""Sales staff were ALL getting flagged "out of office" while genuinely in the office on the
same WiFi. Root cause: "Use my current network as office" stored a bare /32 (exact IP), and
the ISP silently reassigns the office's public IP from time to time - the stored value goes
stale and locks everyone out at once, even though nothing changed on their end. Covers:
(1) the stored network is now a /28 range (tolerates minor IP rotation) instead of one exact
address, (2) an IP that shifts within that /28 is still recognized as office, (3) a mass
out-of-office event (every recently-active tracked user flagged at once) triggers an admin
alert email, with a cooldown so it doesn't spam, and doesn't fire for a single remote worker."""
import sys
import time
from unittest.mock import patch

sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import User, OfficeNetwork
from werkzeug.security import generate_password_hash
import attendance as att

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

app.config['WTF_CSRF_ENABLED'] = False

OFFICE_IP = '217.165.113.138'       # the office's "current" public IP
ROTATED_IP = '217.165.113.140'      # same /28 block (.128-.143) - what the ISP might reassign it to
OUTSIDE_IP = '8.8.8.8'              # nowhere near the office block

with app.app_context():
    users = {}
    for name, role in (('zz_oon_admin', 'admin'), ('zz_oon_s1', 'consultant'), ('zz_oon_s2', 'consultant')):
        u = User.query.filter_by(username=name).first()
        if not u:
            u = User(username=name, email=name + '@x.test', password_hash=generate_password_hash('pw'), role=role)
            db.session.add(u)
        db.session.commit()
        users[name] = u
    OfficeNetwork.query.filter(OfficeNetwork.label == 'ZZ OON Test').delete()
    db.session.commit()
    att.office_networks(force=True)
    att._recent_checks.clear()
    att._last_mass_alert['t'] = 0.0


def client(username, ip=OFFICE_IP):
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': 'pw'}, environ_overrides={'REMOTE_ADDR': ip})
    c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'}, environ_overrides={'REMOTE_ADDR': ip})
    return c

try:
    print('1. "Use my current network" now stores a /28, not a bare /32')
    admin_c = client('zz_oon_admin', ip=OFFICE_IP)
    r = admin_c.post('/attendance/office-network', data={'action': 'add_current', 'label': 'ZZ OON Test'},
                     environ_overrides={'REMOTE_ADDR': OFFICE_IP})
    with app.app_context():
        net = OfficeNetwork.query.filter_by(label='ZZ OON Test').first()
        check('network row created', net is not None)
        check('stored as a /28 range, not the bare IP alone', net and net.cidr.endswith('/28'), net and net.cidr)
        check('the original IP itself still falls inside the stored range',
              net and att.ip_in_office(OFFICE_IP) is True)

        print('\n2. A same-block IP rotation (what the ISP actually does) still resolves as office')
        att.office_networks(force=True)
        check('rotated IP within the same /28 is still recognized as office', att.ip_in_office(ROTATED_IP) is True, ROTATED_IP)
        check('an unrelated IP is correctly NOT office', att.ip_in_office(OUTSIDE_IP) is False)

    print('\n3. Mass out-of-office: everyone recently active flagged at once -> one admin alert, then cooldown')
    att._recent_checks.clear()
    att._last_mass_alert['t'] = 0.0
    with patch('utils.send_email') as mock_send:
        c1 = client('zz_oon_s1', ip=OUTSIDE_IP)
        r1 = c1.post('/attendance/heartbeat', json={'active': True}, environ_overrides={'REMOTE_ADDR': OUTSIDE_IP})
        check('single out-of-office user does NOT trigger an alert (below MASS_OOO_MIN_USERS)', mock_send.call_count == 0, mock_send.call_count)

        c2 = client('zz_oon_s2', ip=OUTSIDE_IP)
        r2 = c2.post('/attendance/heartbeat', json={'active': True}, environ_overrides={'REMOTE_ADDR': OUTSIDE_IP})
        check('a second simultaneous out-of-office user DOES trigger the alert', mock_send.call_count >= 1, mock_send.call_count)
        first_call_count = mock_send.call_count

        r3 = c2.post('/attendance/heartbeat', json={'active': True}, environ_overrides={'REMOTE_ADDR': OUTSIDE_IP})
        check('re-triggering within the cooldown does not send a second alert', mock_send.call_count == first_call_count, mock_send.call_count)

    print('\n4. Not "mass" when some staff genuinely ARE in the office')
    att._recent_checks.clear()
    att._last_mass_alert['t'] = 0.0
    with patch('utils.send_email') as mock_send2:
        client('zz_oon_s1', ip=OFFICE_IP).post('/attendance/heartbeat', json={'active': True}, environ_overrides={'REMOTE_ADDR': OFFICE_IP})
        client('zz_oon_s2', ip=OUTSIDE_IP).post('/attendance/heartbeat', json={'active': True}, environ_overrides={'REMOTE_ADDR': OUTSIDE_IP})
        check('mixed in-office/out-of-office is not treated as a mass event', mock_send2.call_count == 0, mock_send2.call_count)

finally:
    with app.app_context():
        OfficeNetwork.query.filter(OfficeNetwork.label == 'ZZ OON Test').delete()
        User.query.filter(User.username.like('zz_oon_%')).delete()
        db.session.commit()
        att.office_networks(force=True)
        att._recent_checks.clear()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
