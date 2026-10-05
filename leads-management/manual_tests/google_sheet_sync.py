"""Two-way Google Sheet sync. The Google calls are stubbed with rows shaped like the real export
(header names from the actual sheet), so this runs without the key.
Covers: not-configured state; Facebook/Instagram routing and course mapping; no-phone skip;
no duplicates across runs (by Meta id and by phone when there is no id); CRM status written to
the sheet only when it differs; lead links backfilled; re-sorted rows tracked; a failed fetch or
write recorded instead of raised, with imports kept."""
import sys
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import Lead, SheetSyncRow, SheetSyncState
import sheet_sync

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

HEADERS = ['id', 'created_time', 'adset_name', 'platform', 'full_name', 'phone_number', 'email',
           'campaign_name', 'form_name', 'lead_status']
PHONES = ['+971500009001', '+971500009002', '+971500009003', '+971500009004']

def row(num, id_, platform, name, phone, status, adset='AutoCAD Training Course', email=None):
    return {'__row': num, 'id': id_, 'platform': platform, 'full_name': name, 'phone_number': phone,
            'email': email or f'{name.split()[-1].lower()}@example.com', 'adset_name': adset,
            'campaign_name': 'ZZ Camp', 'form_name': 'ZZ Form', 'lead_status': status}

SHEET = [
    row(2, 'zz_leadgen_1', 'fb', 'ZZ Facebook Lead', 'p:' + PHONES[0], 'CREATED'),
    row(3, 'zz_leadgen_2', 'ig', 'ZZ Instagram Lead', 'p:' + PHONES[1], 'CREATED'),
    row(4, 'zz_leadgen_3', 'fb', 'ZZ No Phone', '', 'CREATED'),
]
written = []
fail_write = {'on': False}
fake_fetch = {'rows': None, 'error': None}

def stub_fetch(*a, **k):
    if fake_fetch['error']:
        raise RuntimeError(fake_fetch['error'])
    return HEADERS, [dict(r) for r in fake_fetch['rows']]

def stub_write(sheet_id, tab, key_path, headers, updates):
    if fail_write['on']:
        raise RuntimeError('Writing statuses to the sheet failed (403)')
    written.extend(updates)
    return len(updates)

real = (sheet_sync.fetch_rows, sheet_sync.write_statuses, sheet_sync.config)
def cleanup():
    lead_ids = [l.id for l in Lead.query.filter(Lead.phone.in_(PHONES)).all()]
    SheetSyncRow.query.filter(SheetSyncRow.external_id.like('zz_%') | SheetSyncRow.external_id.like('phone:+97150000900%')).delete(synchronize_session=False)
    Lead.query.filter(Lead.phone.in_(PHONES)).delete(synchronize_session=False)
    SheetSyncState.query.delete()
    db.session.commit()

