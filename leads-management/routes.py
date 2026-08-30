from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func, desc, asc, text
from datetime import datetime, date, timedelta, timezone as _timezone
import json, hmac, hashlib, time, base64, os, secrets, requests, re, uuid

from extensions import db
from models import *
from forms import *
import logging
from utils import create_payment_link, verify_payment_status

# Configure logging
logging.basicConfig(level=logging.DEBUG)

main = Blueprint('main', __name__)


@main.route('/sw.js')
def service_worker():
    """Served from the root path (not /static/) so its scope covers the whole app."""
    response = send_from_directory(current_app.static_folder, 'sw.js')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response


# ── Daily 9:30 PM (Dubai) curfew — every non-admin gets logged out until the next day ──
# Fixed UTC+4 offset (not zoneinfo/tzdata) — UAE has no DST, and this avoids depending on
# an IANA tzdata package that isn't always present on Windows.
_DUBAI_TZ = _timezone(timedelta(hours=4))

def _is_after_dubai_curfew():
    now = datetime.now(_DUBAI_TZ)
    return now.hour > 21 or (now.hour == 21 and now.minute >= 30)

@main.before_request
def _enforce_dubai_curfew():
    if current_user.is_authenticated and not current_user.is_admin() and _is_after_dubai_curfew():
        logout_user()
        flash('Daily access ends at 9:30 PM (Dubai time). Please log in again tomorrow.', 'warning')
        return redirect(url_for('main.login'))

# ── SSO Bridge shared secret (must match Django settings.CRM_SSO_SECRET) ──
_SSO_SECRET = 'orbit-erp-crm-sso-bridge-2024-x9q3mz'
_ERP_URL    = os.environ.get('ERP_URL', 'http://localhost:8000')

def _make_sso_token(username):
    payload = base64.urlsafe_b64encode(json.dumps({'u': username, 't': int(time.time())}).encode()).decode()
    sig = hmac.new(_SSO_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"

def _verify_sso_token(token, max_age=90):
    try:
        payload_b64, sig = token.rsplit('.', 1)
        expected = hmac.new(_SSO_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload_b64 + '==').decode())
        if int(time.time()) - data['t'] > max_age:
            return None
        return data['u']
    except Exception:
        return None

@main.route('/')
@login_required
def dashboard():
    lead_form = LeadForm()
    lead_form.course_interest_id.choices = [(0, 'Select Course')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    meeting_form = MeetingForm()
    meeting_form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').all()]
    meeting_form.student_id.choices = [(0, 'Select Student')] + [(s.id, s.name) for s in Student.query.all()]
    
    _today = date.today()

    # Dashboard statistics - ROLE-BASED ACCESS
    if current_user.is_admin() or current_user.can_view_all_leads:
        total_leads = Lead.query.count()
        recent_leads = Lead.query.order_by(desc(Lead.created_at)).limit(5).all()
        today_followups = Lead.query.filter(Lead.next_followup_date == _today).order_by(Lead.followup_time).all()
        pipeline_data = {
            'New': Lead.query.filter_by(status='New').count(),
            'Contacted': Lead.query.filter_by(status='Contacted').count(),
            'Interested': Lead.query.filter_by(status='Interested').count(),
            'Quoted': Lead.query.filter_by(status='Quoted').count(),
            'Converted': Lead.query.filter_by(status='Converted').count(),
            'Lost': Lead.query.filter_by(status='Lost').count()
        }
        overdue_count = Lead.query.filter(
            Lead.next_followup_date < _today,
            Lead.status.notin_(['Converted', 'Lost'])
        ).count()
        # Consultant performance for admin view
        consultants = User.query.filter_by(active=True, role='consultant').order_by(User.username).all()
        this_month_start = _today.replace(day=1)
        consultant_stats = []
        for c in consultants:
            total = Lead.query.filter_by(assigned_to=c.id).count()
            this_month = Lead.query.filter_by(assigned_to=c.id).filter(
                Lead.created_at >= datetime.combine(this_month_start, datetime.min.time())
            ).count()
            converted = Lead.query.filter_by(assigned_to=c.id, status='Converted').count()
            c_overdue = Lead.query.filter_by(assigned_to=c.id).filter(
                Lead.next_followup_date < _today,
                Lead.status.notin_(['Converted', 'Lost'])
            ).count()
            consultant_stats.append({
                'user': c,
                'total': total,
                'this_month': this_month,
                'converted': converted,
                'rate': round(converted / total * 100, 1) if total > 0 else 0,
                'overdue': c_overdue,
            })
    else:
        # USER SPECIFIC DATA for consultants
        total_leads = Lead.query.filter_by(assigned_to=current_user.id).count()
        recent_leads = Lead.query.filter_by(assigned_to=current_user.id).order_by(desc(Lead.created_at)).limit(5).all()
        today_followups = Lead.query.filter_by(assigned_to=current_user.id).filter(Lead.next_followup_date == _today).order_by(Lead.followup_time).all()
        pipeline_data = Lead.get_user_pipeline_data(current_user.id)
        overdue_count = Lead.query.filter_by(assigned_to=current_user.id).filter(
            Lead.next_followup_date < _today,
            Lead.status.notin_(['Converted', 'Lost'])
        ).count()
        consultant_stats = []

    from models import ImsStudent
    # Students come from IMS sync; consultants see only their own
    if current_user.is_admin() or current_user.can_view_all_leads:
        total_students = ImsStudent.query.count()
    else:
        total_students = ImsStudent.query.filter_by(consultant_username=current_user.username).count()
    total_courses = Course.query.filter_by(is_active=True).count()

    # Monthly revenue from IMS (orbit_invoice DB)
    monthly_revenue = 0.0
    try:
        import pymysql as _pym
        _conn = _pym.connect(host='localhost', user='root', password='', database='orbit_invoice', charset='utf8mb4')
        with _conn.cursor() as _cur:
            _first = _today.replace(day=1).strftime('%Y-%m-%d')
            if current_user.is_admin() or current_user.can_view_all_leads:
                _cur.execute(
                    "SELECT COALESCE(SUM(amount_paid), 0) FROM invoices_invoice WHERE date >= %s",
                    (_first,)
                )
            else:
                _cur.execute(
                    """SELECT COALESCE(SUM(i.amount_paid), 0)
                       FROM invoices_invoice i
                       JOIN auth_user u ON u.id = i.user_id
                       WHERE u.username = %s AND i.date >= %s""",
                    (current_user.username, _first)
                )
            _row = _cur.fetchone()
            monthly_revenue = float(_row[0] or 0)
        _conn.close()
    except Exception:
        monthly_revenue = 0.0

    return render_template('index.html',
                         total_leads=total_leads,
                         total_students=total_students,
                         total_courses=total_courses,
                         recent_leads=recent_leads,
                         today_followups=today_followups,
                         pipeline_data=pipeline_data,
                         monthly_revenue=monthly_revenue,
                         overdue_count=overdue_count,
                         consultant_stats=consultant_stats,
                         lead_form=lead_form,
                         meeting_form=meeting_form,
                         lead=None)

@main.route('/api/leads/<int:id>', methods=['GET'])
@login_required
def get_lead(id):
    lead = Lead.query.get_or_404(id)
    
    # ROLE-BASED ACCESS CONTROL
    if not (current_user.is_admin() or current_user.can_view_all_leads or lead.assigned_to == current_user.id):
        return jsonify({
            'success': False,
            'message': 'You can only view leads assigned to you!'
        }), 403
    
    return jsonify({
        'success': True,
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email,
            'whatsapp': lead.whatsapp,
            'course_interest_id': lead.course_interest_id,
            'course_interest_ids': [ci.course_id for ci in lead.course_interests] or ([lead.course_interest_id] if lead.course_interest_id else []),
            'status': lead.status,
            'lead_source': lead.lead_source,
            'comments': lead.comments,
            'quoted_amount': lead.quoted_amount,
            'next_followup_date': lead.next_followup_date.strftime('%Y-%m-%d') if lead.next_followup_date else '',
            'followup_type': lead.followup_type or ''
        }
    })

@main.route('/leads/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
    # ROLE-BASED ACCESS CONTROL
    if not (current_user.is_admin() or current_user.can_view_all_leads or lead.assigned_to == current_user.id):
        flash('You can only view leads assigned to you!', 'error')
        return redirect(url_for('main.leads'))
    
    # Get all interactions for this lead
    interactions = LeadInteraction.query.filter_by(lead_id=lead_id).order_by(desc(LeadInteraction.interaction_date)).all()
    
    # Get all meetings for this lead
    meetings = Meeting.query.filter_by(lead_id=lead_id).order_by(desc(Meeting.meeting_date)).all()
    
    # Get all quotes for this lead — individual (one course, one price) and bundle (many courses, one total)
    quotes = LeadQuote.query.filter_by(lead_id=lead_id).order_by(desc(LeadQuote.created_at)).all()
    bundles = QuoteBundle.query.filter_by(lead_id=lead_id).order_by(desc(QuoteBundle.created_at)).all()

    # Courses this lead is interested in (falls back to the legacy single field for older leads)
    interested_courses = [ci.course for ci in lead.course_interests]
    if not interested_courses and lead.course_interest:
        interested_courses = [lead.course_interest]

    # Unified, newest-first list for the Quotes panel — individual (one course) and bundle (many courses, one total)
    quote_entries = (
        [{'kind': 'individual', 'data': q, 'created_at': q.created_at} for q in quotes]
        + [{'kind': 'bundle', 'data': b, 'created_at': b.created_at} for b in bundles]
    )
    quote_entries.sort(key=lambda e: e['created_at'] or datetime.min, reverse=True)

    # Sum of every quote/bundle raised for this lead — the "total cost" across all
    # courses when a lead has more than one, since lead.quoted_amount only ever
    # holds the single most-recently-entered quote's value.
    total_quoted_amount = sum(q.quoted_amount for q in quotes) + sum(b.total_amount for b in bundles)

    # Combine all activities and sort by date
    activities = []
    
    # Add interactions
    for interaction in interactions:
        activities.append({
            'type': 'interaction' if interaction.interaction_type != 'Quote Update' else 'quote-update' if interaction.interaction_type != 'Follow-up Update' else 'follow-up-update',
            'subtype': interaction.interaction_type,
            'date': interaction.interaction_date,
            'content': interaction.content,
            'created_by': interaction.created_by.username if interaction.created_by else 'System',
            'is_important': interaction.is_important,
            'data': interaction
        })
    
    # Add meetings
    for meeting in meetings:
        activities.append({
            'type': 'meeting',
            'subtype': meeting.status,
            'date': meeting.meeting_date,
            'content': f"{meeting.title} - {meeting.meeting_type}",
            'created_by': meeting.created_by.username if meeting.created_by else 'System',
            'is_important': False,
            'data': meeting
        })
    
    # Add quotes
    for quote in quotes:
        activities.append({
            'type': 'quote',
            'subtype': quote.status,
            'date': quote.created_at,
            'content': f"Quote for {quote.course.name} - {quote.currency} {quote.quoted_amount}",
            'created_by': quote.created_by.username if quote.created_by else 'System',
            'is_important': True,
            'data': quote
        })

    # Add bundle quotes (one total price covering several courses)
    for bundle in bundles:
        course_names = ', '.join(item.course.name for item in bundle.items)
        activities.append({
            'type': 'quote',
            'subtype': bundle.status,
            'date': bundle.created_at,
            'content': f"Bundle quote for {course_names} - {bundle.currency} {bundle.total_amount}",
            'created_by': bundle.created_by.username if bundle.created_by else 'System',
            'is_important': True,
            'data': bundle
        })

    # Sort newest-first — use .timestamp() float so comparison is always unambiguous
    def _ts(d):
        if d is None:
            return 0.0
        if hasattr(d, 'timestamp'):          # datetime object
            return d.timestamp()
        # date object — convert to midnight datetime first
        return datetime(d.year, d.month, d.day).timestamp()
    activities.sort(key=lambda x: _ts(x['date']), reverse=True)
    
    # Create forms
    activity_form = ActivityForm()
    followup_form = LeadFollowupForm(obj=lead)
    
    # Get courses for quote form
    courses = Course.query.filter_by(is_active=True).all()
    
    # Check if this lead has been converted to an IMS student
    from models import ImsStudent
    linked_student = ImsStudent.query.filter_by(lead_crm_id=lead.id).first()

    return render_template('lead_detail_modern.html',
                         lead=lead,
                         activities=activities,
                         quotes=quotes,
                         bundles=bundles,
                         quote_entries=quote_entries,
                         total_quoted_amount=total_quoted_amount,
                         interested_courses=interested_courses,
                         meetings=meetings,
                         courses=courses,
                         activity_form=activity_form,
                         followup_form=followup_form,
                         linked_student=linked_student,
                         today=date.today())

@main.route('/leads/quote/<int:id>/update_amount', methods=['POST'])
@login_required
def update_quote_amount(id):
    quote = LeadQuote.query.get_or_404(id)
    
    # ROLE-BASED ACCESS CONTROL
    if not (current_user.is_admin() or current_user.can_view_all_leads or quote.lead.assigned_to == current_user.id):
        return jsonify({
            'success': False,
            'message': 'You can only edit quotes for leads assigned to you!'
        }), 403

    quoted_amount = request.form.get('quoted_amount', type=float)
    if not quoted_amount or quoted_amount <= 0:
        return jsonify({
            'success': False,
            'message': 'Invalid quote amount. Please enter a positive number.'
        }), 400

    try:
        # Store old amount for logging
        old_amount = quote.quoted_amount
        
        # Update quote amount
        quote.quoted_amount = quoted_amount
        
        # Update lead's quoted_amount (if this is the latest quote)
        latest_quote = LeadQuote.query.filter_by(lead_id=quote.lead_id).order_by(desc(LeadQuote.created_at)).first()
        if latest_quote.id == quote.id:
            quote.lead.quoted_amount = quoted_amount
        
        # Log the change as an interaction
        interaction = LeadInteraction(
            lead_id=quote.lead_id,
            interaction_type='Quote Update',
            interaction_date=datetime.now(),
            content=f"Quote amount updated from {quote.currency} {old_amount} to {quote.currency} {quoted_amount}",
            created_by_id=current_user.id,
            is_important=True
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote amount updated successfully!'
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating quote amount: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating quote amount: {str(e)}'
        }), 500

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        ua = request.user_agent.string[:300]
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            db.session.add(LoginLog(
                user_id=user.id, username_try=form.username.data,
                ip_address=ip, user_agent=ua, status='success'
            ))
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        # failed attempt — look up user just to get their id if they exist
        _fu = User.query.filter_by(username=form.username.data).first()
        db.session.add(LoginLog(
            user_id=_fu.id if _fu else None,
            username_try=form.username.data,
            ip_address=ip, user_agent=ua, status='failed'
        ))
        db.session.commit()
        flash('Invalid username or password', 'error')

    return render_template('login.html', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

_SOURCE_CATEGORY_FILTERS = {
    # Old leads used the fixed 'Website Inquiry' label; newer ones are
    # 'Website - <form name>' so each Elementor form's leads carry the form's
    # name — the prefix match keeps both matching this category.
    'website': lambda q: q.filter(db.or_(Lead.lead_source == 'Website Inquiry', Lead.lead_source.like('Website%'))),
    'social_media': lambda q: q.filter(Lead.lead_source.in_([
        'Social Media (Facebook)', 'Social Media (Instagram)', 'Social Media (LinkedIn)'
    ])),
}
_SOURCE_CATEGORY_TITLES = {
    'website': 'Website Leads',
    'social_media': 'Social Media Leads',
}

def _leads_view(source_category=None):
    lead_form = LeadForm()

    meeting_form = MeetingForm()
    meeting_form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').all()]
    meeting_form.student_id.choices = [(0, 'Select Student')] + [(s.id, s.name) for s in Student.query.all()]

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    course_filter = request.args.get('course', '')
    consultant_filter = request.args.get('consultant', '', type=int) if (current_user.is_admin() or current_user.can_view_all_leads) else 0
    source_filter_fn = _SOURCE_CATEGORY_FILTERS.get(source_category)

    # ROLE-BASED ACCESS CONTROL FOR LEADS
    if current_user.is_admin() or current_user.can_view_all_leads:
        query = Lead.query
        if source_filter_fn:
            query = source_filter_fn(query)
        if consultant_filter:
            query = query.filter_by(assigned_to=consultant_filter)
        if status_filter:
            query = query.filter_by(status=status_filter)
        if search:
            query = query.filter(
                db.or_(
                    Lead.name.ilike(f'%{search}%'),
                    Lead.phone.ilike(f'%{search}%'),
                    Lead.email.ilike(f'%{search}%')
                )
            )
        if course_filter:
            query = query.filter_by(course_interest_id=course_filter)
    else:
        query = Lead.query.filter_by(assigned_to=current_user.id)
        if source_filter_fn:
            query = source_filter_fn(query)
        if status_filter:
            query = query.filter_by(status=status_filter)
        if search:
            query = query.filter(
                db.or_(
                    Lead.name.ilike(f'%{search}%'),
                    Lead.phone.ilike(f'%{search}%'),
                    Lead.email.ilike(f'%{search}%')
                )
            )
        if course_filter:
            query = query.filter_by(course_interest_id=course_filter)

    leads_pagination = query.order_by(desc(Lead.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )

    # Build map of CRM lead IDs that have been converted (linked to IMS registrations)
    from models import ImsStudent
    page_lead_ids = [l.id for l in leads_pagination.items]
    converted_students = {}
    if page_lead_ids:
        linked = ImsStudent.query.filter(
            ImsStudent.lead_crm_id.in_(page_lead_ids)
        ).with_entities(ImsStudent.lead_crm_id, ImsStudent.registration_number,
                        ImsStudent.first_name, ImsStudent.last_name).all()
        converted_students = {
            row[0]: {'reg': row[1] or '', 'name': f"{row[2]} {row[3]}".strip()}
            for row in linked
        }

    # Compute heat score per lead on this page
    lead_temps = {}
    if page_lead_ids:
        _now = datetime.utcnow()
        _today_d = date.today()
        last_int_rows = db.session.query(
            LeadInteraction.lead_id,
            func.max(LeadInteraction.interaction_date).label('last_date')
        ).filter(LeadInteraction.lead_id.in_(page_lead_ids)
        ).group_by(LeadInteraction.lead_id).all()
        last_int_map = {r.lead_id: r.last_date for r in last_int_rows}
        for lead in leads_pagination.items:
            if lead.status == 'Converted':
                lead_temps[lead.id] = 'converted'
            elif lead.status == 'Lost':
                lead_temps[lead.id] = 'lost'
            elif lead.next_followup_date and lead.next_followup_date < _today_d:
                lead_temps[lead.id] = 'overdue'
            else:
                last_dt = last_int_map.get(lead.id)
                if last_dt:
                    days = (_now - last_dt).days
                    lead_temps[lead.id] = 'hot' if days <= 2 else ('warm' if days <= 7 else 'cold')
                else:
                    days_new = (_now - lead.created_at).days
                    lead_temps[lead.id] = 'new' if days_new <= 1 else ('warm' if days_new <= 5 else 'cold')

    # Duplicate-phone detection — for each lead on this page, find any OTHER lead(s)
    # (anywhere in the system, not just this page) sharing the same phone number.
    lead_duplicates = {}
    page_phones = [l.phone for l in leads_pagination.items if l.phone]
    if page_phones:
        same_phone_leads = Lead.query.filter(Lead.phone.in_(page_phones)).with_entities(
            Lead.id, Lead.phone, Lead.name, Lead.status, Lead.created_at
        ).all()
        by_phone = {}
        for row in same_phone_leads:
            by_phone.setdefault(row.phone, []).append(row)
        for lead in leads_pagination.items:
            others = [r for r in by_phone.get(lead.phone, []) if r.id != lead.id]
            if others:
                lead_duplicates[lead.id] = [
                    {'id': o.id, 'name': o.name, 'status': o.status,
                     'created_at': o.created_at.strftime('%d %b %Y') if o.created_at else ''}
                    for o in others
                ]

    courses = Course.query.filter_by(is_active=True).all()
    statuses = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted', 'Lost']
    consultants = User.query.filter_by(active=True, role='consultant').order_by(User.username).all() \
                  if (current_user.is_admin() or current_user.can_view_all_leads) else []
    all_users = User.query.filter_by(active=True).order_by(User.username).all() \
                if _can_reassign_leads() else []

    # Leads needing follow-up: created > 1h ago by this user, no follow-up set, no interactions
    followup_reminder_leads = []
    if not current_user.is_admin():
        from datetime import timedelta
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        candidates = Lead.query.filter(
            Lead.added_by == current_user.id,
            Lead.created_at <= one_hour_ago,
            Lead.next_followup_date == None,
            Lead.status.notin_(['Converted', 'Lost']),
        ).order_by(Lead.created_at.desc()).limit(20).all()
        for _l in candidates:
            has_interaction = LeadInteraction.query.filter_by(lead_id=_l.id).count() > 0
            if not has_interaction:
                followup_reminder_leads.append(_l)

    return render_template('leads.html',
                         leads=leads_pagination.items,
                         pagination=leads_pagination,
                         courses=courses,
                         statuses=statuses,
                         search=search,
                         status_filter=status_filter,
                         course_filter=course_filter,
                         consultant_filter=consultant_filter,
                         consultants=consultants,
                         all_users=all_users,
                         lead_form=lead_form,
                         meeting_form=meeting_form,
                         lead=None,
                         converted_students=converted_students,
                         lead_temps=lead_temps,
                         lead_duplicates=lead_duplicates,
                         followup_reminder_leads=followup_reminder_leads,
                         page_title=_SOURCE_CATEGORY_TITLES.get(source_category, 'Leads'))

@main.route('/leads')
@login_required
def leads():
    return _leads_view()

def _can_manage_lead_sources():
    return current_user.is_admin() or current_user.is_sales_manager()

_can_manage_campaigns = _can_manage_lead_sources

@main.route('/leads/website')
@login_required
def leads_website():
    if not _can_manage_lead_sources():
        flash('Access denied. Only admins and sales managers can view this section.', 'error')
        return redirect(url_for('main.leads'))
    return _leads_view(source_category='website')

@main.route('/leads/social-media')
@login_required
def leads_social_media():
    if not _can_manage_lead_sources():
        flash('Access denied. Only admins and sales managers can view this section.', 'error')
        return redirect(url_for('main.leads'))
    return _leads_view(source_category='social_media')


# ── External lead intake (Elementor website form, Meta Lead Ads) ──────────────

def _notify_new_source_lead(lead, category):
    """Alert whoever manages lead sources (admins + sales managers) that a fresh
    website/social-media lead just came in and needs assigning."""
    label = 'Website' if category == 'website' else 'Social Media'
    notif_type = 'new_lead_website' if category == 'website' else 'new_lead_social'
    recipients = [u for u in User.query.all() if u.is_admin() or u.is_sales_manager()]
    for u in recipients:
        db.session.add(CRMNotification(
            user_id=u.id,
            message=f'New {label} lead: "{lead.name}" ({lead.phone}).',
            lead_id=lead.id,
            notif_type=notif_type,
        ))
    db.session.commit()


def _intake_lead(name, phone, email, lead_source, course_id=None, note='', notify_category=None, course_text=None):
    """Create a Lead from an external source, or merge into an existing one with the same phone."""
    name = (name or 'Website Lead').strip()[:100]
    phone = (phone or '').strip()[:20]
    email = (email or '').strip()[:120] or None
    course_text = (course_text or '').strip()[:150] or None

    if not phone:
        return None  # Lead.phone is required — nothing usable to store

    existing = Lead.check_duplicate(phone)
    if existing:
        stamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        addition = f"\n\n[{stamp}] New {lead_source} submission received.{(' ' + note) if note else ''}"
        existing.comments = (existing.comments or '') + addition
        if course_text and not existing.course_interest_id:
            existing.course_text = course_text
        db.session.commit()
        return existing

    lead = Lead(
        name=name,
        phone=phone,
        email=email,
        lead_source=lead_source,
        course_interest_id=course_id,
        course_text=course_text if not course_id else None,
        status='New',
        comments=note or None,
    )
    db.session.add(lead)
    db.session.commit()

    if notify_category:
        _notify_new_source_lead(lead, notify_category)

    return lead


@main.route('/webhooks/website/<token>/', methods=['POST'])
def webhook_website(token):
    integration = LeadSourceIntegration.query.filter_by(
        webhook_token=token, source_type='website', is_active=True
    ).first()
    if not integration:
        return jsonify({'status': 'error', 'message': 'invalid or inactive integration'}), 404

    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    def pick(*keys):
        for k in keys:
            for candidate in (k, k.lower(), k.replace('_', '-'), k.replace('-', '_')):
                if candidate in data and data[candidate]:
                    return data[candidate]
        return ''

    name = pick('name', 'full_name', 'your-name', 'your_name', 'fullname')
    phone = pick('phone', 'tel', 'phone_number', 'your-phone', 'your_phone', 'mobile', 'mobile_number', 'mobile-number', 'whatsapp', 'contact_number', 'contact-number')
    email = pick('email', 'your-email', 'your_email')
    message = pick('message', 'comment', 'comments', 'your-message')
    course_text = pick('course', 'course_name', 'course-name', 'interested_course', 'interested-course',
                        'which_course', 'which-course', 'select_course', 'select-course', 'subject')

    # The course typed into the form is free text and often won't match a real
    # course name exactly — don't try to auto-match it to course_interest_id
    # (that would silently misfile leads). Kept in its own field so it's visible
    # on the lead as-typed until staff assign the real course.
    lead = _intake_lead(
        name=name, phone=phone, email=email,
        lead_source=f"Website - {integration.name}"[:50],
        course_id=integration.default_course_id,
        course_text=course_text,
        note=message,
        notify_category='website',
    )
    if lead is None:
        return jsonify({'status': 'error', 'message': 'no phone number in submission'}), 400

    integration.last_lead_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'ok'}), 200


