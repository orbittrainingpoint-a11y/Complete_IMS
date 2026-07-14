from extensions import db
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func


class LoginLog(db.Model):
    """Records every login attempt with IP, user-agent, and outcome."""
    __tablename__ = 'login_log'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, nullable=True)   # no FK to avoid MySQL reserved-word clash
    username_try = db.Column(db.String(64))
    ip_address   = db.Column(db.String(45))
    user_agent   = db.Column(db.String(300))
    status       = db.Column(db.String(10), default='success')  # success / failed
    login_at     = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='consultant')  # super_admin, admin, consultant
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Role-based permissions
    can_view_all_leads = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)
    can_view_reports = db.Column(db.Boolean, default=False)
    can_manage_courses = db.Column(db.Boolean, default=False)
    can_manage_settings = db.Column(db.Boolean, default=False)
    
    # Relationships
    created_by = db.relationship('User', remote_side=[id], backref='created_users')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_admin(self):
        return self.role in ['admin', 'super_admin']

    def is_sales_manager(self):
        return self.role == 'sales_manager'
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_consultant(self):
        return self.role == 'consultant'
    
    def can_view_lead(self, lead):
        """Check if user can view a specific lead"""
        if self.is_admin() or self.can_view_all_leads:
            return True
        return lead.created_by_id == self.id

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    whatsapp = db.Column(db.String(20))
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    email = db.Column(db.String(120))
    course_interest_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    lead_source = db.Column(db.String(50))
    status = db.Column(db.String(20), default='New')  # New, Contacted, Interested, Quoted, Converted, Lost
    quoted_amount = db.Column(db.Float, default=0.0)
    last_contact_date = db.Column(db.Date)
    next_followup_date = db.Column(db.Date)
    followup_time = db.Column(db.Time)  # New field for time
    followup_type = db.Column(db.String(20))  # Call, Email, WhatsApp, Meeting
    followup_priority = db.Column(db.String(20))  # Low, Medium, High, Urgent
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    course_interest = db.relationship('Course', backref='interested_leads')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_leads')
    assigned_consultant = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_leads')
    added_by_user = db.relationship('User', foreign_keys=[added_by], backref='added_leads')
    interactions = db.relationship('LeadInteraction', backref='lead', lazy='dynamic')
    
    @classmethod
    def check_duplicate(cls, phone, whatsapp=None, exclude_id=None):
        """Check if a lead with same phone or WhatsApp already exists"""
        query = cls.query
        if exclude_id:
            query = query.filter(cls.id != exclude_id)
        
        # Check for phone or WhatsApp duplicates
        conditions = [cls.phone == phone]
        if whatsapp:
            conditions.extend([cls.whatsapp == whatsapp, cls.phone == whatsapp, cls.whatsapp == phone])
        
        duplicate_lead = query.filter(db.or_(*conditions)).first()
        if duplicate_lead:
            return duplicate_lead
        return None
        phone_exists = query.filter(cls.phone == phone).first()
        if phone_exists:
            return phone_exists
        
        # Check for email duplicates if email provided
        if email:
            email_exists = query.filter(cls.email == email).first()
            if email_exists:
                return email_exists
        
        return None
    
    @classmethod
    def get_user_pipeline_data(cls, user_id):
        """Get pipeline statistics for a specific user"""
        user_leads = cls.query.filter_by(added_by=user_id)
        
        pipeline_data = {}
        statuses = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted', 'Lost']
        
        for status in statuses:
            count = user_leads.filter_by(status=status).count()
            pipeline_data[status] = count
        
        return pipeline_data
    
    @classmethod
    def get_user_leads(cls, user_id, status=None, search=None, course_filter=None):
        """Get leads for a specific user with optional filters"""
        query = cls.query.filter_by(added_by=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if search:
            query = query.filter(
                db.or_(
                    cls.name.ilike(f'%{search}%'),
                    cls.phone.ilike(f'%{search}%'),
                    cls.email.ilike(f'%{search}%')
                )
            )
        
        if course_filter:
            query = query.filter_by(course_interest_id=course_filter)
        
        return query
    
    def __repr__(self):
        return f'<Lead {self.name}>'

class LeadInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)  # Call, Email, WhatsApp, Meeting, Note
    content = db.Column(db.Text)
    interaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_important = db.Column(db.Boolean, default=False)
    
    created_by = db.relationship('User', backref='interactions')



