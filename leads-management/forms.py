from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FloatField, DateField, IntegerField, BooleanField, PasswordField, HiddenField, TimeField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, ValidationError
from wtforms.widgets import TextArea
from models import Course, User, Setting
import json
from datetime import date

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired()])

class LeadForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    course_interest_id = SelectField('Course Interest', coerce=int, validators=[Optional()])
    lead_source = SelectField('Lead Source', validators=[Optional()])
    status = SelectField('Status', default='New')
    quoted_amount = FloatField('Quoted Amount', validators=[Optional(), NumberRange(min=0)])
    next_followup_date = DateField('Next Follow-up Date', validators=[Optional()])
    followup_type = SelectField('Follow-up Type', validators=[Optional()])
    assigned_to = SelectField('Assigned Consultant', coerce=int, validators=[Optional()])
    comments = TextAreaField('Comments', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(LeadForm, self).__init__(*args, **kwargs)
        # Load choices from database settings
        self.lead_source.choices = Setting.get_choices('lead_source') or [
            ('Website', 'Website'),
            ('Social Media', 'Social Media'),
            ('Referral', 'Referral')
        ]
        self.status.choices = Setting.get_choices('lead_status') or [
            ('New', 'New'),
            ('Contacted', 'Contacted'),
            ('Interested', 'Interested'),
            ('Quoted', 'Quoted'),
            ('Converted', 'Converted'),
            ('Lost', 'Lost')
        ]
        self.followup_type.choices = Setting.get_choices('followup_type') or [
            ('Call', 'Call'),
            ('Email', 'Email'),
            ('WhatsApp', 'WhatsApp')
        ]
        # Load course choices
        self.course_interest_id.choices = [(0, 'Select Course')] + [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]
        # Load consultant users for assignment
        consultants = User.query.filter_by(role='consultant', active=True).all()
        self.assigned_to.choices = [(0, 'Select Consultant')] + [(u.id, u.username) for u in consultants]

class ActivityForm(FlaskForm):
    comment = TextAreaField('Add Activity Comment', validators=[DataRequired()], render_kw={"placeholder": "What happened with this lead?", "rows": "3"})

class CourseForm(FlaskForm):
    name = StringField('Course Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    duration = StringField('Duration', validators=[DataRequired(), Length(max=50)])
    duration_type = SelectField('Duration Type', choices=[
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months')
    ], validators=[DataRequired()])
    category = StringField('Category', validators=[Optional(), Length(max=100)])
    max_students = IntegerField('Max Students', validators=[Optional(), NumberRange(min=1)])
    is_active = BooleanField('Active')
    key_points = TextAreaField('Key Points (JSON)', validators=[Optional()])
    
    def validate_key_points(self, field):
        if field.data:
            try:
                json.loads(field.data)
            except json.JSONDecodeError:
                raise ValidationError('Key Points must be a valid JSON array (e.g., ["point1", "point2"]).')

class MeetingForm(FlaskForm):
    lead_id = SelectField('Lead', coerce=int, validators=[Optional()])
    student_id = SelectField('Student', coerce=int, validators=[Optional()])
    title = StringField('Meeting Title', validators=[DataRequired(), Length(max=200)])
    meeting_type = SelectField('Meeting Type', validators=[DataRequired()])
    meeting_date = DateField('Meeting Date', validators=[DataRequired()])
    meeting_time = TimeField('Meeting Time', validators=[DataRequired()])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired(), NumberRange(min=15, max=480)])
    
    def __init__(self, *args, **kwargs):
        super(MeetingForm, self).__init__(*args, **kwargs)
        # Load choices from database settings
        self.meeting_type.choices = Setting.get_choices('meeting_type') or [
            ('Online', 'Online'),
            ('Offline', 'Offline'),
            ('Phone', 'Phone'),
        ]
    meeting_link = StringField('Meeting Link', validators=[Optional(), Length(max=500)])
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    agenda = TextAreaField('Agenda', validators=[Optional()])
    email_reminder = BooleanField('Send Email Reminder', default=False)
    sms_reminder = BooleanField('Send SMS Reminder', default=False)
    reminder_time = SelectField('Reminder Time', choices=[
        ('', 'Select Reminder Time'),
        ('15', '15 minutes before'),
        ('30', '30 minutes before'),
        ('60', '1 hour before'),
        ('1440', '1 day before')
    ], validators=[Optional()])