@main.route('/webhooks/facebook/<token>/', methods=['GET', 'POST'])
def webhook_facebook(token):
    integration = LeadSourceIntegration.query.filter_by(
        webhook_token=token, source_type='facebook', is_active=True
    ).first()
    if not integration:
        return jsonify({'status': 'error', 'message': 'invalid or inactive integration'}), 404

    if request.method == 'GET':
        # Meta's webhook verification handshake
        if (request.args.get('hub.mode') == 'subscribe'
                and request.args.get('hub.verify_token') == integration.fb_verify_token
                and integration.fb_verify_token):
            return request.args.get('hub.challenge', ''), 200
        return 'verification failed', 403

    payload = request.get_json(silent=True) or {}
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            leadgen_id = value.get('leadgen_id')
            if not leadgen_id or not integration.fb_page_access_token:
                continue
            try:
                resp = requests.get(
                    f'https://graph.facebook.com/v19.0/{leadgen_id}',
                    params={'access_token': integration.fb_page_access_token},
                    timeout=10,
                )
                lead_data = resp.json()
            except Exception:
                logging.exception('Failed to fetch Facebook leadgen data for %s', leadgen_id)
                continue

            fields = {f.get('name', '').lower(): (f.get('values') or [''])[0]
                      for f in lead_data.get('field_data', [])}
            platform = (lead_data.get('platform') or 'facebook').lower()
            source_label = 'Social Media (Instagram)' if 'instagram' in platform else 'Social Media (Facebook)'
            course_text = (fields.get('course') or fields.get('which_course') or fields.get('interested_course')
                           or fields.get('course_name') or fields.get('select_course') or '')

            _intake_lead(
                name=fields.get('full_name') or fields.get('name') or '',
                phone=fields.get('phone_number') or fields.get('phone') or '',
                email=fields.get('email') or '',
                lead_source=source_label,
                course_id=integration.default_course_id,
                course_text=course_text,
                note=f"Meta leadgen_id: {leadgen_id}",
                notify_category='social',
            )
            integration.last_lead_at = datetime.utcnow()
            db.session.commit()

    return jsonify({'status': 'ok'}), 200

@main.route('/overdue-followups')
@login_required
def overdue_followups():
    _today = date.today()
    base_q = Lead.query if (current_user.is_admin() or current_user.can_view_all_leads) \
              else Lead.query.filter_by(assigned_to=current_user.id)

    overdue_leads = base_q.filter(
        Lead.next_followup_date < _today,
        Lead.status.notin_(['Converted', 'Lost'])
    ).order_by(Lead.next_followup_date.asc()).all()

    today_leads = base_q.filter(
        Lead.next_followup_date == _today,
        Lead.status.notin_(['Converted', 'Lost'])
    ).order_by(Lead.followup_time.asc()).all()

    # Last interaction date per lead (for overdue + today combined)
    all_ids = [l.id for l in overdue_leads + today_leads]
    last_int_map = {}
    if all_ids:
        rows = db.session.query(
            LeadInteraction.lead_id,
            func.max(LeadInteraction.interaction_date).label('last_date')
        ).filter(LeadInteraction.lead_id.in_(all_ids)
        ).group_by(LeadInteraction.lead_id).all()
        last_int_map = {r.lead_id: r.last_date for r in rows}

    return render_template('overdue_followups.html',
                           overdue_leads=overdue_leads,
                           today_leads=today_leads,
                           today=_today,
                           last_int_map=last_int_map)


@main.route('/leads/<int:id>/quick-followup', methods=['POST'])
@login_required
def lead_quick_followup(id):
    lead = Lead.query.get_or_404(id)
    data = request.get_json() or {}
    try:
        if data.get('followup_date'):
            lead.next_followup_date = datetime.strptime(data['followup_date'], '%Y-%m-%d').date()
        if data.get('followup_time'):
            from datetime import time as _time
            parts = data['followup_time'].split(':')
            lead.followup_time = _time(int(parts[0]), int(parts[1]))
        else:
            lead.followup_time = None
        if data.get('followup_type'):
            lead.followup_type = data['followup_type']
        if data.get('followup_priority'):
            lead.followup_priority = data['followup_priority']
        if data.get('status'):
            lead.status = data['status']

        # Log reschedule note as an activity if provided
        note = (data.get('note') or '').strip()
        if note:
            interaction = LeadInteraction(
                lead_id=id,
                interaction_type='Note',
                interaction_date=datetime.now(),
                content=note,
                created_by_id=current_user.id,
                is_important=False
            )
            db.session.add(interaction)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@main.route('/leads/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lead(id):
    if id == 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'errors': ['Invalid lead ID.']
            }), 400
        flash('Invalid lead ID.', 'error')
        return redirect(url_for('main.leads'))
    
    lead = Lead.query.get_or_404(id)

    # ROLE-BASED ACCESS CONTROL
    if not (current_user.is_admin() or current_user.can_view_all_leads or lead.assigned_to == current_user.id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'errors': ['You can only edit leads assigned to you!']
            }), 403
        flash('You can only edit leads assigned to you!', 'error')
        return redirect(url_for('main.leads'))

    # 24-hour edit lock: non-admins cannot edit leads older than 24 hours
    if not current_user.is_admin():
        from datetime import timedelta
        lead_age = datetime.now() - lead.created_at
        if lead_age.total_seconds() > 24 * 3600:
            msg = 'This lead can no longer be edited — leads are locked after 24 hours. Contact an admin if you need changes.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'errors': [msg]}), 403
            flash(msg, 'error')
            return redirect(url_for('main.lead_detail', lead_id=lead.id))

    form = LeadForm(obj=lead)
    form.course_interest_id.choices = [(0, 'Select Course')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        # DUPLICATE DETECTION - Check phone/WhatsApp across all users but exclude current lead
        existing_lead = Lead.check_duplicate(form.phone.data, form.whatsapp.data, exclude_id=lead.id)
        if existing_lead:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'errors': [f'Duplicate lead detected based on phone or WhatsApp number! Lead exists (Added by: {existing_lead.added_by_user.username if existing_lead.added_by_user else "Unknown"})']
                }), 400
            flash(f'Duplicate lead detected based on phone or WhatsApp number! Lead exists (Added by: {existing_lead.added_by_user.username if existing_lead.added_by_user else "Unknown"})', 'warning')
            return render_template('edit_lead.html', lead_form=form, lead=lead)
        
        try:
            form.populate_obj(lead)

            course_interest_ids = request.form.getlist('course_interest_ids[]', type=int)
            if not course_interest_ids and form.course_interest_id.data:
                course_interest_ids = [form.course_interest_id.data]
            lead.course_interest_id = course_interest_ids[0] if course_interest_ids else None

            # Handle assignment change by admin
            if current_user.is_admin() and form.assigned_to.data != 0:
                new_assignee = form.assigned_to.data
                if new_assignee != lead.assigned_to:
                    db.session.add(LeadReassignment(
                        lead_id=lead.id,
                        from_user_id=lead.assigned_to,
                        to_user_id=new_assignee,
                        assigned_by_id=current_user.id,
                        note='Assigned via Edit Lead',
                    ))
                    _notify_new_assignment(lead, new_assignee, current_user.id)
                lead.assigned_to = new_assignee
            db.session.commit()

            if course_interest_ids:
                LeadCourseInterest.query.filter_by(lead_id=lead.id).delete()
                for cid in course_interest_ids:
                    db.session.add(LeadCourseInterest(lead_id=lead.id, course_id=cid))
                db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'Lead updated successfully!'
                })
            flash('Lead updated successfully!', 'success')
            return redirect(url_for('main.lead_detail', lead_id=lead.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating lead: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'errors': ['An error occurred while updating the lead. Please try again.']
                }), 500
            flash('An error occurred while updating the lead. Please try again.', 'error')
            return render_template('edit_lead.html', lead_form=form, lead=lead)
    
    # Handle form validation errors for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(f"{field}: {error}")
        return jsonify({
            'success': False,
            'errors': errors or ['Invalid form data. Please check your inputs.']
        }), 400
    
    # For GET requests, render the edit page as a fallback
    meeting_form = MeetingForm()
    meeting_form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').all()]
    meeting_form.student_id.choices = [(0, 'Select Student')] + [(s.id, s.name) for s in Student.query.all()]
    
    return render_template('edit_lead.html', lead_form=form, lead=lead)

@main.route('/leads/add', methods=['POST'])
@login_required
def add_lead():
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Read fields directly — avoids WTForms SelectField validation issues
    name     = (request.form.get('name') or '').strip()
    phone    = (request.form.get('phone') or '').strip()
    whatsapp = (request.form.get('whatsapp') or '').strip()
    email    = (request.form.get('email') or '').strip() or None
    lead_source       = request.form.get('lead_source') or None
    comments          = (request.form.get('comments') or '').strip() or None
    course_interest_ids = request.form.getlist('course_interest_ids[]', type=int)
    if not course_interest_ids:
        # Fallback for any caller still posting the old single-select field name
        single = request.form.get('course_interest_id', '0')
        try:
            single_id = int(single) or None
        except (ValueError, TypeError):
            single_id = None
        course_interest_ids = [single_id] if single_id else []
    course_interest_id = course_interest_ids[0] if course_interest_ids else None

    # All fields except comments are required
    errors = []
    if not name:
        errors.append('Name is required.')
    if not phone:
        errors.append('Phone number is required.')
    if not email:
        errors.append('Email address is required.')
    if not whatsapp:
        errors.append('WhatsApp number is required.')
    if not course_interest_ids:
        errors.append('At least one course interest is required.')
    if not lead_source:
        errors.append('Lead source is required.')

    if errors:
        if is_xhr:
            return jsonify({'success': False, 'errors': errors}), 400
        flash(' '.join(errors), 'error')
        return redirect(url_for('main.leads'))

    # Duplicate check
    existing_lead = Lead.check_duplicate(phone, whatsapp or phone)
    if existing_lead:
        msg = f'Duplicate lead! This number already exists (added by: {existing_lead.added_by_user.username if existing_lead.added_by_user else "Unknown"}).'
        if is_xhr:
            return jsonify({'success': False, 'errors': [msg]}), 400
        flash(msg, 'warning')
        return redirect(url_for('main.leads'))

    try:
        lead = Lead()
        lead.name              = name
        lead.phone             = phone
        lead.whatsapp          = whatsapp or phone
        lead.email             = email
        lead.lead_source       = lead_source
        lead.comments          = comments
        lead.course_interest_id = course_interest_id
        lead.status            = 'New'
        lead.added_by          = current_user.id
        lead.assigned_to       = current_user.id  # self-assign by default

        db.session.add(lead)
        db.session.commit()

        for cid in course_interest_ids:
            db.session.add(LeadCourseInterest(lead_id=lead.id, course_id=cid))
        db.session.commit()

        # Log the initial comment as the first activity entry
        if comments:
            first_note = LeadInteraction(
                lead_id=lead.id,
                interaction_type='Note',
                content=f"[Initial Comment] {comments}",
                interaction_date=lead.created_at or datetime.now(),
                created_by_id=current_user.id,
                is_important=False,
            )
            db.session.add(first_note)
            db.session.commit()

        detail_url = url_for('main.lead_detail', lead_id=lead.id, new_lead='1', _external=False)
        if is_xhr:
            return jsonify({'success': True, 'message': 'Lead added successfully!', 'lead_id': lead.id, 'redirect_url': detail_url})
        flash('Lead added successfully!', 'success')
        return redirect(detail_url)

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating lead: {e}")
        if is_xhr:
            return jsonify({'success': False, 'errors': ['Server error while creating lead. Please try again.']}), 500
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('main.leads'))

@main.route('/leads/bulk-assign', methods=['POST'])
@login_required
def bulk_assign_leads():
    # Only admins can perform bulk assignments
    if not current_user.is_admin():
        flash('Access denied. Only admins can perform bulk assignments.', 'error')
        return redirect(url_for('main.leads'))
    
    form = BulkAssignForm()
    if form.validate_on_submit():
        try:
            lead_ids = form.selected_leads.data.split(',') if form.selected_leads.data else []
            if not lead_ids:
                flash('No leads selected for assignment.', 'warning')
                return redirect(url_for('main.leads'))
            
            # Update selected leads
            updated_count = 0
            for lead_id in lead_ids:
                if lead_id.strip():
                    lead = Lead.query.get(int(lead_id.strip()))
                    if lead:
                        if lead.assigned_to != form.assigned_to.data:
                            db.session.add(LeadReassignment(
                                lead_id=lead.id,
                                from_user_id=lead.assigned_to,
                                to_user_id=form.assigned_to.data,
                                assigned_by_id=current_user.id,
                                note='Bulk assign',
                            ))
                            _notify_new_assignment(lead, form.assigned_to.data, current_user.id)
                        lead.assigned_to = form.assigned_to.data
                        updated_count += 1
            
            db.session.commit()
            flash(f'Successfully assigned {updated_count} leads to the selected consultant.', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error in bulk assignment: {str(e)}")
            flash('An error occurred during bulk assignment. Please try again.', 'error')
    else:
        flash('Invalid form data. Please try again.', 'error')
    
    return redirect(url_for('main.leads'))


def _can_reassign_leads():
    return current_user.is_admin() or current_user.is_sales_manager() or current_user.can_view_all_leads


def _notify_new_assignment(lead, to_user_id, actor_id):
    """Pop-up/bell notification for whoever a lead just got assigned to. No-op for
    self-assignment (actor assigning a lead to themselves needs no notice)."""
    if not to_user_id or to_user_id == actor_id:
        return
    db.session.add(CRMNotification(
        user_id=to_user_id,
        message=f'New lead assigned to you: "{lead.name}" (L-{lead.id}).',
        lead_id=lead.id,
        notif_type='new_assignment',
    ))


def _recent_assignment_status(user_id):
    """Leads currently assigned to user_id, that were assigned via a logged
    LeadReassignment, and that user_id has not yet logged a LeadInteraction on
    since that assignment. Shared by the New Assignments page, its sidebar
    badge count, and the hourly "connect with your lead" pop-up."""
    reassigned_ids_q = db.session.query(LeadReassignment.lead_id).filter_by(
        to_user_id=user_id
    ).subquery()

    candidates = Lead.query.filter(
        Lead.assigned_to == user_id,
        Lead.id.in_(reassigned_ids_q),
    ).order_by(desc(Lead.created_at)).all()

    results = []
    for lead in candidates:
        last_ra = LeadReassignment.query.filter_by(
            lead_id=lead.id, to_user_id=user_id
        ).order_by(LeadReassignment.assigned_at.desc()).first()
        if not last_ra:
            continue
        contacted = LeadInteraction.query.filter(
            LeadInteraction.lead_id == lead.id,
            LeadInteraction.created_by_id == user_id,
            LeadInteraction.interaction_date >= last_ra.assigned_at,
        ).count() > 0
        results.append({'lead': lead, 'reassignment': last_ra, 'contacted': contacted})
    return results


@main.route('/leads/<int:id>/reassign', methods=['POST'])
@login_required
def reassign_lead(id):
    if not _can_reassign_leads():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    lead = Lead.query.get_or_404(id)
    to_user_id = request.form.get('to_user_id', type=int)
    note = request.form.get('note', '').strip()

    if not to_user_id:
        return jsonify({'success': False, 'message': 'Please select a consultant.'}), 400

    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'success': False, 'message': 'User not found.'}), 400

    from_user_id = lead.assigned_to
    if from_user_id == to_user_id:
        return jsonify({'success': False, 'message': 'Lead is already assigned to this person.'}), 400

    reassignment = LeadReassignment(
        lead_id=lead.id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        assigned_by_id=current_user.id,
        note=note or None,
    )
    db.session.add(reassignment)

    # Notify the previous owner (if there was one and it wasn't the reassigner)
    if from_user_id and from_user_id != current_user.id:
        msg = (f"Lead \"{lead.name}\" (L-{lead.id}) has been reassigned from you to "
               f"{to_user.username} by {current_user.username}. "
               f"You no longer need to contact this person.")
        db.session.add(CRMNotification(
            user_id=from_user_id,
            message=msg,
            lead_id=lead.id,
            notif_type='reassignment',
        ))

    _notify_new_assignment(lead, to_user_id, current_user.id)

    lead.assigned_to = to_user_id
    db.session.commit()

    return jsonify({'success': True, 'message': f'Lead "{lead.name}" reassigned to {to_user.username}.'})