class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.String(50))  # e.g., "3 months", "6 weeks"
    duration_type = db.Column(db.String(20))  # weeks, months, days
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    max_students = db.Column(db.Integer, default=20)
    key_points = db.Column(db.Text)  # JSON string of key points
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    students = db.relationship('Student', backref='course')
    # Removed: corporate_trainings = db.relationship('CorporateTraining', backref='course')
    
    def __repr__(self):
        return f'<Course {self.name}>'

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    title = db.Column(db.String(200), nullable=False)
    meeting_type = db.Column(db.String(20), nullable=False)  # Online, Offline
    meeting_date = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, default=60)  # minutes
    status = db.Column(db.String(20), default='Scheduled')  # Scheduled, Completed, Cancelled, No Show
    meeting_link = db.Column(db.String(500))  # For online meetings
    location = db.Column(db.String(200))  # For offline meetings
    agenda = db.Column(db.Text)
    notes = db.Column(db.Text)
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    email_reminder = db.Column(db.Boolean, default=False, nullable=False)
    sms_reminder = db.Column(db.Boolean, default=False, nullable=False)
    reminder_time = db.Column(db.Integer, nullable=True)  # Minutes before meeting
    
    # Relationships
    lead = db.relationship('Lead', backref='meetings')
    student = db.relationship('Student', backref='meetings')
    created_by = db.relationship('User', backref='created_meetings')

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'))  # Original lead if converted
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    country_code = db.Column(db.String(5), default='+971')
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    schedule_days = db.Column(db.Text)  # JSON array of selected days
    schedule_time = db.Column(db.String(20))  # Time slot
    enrollment_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), default='Active')  # Active, Completed, Dropped, Suspended
    fee_paid = db.Column(db.Float, default=0.0)
    total_fee = db.Column(db.Float, nullable=False)
    payment_plan = db.Column(db.String(50))  # Full, Installments
    progress_percentage = db.Column(db.Float, default=0.0)
    batch_name = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    
    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"
    
    # Relationships
    original_lead = db.relationship('Lead', backref='converted_student')
    attendance_records = db.relationship('AttendanceRecord', backref='student')
    
    def __repr__(self):
        return f'<Student {self.name}>'

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Present, Absent, Late
    notes = db.Column(db.Text)

class CorporateTraining(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    contact_person_name = db.Column(db.String(100), nullable=False)
    contact_person_email = db.Column(db.String(120), nullable=False)
    contact_person_country_code = db.Column(db.String(5), default='+971')
    contact_person_phone = db.Column(db.String(20), nullable=False)
    industry = db.Column(db.String(100))
    company_size = db.Column(db.String(50))
    course_names = db.Column(db.Text)  # JSON array of course IDs for multiple courses
    trainee_count = db.Column(db.Integer, nullable=False)
    training_mode = db.Column(db.String(20))  # Onsite, Online, Hybrid
    quotation_amount = db.Column(db.Float, default=0.0)
    expected_start_date = db.Column(db.Date)
    budget_range = db.Column(db.String(50))
    special_requirements = db.Column(db.Text)
    status = db.Column(db.String(20), default='Inquiry')  # Inquiry, Proposal, Negotiation, Confirmed, Completed
    deal_value = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    created_by = db.relationship('User', backref='corporate_leads')

class MessageTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # Welcome, Follow-up, Reminder, etc.
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20))  # Email, SMS, WhatsApp
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    setting_type = db.Column(db.String(20))  # string, number, boolean, json
    description = db.Column(db.String(200))