with app.app_context():
    from routes import _intake_lead
    SheetSyncRow.__table__.drop(db.engine, checkfirst=True)
    SheetSyncState.__table__.drop(db.engine, checkfirst=True)
    db.create_all()
    cleanup()
    sheet_sync.write_statuses = stub_write
    sheet_sync.fetch_rows = stub_fetch
    try:
        print('1. Not configured -> recorded, nothing imported')
        sheet_sync.config = lambda: {'sheet_id': '', 'tab': 'Sheet2', 'key_path': '', 'enabled': False}
        st = sheet_sync.sync_once(_intake_lead)
        check('status not_configured', st.last_status == 'not_configured', st.last_status)

        sheet_sync.config = lambda: {'sheet_id': 'ZZTEST', 'tab': 'Sheet2', 'key_path': 'x.json', 'enabled': True}

        print('\n2. First sync imports Facebook + Instagram, skips the row without a phone')
        fake_fetch['rows'] = SHEET
        st = sheet_sync.sync_once(_intake_lead)
        check('status ok', st.last_status == 'ok', (st.last_status, st.last_error))
        check('counts: 2 imported, 1 skipped', 'imported 2' in st.last_counts and 'no phone number 1' in st.last_counts, st.last_counts)
        fb = Lead.query.filter_by(phone=PHONES[0]).first()
        ig = Lead.query.filter_by(phone=PHONES[1]).first()
        check('Facebook lead source', fb and fb.lead_source == 'Social Media (Facebook)', fb and fb.lead_source)
        check('Instagram lead source', ig and ig.lead_source == 'Social Media (Instagram)', ig and ig.lead_source)
        check('adset_name matched to the course', fb is not None and fb.course_interest_id is not None, fb and fb.course_text)
        link = SheetSyncRow.query.filter_by(external_id='zz_leadgen_1').first()
        check('row linked to its lead and remembers its sheet row', link and link.lead_id == fb.id and link.row_number == 2)
        check('no-phone row not imported', Lead.query.filter_by(email='zz.phone@example.com').first() is None
              and SheetSyncRow.query.filter_by(external_id='zz_leadgen_3').first() is None)

        print('\n3. Re-running never duplicates')
        before = Lead.query.filter(Lead.phone.in_(PHONES)).count()
        st = sheet_sync.sync_once(_intake_lead)
        check('no new leads on re-run', before == Lead.query.filter(Lead.phone.in_(PHONES)).count())
        check('re-run reports known rows', 'already known 2' in st.last_counts, st.last_counts)

        print('\n4. CRM status change is written back to the sheet')
        fb.status = 'Quoted'; db.session.commit()
        written.clear()
        st = sheet_sync.sync_once(_intake_lead)
        check('Quoted -> QUOTED written for that row only', written == [(2, 'QUOTED')], written)
        check('status write count reported', 'statuses written to sheet 1' in st.last_counts, st.last_counts)

        print('\n5. Nothing written when the sheet already matches the CRM')
        fake_fetch['rows'] = [dict(r, lead_status=('QUOTED' if r['__row'] == 2 else 'CREATED')) for r in SHEET]
        written.clear()
        sheet_sync.sync_once(_intake_lead)
        check('no writes when values already match', written == [], written)

        print('\n6. Rows without a Meta id are de-duplicated by phone')
        noid = [row(5, '', 'fb', 'ZZ NoId Lead', 'p:' + PHONES[2], 'CREATED')]
        fake_fetch['rows'] = noid
        sheet_sync.sync_once(_intake_lead)
        sheet_sync.sync_once(_intake_lead)
        check('no-id row imported exactly once across two runs',
              Lead.query.filter_by(phone=PHONES[2]).count() == 1 and
              SheetSyncRow.query.filter_by(external_id=f'phone:{PHONES[2]}').count() == 1)

        print('\n7. A re-sorted sheet updates where each row sits')
        fake_fetch['rows'] = [dict(SHEET[1], __row=9)]
        sheet_sync.sync_once(_intake_lead)
        check('row number follows the sheet', SheetSyncRow.query.filter_by(external_id='zz_leadgen_2').first().row_number == 9)

        print('\n8. A failed status write is recorded and the imports are kept')
        ig.status = 'Lost'; db.session.commit()
        fake_fetch['rows'] = [dict(r, __row=r['__row']) for r in SHEET]
        fail_write['on'] = True
        before = Lead.query.filter(Lead.phone.in_(PHONES)).count()
        st = sheet_sync.sync_once(_intake_lead)
        check('error recorded', st.last_status == 'error' and '403' in (st.last_error or ''), (st.last_status, st.last_error))
        check('lead count unchanged by the failed write', before == Lead.query.filter(Lead.phone.in_(PHONES)).count())
        fail_write['on'] = False

        print('\n9. A failed fetch is recorded, not raised')
        fake_fetch['error'] = 'Google Sheets returned 403: permission denied'
        st = sheet_sync.sync_once(_intake_lead)
        check('fetch error recorded', st.last_status == 'error' and '403' in (st.last_error or ''), (st.last_status, st.last_error))
    finally:
        sheet_sync.fetch_rows, sheet_sync.write_statuses, sheet_sync.config = real
        cleanup()
        print(f'\nRESULT: {OK} passed, {FAIL} failed')