@main.route('/leads/bulk-reassign', methods=['POST'])
@login_required
def bulk_reassign_leads():
    if not _can_reassign_leads():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    lead_ids   = request.form.getlist('lead_ids[]', type=int)
    to_user_id = request.form.get('to_user_id', type=int)
    note       = request.form.get('note', '').strip()

    if not lead_ids:
        return jsonify({'success': False, 'message': 'No leads selected.'}), 400
    if not to_user_id:
        return jsonify({'success': False, 'message': 'Please select a consultant.'}), 400

    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'success': False, 'message': 'User not found.'}), 400

    leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
    skipped = 0
    reassigned = 0

    for lead in leads:
        if lead.assigned_to == to_user_id:
            skipped += 1
            continue

        from_user_id = lead.assigned_to
        db.session.add(LeadReassignment(
            lead_id=lead.id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            assigned_by_id=current_user.id,
            note=note or None,
        ))

        if from_user_id and from_user_id != current_user.id:
            msg = (f"Lead \"{lead.name}\" (L-{lead.id}) has been reassigned from you to "
                   f"{to_user.username} by {current_user.username}.")
            db.session.add(CRMNotification(
                user_id=from_user_id,
                message=msg,
                lead_id=lead.id,
                notif_type='reassignment',
            ))

        _notify_new_assignment(lead, to_user_id, current_user.id)

        lead.assigned_to = to_user_id
        reassigned += 1

    db.session.commit()

    msg = f'{reassigned} lead{"s" if reassigned != 1 else ""} reassigned to {to_user.username}.'
    if skipped:
        msg += f' ({skipped} already assigned — skipped.)'
    return jsonify({'success': True, 'message': msg, 'reassigned': reassigned})


@main.route('/leads/assign-rule', methods=['POST'])
@login_required
def run_assign_rule():
    """Manual, on-demand bulk assignment: assign every currently-unassigned lead matching
    a source type + date range to one consultant. Run fresh each time — nothing is saved
    as a recurring/automatic rule."""
    if not _can_manage_lead_sources():
        return jsonify({'success': False, 'message': 'Access denied. Only admins and sales managers can run this.'}), 403

    lead_type   = request.form.get('lead_type', 'all')
    date_from   = request.form.get('date_from', '')
    date_to     = request.form.get('date_to', '')
    to_user_id  = request.form.get('to_user_id', type=int)

    if not to_user_id:
        return jsonify({'success': False, 'message': 'Please select who to assign to.'}), 400
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'success': False, 'message': 'User not found.'}), 400

    query = Lead.query.filter(Lead.assigned_to.is_(None))

    source_filter_fn = _SOURCE_CATEGORY_FILTERS.get(lead_type)
    if source_filter_fn:
        query = source_filter_fn(query)

    if date_from:
        try:
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid "date from".'}), 400
    if date_to:
        try:
            query = query.filter(Lead.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid "date to".'}), 400

    matched_leads = query.all()
    if not matched_leads:
        return jsonify({'success': True, 'message': 'No unassigned leads matched these criteria.', 'assigned': 0})

    for lead in matched_leads:
        db.session.add(LeadReassignment(
            lead_id=lead.id,
            from_user_id=None,
            to_user_id=to_user_id,
            assigned_by_id=current_user.id,
            note='Assigned via Assign Rule',
        ))
        _notify_new_assignment(lead, to_user_id, current_user.id)
        lead.assigned_to = to_user_id

    db.session.commit()

    msg = f'{len(matched_leads)} unassigned lead{"s" if len(matched_leads) != 1 else ""} assigned to {to_user.username}.'
    return jsonify({'success': True, 'message': msg, 'assigned': len(matched_leads)})


@main.route('/leads/merge', methods=['POST'])
@login_required
def merge_leads():
    """Merge one or more duplicate leads (same phone number) into a single surviving lead.
    Every related record (interactions, meetings, quotes, payment links, reassignment
    history, notifications, converted-student link) is moved onto the survivor before
    the duplicate rows are deleted."""
    if not _can_reassign_leads():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    keep_id = request.form.get('keep_id', type=int)
    remove_ids = request.form.getlist('remove_ids[]', type=int)

    if not keep_id or not remove_ids:
        return jsonify({'success': False, 'message': 'Missing lead selection.'}), 400
    if keep_id in remove_ids:
        return jsonify({'success': False, 'message': 'Cannot merge a lead into itself.'}), 400

    keeper = Lead.query.get(keep_id)
    if not keeper:
        return jsonify({'success': False, 'message': 'Lead to keep was not found.'}), 404

    merged_names = []
    for remove_id in remove_ids:
        dupe = Lead.query.get(remove_id)
        if not dupe:
            continue
        if dupe.phone != keeper.phone:
            return jsonify({'success': False, 'message': f'"{dupe.name}" does not share the same phone number — refusing to merge.'}), 400

        # Move every related record onto the survivor
        LeadInteraction.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        Meeting.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        Student.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        LeadQuote.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        QuoteBundle.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        PaymentLink.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        LeadReassignment.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})
        CRMNotification.query.filter_by(lead_id=dupe.id).update({'lead_id': keeper.id})

        # Course interests: move over any the survivor doesn't already have, drop exact duplicates
        keeper_course_ids = {ci.course_id for ci in keeper.course_interests}
        for ci in LeadCourseInterest.query.filter_by(lead_id=dupe.id).all():
            if ci.course_id in keeper_course_ids:
                db.session.delete(ci)
            else:
                ci.lead_id = keeper.id
                keeper_course_ids.add(ci.course_id)

        # Fill in anything the survivor is missing
        keeper.email = keeper.email or dupe.email
        keeper.whatsapp = keeper.whatsapp or dupe.whatsapp
        keeper.course_interest_id = keeper.course_interest_id or dupe.course_interest_id
        keeper.assigned_to = keeper.assigned_to or dupe.assigned_to
        if (not keeper.quoted_amount) and dupe.quoted_amount:
            keeper.quoted_amount = dupe.quoted_amount

        note = f'\n\n[Merged from duplicate lead L-{dupe.id} "{dupe.name}", {dupe.created_at.strftime("%d %b %Y") if dupe.created_at else ""}]'
        if dupe.comments:
            note += f'\n{dupe.comments}'
        keeper.comments = (keeper.comments or '') + note

        merged_names.append(dupe.name)
        db.session.delete(dupe)

    db.session.commit()

    if not merged_names:
        return jsonify({'success': False, 'message': 'Nothing was merged — leads not found or phone mismatch.'}), 400

    msg = f'Merged {len(merged_names)} duplicate lead{"s" if len(merged_names) != 1 else ""} into "{keeper.name}".'
    return jsonify({'success': True, 'message': msg, 'merged': len(merged_names)})


@main.route('/leads/new-assignments')
@login_required
def new_assignments():
    """Leads recently reassigned to current user that they haven't contacted yet."""
    new_assign_leads = _recent_assignment_status(current_user.id)
    return render_template('new_assignments.html', new_assign_leads=new_assign_leads)


@main.route('/api/notifications/')
@login_required
def get_notifications():
    notifs = CRMNotification.query.filter_by(
        user_id=current_user.id
    ).order_by(CRMNotification.created_at.desc()).limit(20).all()
    unread = CRMNotification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        'unread_count': unread,
        'notifications': [{
            'id': n.id,
            'message': n.message,
            'lead_id': n.lead_id,
            'type': n.notif_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d %H:%M'),
        } for n in notifs]
    })


@main.route('/api/notifications/<int:nid>/read', methods=['POST'])
@login_required
def mark_notification_read(nid):
    n = CRMNotification.query.get_or_404(nid)
    if n.user_id != current_user.id:
        return jsonify({'success': False}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@main.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    CRMNotification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@main.route('/api/new-assignments-count')
@login_required
def new_assignments_count():
    """Count leads reassigned to current user that they haven't contacted yet."""
    results = _recent_assignment_status(current_user.id)
    count = sum(1 for r in results if not r['contacted'])
    return jsonify({'count': count})


@main.route('/api/pending-contacts')
@login_required
def pending_contacts():
    """Leads currently assigned to current user that they haven't contacted yet —
    powers the hourly "connect with your lead" pop-up (and fires immediately for
    a brand-new assignment, since it lands in this list right away)."""
    results = _recent_assignment_status(current_user.id)
    pending = [r for r in results if not r['contacted']]
    return jsonify({
        'count': len(pending),
        'leads': [{
            'id': r['lead'].id,
            'name': r['lead'].name,
            'phone': r['lead'].phone,
            'assigned_at': r['reassignment'].assigned_at.strftime('%b %d, %H:%M') if r['reassignment'].assigned_at else '',
        } for r in pending]
    })


@main.route('/leads/<int:id>/convert', methods=['POST'])
@login_required
def convert_lead(id):
    lead = Lead.query.get_or_404(id)
    
    if lead.course_interest_id is None:
        flash('Please select a course before converting the lead.', 'error')
        return redirect(url_for('main.leads'))
    
    student = Student(
        lead_id=lead.id,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        course_id=lead.course_interest_id,
        total_fee=lead.course_interest.price,
        enrollment_date=date.today()
    )
    
    lead.status = 'Converted'
    
    db.session.add(student)
    db.session.commit()
    
    flash(f'Lead {lead.name} converted to student successfully!', 'success')
    return redirect(url_for('main.students'))

@main.route('/leads/<int:id>', methods=['GET'], endpoint='lead_detail_simple')
@login_required
def lead_detail_simple(id):
    lead = Lead.query.get_or_404(id)
    return render_template('lead_detail.html',
                         lead=lead)

@main.route('/leads/<int:id>/delete', methods=['GET'])
@login_required
def delete_lead(id):
    lead = Lead.query.get_or_404(id)
    # Remove child records before deleting to avoid FK constraint errors
    LeadInteraction.query.filter_by(lead_id=id).delete(synchronize_session=False)
    LeadQuote.query.filter_by(lead_id=id).delete(synchronize_session=False)
    Meeting.query.filter(Meeting.lead_id == id).update({'lead_id': None}, synchronize_session=False)
    Student.query.filter(Student.lead_id == id).update({'lead_id': None}, synchronize_session=False)
    PaymentLink.query.filter(PaymentLink.lead_id == id).update({'lead_id': None}, synchronize_session=False)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead deleted successfully!', 'success')
    return redirect(url_for('main.leads'))

@main.route('/pipeline')
@login_required
def pipeline():
    lead_form = LeadForm()
    lead_form.course_interest_id.choices = [(0, 'Select Course')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    meeting_form = MeetingForm()
    
    # ROLE-BASED ACCESS CONTROL FOR PIPELINE
    if current_user.is_admin() or current_user.can_view_all_leads:
        # Admin sees all leads
        pipeline_query = db.session.query(
            Lead.status,
            func.count(Lead.id).label('count'),
            func.sum(Lead.quoted_amount).label('total_value')
        )
        meeting_form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').all()]
    else:
        # Consultants see only their own leads
        pipeline_query = db.session.query(
            Lead.status,
            func.count(Lead.id).label('count'),
            func.sum(Lead.quoted_amount).label('total_value')
        ).filter(Lead.added_by == current_user.id)
        meeting_form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted', Lead.added_by == current_user.id).all()]
    
    pipeline_data = pipeline_query.group_by(Lead.status).all()
    meeting_form.student_id.choices = [(0, 'Select Student')] + [(s.id, s.name) for s in Student.query.all()]
    
    pipeline_dict = {}
    for status, count, total_value in pipeline_data:
        pipeline_dict[status] = {
            'count': count,
            'total_value': total_value or 0
        }
    
    statuses = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted', 'Lost']
    for status in statuses:
        if status not in pipeline_dict:
            pipeline_dict[status] = {'count': 0, 'total_value': 0}
    
    leads_by_status = {}
    for status in statuses:
        if current_user.is_admin() or current_user.can_view_all_leads:
            leads_by_status[status] = Lead.query.filter_by(status=status).all()
        else:
            leads_by_status[status] = Lead.query.filter_by(status=status, added_by=current_user.id).all()
    
    return render_template('pipeline.html',
                         pipeline_data=pipeline_dict,
                         leads_by_status=leads_by_status,
                         statuses=statuses,
                         lead_form=lead_form,
                         meeting_form=meeting_form,
                         lead=None,
                         today=date.today())

@main.route('/meetings')
@login_required
def meetings():
    today = date.today()
    # Load 3 months back + 6 months forward so calendar navigation works
    range_start = (today.replace(day=1) - timedelta(days=92)).replace(day=1)
    range_end   = today.replace(day=1) + timedelta(days=186)

    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    if current_user.is_admin() or current_user.can_view_all_leads:
        all_meetings = Meeting.query.filter(
            Meeting.meeting_date >= range_start,
            Meeting.meeting_date <= range_end
        ).order_by(Meeting.meeting_date).all()
        meeting_form = MeetingForm()
        meeting_form.lead_id.choices = [(0, 'Select Lead')] + [
            (l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').order_by(Lead.name).all()
        ]
    else:
        all_meetings = Meeting.query.filter(
            Meeting.meeting_date >= range_start,
            Meeting.meeting_date <= range_end,
            Meeting.created_by_id == current_user.id
        ).order_by(Meeting.meeting_date).all()
        meeting_form = MeetingForm()
        meeting_form.lead_id.choices = [(0, 'Select Lead')] + [
            (l.id, l.name) for l in Lead.query.filter(
                Lead.status != 'Converted', Lead.added_by == current_user.id
            ).order_by(Lead.name).all()
        ]

    meeting_form.student_id.choices = [(0, 'Select Student')] + [
        (s.id, s.name) for s in Student.query.order_by(Student.first_name).all()
    ]

    meetings_data = [{
        'id':           m.id,
        'title':        m.title,
        'meeting_date': m.meeting_date.isoformat(),
        'meeting_type': m.meeting_type,
        'duration':     m.duration,
        'status':       m.status,
        'meeting_link': m.meeting_link or '',
        'location':     m.location or '',
        'agenda':       m.agenda or '',
        'notes':        m.notes or '',
        'lead_name':    m.lead.name    if m.lead    else None,
        'lead_id':      m.lead_id,
        'student_name': m.student.name if m.student else None,
        'student_id':   m.student_id,
        'created_by':   m.created_by.username if m.created_by else 'System',
    } for m in all_meetings]

    return render_template('meetings.html',
                           meetings=all_meetings,
                           meetings_data=meetings_data,
                           today=today,
                           week_start=week_start,
                           week_end=week_end,
                           meeting_form=meeting_form)


@main.route('/meetings/<int:meeting_id>/status', methods=['POST'])
@login_required
def update_meeting_status(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    new_status = request.form.get('status', '').strip()
    if new_status not in ('Scheduled', 'Completed', 'Cancelled', 'No Show'):
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    meeting.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'status': new_status})

@main.route('/meetings/add', methods=['GET', 'POST'])
@login_required
def add_meeting():
    form = MeetingForm()
    form.lead_id.choices = [(0, 'Select Lead')] + [(l.id, l.name) for l in Lead.query.filter(Lead.status != 'Converted').all()]
    form.student_id.choices = [(0, 'Select Student')] + [(s.id, s.name) for s in Student.query.all()]
    
    if form.validate_on_submit():
        meeting = Meeting(
            title=form.title.data,
            meeting_type=form.meeting_type.data,
            meeting_date=datetime.combine(form.meeting_date.data, form.meeting_time.data),
            duration=form.duration.data,
            meeting_link=form.meeting_link.data,
            location=form.location.data,
            agenda=form.agenda.data,
            created_by_id=current_user.id,
            email_reminder=form.email_reminder.data,
            sms_reminder=form.sms_reminder.data,
            reminder_time=int(form.reminder_time.data) if form.reminder_time.data else None
        )
        
        if form.lead_id.data != 0:
            meeting.lead_id = form.lead_id.data
        if form.student_id.data != 0:
            meeting.student_id = form.student_id.data
            
        db.session.add(meeting)
        db.session.commit()
        flash('Meeting scheduled successfully!', 'success')
        return redirect(url_for('main.meetings'))
    
    return render_template('modals/meeting_modal.html', meeting_form=form, title='Schedule Meeting')

def _course_student_counts(courses_list):
    """Return {course_id: count} combining ImsStudent + CRM Student, role-filtered."""
    from collections import defaultdict
    from models import ImsStudent

    is_priv = current_user.is_admin() or current_user.can_view_all_leads

    # ImsStudent (ERP-synced)
    ims_q = ImsStudent.query
    if not is_priv:
        ims_q = ims_q.filter(ImsStudent.consultant_username == current_user.username)
    ims_all = ims_q.all()

    # CRM Student
    crm_q = Student.query
    if not is_priv:
        crm_q = crm_q.join(Lead, Student.lead_id == Lead.id).filter(
            Lead.assigned_to == current_user.id
        )
    crm_all = crm_q.all()

    # Identifiers already covered by IMS (for dedup)
    ims_seen = set()
    for s in ims_all:
        if s.email:
            ims_seen.add(s.email.lower().strip())
        if s.phone:
            ims_seen.add(s.phone.strip())

    # course name (lower) → course id
    name_to_id = {c.name.lower(): c.id for c in courses_list}

    ims_counts = defaultdict(int)
    for s in ims_all:
        for cname in s.courses:           # property that JSON-parses courses_json
            cid = name_to_id.get(cname.lower())
            if cid:
                ims_counts[cid] += 1

    crm_counts = defaultdict(int)
    for s in crm_all:
        if not s.course_id:
            continue
        e_key = (s.email or '').lower().strip()
        p_key = (s.phone or '').strip()
        if (e_key and e_key in ims_seen) or (p_key and p_key in ims_seen):
            continue  # already counted via IMS record
        crm_counts[s.course_id] += 1

    return {c.id: ims_counts[c.id] + crm_counts[c.id] for c in courses_list}


@main.route('/courses')
@login_required
def courses():
    courses = Course.query.order_by(Course.name).all()
    for course in courses:
        course.name = course.name.replace('&', '&amp;') if course.name else ''
        course.description = course.description.replace('&', '&amp;') if course.description else ''
        course.category = course.category.replace('&', '&amp;') if course.category else ''
        if course.key_points:
            try:
                key_points = json.loads(course.key_points)
                course.key_points = json.dumps([point.replace('&', '&amp;') for point in key_points])
            except json.JSONDecodeError:
                course.key_points = '[]'

    student_counts = _course_student_counts(courses)
    total_student_count = sum(student_counts.values())

    return render_template('courses.html', courses=courses,
                           student_counts=student_counts,
                           total_student_count=total_student_count)

@main.route('/api/courses')
@login_required
def get_courses():
    courses = Course.query.order_by(Course.name).all()
    counts  = _course_student_counts(courses)
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'price': c.price,
        'duration': c.duration,
        'category': c.category,
        'is_active': c.is_active,
        'students_count': counts.get(c.id, 0),
        'max_students': c.max_students,
        'key_points': json.loads(c.key_points) if c.key_points else []
    } for c in courses])

