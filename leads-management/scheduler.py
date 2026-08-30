"""Background scheduler for WhatsApp campaign sequence steps.

Runs an APScheduler BackgroundScheduler in-process, ticking every 5 minutes.
Production runs 3 gunicorn workers (each importing app.py independently), and
locally the Flask reloader spawns 2 processes — this deliberately lets every
process run its own scheduler rather than trying to elect a single leader.
Correctness comes from an atomic DB claim on whatsapp_enrollment rows inside
routes._process_account_due_enrollments(), not from only one process ticking.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

_scheduler = None


def start_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(lambda: _tick(app), 'interval', minutes=5,
                        id='whatsapp_campaign_tick', max_instances=1)
    _scheduler.start()
    logging.info('WhatsApp campaign scheduler started')


def _tick(app):
    with app.app_context():
        from extensions import db
        got_lock = False
        try:
            got_lock = bool(db.session.execute(text("SELECT GET_LOCK('whatsapp_scheduler_tick', 0)")).scalar())
            if not got_lock:
                return  # another process is already ticking — nothing to do here
            _run_tick(db)
        except Exception:
            logging.exception('WhatsApp scheduler tick failed')
            db.session.rollback()
        finally:
            if got_lock:
                try:
                    db.session.execute(text("SELECT RELEASE_LOCK('whatsapp_scheduler_tick')"))
                    db.session.commit()
                except Exception:
                    pass


def _run_tick(db):
    from models import WhatsAppAccount
    from routes import _process_account_due_enrollments

    for account in WhatsAppAccount.query.filter_by(is_active=True).all():
        try:
            _process_account_due_enrollments(account)
        except Exception:
            logging.exception('Failed processing WhatsApp account %s', account.id)