# Enhanced Student Form
class StudentForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    country_code = SelectField('Country Code', choices=[
        ('+971', '+971 (UAE)'),
        ('+91', '+91 (India)'),
        ('+966', '+966 (Saudi Arabia)')
    ], default='+971')
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email()])
    course_id = SelectField('Course', coerce=int, validators=[DataRequired()])
    enrollment_date = DateField('Enrollment Date', validators=[Optional()], default=lambda: date.today())
    schedule_days = SelectField('Schedule Days', choices=[
        ('weekdays', 'Weekdays (Mon-Fri)'),
        ('weekends', 'Weekends (Sat-Sun)')
    ], validators=[DataRequired()])
    schedule_time = SelectField('Schedule Time', choices=[
        ('09:00-11:00', '09:00 AM - 11:00 AM'),
        ('11:00-13:00', '11:00 AM - 01:00 PM'),
        ('14:00-16:00', '02:00 PM - 04:00 PM'),
        ('16:00-18:00', '04:00 PM - 06:00 PM'),
        ('18:00-20:00', '06:00 PM - 08:00 PM')
    ], validators=[DataRequired()])
    total_fee = FloatField('Total Fee (AED)', validators=[DataRequired(), NumberRange(min=0)])
    fee_paid = FloatField('Fee Paid (AED)', validators=[Optional(), NumberRange(min=0)], default=0)
    payment_plan = SelectField('Payment Plan', choices=[
        ('Full Payment', 'Full Payment'),
        ('2 Installments', '2 Installments'),
        ('3 Installments', '3 Installments'),
        ('Monthly', 'Monthly Installments')
    ], default='Full Payment')
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    batch_name = StringField('Batch Name', validators=[Optional(), Length(max=100)])


class CorporateTrainingForm(FlaskForm):
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=200)])
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
    contact_person_name = StringField('Contact Person Name', validators=[DataRequired(), Length(max=100)])
    contact_person_email = StringField('Contact Person Email', validators=[DataRequired(), Email(), Length(max=120)])
    contact_person_country_code = SelectField('Contact Country Code', choices=[
        ('+971', '+971 (UAE)'),
        ('+91', '+91 (India)'),
        ('+1', '+1 (US/Canada)'),
        ('+44', '+44 (UK)'),
        ('+92', '+92 (Pakistan)'),
        ('+94', '+94 (Sri Lanka)'),
        ('+880', '+880 (Bangladesh)'),
        ('+966', '+966 (Saudi Arabia)'),
        ('+965', '+965 (Kuwait)'),
        ('+973', '+973 (Bahrain)'),
        ('+974', '+974 (Qatar)'),
        ('+968', '+968 (Oman)')
    ], default='+971')
    contact_person_phone = StringField('Contact Person Phone', validators=[DataRequired(), Length(max=20)])
    industry = StringField('Industry', validators=[Optional(), Length(max=100)])
    company_size = SelectField('Company Size', choices=[
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-500', '201-500 employees'),
        ('500+', '500+ employees')
    ], validators=[Optional()])
    course_names = SelectField('Course Names (Multiple)', coerce=str, validators=[Optional()])
    trainee_count = IntegerField('Number of Trainees', validators=[DataRequired(), NumberRange(min=1)])
    training_mode = SelectField('Training Mode', choices=[
        ('Onsite', 'Onsite'),
        ('Online', 'Online'),
        ('Hybrid', 'Hybrid')
    ], validators=[DataRequired()])
    quotation_amount = FloatField('Quotation Amount', validators=[Optional(), NumberRange(min=0)])
    expected_start_date = DateField('Expected Start Date', validators=[Optional()])
    budget_range = StringField('Budget Range', validators=[Optional(), Length(max=50)])
    special_requirements = TextAreaField('Special Requirements', validators=[Optional()])