@main.route('/api/course/<int:course_id>/students')
@login_required
def course_students_api(course_id):
    from models import Student
    course = Course.query.get_or_404(course_id)
    students = Student.query.filter_by(course_id=course_id).order_by(
        desc(Student.enrollment_date)
    ).all()
    return jsonify({
        'course': {'id': course.id, 'name': course.name},
        'total': len(students),
        'students': [{
            'id': s.id,
            'name': s.name,
            'phone': s.phone,
            'email': s.email or '',
            'status': s.status,
            'enrollment_date': s.enrollment_date.isoformat() if s.enrollment_date else '',
            'fee_paid': float(s.fee_paid or 0),
            'total_fee': float(s.total_fee or 0),
            'batch': s.batch_name or '',
            'progress': s.progress_percentage or 0,
        } for s in students]
    })

@main.route('/courses/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(id):
    course = Course.query.get_or_404(id)
    form = CourseForm(obj=course)
    
    if form.validate_on_submit():
        form.populate_obj(course)
        course.slug = form.name.data.lower().replace(' ', '-').replace('/', '-')
        course.key_points = form.key_points.data if form.key_points.data else '[]'
        
        try:
            db.session.commit()
            flash('Course updated successfully!', 'success')
            return redirect(url_for('main.courses'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating course: {str(e)}")
            flash('An error occurred while updating the course. Please try again.', 'error')
    
    return render_template('edit_course.html', form=form, course=course)

@main.route('/courses/add', methods=['GET', 'POST'])
@login_required
def add_course():
    form = CourseForm()
    
    if form.validate_on_submit():
        slug = form.name.data.lower().replace(' ', '-').replace('/', '-')
        
        # Validate and sanitize key_points
        key_points = form.key_points.data if form.key_points.data else '[]'
        try:
            json.loads(key_points)
        except json.JSONDecodeError:
            flash('Invalid key points format. Please provide a valid JSON array (e.g., ["point1", "point2"]).', 'error')
            return render_template('add_course.html', form=form, title='Add New Course')
        
        course = Course(
            name=form.name.data,
            slug=slug,
            description=form.description.data,
            price=form.price.data,
            duration=form.duration.data,
            duration_type=form.duration_type.data,
            category=form.category.data,
            max_students=form.max_students.data or 20,
            is_active=form.is_active.data,
            key_points=key_points
        )
        
        try:
            db.session.add(course)
            db.session.commit()
            flash('Course added successfully!', 'success')
            return redirect(url_for('main.courses'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding course: {str(e)}")
            flash('An error occurred while adding the course. Please try again.', 'error')
    
    return render_template('add_course.html', form=form, title='Add New Course')

@main.route('/students')
@login_required
def students():
    import math, json as _json
    from datetime import date as _date
    from types import SimpleNamespace
    from sqlalchemy.orm import joinedload

    page          = request.args.get('page', 1, type=int)
    search        = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    course_id_str = request.args.get('course_id', '')
    per_page      = 25

    is_privileged = current_user.is_admin() or current_user.can_view_all_leads

    # ── ERP-synced students (ImsStudent) ─────────────────────────────────
    from models import ImsStudent
    ims_q = ImsStudent.query
    if not is_privileged:
        ims_q = ims_q.filter(ImsStudent.consultant_username == current_user.username)
    if search:
        like = f'%{search}%'
        ims_q = ims_q.filter(db.or_(
            ImsStudent.first_name.ilike(like),
            ImsStudent.last_name.ilike(like),
            ImsStudent.phone.ilike(like),
            ImsStudent.email.ilike(like),
            ImsStudent.registration_number.ilike(like),
        ))
    if status_filter:
        ims_q = ims_q.filter(ImsStudent.student_status == status_filter.lower())
    if course_id_str:
        try:
            course_obj = Course.query.get(int(course_id_str))
            if course_obj:
                ims_q = ims_q.filter(ImsStudent.courses_json.ilike(f'%{course_obj.name}%'))
            else:
                ims_q = ims_q.filter(db.false())
        except (ValueError, TypeError):
            pass
    ims_rows = ims_q.order_by(desc(ImsStudent.registration_date)).all()

    # ── CRM-enrolled students (Student) ──────────────────────────────────
    crm_q = Student.query.options(
        joinedload(Student.course),
        joinedload(Student.original_lead).joinedload(Lead.assigned_consultant),
    )
    if not is_privileged:
        crm_q = crm_q.join(Lead, Student.lead_id == Lead.id).filter(
            Lead.assigned_to == current_user.id
        )
    if search:
        like = f'%{search}%'
        crm_q = crm_q.filter(db.or_(
            Student.first_name.ilike(like),
            Student.last_name.ilike(like),
            Student.phone.ilike(like),
            Student.email.ilike(like),
        ))
    if status_filter:
        crm_q = crm_q.filter(Student.status == status_filter)
    if course_id_str:
        try:
            crm_q = crm_q.filter(Student.course_id == int(course_id_str))
        except (ValueError, TypeError):
            pass
    crm_rows = crm_q.order_by(desc(Student.enrollment_date)).all()

    # ── Combine: IMS is authoritative; skip CRM duplicates ───────────────
    seen = set()
    for s in ims_rows:
        if s.email:
            seen.add(s.email.lower().strip())
        if s.phone:
            seen.add(s.phone.strip())

    unified = []

    for s in ims_rows:
        courses_list = []
        try:
            courses_list = _json.loads(s.courses_json or '[]')
        except Exception:
            pass
        unified.append(SimpleNamespace(
            source='erp',
            id=s.id,
            first_name=s.first_name or '',
            last_name=s.last_name or '',
            email=s.email or '',
            phone=s.phone or '',
            name=(f"{s.first_name or ''} {s.last_name or ''}").strip(),
            course_name=', '.join(courses_list) if courses_list else '—',
            consultant_display=s.consultant_name or '—',
            sort_date=s.registration_date if s.registration_date else _date.min,
            date_display=s.registration_date,
            status=(s.student_status or 'active').title(),
            fee_paid=0.0,
            total_fee=float(s.total_fee or 0),
            lead_id=s.lead_crm_id,
            reg_number=s.registration_number or '',
            detail_url=url_for('main.view_student', id=s.id),
        ))

    for s in crm_rows:
        email_key = (s.email or '').lower().strip()
        phone_key = (s.phone or '').strip()
        if (email_key and email_key in seen) or (phone_key and phone_key in seen):
            continue  # already represented by ERP record
        consultant = '—'
        if s.original_lead and s.original_lead.assigned_consultant:
            consultant = s.original_lead.assigned_consultant.username
        unified.append(SimpleNamespace(
            source='crm',
            id=s.id,
            first_name=s.first_name or '',
            last_name=s.last_name or '',
            email=s.email or '',
            phone=s.phone or '',
            name=(f"{s.first_name or ''} {s.last_name or ''}").strip(),
            course_name=s.course.name if s.course else '—',
            consultant_display=consultant,
            sort_date=s.enrollment_date if s.enrollment_date else _date.min,
            date_display=s.enrollment_date,
            status=s.status or 'Active',
            fee_paid=float(s.fee_paid or 0),
            total_fee=float(s.total_fee or 0),
            lead_id=s.lead_id,
            reg_number='',
            detail_url=url_for('main.student_overview', id=s.id),
        ))

    # Sort newest first
    unified.sort(key=lambda x: x.sort_date, reverse=True)

    # Manual pagination
    total      = len(unified)
    start      = (page - 1) * per_page
    page_items = unified[start:start + per_page]

    class _Pager:
        def __init__(self, total, page, per_page):
            self.total    = total
            self.page     = page
            self.per_page = per_page
            self.pages    = max(1, math.ceil(total / per_page))
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1

        def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
            last = 0
            for num in range(1, self.pages + 1):
                if (num <= left_edge or
                        self.page - left_current - 1 < num < self.page + right_current or
                        num > self.pages - right_edge):
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    courses  = Course.query.filter_by(is_active=True).order_by(Course.name).all()
    statuses = ['Active', 'Completed', 'Dropped', 'Suspended', 'Pending']

    return render_template('students.html',
        students=page_items,
        pagination=_Pager(total, page, per_page),
        statuses=statuses,
        courses=courses,
        search=search,
        status_filter=status_filter,
        course_id_filter=course_id_str,
    )

@main.route('/student-management')
@login_required
def student_management():
    students = Student.query.order_by(desc(Student.enrollment_date)).all()
    form = StudentForm()
    form.course_id.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    return render_template('student_form.html', students=students, form=form)

@main.route('/students/add', methods=['POST'])
@login_required
def add_student():
    form = StudentForm()
    form.course_id.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        student = Student(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            country_code=form.country_code.data,
            phone=form.phone.data,
            email=form.email.data,
            course_id=form.course_id.data,
            schedule_days=form.schedule_days.data,
            schedule_time=form.schedule_time.data,
            total_fee=form.total_fee.data,
            fee_paid=form.fee_paid.data or 0.0,
            payment_plan=form.payment_plan.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            batch_name=form.batch_name.data
        )
        db.session.add(student)
        db.session.commit()
        flash('Student added successfully!', 'success')
    
    return redirect(url_for('main.student_management'))

@main.route('/students/<int:id>')
@login_required
def view_student(id):
    from models import ImsStudent
    student = ImsStudent.query.get_or_404(id)
    erp_url = f'{_ERP_URL}/edit-registration/{student.ims_registration_id}/'
    return render_template('student_detail.html', student=student,
                           is_ims_source=True, erp_url=erp_url)

@main.route('/ims-students/<int:id>')
@login_required
def view_ims_student(id):
    from models import ImsStudent
    student = ImsStudent.query.get_or_404(id)
    erp_url = f'{_ERP_URL}/edit-registration/{student.ims_registration_id}/'
    return render_template('student_detail.html', student=student,
                           is_ims_source=True, erp_url=erp_url)

@main.route('/students/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    form = StudentForm(obj=student)
    form.course_id.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        form.populate_obj(student)
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('main.student_management'))
    
    return render_template('student_edit.html', form=form, student=student)

@main.route('/students/<int:id>/payments')
@login_required
def student_payments(id):
    student = Student.query.get_or_404(id)
    return render_template('student_payments.html', student=student)

@main.route('/corporate')
@login_required
def corporate():
    form = CorporateTrainingForm()
    form.course_names.choices = [(str(c.id), c.name) for c in Course.query.filter_by(is_active=True).all()]
    corporate_trainings = CorporateTraining.query.order_by(desc(CorporateTraining.created_at)).all()

    corporate_trainings_data = []
    for training in corporate_trainings:
        course_names = []
        if training.course_names:
            try:
                course_ids = json.loads(training.course_names)
                courses = Course.query.filter(Course.id.in_(course_ids)).all()
                course_names = [course.name for course in courses]
            except json.JSONDecodeError:
                course_names = ["Invalid course data"]
        training_data = {
            'id': training.id,
            'company_name': training.company_name,
            'contact_person': training.contact_person_name,
            'contact_email': training.contact_person_email,
            'contact_phone': training.contact_person_phone,
            'industry': training.industry,
            'company_size': training.company_size,
            'course_names': course_names,
            'trainee_count': training.trainee_count,
            'training_mode': training.training_mode,
            'deal_value': training.deal_value,
            'status': training.status,
            'created_at': training.created_at,
            'budget_range': training.budget_range,
            'special_requirements': training.special_requirements
        }
        corporate_trainings_data.append(training_data)

    return render_template('corporate.html', corporate_trainings=corporate_trainings_data, form=form)

@main.route('/corporate/add', methods=['GET', 'POST'])
@login_required
def add_corporate():
    form = CorporateTrainingForm()
    form.course_names.choices = [(str(c.id), c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        corporate = CorporateTraining(
            company_name=form.company_name.data,
            location=form.location.data,
            contact_person_name=form.contact_person_name.data,
            contact_person_email=form.contact_person_email.data,
            contact_person_country_code=form.contact_person_country_code.data,
            contact_person_phone=form.contact_person_phone.data,
            industry=form.industry.data,
            company_size=form.company_size.data,
            course_names=json.dumps(form.course_names.data) if form.course_names.data else None,
            trainee_count=form.trainee_count.data,
            training_mode=form.training_mode.data,
            quotation_amount=form.quotation_amount.data or 0.0,
            expected_start_date=form.expected_start_date.data,
            budget_range=form.budget_range.data,
            special_requirements=form.special_requirements.data,
            created_by_id=current_user.id
        )
        
        db.session.add(corporate)
        db.session.commit()
        flash('Corporate training inquiry added successfully!', 'success')
        return redirect(url_for('main.corporate'))
    
    return render_template('corporate.html', form=form, corporate_trainings=CorporateTraining.query.order_by(desc(CorporateTraining.created_at)).all())

@main.route('/corporate/<int:deal_id>/status', methods=['POST'])
@login_required
def update_corporate_status(deal_id):
    deal = CorporateTraining.query.get_or_404(deal_id)
    new_status = (request.get_json() or {}).get('status', '').strip()
    valid = ('Inquiry', 'Proposal', 'Negotiation', 'Confirmed', 'Completed', 'Lost')
    if new_status not in valid:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    deal.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'status': new_status})


@main.route('/messages')
@login_required
def messages():
    templates = MessageTemplate.query.order_by(MessageTemplate.name).all()
    template_form = MessageTemplateForm()
    leads = Lead.query.all()
    courses = Course.query.filter_by(is_active=True).all()
    return render_template('messages.html', templates=templates, template_form=template_form, leads=leads, courses=courses)

@main.route('/messages/add', methods=['POST'])
@login_required
def add_template():
    form = MessageTemplateForm()
    if form.validate_on_submit():
        template = MessageTemplate(
            name=form.name.data,
            category=form.category.data,
            subject=form.subject.data,
            content=form.content.data,
            message_type=form.message_type.data,
            is_active=form.is_active.data,
            meta_template_name=form.meta_template_name.data or None,
            meta_language_code=form.meta_language_code.data or 'en_US',
            meta_category=form.meta_category.data or None,
            meta_status=form.meta_status.data or 'not_submitted',
            meta_variable_mapping=_parse_variable_mapping(form.variable_mapping_input.data),
        )
        db.session.add(template)
        db.session.commit()
        flash('Message template added successfully!', 'success')
    return redirect(url_for('main.messages'))

@main.route('/messages/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    template = MessageTemplate.query.get_or_404(id)
    form = MessageTemplateForm(obj=template)
    if request.method == 'GET':
        form.variable_mapping_input.data = _variable_mapping_display(template.meta_variable_mapping)
    if form.validate_on_submit():
        form.populate_obj(template)
        template.meta_variable_mapping = _parse_variable_mapping(form.variable_mapping_input.data)
        db.session.commit()
        flash('Template updated successfully!', 'success')
        return redirect(url_for('main.messages'))
    return render_template('messages.html', template_form=form, template=template)

@main.route('/messages/<int:id>/delete')
@login_required
def delete_template(id):
    template = MessageTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted successfully!', 'success')
    return redirect(url_for('main.messages'))

@main.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    template_id = request.form.get('template_id')
    lead_ids = request.form.getlist('lead_ids')
    course_id = request.form.get('course_id')
    
    template = MessageTemplate.query.get_or_404(template_id)
    template.usage_count += 1
    db.session.commit()
    
    flash(f'Message sent to {len(lead_ids)} recipients!', 'success')
    return redirect(url_for('main.messages'))

@main.route('/api/templates/<int:id>', methods=['GET'])
@login_required
def get_template(id):
    template = MessageTemplate.query.get_or_404(id)
    return jsonify({
        'success': True,
        'template': {
            'id': template.id,
            'name': template.name,
            'category': template.category,
            'message_type': template.message_type,
            'subject': template.subject,
            'content': template.content,
            'is_active': template.is_active
        }
    })

@main.route('/reports')
@login_required
def reports():
    if current_user.role == 'sales_manager':
        flash('Access denied. Reports are not available for your role.', 'error')
        return redirect(url_for('main.dashboard'))
    default_date_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    date_from = request.args.get('date_from', default_date_from)
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))

    monthly_leads = Lead.query.filter(
        Lead.created_at.between(date_from, date_to)
    ).all()

    _cbs_rows = db.session.query(
        Lead.lead_source,
        func.count(Lead.id).label('total'),
        func.sum(db.cast(Lead.status == 'Converted', db.Integer)).label('converted')
    ).filter(
        Lead.created_at.between(date_from, date_to)
    ).group_by(Lead.lead_source).all()
    conversion_by_source = [[r[0] or 'Unknown', r[1], r[2] or 0] for r in _cbs_rows]

    course_popularity = db.session.query(
        Course.name,
        func.count(Student.id).label('enrollments')
    ).join(Student).filter(
        Student.enrollment_date.between(date_from, date_to)
    ).group_by(Course.name).all()

    monthly_trends = db.session.query(
        func.date_format(Lead.created_at, '%Y-%m').label('month'),
        func.count(Lead.id).label('count')
    ).group_by(func.date_format(Lead.created_at, '%Y-%m')).order_by(func.date_format(Lead.created_at, '%Y-%m').desc()).limit(12).all()

    # Monthly grouped data for chart (in date range) — as plain lists for JSON serialization
    _md_rows = db.session.query(
        func.date_format(Lead.created_at, '%b %Y').label('label'),
        func.count(Lead.id).label('total'),
        func.sum(db.cast(Lead.status == 'Converted', db.Integer)).label('converted')
    ).filter(
        Lead.created_at.between(date_from, date_to)
    ).group_by(func.date_format(Lead.created_at, '%Y-%m')).order_by(
        func.date_format(Lead.created_at, '%Y-%m')
    ).all()
    monthly_data = [[r[0], r[1], r[2] or 0] for r in _md_rows]

    # Real stats
    total_leads = len(monthly_leads)
    converted_leads = sum(1 for l in monthly_leads if l.status == 'Converted')
    conversion_rate = round(converted_leads / total_leads * 100, 1) if total_leads > 0 else 0
    total_revenue = db.session.query(
        func.coalesce(func.sum(Lead.quoted_amount), 0)
    ).filter(
        Lead.created_at.between(date_from, date_to),
        Lead.status == 'Converted'
    ).scalar() or 0
    avg_deal = round(total_revenue / converted_leads, 0) if converted_leads > 0 else 0

    return render_template('reports.html',
                         monthly_leads=monthly_leads,
                         conversion_by_source=conversion_by_source,
                         course_popularity=course_popularity,
                         monthly_trends=monthly_trends,
                         monthly_data=monthly_data,
                         date_from=date_from,
                         date_to=date_to,
                         total_leads=total_leads,
                         converted_leads=converted_leads,
                         conversion_rate=conversion_rate,
                         total_revenue=total_revenue,
                         avg_deal=avg_deal)

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Comprehensive settings management"""
    if current_user.role == 'sales_manager':
        flash('Access denied. Settings are not available for your role.', 'error')
        return redirect(url_for('main.dashboard'))
    # Get all settings categories
    lead_sources = Setting.get_by_key('lead_source')
    lead_statuses = Setting.get_by_key('lead_status') 
    followup_types = Setting.get_by_key('followup_type')
    priority_levels = Setting.get_by_key('priority_level')
    meeting_types = Setting.get_by_key('meeting_type')
    
    # Get system settings
    system_settings = {}
    system_keys = ['company_name', 'company_email', 'company_phone', 'company_address', 
                   'default_currency', 'timezone', 'leads_per_page', 'auto_followup_days',
                   'email_notifications', 'sms_notifications']
    
    for key in system_keys:
        system_settings[key] = Setting.get_single_value(key, '')
    
    # Initialize forms
    setting_form = SettingForm()
    system_form = SystemSettingsForm()
    
    # Populate system form with current values
    system_form.company_name.data = system_settings.get('company_name', '')
    system_form.company_email.data = system_settings.get('company_email', '')
    system_form.company_phone.data = system_settings.get('company_phone', '')
    system_form.company_address.data = system_settings.get('company_address', '')
    system_form.default_currency.data = system_settings.get('default_currency', 'USD')
    system_form.timezone.data = system_settings.get('timezone', 'UTC')
    
    # Handle numeric fields with validation
    leads_per_page = system_settings.get('leads_per_page', '20')
    system_form.leads_per_page.data = int(leads_per_page) if leads_per_page and leads_per_page.isdigit() else 20
    
    auto_followup_days = system_settings.get('auto_followup_days', '3')
    system_form.auto_followup_days.data = int(auto_followup_days) if auto_followup_days and auto_followup_days.isdigit() else 3
    
    system_form.email_notifications.data = system_settings.get('email_notifications', 'true') == 'true'
    system_form.sms_notifications.data = system_settings.get('sms_notifications', 'false') == 'true'
    
    # Handle form submissions
    if request.method == 'POST':
        if 'save_system_settings' in request.form and system_form.validate_on_submit():
            # Update system settings
            system_updates = {
                'company_name': system_form.company_name.data,
                'company_email': system_form.company_email.data,
                'company_phone': system_form.company_phone.data,
                'company_address': system_form.company_address.data,
                'default_currency': system_form.default_currency.data,
                'timezone': system_form.timezone.data,
                'leads_per_page': str(system_form.leads_per_page.data),
                'auto_followup_days': str(system_form.auto_followup_days.data),
                'email_notifications': str(system_form.email_notifications.data).lower(),
                'sms_notifications': str(system_form.sms_notifications.data).lower()
            }
            
            for key, value in system_updates.items():
                setting = Setting.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                    setting.updated_at = datetime.utcnow()
                else:
                    new_setting = Setting(
                        key=key,
                        value=value,
                        display_name=key.replace('_', ' ').title(),
                        is_active=True
                    )
                    db.session.add(new_setting)
            
            db.session.commit()
            flash('System settings updated successfully!', 'success')
            return redirect(url_for('main.settings'))
            
        elif 'add_setting' in request.form and setting_form.validate_on_submit():
            # Add new setting
            new_setting = Setting(
                key=setting_form.key.data,
                value=setting_form.value.data,
                display_name=setting_form.display_name.data,
                description=setting_form.description.data,
                is_active=setting_form.is_active.data,
                sort_order=setting_form.sort_order.data
            )
            db.session.add(new_setting)
            db.session.commit()
            flash('Setting added successfully!', 'success')
            return redirect(url_for('main.settings'))
    
    return render_template('settings.html', 
                         lead_sources=lead_sources,
                         lead_statuses=lead_statuses,
                         followup_types=followup_types,
                         priority_levels=priority_levels,
                         meeting_types=meeting_types,
                         system_settings=system_settings,
                         setting_form=setting_form,
                         system_form=system_form)

@main.route('/settings/delete/<int:setting_id>', methods=['POST'])
@login_required
def delete_setting(setting_id):
    """Delete a setting"""
    if not (current_user.is_admin() or current_user.can_manage_settings):
        flash('Access denied. You do not have permission to manage settings.', 'error')
        return redirect(url_for('main.settings'))
    
    setting = Setting.query.get_or_404(setting_id)
    db.session.delete(setting)
    db.session.commit()
    flash(f'Setting "{setting.display_name}" deleted successfully!', 'success')
    return redirect(url_for('main.settings'))

@main.route('/settings/toggle/<int:setting_id>', methods=['POST'])
@login_required
def toggle_setting(setting_id):
    """Toggle setting active status"""
    if not (current_user.is_admin() or current_user.can_manage_settings):
        flash('Access denied. You do not have permission to manage settings.', 'error')
        return redirect(url_for('main.settings'))
    
    setting = Setting.query.get_or_404(setting_id)
    setting.is_active = not setting.is_active
    setting.updated_at = datetime.utcnow()
    db.session.commit()
    
    status = "activated" if setting.is_active else "deactivated"
    flash(f'Setting "{setting.display_name}" {status} successfully!', 'success')
    return redirect(url_for('main.settings'))

@main.route('/api/leads/<int:id>/status', methods=['POST'])
@login_required
def update_lead_status(id):
    lead = Lead.query.get_or_404(id)
    new_status = request.json.get('status')
    
    if new_status in ['New', 'Contacted', 'Interested', 'Quoted', 'Converted', 'Lost']:
        lead.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid status'}), 400

@main.route('/api/overdue-count')
@login_required
def api_overdue_count():
    _today = date.today()
    base_q = Lead.query if (current_user.is_admin() or current_user.can_view_all_leads) \
              else Lead.query.filter_by(assigned_to=current_user.id)
    count = base_q.filter(
        Lead.next_followup_date < _today,
        Lead.status.notin_(['Converted', 'Lost'])
    ).count()
    return jsonify({'count': count})


@main.route('/api/pipeline/data')
@login_required
def pipeline_api_data():
    pipeline_data = db.session.query(
        Lead.status,
        func.count(Lead.id).label('count'),
        func.sum(Lead.quoted_amount).label('total_value')
    ).group_by(Lead.status).all()
    
    result = {}
    for status, count, total_value in pipeline_data:
        result[status] = {
            'count': count,
            'total_value': float(total_value or 0)
        }
    
    return jsonify(result)

@main.route('/api/charts/revenue')
@login_required
def api_charts_revenue():
    """Last 6 months of IMS revenue (amount_paid) via pymysql cross-DB query."""
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        d = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        months.append(d)

    result = []
    try:
        import pymysql as _pm
        _c = _pm.connect(host='localhost', user='root', password='', database='orbit_invoice', charset='utf8mb4')
        with _c.cursor() as cur:
            for m in months:
                next_m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
                cur.execute(
                    "SELECT COALESCE(SUM(amount_paid),0) FROM invoices_invoice WHERE date >= %s AND date < %s",
                    (m.strftime('%Y-%m-%d'), next_m.strftime('%Y-%m-%d'))
                )
                row = cur.fetchone()
                result.append({'month': m.strftime('%b %Y'), 'revenue': float(row[0] or 0)})
        _c.close()
    except Exception:
        result = [{'month': m.strftime('%b %Y'), 'revenue': 0} for m in months]

    return jsonify(result)


@main.route('/api/charts/conversion')
@login_required
def api_charts_conversion():
    """Conversion rate by lead source from CRM lead data."""
    from sqlalchemy import func as _f
    rows = db.session.query(
        Lead.lead_source,
        _f.count(Lead.id).label('total'),
        _f.sum(_f.cast(Lead.status == 'Converted', db.Integer)).label('converted')
    ).filter(Lead.lead_source != None, Lead.lead_source != '').group_by(Lead.lead_source).all()

    result = [
        {
            'source': r.lead_source or 'Unknown',
            'total': r.total,
            'converted': int(r.converted or 0),
            'rate': round(int(r.converted or 0) / r.total * 100, 1) if r.total else 0
        }
        for r in rows if r.total > 0
    ]
    return jsonify(result)


@main.route('/api/charts/leads-trend')
@login_required
def api_charts_leads_trend():
    """Monthly lead creation + conversion count for last 6 months."""
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        d = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        months.append(d)

    result = []
    for m in months:
        next_m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        total = Lead.query.filter(Lead.created_at >= m, Lead.created_at < next_m).count()
        converted = Lead.query.filter(
            Lead.created_at >= m, Lead.created_at < next_m, Lead.status == 'Converted'
        ).count()
        result.append({'month': m.strftime('%b %Y'), 'leads': total, 'converted': converted})

    return jsonify(result)


@main.route('/corporate-leads')
@login_required
def corporate_leads():
    leads = CorporateTraining.query.order_by(desc(CorporateTraining.created_at)).all()
    form = CorporateTrainingForm()
    form.course_names.choices = [(str(c.id), c.name) for c in Course.query.filter_by(is_active=True).all()]
    return render_template('corporate_leads.html', corporate_leads=leads, form=form)

@main.route('/corporate-leads/add', methods=['POST'])
@login_required
def add_corporate_lead():
    form = CorporateTrainingForm()
    form.course_names.choices = [(str(c.id), c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        lead = CorporateTraining(
            company_name=form.company_name.data,
            location=form.location.data,
            contact_person_name=form.contact_person_name.data,
            contact_person_email=form.contact_person_email.data,
            contact_person_country_code=form.contact_person_country_code.data,
            contact_person_phone=form.contact_person_phone.data,
            industry=form.industry.data,
            company_size=form.company_size.data,
            course_names=json.dumps([form.course_names.data]) if form.course_names.data else None,
            trainee_count=form.trainee_count.data,
            training_mode=form.training_mode.data,
            quotation_amount=form.quotation_amount.data or 0.0,
            expected_start_date=form.expected_start_date.data,
            budget_range=form.budget_range.data,
            special_requirements=form.special_requirements.data,
            created_by_id=current_user.id
        )
        db.session.add(lead)
        db.session.commit()
        flash('Corporate lead added successfully!', 'success')
    
    return redirect(url_for('main.corporate_leads'))

@main.route('/corporate-leads/<int:id>')
@login_required
def view_corporate_lead(id):
    lead = CorporateTraining.query.get_or_404(id)
    course_names_list = []
    if lead.course_names:
        try:
            course_ids = json.loads(lead.course_names)
            courses = Course.query.filter(Course.id.in_(course_ids)).all()
            course_names_list = [course.name for course in courses]
        except json.JSONDecodeError:
            course_names_list = []
    return render_template('corporate_lead_detail.html', lead=lead, course_names_list=course_names_list)

@main.route('/leads/<int:id>/detail', endpoint='lead_detail_full')
@login_required
def lead_detail(id):
    lead = Lead.query.get_or_404(id)
    interactions = LeadInteraction.query.filter_by(lead_id=id).order_by(desc(LeadInteraction.interaction_date)).all()
    quotes = LeadQuote.query.filter_by(lead_id=id).order_by(desc(LeadQuote.created_at)).all()
    
    quote_form = LeadQuoteForm()
    quote_form.course_id.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    interaction_form = LeadInteractionForm()
    followup_form = LeadFollowupForm()
    
    return render_template('leads/detail.html',
                         lead=lead,
                         interactions=interactions,
                         quotes=quotes,
                         quote_form=quote_form,
                         interaction_form=interaction_form,
                         followup_form=followup_form)

@main.route("/leads/<int:id>/add_quote", methods=["POST"])
@login_required
def add_lead_quote(id):
    lead = Lead.query.get_or_404(id)

    mode = request.form.get('mode', 'individual')
    valid_until = request.form.get('valid_until')
    quote_notes = request.form.get('quote_notes', '')
    currency = request.form.get('currency', 'AED')

    if not valid_until:
        flash("Please fill all required fields", "error")
        return redirect(url_for("main.lead_detail", lead_id=id))

    try:
        from datetime import datetime
        valid_until_date = datetime.strptime(valid_until, '%Y-%m-%d').date()

        if mode == 'total':
            course_ids = request.form.getlist('course_ids[]', type=int)
            total_amount = request.form.get('total_amount', type=float)
            if not course_ids or not total_amount:
                flash("Please select at least one course and enter a total amount", "error")
                return redirect(url_for("main.lead_detail", lead_id=id))

            bundle = QuoteBundle(
                lead_id=id,
                total_amount=total_amount,
                currency=currency,
                valid_until=valid_until_date,
                quote_notes=quote_notes,
                created_by_id=current_user.id,
            )
            db.session.add(bundle)
            db.session.flush()  # get bundle.id before commit
            for cid in course_ids:
                db.session.add(QuoteBundleItem(bundle_id=bundle.id, course_id=cid))

            if lead.status not in ["Converted", "Lost"]:
                lead.status = "Quoted"
                lead.quoted_amount = total_amount

            db.session.commit()
            flash("Bundle quote added successfully!", "success")

        else:
            # Individual mode: one course + one price per row. Accepts either the
            # batch fields (course_ids[] / amounts[]) or the legacy single fields
            # (course_id / quoted_amount) so nothing else calling this endpoint breaks.
            course_ids = request.form.getlist('course_ids[]', type=int)
            amounts = request.form.getlist('amounts[]', type=float)
            if not course_ids:
                single_course = request.form.get('course_id', type=int)
                single_amount = request.form.get('quoted_amount', type=float)
                if single_course and single_amount:
                    course_ids = [single_course]
                    amounts = [single_amount]

            if not course_ids or len(course_ids) != len(amounts) or not all(amounts):
                flash("Please enter a price for every selected course", "error")
                return redirect(url_for("main.lead_detail", lead_id=id))

            last_amount = None
            for cid, amount in zip(course_ids, amounts):
                db.session.add(LeadQuote(
                    lead_id=id,
                    course_id=cid,
                    quoted_amount=amount,
                    currency=currency,
                    valid_until=valid_until_date,
                    quote_notes=quote_notes,
                    created_by_id=current_user.id,
                ))
                last_amount = amount

            if lead.status not in ["Converted", "Lost"]:
                lead.status = "Quoted"
                lead.quoted_amount = last_amount

            db.session.commit()
            flash("Quote added successfully!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding quote: {str(e)}", "error")

    return redirect(url_for("main.lead_detail", lead_id=id))

@main.route("/leads/<int:lead_id>/add_activity", methods=["POST"])
@login_required
def add_lead_activity(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    content = request.form.get('comment', '').strip()
    if not content:
        flash("Activity content cannot be empty.", "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id, tab='activity'))

    itype = request.form.get('interaction_type', 'Note')
    valid_types = ['Call', 'Email', 'WhatsApp', 'Meeting', 'Note', 'Comment', 'Quote Update']
    if itype not in valid_types:
        itype = 'Note'

    is_imp = request.form.get('is_important', '0') == '1'
    interaction_date = datetime.now()

    interaction = LeadInteraction(
        lead_id=lead_id,
        interaction_type=itype,
        interaction_date=interaction_date,
        content=content,
        created_by_id=current_user.id,
        is_important=is_imp
    )
    lead.last_contact_date = interaction_date.date() if hasattr(interaction_date, 'date') else interaction_date
    db.session.add(interaction)
    db.session.commit()
    flash("Activity logged successfully!", "success")
    return redirect(url_for("main.lead_detail", lead_id=lead_id, tab='activity'))

@main.route("/leads/<int:id>/add_interaction", methods=["POST"])
@login_required
def add_lead_interaction(id):
    lead = Lead.query.get_or_404(id)
    form = LeadInteractionForm()
    
    if form.validate_on_submit():
        interaction = LeadInteraction(
            lead_id=id,
            interaction_type=form.interaction_type.data,
            interaction_date=datetime.combine(form.interaction_date.data, datetime.min.time()),
            notes=form.notes.data,
            outcome=form.outcome.data,
            created_by_id=current_user.id
        )
        
        lead.last_contact_date = form.interaction_date.data
        
        db.session.add(interaction)
        db.session.commit()
        flash("Interaction recorded successfully!", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("main.lead_detail", lead_id=id))



@main.route("/leads/<int:id>/update_followup", methods=["POST"])
@login_required
def update_lead_followup(id):
    lead = Lead.query.get_or_404(id)
    
    # ROLE-BASED ACCESS CONTROL
    if not (current_user.is_admin() or current_user.can_view_all_leads or lead.added_by == current_user.id):
        return jsonify({
            'success': False,
            'message': 'You can only edit your own leads!'
        }), 403

    form = LeadFollowupForm()
    
    if form.validate_on_submit():
        try:
            # Store old values for logging
            old_date = lead.next_followup_date
            old_time = lead.followup_time
            old_type = lead.followup_type
            old_priority = lead.followup_priority

            # Update lead with new values
            lead.next_followup_date = form.followup_date.data
            lead.followup_time = form.followup_time.data
            lead.followup_type = form.followup_type.data
            lead.followup_priority = form.priority.data

            # Log the change as an interaction
            content = f"Follow-up updated: "
            changes = []
            if old_date != form.followup_date.data:
                changes.append(f"Date changed from {old_date or 'Not set'} to {form.followup_date.data}")
            if old_time != form.followup_time.data:
                changes.append(f"Time changed from {old_time or 'Not set'} to {form.followup_time.data}")
            if old_type != form.followup_type.data:
                changes.append(f"Type changed from {old_type or 'Not set'} to {form.followup_type.data}")
            if old_priority != form.priority.data:
                changes.append(f"Priority changed from {old_priority or 'Not set'} to {form.priority.data}")
            if form.notes.data:
                changes.append(f"Notes: {form.notes.data}")
            
            content += "; ".join(changes) if changes else "No changes made"

            interaction = LeadInteraction(
                lead_id=lead.id,
                interaction_type='Follow-up Update',
                interaction_date=datetime.now(),
                content=content,
                created_by_id=current_user.id,
                is_important=True
            )
            
            db.session.add(interaction)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Follow-up updated successfully!'
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating follow-up: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error updating follow-up: {str(e)}'
            }), 500
    else:
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(f"{field}: {error}")
        return jsonify({
            'success': False,
            'message': 'Form validation failed',
            'errors': errors
        }), 400 

@main.route('/corporate-leads/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_corporate_lead(id):
    lead = CorporateTraining.query.get_or_404(id)
    form = CorporateTrainingForm(obj=lead)
    form.course_names.choices = [(str(c.id), c.name) for c in Course.query.filter_by(is_active=True).all()]
    
    if lead.course_names:
        try:
            form.course_names.data = json.loads(lead.course_names)
        except json.JSONDecodeError:
            form.course_names.data = []
    
    if form.validate_on_submit():
        form.populate_obj(lead)
        lead.course_names = json.dumps(form.course_names.data) if form.course_names.data else None
        db.session.commit()
        flash('Corporate lead updated successfully!', 'success')
        return redirect(url_for('main.corporate_leads'))
    
    return render_template('corporate_lead_edit.html', form=form, lead=lead)

@main.route('/corporate-leads/<int:id>/delete')
@login_required
def delete_corporate_lead(id):
    lead = CorporateTraining.query.get_or_404(id)
    db.session.delete(lead)
    db.session.commit()
    flash('Corporate lead deleted successfully!', 'success')
    return redirect(url_for('main.corporate_leads'))

@main.route("/trainers")
@login_required
def trainers():
    trainers = Trainer.query.filter_by(is_active=True).all()
    trainer_form = TrainerForm()
    
    return render_template("trainers.html", trainers=trainers, trainer_form=trainer_form)

@main.route("/trainers/add", methods=["POST"])
@login_required
def add_trainer():
    form = TrainerForm()
    
    if form.validate_on_submit():
        trainer = Trainer(
            name=form.name.data,
            phone=form.phone.data,
            email=form.email.data,
            specialization=form.specialization.data,
            is_active=form.is_active.data
        )
        
        db.session.add(trainer)
        db.session.flush()
        
        for course_id in form.course_ids.data:
            trainer_course = TrainerCourse(trainer_id=trainer.id, course_id=course_id)
            db.session.add(trainer_course)
        
        db.session.commit()
        flash("Trainer added successfully!", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("main.trainers"))

@main.route("/trainers/<int:id>/schedule")
@login_required
def trainer_schedule(id):
    trainer = Trainer.query.get_or_404(id)
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Calculate list of days for the week
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    
    current_week_classes = ClassSchedule.query.filter(
        ClassSchedule.trainer_id == id,
        ClassSchedule.class_date >= start_of_week,
        ClassSchedule.class_date <= end_of_week,
        ClassSchedule.is_cancelled == False
    ).order_by(ClassSchedule.class_date, ClassSchedule.start_time).all()
    
    # Generate time slots
    time_slots = []
    for hour in range(8, 22):
        for minute in [0, 30]:
            time_slots.append(f"{hour:02d}:{minute:02d}")
    
    # Group classes by date and time (for efficiency)
    schedule_grid = {}
    for day in week_days:
        schedule_grid[day] = {ts: [] for ts in time_slots}
    
    for class_item in current_week_classes:
        time_str = class_item.start_time.strftime('%H:%M')
        if time_str in schedule_grid[class_item.class_date]:
            schedule_grid[class_item.class_date][time_str].append(class_item)
    
    schedule_form = ClassScheduleForm()
    schedule_form.trainer_id.choices = [(trainer.id, trainer.name)]
    schedule_form.trainer_id.data = trainer.id
    schedule_form.course_id.choices = [(c.id, c.name) for c in trainer.courses]
    schedule_form.student_ids.choices = [(s.id, s.name) for s in Student.query.filter_by(status="Active").all()]
    
    if not current_week_classes:
        flash("No classes scheduled for this week.", "info")
    
    return render_template("trainer_schedule.html",
                          trainer=trainer,
                          schedule_grid=schedule_grid,
                          time_slots=time_slots,
                          current_week_classes=current_week_classes,
                          schedule_form=schedule_form,
                          start_of_week=start_of_week,
                          end_of_week=end_of_week,
                          week_days=week_days)

@main.route("/schedule/add_class", methods=["POST"])
@login_required
def add_class_schedule():
    form = ClassScheduleForm()
    form.trainer_id.choices = [(t.id, t.name) for t in Trainer.query.filter_by(is_active=True).all()]
    form.course_id.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    form.student_ids.choices = [(s.id, s.name) for s in Student.query.filter_by(status="Active").all()]
    
    if form.validate_on_submit():
        class_schedule = ClassSchedule(
            trainer_id=form.trainer_id.data,
            course_id=form.course_id.data,
            class_date=form.class_date.data,
            start_time=form.start_time.data,
            duration_minutes=form.duration_minutes.data,
            class_type=form.class_type.data,
            location=form.location.data,
            online_link=form.online_link.data,
            notes=form.notes.data
        )
        
        db.session.add(class_schedule)
        db.session.flush()
        
        for student_id in form.student_ids.data:
            class_student = ClassStudent(
                class_schedule_id=class_schedule.id,
                student_id=student_id
            )
            db.session.add(class_student)
        
        db.session.commit()
        flash("Class scheduled successfully!", "success")
        return redirect(url_for("main.trainer_schedule", id=form.trainer_id.data))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
        return redirect(url_for("main.trainers"))

# ENHANCED STUDENT MANAGEMENT ROUTES

@main.route('/students/<int:id>/delete', methods=['POST'])
@login_required
def delete_student_record(id):
    if not current_user.is_admin():
        flash('Access denied. Only admins can delete students.', 'error')
        return redirect(url_for('main.students'))
    
    student = Student.query.get_or_404(id)
    try:
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting student: {str(e)}")
        flash('An error occurred while deleting the student. Please try again.', 'error')
    
    return redirect(url_for('main.students'))

@main.route('/students/<int:id>/overview')
@login_required
def student_overview(id):
    student = Student.query.get_or_404(id)
    return render_template('student_detail.html', student=student)

# ENHANCED TRAINER MANAGEMENT ROUTES
@main.route('/trainers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trainer(id):
    if not current_user.is_admin():
        flash('Access denied. Only admins can edit trainers.', 'error')
        return redirect(url_for('main.trainers'))
    
    trainer = Trainer.query.get_or_404(id)
    form = TrainerForm(obj=trainer)
    
    if request.method == 'GET':
        return render_template('edit_trainer.html', form=form, trainer=trainer)
    
    if form.validate_on_submit():
        try:
            form.populate_obj(trainer)
            db.session.commit()
            flash('Trainer updated successfully!', 'success')
            return redirect(url_for('main.trainers'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating trainer: {str(e)}")
            flash('An error occurred while updating the trainer. Please try again.', 'error')
    
    return render_template('edit_trainer.html', form=form, trainer=trainer)

@main.route('/trainers/<int:id>/delete', methods=['POST'])
@login_required
def delete_trainer(id):
    if not current_user.is_admin():
        flash('Access denied. Only admins can delete trainers.', 'error')
        return redirect(url_for('main.trainers'))
    
    trainer = Trainer.query.get_or_404(id)
    try:
        db.session.delete(trainer)
        db.session.commit()
        flash('Trainer deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting trainer: {str(e)}")
        flash('An error occurred while deleting the trainer. Please try again.', 'error')
    
    return redirect(url_for('main.trainers'))

@main.route('/trainers/<int:id>')
@login_required
def trainer_detail(id):
    trainer = Trainer.query.get_or_404(id)
    
    # Get upcoming schedules
    from datetime import datetime
    upcoming_schedules = ClassSchedule.query.filter(
        ClassSchedule.trainer_id == id,
        ClassSchedule.class_date >= datetime.now().date(),
        ClassSchedule.is_cancelled == False
    ).order_by(ClassSchedule.class_date, ClassSchedule.start_time).limit(5).all()
    
    return render_template('trainer_detail.html', trainer=trainer, upcoming_schedules=upcoming_schedules)

@main.route("/schedule/weekly")
@login_required
def weekly_schedule():
    from datetime import datetime, timedelta
    
    week_offset = request.args.get("week", 0, type=int)
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    week_classes = ClassSchedule.query.filter(
        ClassSchedule.class_date >= start_of_week,
        ClassSchedule.class_date <= end_of_week,
        ClassSchedule.is_cancelled == False
    ).order_by(ClassSchedule.class_date, ClassSchedule.start_time).all()
    
    week_schedule = {}
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        week_schedule[day] = [cls for cls in week_classes if cls.class_date == day]
    
    return render_template("weekly_schedule.html",
                         week_schedule=week_schedule,
                         start_of_week=start_of_week,
                         end_of_week=end_of_week,
                         week_offset=week_offset)

@main.route("/schedule/monthly")
@login_required
def monthly_schedule():
    from datetime import datetime, timedelta
    from calendar import monthrange
    
    year = request.args.get("year", datetime.now().year, type=int)
    month = request.args.get("month", datetime.now().month, type=int)
    
    first_day = datetime(year, month, 1).date()
    last_day_num = monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num).date()
    
    month_classes = ClassSchedule.query.filter(
        ClassSchedule.class_date >= first_day,
        ClassSchedule.class_date <= last_day,
        ClassSchedule.is_cancelled == False
    ).order_by(ClassSchedule.class_date, ClassSchedule.start_time).all()
    
    monthly_schedule = {}
    current_day = first_day
    while current_day <= last_day:
        monthly_schedule[current_day] = [cls for cls in month_classes if cls.class_date == current_day]
        current_day += timedelta(days=1)
    
    return render_template("monthly_schedule.html",
                         monthly_schedule=monthly_schedule,
                         year=year,
                         month=month,
                         first_day=first_day,
                         last_day=last_day)

@main.route("/payments")
@login_required
def payments():
    vault_provider = PaymentProvider.query.filter_by(name="Vault").first()
    tabby_provider = PaymentProvider.query.filter_by(name="Tabby").first()
    tamara_provider = PaymentProvider.query.filter_by(name="Tamara").first()
    
    vault_links = PaymentLink.query.filter_by(provider_id=vault_provider.id).order_by(desc(PaymentLink.created_at)).all() if vault_provider else []
    tabby_links = PaymentLink.query.filter_by(provider_id=tabby_provider.id).order_by(desc(PaymentLink.created_at)).all() if tabby_provider else []
    tamara_links = PaymentLink.query.filter_by(provider_id=tamara_provider.id).order_by(desc(PaymentLink.created_at)).all() if tamara_provider else []
    
    total_pending = PaymentLink.query.filter_by(status="pending").count()
    total_paid = PaymentLink.query.filter_by(status="paid").count()
    total_failed = PaymentLink.query.filter_by(status="failed").count()
    
    payment_link_form = PaymentLinkForm()
    payment_link_form.lead_id.choices = [(0, "Select Lead")] + [(l.id, l.name) for l in Lead.query.all()]
    payment_link_form.student_id.choices = [(0, "Select Student")] + [(s.id, s.name) for s in Student.query.all()]
    payment_link_form.provider_id.choices = [(p.id, p.name) for p in PaymentProvider.query.filter_by(is_active=True).all()]
    
    return render_template("payments.html",
                         vault_provider=vault_provider,
                         tabby_provider=tabby_provider,
                         tamara_provider=tamara_provider,
                         vault_links=vault_links,
                         tabby_links=tabby_links,
                         tamara_links=tamara_links,
                         total_pending=total_pending,
                         total_paid=total_paid,
                         total_failed=total_failed,
                         payment_link_form=payment_link_form)

@main.route("/payments/create_link", methods=["POST"])
@login_required
def create_payment_link():
    form = PaymentLinkForm()
    form.lead_id.choices = [(0, "Select Lead")] + [(l.id, l.name) for l in Lead.query.all()]
    form.student_id.choices = [(0, "Select Student")] + [(s.id, s.name) for s in Student.query.all()]
    form.provider_id.choices = [(p.id, p.name) for p in PaymentProvider.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            import uuid
            payment_reference = f"PAY_{uuid.uuid4().hex[:8].upper()}"
            
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=form.expires_in_days.data)
            
            payment_link = PaymentLink(
                lead_id=form.lead_id.data if form.lead_id.data > 0 else None,
                student_id=form.student_id.data if form.student_id.data > 0 else None,
                provider_id=form.provider_id.data,
                amount=form.amount.data,
                currency=form.currency.data,
                description=form.description.data,
                payment_reference=payment_reference,
                expires_at=expires_at,
                created_by_id=current_user.id
            )
            
            provider = PaymentProvider.query.get(form.provider_id.data)
            
            customer_info = None
            if form.lead_id.data and form.lead_id.data > 0:
                lead = Lead.query.get(form.lead_id.data)
                if lead:
                    customer_info = {
                        "name": lead.name,
                        "email": lead.email or "",
                        "phone": lead.phone or ""
                    }
            
            callback_url = url_for('main.payment_callback', _external=True)
            api_result = create_payment_link(
                provider=provider.name.lower(),
                amount=form.amount.data,
                currency=form.currency.data,
                description=form.description.data,
                customer_info=customer_info,
                callback_url=callback_url
            )
            
            if api_result.get('success'):
                payment_link.payment_url = api_result.get('payment_link')
                payment_link.external_payment_id = api_result.get('payment_id')
            else:
                payment_link.payment_url = f"#{provider.name.lower()}_payment_pending"
            
            db.session.add(payment_link)
            db.session.commit()
            
            flash(f"Payment link created successfully! Reference: {payment_reference}", "success")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating payment link: {str(e)}", "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("main.payments"))

@main.route("/payments/providers")
@login_required
def payment_providers():
    providers = PaymentProvider.query.all()
    provider_form = PaymentProviderForm()
    
    return render_template("payment_providers.html", 
                         providers=providers, 
                         provider_form=provider_form)

@main.route("/payments/providers/add", methods=["POST"])
@login_required
def add_payment_provider():
    form = PaymentProviderForm()
    
    if form.validate_on_submit():
        try:
            existing_provider = PaymentProvider.query.filter_by(name=form.name.data).first()
            
            if existing_provider:
                existing_provider.api_key = form.api_key.data
                existing_provider.api_secret = form.api_secret.data
                existing_provider.environment = form.environment.data
                existing_provider.webhook_url = form.webhook_url.data
                existing_provider.is_active = form.is_active.data
                flash(f"{form.name.data} provider updated successfully!", "success")
            else:
                provider = PaymentProvider(
                    name=form.name.data,
                    api_key=form.api_key.data,
                    api_secret=form.api_secret.data,
                    environment=form.environment.data,
                    webhook_url=form.webhook_url.data,
                    is_active=form.is_active.data
                )
                db.session.add(provider)
                flash(f"{form.name.data} provider added successfully!", "success")
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving provider: {str(e)}", "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("main.payment_providers"))


# ── Lead Source Integrations settings ─────────────────────────────────────────

@main.route('/settings/lead-sources')
@login_required
def lead_source_integrations():
    if not _can_manage_lead_sources():
        flash('Access denied. Only admins and sales managers can manage lead source integrations.', 'error')
        return redirect(url_for('main.leads'))

    integrations = LeadSourceIntegration.query.order_by(LeadSourceIntegration.source_type).all()
    website_form = WebsiteIntegrationForm()
    facebook_form = FacebookIntegrationForm()
    course_choices = [(0, 'None')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
    website_form.default_course_id.choices = course_choices
    facebook_form.default_course_id.choices = course_choices
    course_map = {c.id: c.name for c in Course.query.all()}

    return render_template('lead_source_integrations.html',
                            integrations=integrations,
                            course_map=course_map,
                            website_form=website_form,
                            facebook_form=facebook_form)


@main.route('/settings/lead-sources/website/add', methods=['POST'])
@login_required
def add_website_integration():
    if not _can_manage_lead_sources():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))

    form = WebsiteIntegrationForm()
    form.default_course_id.choices = [(0, 'None')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]

    if form.validate_on_submit():
        integration = LeadSourceIntegration(
            source_type='website',
            name=form.name.data,
            is_active=form.is_active.data,
            webhook_token=secrets.token_urlsafe(32),
            default_course_id=form.default_course_id.data or None,
        )
        db.session.add(integration)
        db.session.commit()
        flash('Website integration created — copy the webhook URL below into Elementor.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")

    return redirect(url_for('main.lead_source_integrations'))


@main.route('/settings/lead-sources/facebook/add', methods=['POST'])
@login_required
def add_facebook_integration():
    if not _can_manage_lead_sources():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))

    form = FacebookIntegrationForm()
    form.default_course_id.choices = [(0, 'None')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]

    if form.validate_on_submit():
        integration = LeadSourceIntegration(
            source_type='facebook',
            name=form.name.data,
            is_active=form.is_active.data,
            webhook_token=secrets.token_urlsafe(32),
            fb_verify_token=secrets.token_urlsafe(16),
            fb_app_id=form.fb_app_id.data,
            fb_app_secret=form.fb_app_secret.data,
            fb_page_id=form.fb_page_id.data,
            fb_page_access_token=form.fb_page_access_token.data,
            default_course_id=form.default_course_id.data or None,
        )
        db.session.add(integration)
        db.session.commit()
        flash('Facebook/Instagram integration created — use the callback URL and verify token below in Meta\'s App Dashboard.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")

    return redirect(url_for('main.lead_source_integrations'))


@main.route('/settings/lead-sources/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_lead_source_integration(id):
    if not _can_manage_lead_sources():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))
    integration = LeadSourceIntegration.query.get_or_404(id)
    integration.is_active = not integration.is_active
    db.session.commit()
    flash(f"{integration.name} {'activated' if integration.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('main.lead_source_integrations'))


@main.route('/settings/lead-sources/<int:id>/delete', methods=['POST'])
@login_required
def delete_lead_source_integration(id):
    if not _can_manage_lead_sources():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))
    integration = LeadSourceIntegration.query.get_or_404(id)
    db.session.delete(integration)
    db.session.commit()
    flash('Integration deleted.', 'success')
    return redirect(url_for('main.lead_source_integrations'))


@main.route("/payments/settings")
@login_required
def payment_settings():
    settings = PaymentSettings.query.first()
    form = PaymentSettingsForm()
    
    if settings:
        form.company_name.data = settings.company_name
        form.company_email.data = settings.company_email
        form.company_phone.data = settings.company_phone
        form.company_address.data = settings.company_address
        form.tax_registration_number.data = settings.tax_registration_number
        form.payment_terms.data = settings.payment_terms
        form.invoice_notes.data = settings.invoice_notes
        form.default_currency.data = settings.default_currency
        form.auto_send_receipts.data = settings.auto_send_receipts
        form.payment_reminder_enabled.data = settings.payment_reminder_enabled
        form.payment_reminder_days.data = settings.payment_reminder_days
    
    return render_template("payment_settings.html", form=form, settings=settings)

@main.route("/payments/settings/save", methods=["POST"])
@login_required
def save_payment_settings():
    form = PaymentSettingsForm()
    
    if form.validate_on_submit():
        try:
            settings = PaymentSettings.query.first()
            
            if not settings:
                settings = PaymentSettings()
                db.session.add(settings)
            
            settings.company_name = form.company_name.data
            settings.company_email = form.company_email.data
            settings.company_phone = form.company_phone.data
            settings.company_address = form.company_address.data
            settings.tax_registration_number = form.tax_registration_number.data
            settings.payment_terms = form.payment_terms.data
            settings.invoice_notes = form.invoice_notes.data
            settings.default_currency = form.default_currency.data
            settings.auto_send_receipts = form.auto_send_receipts.data
            settings.payment_reminder_enabled = form.payment_reminder_enabled.data
            settings.payment_reminder_days = form.payment_reminder_days.data
            settings.updated_at = datetime.now()
            
            db.session.commit()
            flash("Payment settings saved successfully!", "success")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving settings: {str(e)}", "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("main.payment_settings"))

def generate_vault_payment_url(payment_link, provider):
    return f"https://vault-api-{provider.environment}.com/pay/{payment_link.payment_reference}"

def generate_tabby_payment_url(payment_link, provider):
    return f"https://api.tabby.ai/{provider.environment}/checkout/{payment_link.payment_reference}"

def generate_tamara_payment_url(payment_link, provider):
    return f"https://api.tamara.co/{provider.environment}/checkout/{payment_link.payment_reference}"

# User Management Routes
@main.route('/users')
@login_required
def users():
    """View all users - only for admins and users with user management permission"""
    if current_user.role == 'sales_manager' or not (current_user.is_admin() or current_user.can_manage_users):
        flash('Access denied. You do not have permission to manage users.', 'error')
        return redirect(url_for('main.dashboard'))

    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=all_users)


@main.route('/admin/login-logs')
@login_required
def admin_login_logs():
    """Login history with IP — admin only."""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))

    page      = request.args.get('page', 1, type=int)
    user_f    = request.args.get('user', '', type=str)
    status_f  = request.args.get('status', '', type=str)
    ip_f      = request.args.get('ip', '', type=str)

    q = LoginLog.query.order_by(LoginLog.login_at.desc())
    if user_f:
        q = q.filter(LoginLog.username_try.ilike(f'%{user_f}%'))
    if status_f:
        q = q.filter(LoginLog.status == status_f)
    if ip_f:
        q = q.filter(LoginLog.ip_address.ilike(f'%{ip_f}%'))

    from math import ceil
    per_page  = 50
    total     = q.count()
    logs      = q.offset((page - 1) * per_page).limit(per_page).all()
    pages     = ceil(total / per_page) if total else 1

    # attach user objects manually (no FK relationship)
    uid_set    = {l.user_id for l in logs if l.user_id}
    user_map   = {u.id: u for u in User.query.filter(User.id.in_(uid_set)).all()} if uid_set else {}

    # summary counts
    total_logins   = LoginLog.query.count()
    success_count  = LoginLog.query.filter_by(status='success').count()
    failed_count   = LoginLog.query.filter_by(status='failed').count()
    unique_ips     = db.session.query(func.count(func.distinct(LoginLog.ip_address))).scalar()

    return render_template('admin_login_logs.html',
        logs=logs, user_map=user_map,
        page=page, pages=pages, total=total,
        user_f=user_f, status_f=status_f, ip_f=ip_f,
        total_logins=total_logins, success_count=success_count,
        failed_count=failed_count, unique_ips=unique_ips,
    )

@main.route('/users/add', methods=['GET', 'POST'])
@login_required  
def add_user():
    """Add new user - only for admins"""
    if not current_user.is_admin():
        flash('Access denied. Only administrators can add users.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = UserForm()
    
    if form.validate_on_submit():
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        
        if existing_user:
            flash('Username or email already exists!', 'error')
            return render_template('add_user.html', form=form)
        
        # Create new user
        new_user = User()
        new_user.username = form.username.data
        new_user.email = form.email.data
        new_user.password_hash = generate_password_hash(form.password.data)
        new_user.role = form.role.data
        new_user.active = form.active.data
        new_user.created_by_id = current_user.id
        
        # Set permissions for superadmin role
        if form.role.data == 'superadmin':
            new_user.can_view_all_leads = form.can_view_all_leads.data
            new_user.can_manage_users = form.can_manage_users.data
            new_user.can_view_reports = form.can_view_reports.data
            new_user.can_manage_courses = form.can_manage_courses.data
            new_user.can_manage_settings = form.can_manage_settings.data
        elif form.role.data == 'admin':
            # Admin gets all permissions
            new_user.can_view_all_leads = True
            new_user.can_manage_users = True
            new_user.can_view_reports = True
            new_user.can_manage_courses = True
            new_user.can_manage_settings = True
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User {new_user.username} created successfully!', 'success')
        return redirect(url_for('main.users'))
    
    return render_template('add_user.html', form=form)

@main.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    """Edit existing user - only for admins"""
    if not current_user.is_admin():
        flash('Access denied. Only administrators can edit users.', 'error')
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(id)
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        # Check if username or email conflicts with other users
        existing_user = User.query.filter(
            User.id != id,
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        
        if existing_user:
            flash('Username or email already exists!', 'error')
            return render_template('edit_user.html', form=form, user=user)
        
        # Update user details
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.active = form.active.data
        
        # Update permissions for superadmin role
        if form.role.data == 'superadmin':
            user.can_view_all_leads = form.can_view_all_leads.data
            user.can_manage_users = form.can_manage_users.data
            user.can_view_reports = form.can_view_reports.data
            user.can_manage_courses = form.can_manage_courses.data
            user.can_manage_settings = form.can_manage_settings.data
        elif form.role.data == 'admin':
            # Admin gets all permissions
            user.can_view_all_leads = True
            user.can_manage_users = True
            user.can_view_reports = True
            user.can_manage_courses = True
            user.can_manage_settings = True
        else:  # consultant
            user.can_view_all_leads = False
            user.can_manage_users = False
            user.can_view_reports = False
            user.can_manage_courses = False
            user.can_manage_settings = False
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('main.users'))
    
    return render_template('edit_user.html', form=form, user=user)

@main.route('/users/<int:id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(id):
    """Toggle user active/inactive status - only for admins"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    user = User.query.get_or_404(id)
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot deactivate your own account'}), 400
    
    user.active = not user.active
    db.session.commit()
    
    status = 'activated' if user.active else 'deactivated'
    return jsonify({'success': True, 'message': f'User {status} successfully'})

@main.route('/users/<int:id>/reset-password', methods=['POST'])
@login_required
def reset_user_password(id):
    """Reset user password - only for admins"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    user = User.query.get_or_404(id)
    
    # Generate temporary password
    temp_password = f"temp{user.id}{datetime.now().strftime('%d%m')}"
    user.password_hash = generate_password_hash(temp_password)
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Password reset successfully',
        'temp_password': temp_password
    })

@main.route('/profile')
@login_required
def user_profile():
    """View current user profile"""
    return render_template('user_profile.html', user=current_user)

@main.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change current user password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not check_password_hash(current_user.password_hash, form.current_password.data):
            flash('Current password is incorrect!', 'error')
            return render_template('change_password.html', form=form)
        
        if form.new_password.data != form.confirm_password.data:
            flash('New passwords do not match!', 'error')
            return render_template('change_password.html', form=form)
        
        current_user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('main.user_profile'))
    
    return render_template('change_password.html', form=form)

# ══════════════════════════════════════════════════════════════
#  ORBIT ERP INTEGRATION BRIDGE
# ══════════════════════════════════════════════════════════════

@main.route('/api/erp/lead/<int:id>', methods=['GET'])
@login_required
def erp_lead_data(id):
    """Return lead data for Django ERP registration pre-fill."""
    lead = Lead.query.get_or_404(id)
    parts = lead.name.strip().split(' ', 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''
    return jsonify({
        'id': lead.id,
        'first_name': first_name,
        'last_name': last_name,
        'phone': lead.phone,
        'whatsapp': lead.whatsapp or '',
        'email': lead.email or '',
        'course_id': lead.course_interest_id,
        'course_name': lead.course_interest.name if lead.course_interest else '',
        'status': lead.status,
        'erp_url': f'{_ERP_URL}/register/?crm_id={lead.id}'
                   f'&fn={first_name}&ln={last_name}'
                   f'&ph={lead.phone or ""}'
                   f'&em={lead.email or ""}'
                   f'&ci={lead.course_interest_id or ""}'
    })


@main.route('/api/internal/lead/<int:id>', methods=['GET'])
def internal_lead_lookup(id):
    """Server-to-server lead lookup for ERP registration form (HMAC-verified)."""
    auth = request.headers.get('Authorization', '')
    if not hmac.compare_digest(auth, f'Bearer {_SSO_SECRET}'):
        return jsonify({'error': 'unauthorized'}), 401
    try:
        lead = db.session.get(Lead, id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        return jsonify({
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone or '',
            'email': lead.email or '',
            'status': lead.status,
        })
    except Exception as e:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500


@main.route('/leads/<int:id>/register-in-erp', methods=['GET'])
@login_required
def register_in_erp(id):
    """Redirect to Django ERP with lead data pre-filled."""
    lead = Lead.query.get_or_404(id)
    parts = lead.name.strip().split(' ', 1)
    fn = parts[0]
    ln = parts[1] if len(parts) > 1 else ''
    from urllib.parse import urlencode
    params = urlencode({
        'crm_id': lead.id,
        'fn': fn,
        'ln': ln,
        'ph': lead.phone or '',
        'em': lead.email or '',
        'ci': lead.course_interest_id or '',
        # SSO token so ERP auto-logs in the CRM user
        'sso_t': _make_sso_token(current_user.username),
    })
    if lead.status == 'Converted':
        flash(f'Lead {lead.name} is already converted.', 'info')
    return redirect(f'{_ERP_URL}/crm-auth/?t={_make_sso_token(current_user.username)}&next=/register/?{params}')


# ══════════════════════════════════════════════════════════════════
#  SSO — auto-login from Orbit ERP token
# ══════════════════════════════════════════════════════════════════

@main.route('/auto-login')
def auto_login():
    """Receive HMAC-signed token from Django ERP and log user in automatically."""
    token = request.args.get('t', '')
    username = _verify_sso_token(token)
    if not username:
        flash('Session link expired or invalid. Please log in.', 'warning')
        return redirect(url_for('main.login'))

    user = User.query.filter_by(username=username, active=True).first()
    if not user:
        flash(f'User "{username}" not found in CRM. Contact your admin.', 'danger')
        return redirect(url_for('main.login'))

    login_user(user, remember=False)
    return redirect(url_for('main.dashboard'))


@main.route('/erp-jump')
@login_required
def erp_jump():
    """Jump to Orbit ERP auto-logged-in.
    ?crm_lead=<id>  → open registration form pre-linked to this lead
    ?action=reg-link&crm_lead=<id>  → open student-links page with lead ID pre-filled
    """
    token = _make_sso_token(current_user.username)
    crm_lead = request.args.get('crm_lead', '').strip()
    action = request.args.get('action', '')
    if action == 'reg-link' and crm_lead:
        # Send to IMS student links page with lead ID pre-filled
        import urllib.parse
        next_path = urllib.parse.quote(f'/portal/student-links/?cli={crm_lead}', safe='')
        return redirect(f'{_ERP_URL}/crm-auth/?t={token}&next={next_path}')
    elif crm_lead:
        return redirect(f'{_ERP_URL}/crm-auth/?t={token}&crm_id={crm_lead}')
    return redirect(f'{_ERP_URL}/crm-auth/?t={token}')


# ══════════════════════════════════════════════════════════════════════════
# WhatsApp Marketing Campaigns (official Meta Cloud API)
# ══════════════════════════════════════════════════════════════════════════

# ── Small helpers ────────────────────────────────────────────────────────

def _normalize_whatsapp_number(raw, default_cc='971'):
    """Best-effort normalize a phone string to Meta's expected digits-only E.164
    (no leading '+'). Leads in this DB have inconsistent formats — +971..., 05...,
    971..., bare 9-digit local — so this is a heuristic, not a strict validator."""
    if not raw:
        return None
    has_plus = raw.strip().startswith('+')
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return None
    if digits.startswith('00'):
        digits = digits[2:]
        has_plus = True
    if has_plus or digits.startswith(default_cc):
        return digits
    if digits.startswith('0'):
        return default_cc + digits[1:]
    if len(digits) <= 10:
        return default_cc + digits
    return digits


def _parse_variable_mapping(text_input):
    """Turn the template editor's shorthand ("lead.name, lead.course, static:20% off")
    into the JSON list stored on MessageTemplate.meta_variable_mapping."""
    if not text_input or not text_input.strip():
        return None
    mapping = []
    for token in text_input.split(','):
        token = token.strip()
        if not token:
            continue
        if token.startswith('static:'):
            mapping.append({'source': 'static', 'static_value': token[len('static:'):].strip(), 'label': 'Static text'})
        elif token in ('lead.name', 'lead.course', 'lead.phone', 'lead.email'):
            mapping.append({'source': token, 'label': token})
        else:
            # Unknown token — treat as static text so nothing silently vanishes
            mapping.append({'source': 'static', 'static_value': token, 'label': 'Static text'})
    return json.dumps(mapping) if mapping else None


def _variable_mapping_display(mapping_json):
    if not mapping_json:
        return ''
    try:
        mapping = json.loads(mapping_json)
    except Exception:
        return ''
    parts = []
    for m in mapping:
        parts.append(f"static:{m.get('static_value', '')}" if m.get('source') == 'static' else m.get('source', ''))
    return ', '.join(parts)


def _resolve_variable_value(source, static_value, lead):
    if source == 'lead.name':
        return lead.name or ''
    if source == 'lead.course':
        if lead.course_interest:
            return lead.course_interest.name
        return lead.course_text or ''
    if source == 'lead.phone':
        return lead.phone or ''
    if source == 'lead.email':
        return lead.email or ''
    if source == 'static':
        return static_value or ''
    return ''


def _render_template_variables(template, lead):
    try:
        mapping = json.loads(template.meta_variable_mapping or '[]')
    except Exception:
        mapping = []
    return [_resolve_variable_value(m.get('source'), m.get('static_value'), lead) for m in mapping]


def _fanout_whatsapp_optout(phone):
    """A phone number can exist on more than one Lead row (duplicate detection
    already handles this elsewhere) — flip opt-out on every row that shares it,
    not just the first match, and stop any active enrollment for those leads."""
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) < 9:
        return
    suffix = digits[-9:]
    matches = Lead.query.filter(
        db.or_(Lead.phone.like(f'%{suffix}'), Lead.whatsapp.like(f'%{suffix}'))
    ).all()
    now = datetime.utcnow()
    for lead in matches:
        lead.whatsapp_opted_out = True
        lead.whatsapp_opted_out_at = now
        WhatsAppEnrollment.query.filter_by(lead_id=lead.id, status='active').update({
            'status': 'opted_out', 'stopped_reason': 'opted_out',
        })
    db.session.commit()


def _apply_campaign_audience_filters(status=None, course_id=None, lead_source=None, assigned_to=None, date_from=None, date_to=None):
    """Leads eligible for a WhatsApp campaign: opted-in, and have some usable number."""
    query = Lead.query.filter(
        Lead.whatsapp_opted_out.isnot(True),
        db.or_(Lead.whatsapp.isnot(None), Lead.phone.isnot(None)),
    )
    if status:
        query = query.filter(Lead.status == status)
    if course_id:
        query = query.filter(Lead.course_interest_id == course_id)
    if lead_source:
        query = query.filter(Lead.lead_source == lead_source)
    if assigned_to:
        query = query.filter(Lead.assigned_to == assigned_to)
    if date_from:
        try:
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Lead.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass
    return query


# ── Sending ──────────────────────────────────────────────────────────────

def send_whatsapp_template(account, to_phone, meta_template_name, meta_language_code, variables):
    """POST a template message via the Meta WhatsApp Cloud API.
    Returns (success: bool, meta_message_id: str|None, error: dict|None)."""
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_phone,
        'type': 'template',
        'template': {'name': meta_template_name, 'language': {'code': meta_language_code or 'en_US'}},
    }
    if variables:
        payload['template']['components'] = [{
            'type': 'body',
            'parameters': [{'type': 'text', 'text': str(v)} for v in variables],
        }]
    try:
        resp = requests.post(
            f'https://graph.facebook.com/v20.0/{account.phone_number_id}/messages',
            headers={'Authorization': f'Bearer {account.access_token}'},
            json=payload,
            timeout=10,
        )
        data = resp.json()
    except Exception:
        logging.exception('WhatsApp send failed for %s (template %s)', to_phone, meta_template_name)
        return False, None, {'message': 'request_exception'}

    if resp.status_code == 200 and data.get('messages'):
        return True, data['messages'][0]['id'], None
    return False, None, data.get('error') or {'message': f'HTTP {resp.status_code}', 'raw': data}


def send_whatsapp_text(account, to_phone, body):
    """POST a plain free-text message — only valid within Meta's 24-hour customer
    service window since the customer's last inbound message (a real reply to an
    open conversation, not a proactive/marketing send, so no approved template
    needed). Returns (success: bool, meta_message_id: str|None, error: dict|None)."""
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_phone,
        'type': 'text',
        'text': {'body': body},
    }
    try:
        resp = requests.post(
            f'https://graph.facebook.com/v20.0/{account.phone_number_id}/messages',
            headers={'Authorization': f'Bearer {account.access_token}'},
            json=payload,
            timeout=10,
        )
        data = resp.json()
    except Exception:
        logging.exception('WhatsApp text reply failed for %s', to_phone)
        return False, None, {'message': 'request_exception'}

    if resp.status_code == 200 and data.get('messages'):
        return True, data['messages'][0]['id'], None
    return False, None, data.get('error') or {'message': f'HTTP {resp.status_code}', 'raw': data}


def _log_and_fail(enrollment, lead, template_id, step_order, error_code, error_message):
    now = datetime.utcnow()
    db.session.add(WhatsAppMessageLog(
        campaign_id=enrollment.campaign_id, enrollment_id=enrollment.id, step_order=step_order,
        lead_id=lead.id, template_id=template_id, status='failed',
        error_code=error_code, error_message=error_message, created_at=now,
    ))
    enrollment.attempts = (enrollment.attempts or 0) + 1
    if enrollment.attempts >= 3:
        enrollment.status = 'failed'
        enrollment.stopped_reason = error_code
    else:
        enrollment.next_due_at = now + timedelta(hours=1)
    enrollment.claim_token = None
    enrollment.claimed_at = None
    db.session.commit()


def _notify_campaign_failure(campaign, lead, error):
    recipients = [u for u in User.query.all() if u.is_admin() or u.is_sales_manager()]
    msg = f'WhatsApp campaign "{campaign.name}": failed to reach {lead.name} after 3 attempts.'
    for u in recipients:
        db.session.add(CRMNotification(user_id=u.id, message=msg, lead_id=lead.id, notif_type='campaign_failure'))


def _process_enrollment_step(account, enrollment):
    campaign = WhatsAppCampaign.query.get(enrollment.campaign_id)
    if not campaign or campaign.status != 'running':
        WhatsAppEnrollment.query.filter_by(id=enrollment.id).update({'claim_token': None, 'claimed_at': None})
        db.session.commit()
        return

    lead = Lead.query.get(enrollment.lead_id)
    if not lead or lead.whatsapp_opted_out:
        enrollment.status = 'opted_out' if lead else 'stopped'
        enrollment.stopped_reason = 'opted_out' if lead else 'lead_deleted'
        enrollment.claim_token = None
        enrollment.claimed_at = None
        db.session.commit()
        return

    next_step_exists = False
    if campaign.campaign_type == 'broadcast':
        template_id = campaign.template_id
        step_order = 0
    else:
        step = WhatsAppCampaignStep.query.filter_by(campaign_id=campaign.id, step_order=enrollment.current_step_order).first()
        if not step:
            enrollment.status = 'completed'
            enrollment.completed_at = datetime.utcnow()
            enrollment.claim_token = None
            enrollment.claimed_at = None
            db.session.commit()
            return
        template_id = step.template_id
        step_order = step.step_order
        next_step_exists = WhatsAppCampaignStep.query.filter_by(campaign_id=campaign.id, step_order=step_order + 1).first() is not None

    template = MessageTemplate.query.get(template_id)
    to_phone = _normalize_whatsapp_number(lead.whatsapp or lead.phone)

    if not template or not template.meta_template_name:
        _log_and_fail(enrollment, lead, template_id, step_order, 'template_missing', 'Template not found or has no Meta template name')
        return
    if not to_phone:
        _log_and_fail(enrollment, lead, template_id, step_order, 'invalid_number', 'Unparseable phone number')
        return

    variables = _render_template_variables(template, lead)
    success, meta_message_id, error = send_whatsapp_template(
        account, to_phone, template.meta_template_name, template.meta_language_code, variables)

    now = datetime.utcnow()
    display_text = f'[Template: {template.name}] ' + ' / '.join(str(v) for v in variables) if variables else f'[Template: {template.name}]'
    db.session.add(WhatsAppMessageLog(
        campaign_id=campaign.id, enrollment_id=enrollment.id, step_order=step_order,
        lead_id=lead.id, template_id=template_id, to_phone=to_phone,
        meta_message_id=meta_message_id, rendered_variables=json.dumps(variables),
        inbound_body=display_text,  # reused field: readable text for the conversation thread view
        status='sent' if success else 'failed',
        error_code=(error or {}).get('code') if error else None,
        error_message=json.dumps(error) if error else None,
        sent_at=now if success else None,
        created_at=now,
    ))

    if success:
        db.session.add(LeadInteraction(
            lead_id=lead.id, interaction_type='WhatsApp',
            content=f'Campaign "{campaign.name}" — sent "{template.name}"',
            interaction_date=now, is_important=False,
        ))
        enrollment.attempts = 0
        if campaign.campaign_type == 'broadcast' or not next_step_exists:
            enrollment.status = 'completed'
            enrollment.completed_at = now
        else:
            next_step = WhatsAppCampaignStep.query.filter_by(campaign_id=campaign.id, step_order=step_order + 1).first()
            enrollment.current_step_order = next_step.step_order
            enrollment.next_due_at = enrollment.enrolled_at + timedelta(days=next_step.day_offset)
    else:
        enrollment.attempts = (enrollment.attempts or 0) + 1
        if enrollment.attempts >= 3:
            enrollment.status = 'failed'
            enrollment.stopped_reason = 'max_attempts'
            _notify_campaign_failure(campaign, lead, error)
        else:
            enrollment.next_due_at = now + timedelta(hours=1)  # brief backoff before retry

    enrollment.claim_token = None
    enrollment.claimed_at = None
    db.session.commit()


def _process_account_due_enrollments(account):
    """Called by scheduler.py every tick. Safe under concurrent processes: the
    claim UPDATE below is what guarantees a given enrollment is only ever
    processed by one of them, not any process-level "only one worker" trick."""
    if account.quiet_hours_start and account.quiet_hours_end:
        current_time = datetime.now(_DUBAI_TZ).time()
        if not (account.quiet_hours_start <= current_time <= account.quiet_hours_end):
            return  # due enrollments just wait for the next in-window tick

    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    sent_last_24h = (
        db.session.query(func.count(WhatsAppMessageLog.id))
        .join(WhatsAppCampaign, WhatsAppMessageLog.campaign_id == WhatsAppCampaign.id)
        .filter(
            WhatsAppCampaign.account_id == account.id,
            WhatsAppMessageLog.direction == 'outbound',
            WhatsAppMessageLog.status.in_(['sent', 'delivered', 'read']),
            WhatsAppMessageLog.created_at >= day_ago,
        ).scalar()
    ) or 0
    remaining_budget = max(0, (account.daily_send_limit or 250) - sent_last_24h)
    if remaining_budget <= 0:
        return

    campaign_ids = [c.id for c in WhatsAppCampaign.query.filter_by(account_id=account.id, status='running').all()]
    if not campaign_ids:
        return

    batch_size = min(account.max_sends_per_tick or 20, remaining_budget)
    run_id = str(uuid.uuid4())
    stale_before = now - timedelta(minutes=5)

    stmt = text("""
        UPDATE whatsapp_enrollment
        SET claim_token = :run_id, claimed_at = :now
        WHERE status = 'active' AND next_due_at <= :now
          AND campaign_id IN :campaign_ids
          AND (claim_token IS NULL OR claimed_at < :stale_before)
        ORDER BY next_due_at
        LIMIT :batch_size
    """).bindparams(db.bindparam('campaign_ids', expanding=True))

    # No explicit isolation-level override needed: InnoDB's UPDATE/DELETE (and
    # SELECT ... FOR UPDATE) always perform a locking "current read" on the rows
    # matching WHERE — reading the latest committed data — regardless of the
    # transaction's isolation level. That's what makes this claim exclusive across
    # concurrent processes even under MySQL's default REPEATABLE READ; verified
    # under real concurrent load (6 threads racing 50 rows, zero double-claims).
    db.session.execute(stmt, {
        'run_id': run_id, 'now': now, 'stale_before': stale_before,
        'campaign_ids': campaign_ids, 'batch_size': batch_size,
    })
    db.session.commit()  # commit immediately — this is what makes the claim exclusive

    claimed = WhatsAppEnrollment.query.filter_by(claim_token=run_id).all()
    for enrollment in claimed:
        _process_enrollment_step(account, enrollment)


# ── Webhook: delivery status + inbound messages/opt-out ─────────────────

_WHATSAPP_OPTOUT_KEYWORDS = {'stop', 'unsubscribe', 'opt out', 'optout'}


def _handle_whatsapp_status(status_update):
    meta_message_id = status_update.get('id')
    new_status = status_update.get('status')
    if not meta_message_id or new_status not in ('sent', 'delivered', 'read', 'failed'):
        return
    log = WhatsAppMessageLog.query.filter_by(meta_message_id=meta_message_id).first()
    if not log:
        return
    log.status = new_status
    log.status_updated_at = datetime.utcnow()
    if new_status == 'failed':
        errors = status_update.get('errors') or []
        if errors:
            log.error_code = str(errors[0].get('code', ''))
            log.error_message = errors[0].get('title', '')
    db.session.commit()


def _notify_whatsapp_inbound(lead, from_phone, body):
    """Alert admins + sales managers that a customer replied on WhatsApp."""
    recipients = [u for u in User.query.all() if u.is_admin() or u.is_sales_manager()]
    who = lead.name if lead else from_phone
    preview = (body or '').strip()[:120] or '(no text — image/attachment/other)'
    for u in recipients:
        db.session.add(CRMNotification(
            user_id=u.id,
            message=f'WhatsApp reply from {who}: "{preview}"',
            lead_id=lead.id if lead else None,
            notif_type='whatsapp_inbound',
        ))
    db.session.commit()


def _handle_whatsapp_inbound(msg):
    from_phone = msg.get('from', '')
    body = (msg.get('text') or {}).get('body', '') if msg.get('type') == 'text' else ''

    suffix = re.sub(r'\D', '', from_phone)[-9:]
    lead = Lead.query.filter(
        db.or_(Lead.phone.like(f'%{suffix}'), Lead.whatsapp.like(f'%{suffix}'))
    ).first() if len(suffix) >= 9 else None

    db.session.add(WhatsAppMessageLog(
        lead_id=lead.id if lead else None, direction='inbound', to_phone=from_phone,
        inbound_body=body, status='delivered', created_at=datetime.utcnow(),
    ))
    db.session.commit()

    if body.strip().lower() in _WHATSAPP_OPTOUT_KEYWORDS:
        _fanout_whatsapp_optout(from_phone)

    _notify_whatsapp_inbound(lead, from_phone, body)


@main.route('/webhooks/whatsapp/<token>/', methods=['GET', 'POST'])
def webhook_whatsapp(token):
    account = WhatsAppAccount.query.filter_by(webhook_token=token, is_active=True).first()
    if not account:
        return jsonify({'status': 'error'}), 404

    if request.method == 'GET':
        if (request.args.get('hub.mode') == 'subscribe'
                and request.args.get('hub.verify_token') == account.verify_token
                and account.verify_token):
            return request.args.get('hub.challenge', ''), 200
        return 'verification failed', 403

    if account.app_secret:
        signature = request.headers.get('X-Hub-Signature-256', '')
        expected = 'sha256=' + hmac.new(account.app_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return jsonify({'status': 'error', 'message': 'invalid signature'}), 403

    payload = request.get_json(silent=True) or {}
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            for status_update in value.get('statuses', []):
                _handle_whatsapp_status(status_update)
            for msg in value.get('messages', []):
                _handle_whatsapp_inbound(msg)
    return jsonify({'status': 'ok'}), 200


# ── Settings ─────────────────────────────────────────────────────────────

@main.route('/settings/whatsapp')
@login_required
def whatsapp_settings():
    if not current_user.is_admin():
        flash('Access denied. Only admins can manage WhatsApp settings.', 'error')
        return redirect(url_for('main.dashboard'))
    account = WhatsAppAccount.query.first()
    form = WhatsAppAccountForm(obj=account) if account else WhatsAppAccountForm()
    return render_template('whatsapp_settings.html', account=account, form=form)


@main.route('/settings/whatsapp/save', methods=['POST'])
@login_required
def save_whatsapp_settings():
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    form = WhatsAppAccountForm()
    account = WhatsAppAccount.query.first()
    if form.validate_on_submit():
        if not account:
            account = WhatsAppAccount(webhook_token=secrets.token_urlsafe(32), verify_token=secrets.token_urlsafe(16))
            db.session.add(account)
        account.name = form.name.data
        account.phone_number_id = form.phone_number_id.data or None
        account.waba_id = form.waba_id.data or None
        account.business_display_phone = form.business_display_phone.data or None
        if form.access_token.data:  # blank field on edit = keep the existing token
            account.access_token = form.access_token.data
        account.app_secret = form.app_secret.data or None
        account.daily_send_limit = form.daily_send_limit.data or 250
        account.max_sends_per_tick = form.max_sends_per_tick.data or 20
        account.quiet_hours_start = form.quiet_hours_start.data
        account.quiet_hours_end = form.quiet_hours_end.data
        account.is_active = form.is_active.data
        db.session.commit()
        flash('WhatsApp settings saved.', 'success')
    else:
        flash('Please check the form for errors.', 'error')
    return redirect(url_for('main.whatsapp_settings'))


@main.route('/settings/whatsapp/test', methods=['POST'])
@login_required
def test_whatsapp_connection():
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403
    account = WhatsAppAccount.query.first()
    if not account or not account.phone_number_id or not account.access_token:
        return jsonify({'success': False, 'message': 'Configure Phone Number ID and Access Token first.'}), 400
    try:
        resp = requests.get(
            f'https://graph.facebook.com/v20.0/{account.phone_number_id}',
            params={'access_token': account.access_token},
            timeout=10,
        )
        data = resp.json()
    except Exception:
        logging.exception('WhatsApp connection test failed')
        account.last_test_at = datetime.utcnow()
        account.last_test_result = 'failed'
        db.session.commit()
        return jsonify({'success': False, 'message': 'Network error contacting Meta.'}), 500

    account.last_test_at = datetime.utcnow()
    if resp.status_code == 200 and data.get('id'):
        account.last_test_result = 'ok'
        db.session.commit()
        return jsonify({'success': True, 'message': f'Connected — {data.get("display_phone_number", data.get("id"))}'})
    account.last_test_result = 'failed'
    db.session.commit()
    return jsonify({'success': False, 'message': (data.get('error') or {}).get('message', 'Connection failed.')}), 400


# ── WhatsApp Inbox (inbound replies) ───────────────────────────────────────

@main.route('/whatsapp/inbox')
@login_required
def whatsapp_inbox():
    if not _can_manage_campaigns():
        flash('Access denied. Only admins and sales managers can view the WhatsApp inbox.', 'error')
        return redirect(url_for('main.leads'))

    # One row per conversation (grouped by lead, or by phone for unmatched numbers),
    # showing the most recent message in each — a normal "inbox" view, not a flat log.
    recent = WhatsAppMessageLog.query.order_by(desc(WhatsAppMessageLog.created_at)).limit(500).all()
    seen = set()
    conversations = []
    for m in recent:
        key = ('lead', m.lead_id) if m.lead_id else ('phone', m.to_phone)
        if key in seen:
            continue
        seen.add(key)
        conversations.append(m)

    lead_ids = [c.lead_id for c in conversations if c.lead_id]
    lead_map = {l.id: l for l in Lead.query.filter(Lead.id.in_(lead_ids)).all()}
    return render_template('whatsapp_inbox.html', conversations=conversations, lead_map=lead_map)


@main.route('/whatsapp/inbox/<int:lead_id>')
@login_required
def whatsapp_conversation(lead_id):
    if not _can_manage_campaigns():
        flash('Access denied. Only admins and sales managers can view WhatsApp conversations.', 'error')
        return redirect(url_for('main.leads'))
    lead = Lead.query.get_or_404(lead_id)
    messages = WhatsAppMessageLog.query.filter_by(lead_id=lead_id).order_by(WhatsAppMessageLog.created_at).all()

    last_inbound = (
        WhatsAppMessageLog.query.filter_by(lead_id=lead_id, direction='inbound')
        .order_by(desc(WhatsAppMessageLog.created_at)).first()
    )
    window_open = bool(
        last_inbound and last_inbound.created_at
        and (datetime.utcnow() - last_inbound.created_at) < timedelta(hours=24)
    )
    account = WhatsAppAccount.query.filter_by(is_active=True).first()
    return render_template('whatsapp_conversation.html', lead=lead, messages=messages,
                            window_open=window_open, account=account)


@main.route('/whatsapp/inbox/<int:lead_id>/reply', methods=['POST'])
@login_required
def whatsapp_reply(lead_id):
    if not _can_manage_campaigns():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403
    lead = Lead.query.get_or_404(lead_id)
    body = (request.form.get('body') or '').strip()
    if not body:
        return jsonify({'success': False, 'message': 'Message cannot be empty.'}), 400
    if lead.whatsapp_opted_out:
        return jsonify({'success': False, 'message': 'This lead has opted out of WhatsApp messages.'}), 400

    last_inbound = (
        WhatsAppMessageLog.query.filter_by(lead_id=lead_id, direction='inbound')
        .order_by(desc(WhatsAppMessageLog.created_at)).first()
    )
    window_open = bool(
        last_inbound and last_inbound.created_at
        and (datetime.utcnow() - last_inbound.created_at) < timedelta(hours=24)
    )
    if not window_open:
        return jsonify({'success': False, 'message': "This customer hasn't messaged in the last 24 hours — "
                                                       "free-text replies aren't allowed. Use an approved template via a campaign instead."}), 400

    account = WhatsAppAccount.query.filter_by(is_active=True).first()
    if not account:
        return jsonify({'success': False, 'message': 'WhatsApp is not configured yet.'}), 400

    to_phone = _normalize_whatsapp_number(lead.whatsapp or lead.phone)
    if not to_phone:
        return jsonify({'success': False, 'message': 'This lead has no usable phone number.'}), 400

    success, meta_message_id, error = send_whatsapp_text(account, to_phone, body)
    now = datetime.utcnow()
    db.session.add(WhatsAppMessageLog(
        lead_id=lead.id, direction='outbound', to_phone=to_phone,
        meta_message_id=meta_message_id, inbound_body=body,  # reused field: raw text for both directions
        status='sent' if success else 'failed',
        error_code=(error or {}).get('code') if error else None,
        error_message=json.dumps(error) if error else None,
        sent_at=now if success else None, created_at=now,
    ))
    if success:
        db.session.add(LeadInteraction(
            lead_id=lead.id, interaction_type='WhatsApp',
            content=f'Replied: {body[:200]}', interaction_date=now, is_important=False,
        ))
    db.session.commit()

    if not success:
        return jsonify({'success': False, 'message': (error or {}).get('message', 'Failed to send.')}), 400
    return jsonify({'success': True})


# ── Campaigns ────────────────────────────────────────────────────────────

@main.route('/campaigns')
@login_required
def campaigns():
    if not _can_manage_campaigns():
        flash('Access denied. Only admins and sales managers can manage campaigns.', 'error')
        return redirect(url_for('main.leads'))
    all_campaigns = WhatsAppCampaign.query.order_by(desc(WhatsAppCampaign.created_at)).all()
    stats = {}
    for c in all_campaigns:
        counts = dict(
            db.session.query(WhatsAppMessageLog.status, func.count(WhatsAppMessageLog.id))
            .filter(WhatsAppMessageLog.campaign_id == c.id, WhatsAppMessageLog.direction == 'outbound')
            .group_by(WhatsAppMessageLog.status).all()
        )
        stats[c.id] = {
            'enrolled': WhatsAppEnrollment.query.filter_by(campaign_id=c.id).count(),
            'sent': counts.get('sent', 0) + counts.get('delivered', 0) + counts.get('read', 0),
            'failed': counts.get('failed', 0),
            'opted_out': WhatsAppEnrollment.query.filter_by(campaign_id=c.id, status='opted_out').count(),
        }
    return render_template('campaigns.html', campaigns=all_campaigns, stats=stats)


@main.route('/campaigns/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    if not _can_manage_campaigns():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))

    account = WhatsAppAccount.query.filter_by(is_active=True).first()
    templates = MessageTemplate.query.filter_by(message_type='WhatsApp', is_active=True).all()
    courses = Course.query.filter_by(is_active=True).all()
    consultants = User.query.order_by(User.username).all()

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        campaign_type = request.form.get('campaign_type', 'broadcast')
        if not name:
            flash('Campaign name is required.', 'error')
            return redirect(url_for('main.new_campaign'))
        if not account:
            flash('Configure WhatsApp settings before creating a campaign.', 'error')
            return redirect(url_for('main.whatsapp_settings'))

        audience = {
            'status': request.form.get('status') or None,
            'course_id': request.form.get('course_id', type=int) or None,
            'lead_source': request.form.get('lead_source') or None,
            'assigned_to': request.form.get('assigned_to', type=int) or None,
            'date_from': request.form.get('date_from') or None,
            'date_to': request.form.get('date_to') or None,
        }
        campaign = WhatsAppCampaign(
            name=name, campaign_type=campaign_type, status='draft',
            account_id=account.id, audience_filters=json.dumps(audience),
            created_by_id=current_user.id,
        )

        if campaign_type == 'broadcast':
            template_id = request.form.get('template_id', type=int)
            if not template_id:
                flash('Select a template for the broadcast.', 'error')
                return redirect(url_for('main.new_campaign'))
            campaign.template_id = template_id
            db.session.add(campaign)
            db.session.commit()
        else:
            step_templates = request.form.getlist('step_template_id[]', type=int)
            step_offsets = request.form.getlist('step_day_offset[]', type=int)
            if not step_templates:
                flash('Add at least one step to the sequence.', 'error')
                return redirect(url_for('main.new_campaign'))
            db.session.add(campaign)
            db.session.flush()
            for i, (tid, offset) in enumerate(zip(step_templates, step_offsets)):
                db.session.add(WhatsAppCampaignStep(campaign_id=campaign.id, step_order=i, day_offset=offset or 0, template_id=tid))
            db.session.commit()

        flash('Campaign created as a draft. Review and launch it from the campaign page.', 'success')
        return redirect(url_for('main.campaign_detail', id=campaign.id))

    return render_template('campaign_builder.html', account=account, templates=templates, courses=courses, consultants=consultants)


@main.route('/campaigns/audience-preview', methods=['POST'])
@login_required
def campaign_audience_preview():
    if not _can_manage_campaigns():
        return jsonify({'success': False}), 403
    query = _apply_campaign_audience_filters(
        status=request.form.get('status') or None,
        course_id=request.form.get('course_id', type=int),
        lead_source=request.form.get('lead_source') or None,
        assigned_to=request.form.get('assigned_to', type=int),
        date_from=request.form.get('date_from') or None,
        date_to=request.form.get('date_to') or None,
    )
    return jsonify({'success': True, 'count': query.count()})


def _launch_campaign_enrollments(campaign, leads):
    now = datetime.utcnow()
    if campaign.campaign_type == 'broadcast':
        first_offset = 0
    else:
        first_step = WhatsAppCampaignStep.query.filter_by(campaign_id=campaign.id, step_order=0).first()
        first_offset = first_step.day_offset if first_step else 0

    existing_lead_ids = {e.lead_id for e in WhatsAppEnrollment.query.filter_by(campaign_id=campaign.id).all()}
    added = 0
    for lead in leads:
        if lead.id in existing_lead_ids:
            continue
        db.session.add(WhatsAppEnrollment(
            campaign_id=campaign.id, lead_id=lead.id,
            phone_snapshot=lead.whatsapp or lead.phone,
            status='active', current_step_order=0,
            next_due_at=now + timedelta(days=first_offset),
            enrolled_at=now,
        ))
        added += 1
    db.session.commit()
    return added


@main.route('/campaigns/<int:id>/launch', methods=['POST'])
@login_required
def launch_campaign(id):
    if not _can_manage_campaigns():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403
    campaign = WhatsAppCampaign.query.get_or_404(id)
    if campaign.status not in ('draft', 'paused'):
        return jsonify({'success': False, 'message': f'Campaign is already {campaign.status}.'}), 400

    if campaign.campaign_type == 'broadcast':
        template_ids = [campaign.template_id]
    else:
        template_ids = [s.template_id for s in WhatsAppCampaignStep.query.filter_by(campaign_id=campaign.id).all()]
    templates_map = {t.id: t for t in MessageTemplate.query.filter(MessageTemplate.id.in_(template_ids)).all()}
    for tid in template_ids:
        t = templates_map.get(tid)
        if not t or t.meta_status != 'approved' or not t.meta_template_name:
            name = t.name if t else tid
            return jsonify({'success': False, 'message': f'Template "{name}" is not an approved WhatsApp template yet.'}), 400

    filters = json.loads(campaign.audience_filters or '{}')
    leads = _apply_campaign_audience_filters(**filters).all()
    if not leads:
        return jsonify({'success': False, 'message': "No leads match this campaign's audience filters."}), 400

    added = _launch_campaign_enrollments(campaign, leads)
    campaign.status = 'running'
    campaign.launched_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': f'Campaign launched — {added} lead(s) enrolled.'})


@main.route('/campaigns/<int:id>/pause', methods=['POST'])
@login_required
def pause_campaign(id):
    if not _can_manage_campaigns():
        return jsonify({'success': False}), 403
    campaign = WhatsAppCampaign.query.get_or_404(id)
    if campaign.status == 'running':
        campaign.status = 'paused'
        db.session.commit()
    return jsonify({'success': True})


@main.route('/campaigns/<int:id>/resume', methods=['POST'])
@login_required
def resume_campaign(id):
    if not _can_manage_campaigns():
        return jsonify({'success': False}), 403
    campaign = WhatsAppCampaign.query.get_or_404(id)
    if campaign.status == 'paused':
        campaign.status = 'running'
        db.session.commit()
    return jsonify({'success': True})


@main.route('/campaigns/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_campaign(id):
    if not _can_manage_campaigns():
        return jsonify({'success': False}), 403
    campaign = WhatsAppCampaign.query.get_or_404(id)
    campaign.status = 'cancelled'
    WhatsAppEnrollment.query.filter_by(campaign_id=campaign.id, status='active').update({
        'status': 'stopped', 'stopped_reason': 'manual_cancel',
    })
    db.session.commit()
    return jsonify({'success': True})


@main.route('/campaigns/<int:id>')
@login_required
def campaign_detail(id):
    if not _can_manage_campaigns():
        flash('Access denied.', 'error')
        return redirect(url_for('main.leads'))
    campaign = WhatsAppCampaign.query.get_or_404(id)
    steps = (WhatsAppCampaignStep.query.filter_by(campaign_id=id).order_by(WhatsAppCampaignStep.step_order).all()
             if campaign.campaign_type == 'sequence' else [])
    template = MessageTemplate.query.get(campaign.template_id) if campaign.template_id else None
    step_templates = {s.template_id: MessageTemplate.query.get(s.template_id) for s in steps}
    enrollments = WhatsAppEnrollment.query.filter_by(campaign_id=id).order_by(desc(WhatsAppEnrollment.enrolled_at)).all()
    lead_map = {l.id: l for l in Lead.query.filter(Lead.id.in_([e.lead_id for e in enrollments])).all()} if enrollments else {}
    logs = WhatsAppMessageLog.query.filter_by(campaign_id=id, direction='outbound').order_by(desc(WhatsAppMessageLog.created_at)).limit(200).all()
    return render_template('campaign_detail.html', campaign=campaign, steps=steps, template=template,
                            step_templates=step_templates, enrollments=enrollments, lead_map=lead_map, logs=logs)


@main.route('/leads/bulk-enroll-whatsapp', methods=['POST'])
@login_required
def bulk_enroll_whatsapp():
    if not _can_manage_campaigns():
        return jsonify({'success': False, 'message': 'Access denied.'}), 403
    campaign_id = request.form.get('campaign_id', type=int)
    lead_ids = request.form.getlist('lead_ids[]', type=int)
    campaign = WhatsAppCampaign.query.get_or_404(campaign_id) if campaign_id else None
    if not campaign or campaign.status not in ('running', 'draft'):
        return jsonify({'success': False, 'message': 'Pick an active or draft campaign.'}), 400
    if not lead_ids:
        return jsonify({'success': False, 'message': 'No leads selected.'}), 400
    leads = Lead.query.filter(Lead.id.in_(lead_ids), Lead.whatsapp_opted_out.isnot(True)).all()
    added = _launch_campaign_enrollments(campaign, leads)
    return jsonify({'success': True, 'message': f'{added} lead(s) added to "{campaign.name}".'})


@main.route('/leads/<int:id>/whatsapp-opt-out', methods=['POST'])
@login_required
def set_lead_whatsapp_opt_out(id):
    lead = Lead.query.get_or_404(id)
    _fanout_whatsapp_optout(lead.whatsapp or lead.phone)
    return jsonify({'success': True, 'message': 'Marked as opted out of WhatsApp campaigns.'})
