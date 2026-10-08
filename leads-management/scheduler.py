"""Background scheduler for WhatsApp campaign sequence steps.

Runs an APScheduler BackgroundScheduler in-process, ticking every 5 minutes.
Production runs 3 gunicorn workers (each importing app.py independently), and
locally the Flask reloader spawns 2 processes — this deliberately lets every
process run its own scheduler rather than trying to elect a single leader.
Correctness comes from an atomic DB claim on whatsapp_enrollment rows inside
routes._process_account_due_enrollments(), not from only one process ticking.
"""
import logging
from contextlib import contextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

_scheduler = None


@contextmanager
def _named_lock(lock_name):
    """Acquire a MySQL named lock on one dedicated connection, held open for the whole
    block, and release it on that same connection. GET_LOCK/RELEASE_LOCK are tied to the
    exact connection that took them — using db.session for this is unsafe whenever the work
    inside the block commits (as sheet_sync.sync_once does, deliberately, so imports survive
    even if the later write-back fails): each commit can hand the ORM session a different
    pooled connection, so RELEASE_LOCK can silently run on the wrong one and leave the lock
    stuck until that connection happens to get recycled. Yields whether the lock was taken."""
    from extensions import db
    conn = db.engine.connect()
    got = False
    try:
        got = bool(conn.execute(text('SELECT GET_LOCK(:n, 0)'), {'n': lock_name}).scalar())
        yield got
    finally:
        if got:
            try:
                conn.execute(text('SELECT RELEASE_LOCK(:n)'), {'n': lock_name})
            except Exception:
                logging.exception('Could not release lock %s', lock_name)
        conn.close()


def start_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(lambda: _tick(app), 'interval', minutes=5,
                        id='whatsapp_campaign_tick', max_instances=1)
    _scheduler.add_job(lambda: _attendance_tick(app), 'interval', minutes=15,
                        id='attendance_settle', max_instances=1)
    _scheduler.add_job(lambda: _sheet_tick(app), 'interval', minutes=1,
                        id='google_sheet_sync', max_instances=1)
    _scheduler.start()
    logging.info('WhatsApp campaign scheduler started')


def _tick(app):
    with app.app_context():
        from extensions import db
        try:
            with _named_lock('whatsapp_scheduler_tick') as got_lock:
                if not got_lock:
                    return  # another process is already ticking — nothing to do here
                _run_tick(db)
        except Exception:
            logging.exception('WhatsApp scheduler tick failed')
            db.session.rollback()


def _run_tick(db):
    from models import WhatsAppAccount
    from routes import _process_account_due_enrollments

    for account in WhatsAppAccount.query.filter_by(is_active=True).all():
        try:
            _process_account_due_enrollments(account)
        except Exception:
            logging.exception('Failed processing WhatsApp account %s', account.id)


def _attendance_tick(app):
    """Mark sessions left open past their Dubai date as unpaid leave, even if the
    person never opens the CRM again (so admin reports are right without waiting)."""
    with app.app_context():
        from extensions import db
        try:
            with _named_lock('attendance_settle') as got_lock:
                if not got_lock:
                    return
                import attendance
                attendance.settle_stale_sessions()
        except Exception:
            logging.exception('Attendance settle tick failed')
            db.session.rollback()


def _sheet_tick(app):
    """Import new social media leads from the Google Sheet. GET_LOCK keeps the 3 gunicorn
    workers from all fetching the sheet at the same moment (the row dedupe is the real guard)."""
    import os
    if os.environ.get('GOOGLE_SHEET_ENABLED', '').strip() != '1':
        return
    with app.app_context():
        from extensions import db
        try:
            with _named_lock('google_sheet_sync') as got_lock:
                if not got_lock:
                    return
                import sheet_sync
                from routes import _intake_lead
                sheet_sync.sync_once(_intake_lead)
        except Exception:
            logging.exception('Google Sheet sync tick failed')
            db.session.rollback()