# Message Template Form
class MessageTemplateForm(FlaskForm):
    name = StringField('Template Name', validators=[DataRequired(), Length(max=100)])
    category = SelectField('Category', choices=[
        ('Lead Follow-up', 'Lead Follow-up'),
        ('Course Information', 'Course Information'),
        ('Payment Reminder', 'Payment Reminder'),
        ('Welcome Message', 'Welcome Message'),
        ('Course Completion', 'Course Completion'),
        ('Corporate Training', 'Corporate Training')
    ], validators=[DataRequired()])
    subject = StringField('Subject', validators=[Optional(), Length(max=200)], 
                         description='For Email messages only')
    content = TextAreaField('Message Content', validators=[DataRequired()], 
                           description='Use variables: {name}, {phone}, {email}, {course_name}, {company_name}')
    message_type = SelectField('Message Type', choices=[
        ('SMS', 'SMS'),
        ('WhatsApp', 'WhatsApp'),
        ('Email', 'Email')
    ], default='SMS', validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)

class SendMessageForm(FlaskForm):
    template_id = SelectField('Message Template', coerce=int, validators=[DataRequired()])
    lead_ids = SelectField('Select Leads', coerce=str, validators=[Optional()])
    course_id = SelectField('Course', coerce=int, validators=[Optional()])
    custom_variables = TextAreaField('Custom Variables (JSON)', validators=[Optional()])

class SettingsForm(FlaskForm):
    # Company Settings
    company_name = StringField('Company Name', validators=[Optional(), Length(max=200)])
    company_email = StringField('Company Email', validators=[Optional(), Email(), Length(max=120)])
    company_phone = StringField('Company Phone', validators=[Optional(), Length(max=20)])
    company_address = TextAreaField('Company Address', validators=[Optional()])
    
    # Email Settings
    mail_server = StringField('Mail Server', validators=[Optional(), Length(max=100)])
    mail_port = IntegerField('Mail Port', validators=[Optional(), NumberRange(min=1, max=65535)])
    mail_username = StringField('Mail Username', validators=[Optional(), Email(), Length(max=120)])
    mail_password = PasswordField('Mail Password', validators=[Optional()])
    mail_use_tls = BooleanField('Use TLS', default=True)
    
    # Payment Gateway Settings
    vault_api_key = StringField('Vault Pay API Key', validators=[Optional(), Length(max=200)])
    vault_secret_key = StringField('Vault Pay Secret Key', validators=[Optional(), Length(max=200)])
    tabby_public_key = StringField('Tabby Public Key', validators=[Optional(), Length(max=200)])
    tabby_secret_key = StringField('Tabby Secret Key', validators=[Optional(), Length(max=200)])
    tamara_api_key = StringField('Tamara API Key', validators=[Optional(), Length(max=200)])

class SettingForm(FlaskForm):
    key = StringField('Setting Key', validators=[DataRequired(), Length(max=100)])
    value = StringField('Setting Value', validators=[DataRequired(), Length(max=500)])
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    sort_order = IntegerField('Sort Order', validators=[Optional(), NumberRange(min=0)], default=0)

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[Optional()])
    role = SelectField('Role', choices=[
        ('consultant', 'Consultant'),
        ('sales_manager', 'Sales Manager'),
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin')
    ], validators=[DataRequired()])
    active = BooleanField('Active', default=True)
    can_view_all_leads = BooleanField('Can View All Leads', default=False)
    can_manage_users = BooleanField('Can Manage Users', default=False)
    can_view_reports = BooleanField('Can View Reports', default=False)
    can_manage_courses = BooleanField('Can Manage Courses', default=False)
    can_manage_settings = BooleanField('Can Manage Settings', default=False)
    
    def validate_confirm_password(self, field):
        if self.password.data and field.data != self.password.data:
            raise ValidationError('Passwords must match.')

