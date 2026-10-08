"""A repeat submission with a phone number already in the CRM used to always merge into the
existing lead as a buried comment, however old or closed that lead was. That's how a 13-month-old
"Quoted" lead about 3D Printing silently swallowed a brand-new "Blender" enquiry from the same
phone, with nobody seeing a new lead appear. Now: merging only happens while the existing lead is
still active and recently touched; a Converted/Lost or 90+ day stale lead gets a fresh new lead
instead, with a pointer comment back to the old one."""
import sys
import datetime as dt
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
from extensions import db
from models import Lead, LeadInteraction, User
from routes import _intake_lead

OK = FAIL = 0
def check(label, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1; print('  ok  ', label)
    else: FAIL += 1; print('  FAIL', label, extra)

PHONES = [f'+97150000{n}' for n in range(8801, 8810)]


def cleanup():
    Lead.query.filter(Lead.phone.in_(PHONES)).delete(synchronize_session=False)
    db.session.commit()


with app.app_context():
    cleanup()
    try:
        print('1. Active, recent lead -> still merges (unchanged behavior)')
        recent = Lead(name='ZZ Recent', phone=PHONES[0], status='Interested',
                      created_at=dt.datetime.utcnow() - dt.timedelta(days=5), lead_source='Website')
        db.session.add(recent); db.session.commit()
        result = _intake_lead(name='ZZ Recent Again', phone=PHONES[0], email='', lead_source='Website - Form')
        check('merged into the existing lead', result.id == recent.id)
        check('comment appended', 'New Website - Form submission' in (result.comments or ''))
        check('no second lead created', Lead.query.filter_by(phone=PHONES[0]).count() == 1)

        print('\n2. Converted lead -> new lead created, even if recent')
        conv = Lead(name='ZZ Converted', phone=PHONES[1], status='Converted',
                    created_at=dt.datetime.utcnow() - dt.timedelta(days=2), lead_source='Website')
        db.session.add(conv); db.session.commit()
        result = _intake_lead(name='ZZ Converted Again', phone=PHONES[1], email='', lead_source='Website - Form')
        check('a new lead was created, not merged', result.id != conv.id)
        check('two leads now exist for this phone', Lead.query.filter_by(phone=PHONES[1]).count() == 2)
        check('new lead points back to the old one', f'lead #{conv.id}' in (result.comments or ''), result.comments)

        print('\n3. Lost lead -> new lead created')
        lost = Lead(name='ZZ Lost', phone=PHONES[2], status='Lost',
                    created_at=dt.datetime.utcnow() - dt.timedelta(days=1), lead_source='Website')
        db.session.add(lost); db.session.commit()
        result = _intake_lead(name='ZZ Lost Again', phone=PHONES[2], email='', lead_source='Website - Form')
        check('a new lead was created for a Lost phone', result.id != lost.id)

        print('\n4. Real-world case: 13-month-old Quoted lead, no recent activity -> new lead')
        old_quoted = Lead(name='ZZ Old Quoted', phone=PHONES[3], status='Quoted',
                          created_at=dt.datetime.utcnow() - dt.timedelta(days=400), lead_source='Website')
        db.session.add(old_quoted); db.session.commit()
        result = _intake_lead(name='ZZ Old Quoted Again', phone=PHONES[3], email='',
                              lead_source='Website - Download Brochure', course_text='Blender')
        check('a fresh lead was created instead of a buried comment', result.id != old_quoted.id)
        check('the new lead carries the new course interest', result.course_text == 'Blender')
        check('the old lead is untouched', old_quoted.comments is None)

        print('\n5. Quoted lead, still recent -> merges (not every Quoted lead is stale)')
        recent_quoted = Lead(name='ZZ Recent Quoted', phone=PHONES[4], status='Quoted',
                             created_at=dt.datetime.utcnow() - dt.timedelta(days=10), lead_source='Website')
        db.session.add(recent_quoted); db.session.commit()
        result = _intake_lead(name='ZZ Recent Quoted Again', phone=PHONES[4], email='', lead_source='Website - Form')
        check('merged into the recent Quoted lead', result.id == recent_quoted.id)

        print('\n6. Old lead but a recent interaction logged -> still counts as active, merges')
        old_but_active = Lead(name='ZZ Old Active', phone=PHONES[5], status='Interested',
                              created_at=dt.datetime.utcnow() - dt.timedelta(days=300), lead_source='Website')
        db.session.add(old_but_active); db.session.commit()
        db.session.add(LeadInteraction(lead_id=old_but_active.id, interaction_date=dt.datetime.utcnow() - dt.timedelta(days=3),
                                       interaction_type='Call', content='follow-up call'))
        db.session.commit()
        result = _intake_lead(name='ZZ Old Active Again', phone=PHONES[5], email='', lead_source='Website - Form')
        check('merged -- recent interaction makes it active, not stale', result.id == old_but_active.id)

        print('\n7. Old lead with only an old interaction -> stale, new lead')
        old_and_inactive = Lead(name='ZZ Old Inactive', phone=PHONES[6], status='Interested',
                                created_at=dt.datetime.utcnow() - dt.timedelta(days=300), lead_source='Website')
        db.session.add(old_and_inactive); db.session.commit()
        db.session.add(LeadInteraction(lead_id=old_and_inactive.id, interaction_date=dt.datetime.utcnow() - dt.timedelta(days=200),
                                       interaction_type='Call', content='old call'))
        db.session.commit()
        result = _intake_lead(name='ZZ Old Inactive Again', phone=PHONES[6], email='', lead_source='Website - Form')
        check('new lead created -- last interaction was also stale', result.id != old_and_inactive.id)
    finally:
        cleanup()
        print(f'\nRESULT: {OK} passed, {FAIL} failed')
