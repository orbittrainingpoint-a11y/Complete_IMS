"""The ERP's student check-in asks this endpoint whether a given IP is on the office WiFi,
so in-person attendance trusts the exact same ranges staff attendance already uses (one
source of truth). Covers: HMAC auth, a matching IP, a non-matching IP, and "no networks
configured -> everywhere counts as office" (same policy as staff attendance)."""
import sys
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import OfficeNetwork
import routes

OK = FAIL = 0
def check(l, c, x=''):
    global OK, FAIL
    if c: OK += 1; print('  ok  ', l)
    else: FAIL += 1; print('  FAIL', l, x)

SECRET = routes._SSO_SECRET
c = app.test_client()

with app.app_context():
    before_ids = [n.id for n in OfficeNetwork.query.all()]
    made = []
    try:
        print('1. Unauthorized without the right bearer token')
        r = c.get('/api/internal/office-check?ip=1.2.3.4')
        check('401 with no Authorization header', r.status_code == 401)
        r = c.get('/api/internal/office-check?ip=1.2.3.4', headers={'Authorization': 'Bearer wrong'})
        check('401 with the wrong token', r.status_code == 401)

        net = OfficeNetwork(cidr='203.0.113.0/24', label='ZZ Test Office Range')
        db.session.add(net); db.session.commit(); made.append(net.id)
        routes.att.office_networks(force=True)

        print('\n2. Matching IP -> in_office true')
        r = c.get('/api/internal/office-check?ip=203.0.113.50', headers={'Authorization': f'Bearer {SECRET}'})
        check('200 + in_office true', r.status_code == 200 and r.get_json()['in_office'] is True, r.get_json())

        print('\n3. Non-matching IP -> in_office false')
        r = c.get('/api/internal/office-check?ip=8.8.8.8', headers={'Authorization': f'Bearer {SECRET}'})
        check('200 + in_office false', r.status_code == 200 and r.get_json()['in_office'] is False, r.get_json())

        print('\n4. No networks configured at all -> everywhere counts as office')
        OfficeNetwork.query.filter(OfficeNetwork.id.in_(made)).delete(synchronize_session=False)
        db.session.commit(); routes.att.office_networks(force=True)
        if not OfficeNetwork.query.count():
            r = c.get('/api/internal/office-check?ip=8.8.8.8', headers={'Authorization': f'Bearer {SECRET}'})
            check('in_office true when nothing is configured', r.get_json()['in_office'] is True, r.get_json())
        else:
            print('  (skipped — other real office networks exist in this DB, cannot test the empty case)')
    finally:
        OfficeNetwork.query.filter(OfficeNetwork.id.in_(made)).delete(synchronize_session=False)
        db.session.commit()
        routes.att.office_networks(force=True)
        print(f'\nRESULT: {OK} passed, {FAIL} failed')