class BulkAssignForm(FlaskForm):
    selected_leads = HiddenField('Selected Leads')
    assigned_to = SelectField('Assign to Consultant', coerce=int, validators=[DataRequired()])
    
    def __init__(self, *args, **kwargs):
        super(BulkAssignForm, self).__init__(*args, **kwargs)
        from models import User
        consultants = User.query.filter_by(role='consultant', active=True).all()
        self.assigned_to.choices = [(u.id, u.username) for u in consultants]


# Payment Forms
class PaymentProviderForm(FlaskForm):
    name = SelectField("Payment Provider", choices=[
        ("Vault", "Vault Pay"),
        ("Tabby", "Tabby"),
        ("Tamara", "Tamara")
    ], validators=[DataRequired()])
    api_key = StringField("API Key", validators=[DataRequired(), Length(max=500)])
    api_secret = StringField("API Secret/Private Key", validators=[DataRequired(), Length(max=500)])
    environment = SelectField("Environment", choices=[
        ("sandbox", "Sandbox/Testing"),
        ("production", "Production/Live")
    ], default="sandbox", validators=[DataRequired()])
    webhook_url = StringField("Webhook URL", validators=[Optional(), Length(max=500)])
    is_active = BooleanField("Active", default=True)

class PaymentLinkForm(FlaskForm):
    lead_id = SelectField("Lead", coerce=int, validators=[Optional()])
    student_id = SelectField("Student", coerce=int, validators=[Optional()])
    provider_id = SelectField("Payment Provider", coerce=int, validators=[DataRequired()])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    currency = SelectField("Currency", choices=[
        ("AED", "AED"),
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("SAR", "SAR")
    ], default="AED", validators=[DataRequired()])
    description = StringField("Payment Description", validators=[DataRequired(), Length(max=500)])
    expires_in_days = IntegerField("Expires in (days)", validators=[DataRequired(), NumberRange(min=1, max=365)], default=7)

# User Management Forms
class SystemSettingsForm(FlaskForm):
    # Company Information
    company_name = StringField('Company Name', validators=[Optional(), Length(max=200)])
    company_email = StringField('Company Email', validators=[Optional(), Email(), Length(max=120)])
    company_phone = StringField('Company Phone', validators=[Optional(), Length(max=20)])
    company_address = TextAreaField('Company Address', validators=[Optional()])
    
    # Email Configuration
    smtp_server = StringField('SMTP Server', validators=[Optional(), Length(max=100)])
    smtp_port = IntegerField('SMTP Port', validators=[Optional(), NumberRange(min=1, max=65535)], default=587)
    smtp_username = StringField('SMTP Username', validators=[Optional(), Email(), Length(max=120)])
    smtp_password = PasswordField('SMTP Password', validators=[Optional()])
    smtp_use_tls = BooleanField('Use TLS', default=True)
    
    # Default Settings
    default_currency = SelectField('Default Currency', choices=[
        ('AED', 'AED'), ('USD', 'USD'), ('EUR', 'EUR'), ('SAR', 'SAR')
    ], default='AED')
    timezone = SelectField('Timezone', choices=[
        ('UTC', 'UTC'),
        ('Asia/Dubai', 'Asia/Dubai'),
        ('America/New_York', 'America/New_York')
    ], default='Asia/Dubai')
    leads_per_page = IntegerField('Leads Per Page', validators=[Optional(), NumberRange(min=1, max=100)], default=20)
    auto_assign_leads = BooleanField('Auto Assign Leads', default=False)
    enable_email_notifications = BooleanField('Enable Email Notifications', default=True)
    session_timeout = IntegerField('Session Timeout (minutes)', validators=[Optional(), NumberRange(min=5, max=1440)], default=60)
    auto_followup_days = IntegerField('Auto Follow-up Days', validators=[DataRequired(), NumberRange(min=1, max=30)])
    email_notifications = BooleanField('Enable Email Notifications', default=True)
    sms_notifications = BooleanField('Enable SMS Notifications', default=False)