# Lead Quote Models

class LeadQuote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    quoted_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='AED')
    valid_until = db.Column(db.Date, nullable=False)
    quote_notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='Active')  # Active, Accepted, Rejected, Expired
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    lead = db.relationship('Lead', backref='quotes')
    course = db.relationship('Course', backref='quotes')
    created_by = db.relationship('User', backref='created_quotes')

# Trainer Management Models  
class Trainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    specialization = db.Column(db.String(200))
    hourly_rate = db.Column(db.Float)
    bio = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Weekly availability
    monday_start = db.Column(db.Time)
    monday_end = db.Column(db.Time)
    tuesday_start = db.Column(db.Time)
    tuesday_end = db.Column(db.Time)
    wednesday_start = db.Column(db.Time)
    wednesday_end = db.Column(db.Time)
    thursday_start = db.Column(db.Time)
    thursday_end = db.Column(db.Time)
    friday_start = db.Column(db.Time)
    friday_end = db.Column(db.Time)
    saturday_start = db.Column(db.Time)
    saturday_end = db.Column(db.Time)
    sunday_start = db.Column(db.Time)
    sunday_end = db.Column(db.Time)
    
    # Relationships
    trainer_courses = db.relationship('TrainerCourse', backref='trainer', cascade='all, delete-orphan')
    class_schedules = db.relationship('ClassSchedule', backref='trainer')
    
    @property
    def courses(self):
        return [tc.course for tc in self.trainer_courses]
    
    def get_availability_for_day(self, day_name):
        """Get availability for a specific day"""
        start_attr = f"{day_name.lower()}_start"
        end_attr = f"{day_name.lower()}_end"
        start_time = getattr(self, start_attr)
        end_time = getattr(self, end_attr)
        return (start_time, end_time) if start_time and end_time else None

class TrainerCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainer.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Relationships
    course = db.relationship('Course', backref='trainer_courses')

class ClassSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainer.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    class_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    class_type = db.Column(db.String(20), default='Regular')
    location = db.Column(db.String(100))
    online_link = db.Column(db.String(500))
    notes = db.Column(db.Text)
    is_cancelled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    course = db.relationship('Course', backref='class_schedules')
    class_students = db.relationship('ClassStudent', backref='class_schedule', cascade='all, delete-orphan')
    
    @property
    def end_time(self):
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(date.today(), self.start_time)
        end_datetime = start_datetime + timedelta(minutes=self.duration_minutes)
        return end_datetime.time()
    
    @property
    def students(self):
        return [cs.student for cs in self.class_students.all()]

