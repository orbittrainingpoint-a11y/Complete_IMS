"""Pull social media leads (Meta Lead Ads exported to Google Sheets) into the CRM.

Config lives in the environment (set in .env.crm on the server):
  GOOGLE_SHEET_ID        spreadsheet id (the part of the URL between /d/ and /edit)
  GOOGLE_SHEET_TAB       tab name, e.g. Sheet2
  GOOGLE_SA_KEY_PATH     path to the service-account JSON key (never committed, never printed)
  GOOGLE_SHEET_ENABLED   "1" to run the 5-minute sync (default off)

Each row is imported once: its Meta `id` column (the leadgen id) is recorded in
sheet_sync_row, so a re-run or a re-sorted sheet never creates duplicates. Rows without
a phone number can't become leads (Lead.phone is required) and are counted as skipped.
"""
import logging
import os
from datetime import datetime

from extensions import db
from models import SheetSyncRow, SheetSyncState

SHEETS_URL = 'https://sheets.googleapis.com/v4/spreadsheets/{sheet}/values/{tab}'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def config():
    return {
        'sheet_id': os.environ.get('GOOGLE_SHEET_ID', '').strip(),
        'tab': os.environ.get('GOOGLE_SHEET_TAB', 'Sheet1').strip(),
        'key_path': os.environ.get('GOOGLE_SA_KEY_PATH', '').strip(),
        'enabled': os.environ.get('GOOGLE_SHEET_ENABLED', '').strip() == '1',
    }


def _session(key_path):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return AuthorizedSession(creds)


def fetch_rows(sheet_id, tab, key_path):
    """Return the sheet as a list of dicts keyed by the header row (lower-cased, stripped)."""
    session = _session(key_path)
    resp = session.get(SHEETS_URL.format(sheet=sheet_id, tab=tab), timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f'Google Sheets returned {resp.status_code}: {resp.text[:300]}')
    values = resp.json().get('values', [])
    if not values:
        return []
    headers = [h.strip().lower() for h in values[0]]
    rows = []
    for raw in values[1:]:
        raw = raw + [''] * (len(headers) - len(raw))
        rows.append({h: (raw[i] or '').strip() for i, h in enumerate(headers) if h})
    return rows


def _source_label(platform):
    p = (platform or '').lower()
    return 'Social Media (Instagram)' if p in ('ig', 'instagram') else 'Social Media (Facebook)'


def _clean_phone(raw):
    """Meta exports phones as 'p:+971...'. Keep the digits (and a leading +); None if too short."""
    s = (raw or '').strip()
    if s.lower().startswith('p:'):
        s = s[2:]
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) < 9:
        return None
    return ('+' if s.startswith('+') else '') + digits


def _import_row(row, intake):
    """Import one sheet row. Returns 'imported', 'duplicate', or 'skipped'."""
    external_id = row.get('id', '')
    if external_id and SheetSyncRow.query.filter_by(external_id=external_id).first():
        return 'duplicate'
    phone = _clean_phone(row.get('phone_number'))
    if not phone:
        return 'skipped'
    lead = intake(
        name=row.get('full_name', ''),
        phone=phone,
        email=row.get('email', ''),
        lead_source=_source_label(row.get('platform')),
        course_text=row.get('adset_name', ''),
        note=f"Meta leadgen id {external_id or '-'} · campaign: {row.get('campaign_name', '-')} · "
             f"ad set: {row.get('adset_name', '-')} · form: {row.get('form_name', '-')}",
        notify_category='social',
    )
    if lead is None:
        return 'skipped'
    if external_id:
        db.session.add(SheetSyncRow(external_id=external_id, imported_at=datetime.utcnow()))
    return 'imported'


def _get_state():
    state = SheetSyncState.query.get(1)
    if state is None:
        state = SheetSyncState(id=1)
        db.session.add(state)
    return state


def sync_once(intake):
    """Run one sync. `intake` is routes._intake_lead (passed in to avoid a circular import).
    Records the outcome in sheet_sync_state so the admin page can show it."""
    cfg = config()
    state = _get_state()
    state.last_run_at = datetime.utcnow()
    if not (cfg['sheet_id'] and cfg['key_path']):
        state.last_status = 'not_configured'
        state.last_error = 'GOOGLE_SHEET_ID / GOOGLE_SA_KEY_PATH not set.'
        db.session.commit()
        return state
    try:
        rows = fetch_rows(cfg['sheet_id'], cfg['tab'], cfg['key_path'])
        counts = {'imported': 0, 'duplicate': 0, 'skipped': 0}
        for row in rows:
            counts[_import_row(row, intake)] += 1
        state.last_status = 'ok'
        state.last_error = None
        state.rows_seen = len(rows)
        state.last_counts = (f"imported {counts['imported']} · already in CRM {counts['duplicate']} · "
                             f"no phone number {counts['skipped']}")
    except Exception as e:
        db.session.rollback()
        logging.exception('Google Sheet sync failed')
        state = _get_state()
        state.last_run_at = datetime.utcnow()
        state.last_status = 'error'
        state.last_error = str(e)[:500]
    db.session.commit()
    return state
