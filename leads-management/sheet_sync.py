"""Two-way sync between the Google Sheet of social media leads and the CRM.

  Sheet -> CRM: every new row becomes a lead (name, phone, email, adset_name as the course,
                platform -> Facebook/Instagram source). Rows are keyed on the Meta `id`
                column (or the phone number when there is no id), so a row is never imported twice.
  CRM -> Sheet: the CRM lead's status is written to the sheet's lead_status column using
                STATUS_TO_SHEET. Only rows whose value differs are written.

Config lives in the environment (set in .env.crm on the server):
  GOOGLE_SHEET_ID        spreadsheet id (the part of the URL between /d/ and /edit)
  GOOGLE_SHEET_TAB       tab name, e.g. Sheet2
  GOOGLE_SA_KEY_PATH     path to the service-account JSON key (never committed, never printed)
  GOOGLE_SHEET_ENABLED   "1" to run the sync every minute (default off)

The service account needs Editor access to the sheet for the CRM -> Sheet direction.
"""
import logging
import os
from datetime import datetime

from extensions import db
from models import Lead, SheetSyncRow, SheetSyncState

SHEETS_BASE = 'https://sheets.googleapis.com/v4/spreadsheets/{sheet}'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
STATUS_COLUMN = 'lead_status'

# CRM lead status -> value written to the sheet's lead_status column
STATUS_TO_SHEET = {
    'New': 'CREATED',
    'Contacted': 'CONTACTED',
    'Interested': 'INTERESTED',
    'Quoted': 'QUOTED',
    'Converted': 'CONVERTED',
    'Lost': 'LOST',
}


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


def _col_letter(index):
    letters = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def fetch_rows(sheet_id, tab, key_path):
    """Return (headers, rows). Each row is a dict keyed by lower-cased header, plus '__row'
    holding its real row number in the sheet (header is row 1), needed for write-back."""
    session = _session(key_path)
    url = f'{SHEETS_BASE.format(sheet=sheet_id)}/values/{tab}'
    resp = session.get(url, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f'Google Sheets returned {resp.status_code}: {resp.text[:300]}')
    values = resp.json().get('values', [])
    if not values:
        return [], []
    headers = [h.strip().lower() for h in values[0]]
    rows = []
    for number, raw in enumerate(values[1:], start=2):
        raw = raw + [''] * (len(headers) - len(raw))
        row = {h: (raw[i] or '').strip() for i, h in enumerate(headers) if h}
        row['__row'] = number
        rows.append(row)
    return headers, rows


def write_statuses(sheet_id, tab, key_path, headers, updates):
    """updates: list of (row_number, sheet_value). One batched call for all of them."""
    if not updates or STATUS_COLUMN not in headers:
        return 0
    col = _col_letter(headers.index(STATUS_COLUMN))
    data = [{'range': f"{tab}!{col}{row}", 'values': [[value]]} for row, value in updates]
    session = _session(key_path)
    resp = session.post(f'{SHEETS_BASE.format(sheet=sheet_id)}/values:batchUpdate',
                        json={'valueInputOption': 'RAW', 'data': data}, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f'Writing statuses to the sheet failed ({resp.status_code}): {resp.text[:300]}')
    return len(data)


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


def _import_new(row, phone, key, intake):
    """Create the lead for a sheet row we haven't seen. Returns the SheetSyncRow or None."""
    lead = intake(
        name=row.get('full_name', ''),
        phone=phone,
        email=row.get('email', ''),
        lead_source=_source_label(row.get('platform')),
        course_text=row.get('adset_name', ''),
        note=f"Meta leadgen id {row.get('id') or '-'} · campaign: {row.get('campaign_name', '-')} · "
             f"ad set: {row.get('adset_name', '-')} · form: {row.get('form_name', '-')}",
        notify_category='social',
    )
    if lead is None:
        return None
    link = SheetSyncRow(external_id=key, lead_id=lead.id, row_number=row['__row'], imported_at=datetime.utcnow())
    db.session.add(link)
    return link


def _process(rows, intake):
    """Returns (counts, updates) where updates are (row_number, sheet_value) to write back."""
    counts = {'imported': 0, 'known': 0, 'skipped': 0}
    updates = []
    for row in rows:
        phone = _clean_phone(row.get('phone_number'))
        key = (row.get('id') or '').strip() or (f'phone:{phone}' if phone else '')
        link = SheetSyncRow.query.filter_by(external_id=key).first() if key else None

        if link is None:
            if not phone or not key:
                counts['skipped'] += 1
                continue
            link = _import_new(row, phone, key, intake)
            if link is None:
                counts['skipped'] += 1
                continue
            counts['imported'] += 1
        else:
            counts['known'] += 1
            link.row_number = row['__row']  # the sheet may have been re-sorted
            if link.lead_id is None and phone:  # rows imported before lead links existed
                existing = Lead.query.filter_by(phone=phone).first()
                if existing:
                    link.lead_id = existing.id

        if link.lead_id:
            lead = Lead.query.get(link.lead_id)
            target = STATUS_TO_SHEET.get(lead.status) if lead else None
            current = (row.get(STATUS_COLUMN) or '').strip().upper()
            if target and current != target:
                updates.append((row['__row'], target))
    return counts, updates


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
        headers, rows = fetch_rows(cfg['sheet_id'], cfg['tab'], cfg['key_path'])
        counts, updates = _process(rows, intake)
        db.session.commit()  # imports are saved even if the write-back below fails
        pushed = write_statuses(cfg['sheet_id'], cfg['tab'], cfg['key_path'], headers, updates)
        state.last_status = 'ok'
        state.last_error = None
        state.rows_seen = len(rows)
        state.last_counts = (f"imported {counts['imported']} · already known {counts['known']} · "
                             f"no phone number {counts['skipped']} · statuses written to sheet {pushed}")
    except Exception as e:
        db.session.rollback()
        logging.exception('Google Sheet sync failed')
        state = _get_state()
        state.last_run_at = datetime.utcnow()
        state.last_status = 'error'
        state.last_error = str(e)[:500]
    db.session.commit()
    return state