# Student and Trainer Management Forms
class LegacyStudentForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=20)])
    course_id = SelectField('Course', coerce=int, validators=[Optional()])
    enrollment_date = DateField('Enrollment Date', validators=[Optional()], default=lambda: date.today())
    payment_status = SelectField('Payment Status', choices=[
        ('Pending', 'Pending'),
        ('Partial', 'Partial'),
        ('Paid', 'Paid')
    ], default='Pending', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    
    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        from models import Course
        courses = Course.query.filter_by(is_active=True).all()
        self.course_id.choices = [(0, 'Select Course')] + [(c.id, c.name) for c in courses]

class TrainerForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    specialization = StringField('Specialization', validators=[Optional(), Length(max=200)])
    hourly_rate = FloatField('Hourly Rate', validators=[Optional(), NumberRange(min=0)])
    bio = TextAreaField('Bio', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    
    # Availability fields
    monday_start = TimeField('Monday Start', validators=[Optional()])
    monday_end = TimeField('Monday End', validators=[Optional()])
    tuesday_start = TimeField('Tuesday Start', validators=[Optional()])
    tuesday_end = TimeField('Tuesday End', validators=[Optional()])
    wednesday_start = TimeField('Wednesday Start', validators=[Optional()])
    wednesday_end = TimeField('Wednesday End', validators=[Optional()])
    thursday_start = TimeField('Thursday Start', validators=[Optional()])
    thursday_end = TimeField('Thursday End', validators=[Optional()])
    friday_start = TimeField('Friday Start', validators=[Optional()])
    friday_end = TimeField('Friday End', validators=[Optional()])
    saturday_start = TimeField('Saturday Start', validators=[Optional()])
    saturday_end = TimeField('Saturday End', validators=[Optional()])
    sunday_start = TimeField('Sunday Start', validators=[Optional()])
    sunday_end = TimeField('Sunday End', validators=[Optional()])

class ScheduleForm(FlaskForm):
    trainer_id = SelectField('Trainer', coerce=int, validators=[DataRequired()])
    course_id = SelectField('Course', coerce=int, validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    student_ids = SelectMultipleField('Students', coerce=int, validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)
        from models import Trainer, Course, Student
        
        trainers = Trainer.query.filter_by(is_active=True).all()
        self.trainer_id.choices = [(t.id, t.name) for t in trainers]
        
        courses = Course.query.filter_by(is_active=True).all()
        self.course_id.choices = [(c.id, c.name) for c in courses]
        
        students = Student.query.filter_by(is_active=True).all()
        self.student_ids.choices = [(s.id, s.name) for s in students]

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField('Role', choices=[
        ('consultant', 'Consultant'),
        ('sales_manager', 'Sales Manager'),
        ('admin', 'Admin'),
        ('superadmin', 'Super Admin')
    ], validators=[DataRequired()])
    active = BooleanField('Active', default=True)
    
    # Permissions for superadmin role
    can_view_all_leads = BooleanField('Can View All Leads', default=False)
    can_manage_users = BooleanField('Can Manage Users', default=False)
    can_view_reports = BooleanField('Can View Reports', default=False)
    can_manage_courses = BooleanField('Can Manage Courses', default=False)
    can_manage_settings = BooleanField('Can Manage Settings', default=False)

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired()])

# Lead Detail and Interaction Forms
class LeadQuoteForm(FlaskForm):
    course_id = SelectField('Course', coerce=int, validators=[DataRequired()])
    quoted_amount = FloatField('Quote Amount', validators=[DataRequired(), NumberRange(min=0)])
    currency = SelectField('Currency', choices=[
        ('AED', 'AED'),
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('SAR', 'SAR')
    ], default='AED')
    valid_until = DateField('Valid Until', validators=[DataRequired()])
    quote_notes = TextAreaField('Quote Notes', validators=[Optional()])

class LeadInteractionForm(FlaskForm):
    interaction_type = SelectField('Type', choices=[
        ('Call', 'Phone Call'),
        ('Email', 'Email'),
        ('WhatsApp', 'WhatsApp'),
        ('Meeting', 'In-Person Meeting'),
        ('SMS', 'SMS'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    interaction_date = DateField('Date', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[DataRequired(), Length(min=10, max=1000)])
    outcome = SelectField('Outcome', choices=[
        ('Positive', 'Positive'),
        ('Neutral', 'Neutral'),
        ('Negative', 'Negative'),
        ('No Response', 'No Response'),
        ('Follow-up Needed', 'Follow-up Needed')
    ])

class LeadFollowupForm(FlaskForm):
    followup_date = DateField('Follow-up Date', validators=[DataRequired()])
    followup_time = TimeField('Follow-up Time', validators=[DataRequired()])
    followup_type = SelectField('Follow-up Type', choices=[
        ('Call', 'Phone Call'),
        ('Email', 'Email'),
        ('WhatsApp', 'WhatsApp'),
        ('Meeting', 'Meeting'),
        ('SMS', 'SMS')
    ], validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent')
    ], default='Medium', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])

# Trainer Management Forms
class TrainerForm(FlaskForm):
    name = StringField('Trainer Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    specialization = StringField('Specialization', validators=[Optional(), Length(max=200)])
    course_ids = SelectMultipleField('Courses', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    
    def __init__(self, *args, **kwargs):
        super(TrainerForm, self).__init__(*args, **kwargs)
        from models import Course
        self.course_ids.choices = [(c.id, c.name) for c in Course.query.filter_by(is_active=True).all()]

class ClassScheduleForm(FlaskForm):
    trainer_id = SelectField('Trainer', coerce=int, validators=[DataRequired()])
    course_id = SelectField('Course', coerce=int, validators=[DataRequired()])
    class_date = DateField('Class Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    duration_minutes = SelectField('Duration', choices=[
        (30, '30 minutes'),
        (60, '1 hour'),
        (90, '1.5 hours'),
        (120, '2 hours'),
        (150, '2.5 hours'),
        (180, '3 hours')
    ], coerce=int, default=60, validators=[DataRequired()])
    student_ids = SelectMultipleField('Students', coerce=int, validators=[Optional()])
    class_type = SelectField('Class Type', choices=[
        ('Regular', 'Regular Class'),
        ('Makeup', 'Makeup Class'),
        ('Extra', 'Extra Session'),
        ('Assessment', 'Assessment'),
        ('Review', 'Review Session')
    ], default='Regular')
    location = StringField('Location/Room', validators=[Optional(), Length(max=100)])
    online_link = StringField('Online Meeting Link', validators=[Optional(), Length(max=500)])
    notes = TextAreaField('Notes', validators=[Optional()])

class PaymentSettingsForm(FlaskForm):
    company_name = StringField("Company Name", validators=[DataRequired(), Length(max=200)])
    company_email = StringField("Company Email", validators=[DataRequired(), Email(), Length(max=120)])
    company_phone = StringField("Company Phone", validators=[DataRequired(), Length(max=20)])
    company_address = TextAreaField("Company Address", validators=[Optional()])
    tax_registration_number = StringField("Tax Registration Number", validators=[Optional(), Length(max=50)])
    payment_terms = TextAreaField("Payment Terms", validators=[Optional()])
    invoice_notes = TextAreaField("Default Invoice Notes", validators=[Optional()])
    default_currency = SelectField("Default Currency", choices=[
        ("AED", "AED (UAE Dirham)"),
        ("USD", "USD (US Dollar)"),
        ("EUR", "EUR (Euro)"),
        ("SAR", "SAR (Saudi Riyal)")
    ], default="AED", validators=[DataRequired()])
    auto_send_receipts = BooleanField("Auto Send Payment Receipts", default=True)
    payment_reminder_enabled = BooleanField("Enable Payment Reminders", default=True)
    payment_reminder_days = IntegerField("Send Reminder Before (days)", 
                                       validators=[Optional(), NumberRange(min=1, max=30)], default=3)