class ClassStudent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_schedule_id = db.Column(db.Integer, db.ForeignKey('class_schedule.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    attendance_status = db.Column(db.String(20), default='Scheduled')  # Scheduled, Present, Absent, Late
    
    # Relationships
    student = db.relationship('Student', backref='class_enrollments')

# Payment Models
class PaymentProvider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Vault, Tabby, Tamara
    is_active = db.Column(db.Boolean, default=True)
    api_key = db.Column(db.String(500))
    api_secret = db.Column(db.String(500))
    environment = db.Column(db.String(20), default='sandbox')  # sandbox, production
    webhook_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentProvider {self.name}>'

class PaymentLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('payment_provider.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), default='AED')
    description = db.Column(db.String(500))
    payment_url = db.Column(db.String(1000))
    payment_reference = db.Column(db.String(200), unique=True)
    status = db.Column(db.String(20), default='pending')  # pending, paid, failed, expired, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    webhook_data = db.Column(db.Text)  # JSON data from payment provider
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    lead = db.relationship('Lead', backref='payment_links')
    student = db.relationship('Student', backref='payment_links')
    provider = db.relationship('PaymentProvider', backref='payment_links')
    created_by = db.relationship('User', backref='created_payment_links')
    
    def __repr__(self):
        return f'<PaymentLink {self.payment_reference}>'

class PaymentSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    company_email = db.Column(db.String(120), nullable=False)
    company_phone = db.Column(db.String(20), nullable=False)
    company_address = db.Column(db.Text)
    tax_registration_number = db.Column(db.String(50))
    payment_terms = db.Column(db.Text)
    invoice_notes = db.Column(db.Text)
    default_currency = db.Column(db.String(5), default='AED')
    auto_send_receipts = db.Column(db.Boolean, default=True)
    payment_reminder_enabled = db.Column(db.Boolean, default=True)
    payment_reminder_days = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Text, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # __table_args__ = (db.Index('idx_key_value', 'key', db.text('value(150)')),)  # Commented out for SQLite compatibility
    
    @classmethod
    def get_by_key(cls, key):
        return cls.query.filter_by(key=key, is_active=True).order_by(cls.sort_order).all()
    
    @classmethod
    def get_single_value(cls, key, default=None):
        setting = cls.query.filter_by(key=key, is_active=True).first()
        return setting.value if setting else default
    
    @classmethod
    def get_choices(cls, key):
        settings = cls.get_by_key(key)
        return [(s.value, s.display_name) for s in settings]
    
    @classmethod
    def get_system_settings(cls):
        """Get all system settings as a dictionary"""
        settings = cls.query.filter(cls.key.like('system_%')).all()
        return {s.key: s.value for s in settings}
    
    def __repr__(self):
        return f'<Setting {self.key}: {self.value}>'


class LeadReassignment(db.Model):
    __tablename__ = 'lead_reassignment'
    id             = db.Column(db.Integer, primary_key=True)
    lead_id        = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    from_user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    to_user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_at    = db.Column(db.DateTime, default=datetime.utcnow)
    note           = db.Column(db.String(500))

    lead        = db.relationship('Lead', backref='reassignments')
    from_user   = db.relationship('User', foreign_keys=[from_user_id],   backref='leads_taken_from')
    to_user     = db.relationship('User', foreign_keys=[to_user_id],     backref='leads_received')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id], backref='reassignments_made')


class CRMNotification(db.Model):
    __tablename__ = 'crm_notification'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message    = db.Column(db.String(500), nullable=False)
    lead_id    = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    notif_type = db.Column(db.String(30), default='reassignment')
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='crm_notifications')
    lead = db.relationship('Lead', backref='crm_notifications')


class ImsStudent(db.Model):
    """Synced from Orbit ERP (orbit_invoice.invoices_registration) — never edited directly in CRM."""
    __tablename__ = 'ims_student'

    id                    = db.Column(db.Integer, primary_key=True)
    ims_registration_id   = db.Column(db.Integer, unique=True, nullable=False)
    registration_number   = db.Column(db.String(20))
    first_name            = db.Column(db.String(100), nullable=False)
    last_name             = db.Column(db.String(100), default='')
    phone                 = db.Column(db.String(30))
    email                 = db.Column(db.String(120))
    country               = db.Column(db.String(100))
    student_status        = db.Column(db.String(20), default='active')
    registration_date     = db.Column(db.Date)
    registration_type     = db.Column(db.String(5), default='OT')
    class_type            = db.Column(db.String(20))
    courses_json          = db.Column(db.Text)           # JSON list of course names
    total_fee             = db.Column(db.Numeric(12, 2), default=0)
    consultant_name       = db.Column(db.String(150))    # free-text from IMS
    consultant_username   = db.Column(db.String(64))     # matched CRM username
    lead_crm_id           = db.Column(db.Integer)        # FK to CRM lead.id if converted
    synced_at             = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at            = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def courses(self):
        import json
        try:
            return json.loads(self.courses_json or '[]')
        except Exception:
            return []

    @property
    def status_color(self):
        return {
            'active': 'green', 'completed': 'blue',
            'dropped': 'red', 'suspended': 'orange', 'pending': 'gray',
        }.get(self.student_status, 'gray')

    def __repr__(self):
        return f'<ImsStudent {self.registration_number} {self.name}>'

