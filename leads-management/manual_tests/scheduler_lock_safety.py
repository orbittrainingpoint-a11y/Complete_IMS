"""Regression test for the stuck-named-lock bug: GET_LOCK/RELEASE_LOCK are tied to the exact
MySQL connection that took them, but the scheduler's tick functions run work that commits via
db.session mid-way (sheet_sync.sync_once does this deliberately). Under the old code, GET_LOCK
and RELEASE_LOCK both went through db.session, so a commit in between could swap the ORM to a
different pooled connection and make RELEASE_LOCK silently fail on the wrong one -- leaving the
lock stuck until that connection happened to get recycled, which is why the Google Sheet sync
went dark for several minutes at a time. _named_lock fixes this by holding one dedicated
connection for the whole block, independent of whatever db.session does inside it."""
import sys
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from sqlalchemy import text
import scheduler

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

LOCK = 'zz_sched_lock_test'


def is_free(name):
    with app.app_context():
        with db.engine.connect() as c:
            got = bool(c.execute(text('SELECT GET_LOCK(:n, 0)'), {'n': name}).scalar())
            if got:
                c.execute(text('SELECT RELEASE_LOCK(:n)'), {'n': name})
            return got


with app.app_context():
    try:
        print('1. Lock is released even when db.session commits inside the block (the real bug)')
        with scheduler._named_lock(LOCK) as got:
            check('lock acquired', got)
            # Simulate what sheet_sync.sync_once does: a commit partway through the work,
            # which under the old db.session-based locking could swap the pooled connection.
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            db.session.execute(text('SELECT 1'))
            db.session.commit()
        check('lock is free again immediately after the block exits', is_free(LOCK))

        print('\n2. A second holder is correctly refused while the first is still inside the block')
        with scheduler._named_lock(LOCK) as got1:
            check('first acquires', got1)
            with scheduler._named_lock(LOCK) as got2:
                check('second is refused while the first still holds it', got2 is False)
        check('lock is free again after both blocks exit', is_free(LOCK))

        print('\n3. An exception inside the block still releases the lock')
        try:
            with scheduler._named_lock(LOCK) as got:
                check('lock acquired before raising', got)
                raise RuntimeError('simulated failure mid-tick')
        except RuntimeError:
            pass
        check('lock is free again after the exception propagated', is_free(LOCK))
    finally:
        is_free(LOCK)  # make sure nothing is left stuck for other tests
        print(f'\nRESULT: {OK} passed, {FAIL} failed')
