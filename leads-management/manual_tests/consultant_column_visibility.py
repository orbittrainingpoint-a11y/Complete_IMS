"""The Leads table and Pipeline kanban cards show which consultant a lead is assigned to.
That's useful for sales managers (who see the whole team) but should stay hidden from a plain
consultant looking at their own leads. Covers: leads.html's "Consultant" column and
pipeline.html's kcard consultant line are shown to admin/sales_manager, hidden otherwise."""
import sys
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import User, Lead
from werkzeug.security import generate_password_hash

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    users = {}
    for name, role, extra in (
        ('zz_cc_consultant', 'consultant', {}),
        ('zz_cc_manager', 'sales_manager', {'can_view_all_leads': True}),
        ('zz_cc_admin', 'admin', {}),
    ):
        u = User.query.filter_by(username=name).first()
        if not u:
            u = User(username=name, email=name + '@x.test', password_hash=generate_password_hash('pw'), role=role)
            db.session.add(u)
        for k, v in extra.items():
            setattr(u, k, v)
        db.session.commit()
        users[name] = u

    lead = Lead.query.filter_by(name='ZZ Consultant Col Lead').first()
    if not lead:
        lead = Lead(name='ZZ Consultant Col Lead', phone='+971500000777',
                    assigned_to=users['zz_cc_consultant'].id, added_by=users['zz_cc_consultant'].id, status='New')
        db.session.add(lead)
        db.session.commit()


def client(username):
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': 'pw'})
    c.post('/sound-check', data={'method': 'mic', 'delta_db': '18'})
    return c

try:
    print('1. Leads table: Consultant column')
    r = client('zz_cc_consultant').get('/leads')
    check('plain consultant does not see the Consultant column', b'<th>Consultant</th>' not in r.data)
    r = client('zz_cc_manager').get('/leads')
    check('sales_manager sees the Consultant column', b'<th>Consultant</th>' in r.data)
    check('sales_manager sees the assigned consultant\'s name', b'zz_cc_consultant' in r.data)
    r = client('zz_cc_admin').get('/leads')
    check('admin sees the Consultant column', b'<th>Consultant</th>' in r.data)

    print('\n2. Pipeline kanban: consultant line on the card')
    r = client('zz_cc_consultant').get('/pipeline')
    check('plain consultant does not see fa-user-tie consultant line', b'fa-user-tie' not in r.data)
    r = client('zz_cc_manager').get('/pipeline')
    check('sales_manager sees the consultant line on cards', b'fa-user-tie' in r.data)
    check('sales_manager sees the assigned consultant\'s name on the card', b'zz_cc_consultant' in r.data)
finally:
    with app.app_context():
        Lead.query.filter_by(name='ZZ Consultant Col Lead').delete()
        User.query.filter(User.username.like('zz_cc_%')).delete()
        db.session.commit()
    print(f'\nRESULT: {OK} passed, {FAIL} failed')
