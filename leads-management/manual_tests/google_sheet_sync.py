"""Google Sheet social-lead sync. The Google call is stubbed with rows shaped exactly like the
Meta export (header names from the real sheet), so this runs without the service-account key.
Covers: not-configured state, Facebook/Instagram routing, adset_name -> course text, rows
without a phone skipped, re-runs never duplicating, and a failed fetch recorded not raised."""
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

PHONES = ['+971500009001', '+971500009002', '+971500009003']
FAKE_ROWS = [
    {'id': 'zz_leadgen_1', 'platform': 'fb', 'full_name': 'ZZ Facebook Lead', 'phone_number': PHONES[0],
     'email': 'zz.fb@example.com', 'adset_name': 'Revit Architecture', 'campaign_name': 'ZZ Camp',
     'form_name': 'ZZ Form'},
    {'id': 'zz_leadgen_2', 'platform': 'ig', 'full_name': 'ZZ Instagram Lead', 'phone_number': PHONES[1],
     'email': 'zz.ig@example.com', 'adset_name': 'AutoCAD', 'campaign_name': 'ZZ Camp', 'form_name': 'ZZ Form'},
    {'id': 'zz_leadgen_3', 'platform': 'fb', 'full_name': 'ZZ No Phone', 'phone_number': '',
     'email': 'zz.nophone@example.com', 'adset_name': 'AutoCAD', 'campaign_name': 'ZZ Camp', 'form_name': 'ZZ Form'},
]

real_fetch = sheet_sync.fetch_rows
real_config = sheet_sync.config
def cleanup():
    Lead.query.filter(Lead.phone.in_(PHONES)).delete(synchronize_session=False)
    SheetSyncRow.query.filter(SheetSyncRow.external_id.like('zz_leadgen_%')).delete(synchronize_session=False)
    SheetSyncState.query.delete()
    db.session.commit()

with app.app_context():
    from routes import _intake_lead
    cleanup()
    try:
        print('1. Not configured -> recorded, nothing imported')
        sheet_sync.config = lambda: {'sheet_id': '', 'tab': 'Sheet2', 'key_path': '', 'enabled': False}
        st = sheet_sync.sync_once(_intake_lead)
        check('status not_configured', st.last_status == 'not_configured', st.last_status)

        sheet_sync.config = lambda: {'sheet_id': 'ZZTEST', 'tab': 'Sheet2', 'key_path': 'x.json', 'enabled': True}

        print('\n2. First sync imports Facebook + Instagram, skips the row without a phone')
        sheet_sync.fetch_rows = lambda *a, **k: FAKE_ROWS
        st = sheet_sync.sync_once(_intake_lead)
        check('status ok', st.last_status == 'ok', (st.last_status, st.last_error))
        check('counts text reports 2 imported, 1 without phone', 'imported 2' in (st.last_counts or '') and 'no phone number 1' in (st.last_counts or ''), st.last_counts)
        fb = Lead.query.filter_by(phone=PHONES[0]).first()
        ig = Lead.query.filter_by(phone=PHONES[1]).first()
        check('Facebook lead created', fb is not None)
        check('Instagram lead created', ig is not None)
        check('no-phone row not created as a lead', Lead.query.filter_by(email='zz.nophone@example.com').first() is None)
        check('Facebook lead source is Social Media (Facebook)', fb and fb.lead_source == 'Social Media (Facebook)', fb and fb.lead_source)
        check('Instagram lead source is Social Media (Instagram)', ig and ig.lead_source == 'Social Media (Instagram)', ig and ig.lead_source)
        check('adset_name carried through as the course (text or matched course)',
              fb is not None and ('Revit' in (fb.course_text or '') or fb.course_interest_id is not None), (fb and fb.course_text, fb and fb.course_interest_id))
        check('leadgen id recorded for dedupe', SheetSyncRow.query.filter_by(external_id='zz_leadgen_1').first() is not None)

        print('\n3. Re-running never duplicates')
        before = Lead.query.filter(Lead.phone.in_(PHONES)).count()
        st = sheet_sync.sync_once(_intake_lead)
        after = Lead.query.filter(Lead.phone.in_(PHONES)).count()
        check('no new leads on second run', before == after, (before, after))
        check('second run reports already-in-CRM rows', 'already in CRM 2' in (st.last_counts or ''), st.last_counts)

        print('\n4. A failing Google call is recorded, not raised')
        def boom(*a, **k): raise RuntimeError('Google Sheets returned 403: permission denied')
        sheet_sync.fetch_rows = boom
        st = sheet_sync.sync_once(_intake_lead)
        check('status error recorded', st.last_status == 'error' and '403' in (st.last_error or ''), (st.last_status, st.last_error))
    finally:
        sheet_sync.fetch_rows = real_fetch
        sheet_sync.config = real_config
        cleanup()
        print(f'\nRESULT: {OK} passed, {FAIL} failed')
