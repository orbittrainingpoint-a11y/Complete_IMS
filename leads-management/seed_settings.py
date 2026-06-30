"""
Seed script to populate default settings for the CRM system
"""
from app import app, db
from models import Setting

def seed_default_settings():
    """Create default settings for the CRM system"""
    with app.app_context():
        # Lead Sources
        lead_sources = [
            "Website Inquiry",
            "Social Media (Facebook)",
            "Social Media (Instagram)", 
            "Social Media (LinkedIn)",
            "Google Ads",
            "Referral",
            "Walk-in",
            "Phone Call",
            "Email Campaign",
            "Trade Show/Event",
            "Partner/Affiliate",
            "WhatsApp",
            "Cold Call",
            "Direct Mail",
            "Other"
        ]
        
        for source in lead_sources:
            existing = Setting.query.filter_by(key="lead_source", value=source).first()
            if not existing:
                setting = Setting(
                    key="lead_source",
                    value=source,
                    display_name=source,
                    is_active=True,
                    sort_order=lead_sources.index(source)
                )
                db.session.add(setting)
        
        # Lead Statuses
        lead_statuses = [
            ("New", "New lead, not yet contacted"),
            ("Contacted", "Initial contact made"),
            ("Interested", "Showed interest in courses"),
            ("Quoted", "Quote/proposal provided"),
            ("Follow-up", "Requires follow-up"),
            ("Converted", "Successfully enrolled"),
            ("Lost", "Lead lost or not interested"),
            ("On Hold", "Temporarily paused")
        ]
        
        for status, description in lead_statuses:
            existing = Setting.query.filter_by(key="lead_status", value=status).first()
            if not existing:
                setting = Setting(
                    key="lead_status",
                    value=status,
                    display_name=status,
                    description=description,
                    is_active=True,
                    sort_order=lead_statuses.index((status, description))
                )
                db.session.add(setting)
        
        # Follow-up Types
        followup_types = [
            "Phone Call",
            "Email",
            "WhatsApp Message",
            "SMS",
            "In-Person Meeting",
            "Video Call",
            "Site Visit"
        ]
        
        for followup_type in followup_types:
            existing = Setting.query.filter_by(key="followup_type", value=followup_type).first()
            if not existing:
                setting = Setting(
                    key="followup_type",
                    value=followup_type,
                    display_name=followup_type,
                    is_active=True,
                    sort_order=followup_types.index(followup_type)
                )
                db.session.add(setting)
        
        # Priority Levels
        priority_levels = [
            ("Low", "Low priority"),
            ("Medium", "Medium priority"),
            ("High", "High priority"),
            ("Urgent", "Urgent - immediate attention required")
        ]
        
        for priority, description in priority_levels:
            existing = Setting.query.filter_by(key="priority_level", value=priority).first()
            if not existing:
                setting = Setting(
                    key="priority_level",
                    value=priority,
                    display_name=priority,
                    description=description,
                    is_active=True,
                    sort_order=priority_levels.index((priority, description))
                )
                db.session.add(setting)
        
        # Meeting Types
        meeting_types = [
            "Consultation",
            "Course Demo",
            "Follow-up Meeting",
            "Contract Signing",
            "Technical Discussion",
            "Price Negotiation",
            "Course Planning",
            "Progress Review"
        ]
        
        for meeting_type in meeting_types:
            existing = Setting.query.filter_by(key="meeting_type", value=meeting_type).first()
            if not existing:
                setting = Setting(
                    key="meeting_type",
                    value=meeting_type,
                    display_name=meeting_type,
                    is_active=True,
                    sort_order=meeting_types.index(meeting_type)
                )
                db.session.add(setting)
        
        # System Settings
        system_settings = [
            ("company_name", "Training Center", "Company Name"),
            ("company_email", "info@trainingcenter.com", "Company Email"),
            ("company_phone", "+1234567890", "Company Phone"),
            ("company_address", "123 Training Street, Education City", "Company Address"),
            ("default_currency", "USD", "Default Currency"),
            ("timezone", "UTC", "Default Timezone"),
            ("leads_per_page", "20", "Leads Per Page"),
            ("auto_followup_days", "3", "Auto Follow-up Days"),
            ("email_notifications", "true", "Email Notifications Enabled"),
            ("sms_notifications", "false", "SMS Notifications Enabled")
        ]
        
        for key, value, display_name in system_settings:
            existing = Setting.query.filter_by(key=key).first()
            if not existing:
                setting = Setting(
                    key=key,
                    value=value,
                    display_name=display_name,
                    is_active=True
                )
                db.session.add(setting)
        
        try:
            db.session.commit()
            print("✓ Default settings created successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating settings: {str(e)}")

if __name__ == "__main__":
    seed_default_settings()"""
Seed script to populate default settings for the CRM system
"""
from app import app, db
from models import Setting

def seed_default_settings():
    """Create default settings for the CRM system"""
    with app.app_context():
        # Lead Sources
        lead_sources = [
            "Website Inquiry",
            "Social Media (Facebook)",
            "Social Media (Instagram)", 
            "Social Media (LinkedIn)",
            "Google Ads",
            "Referral",
            "Walk-in",
            "Phone Call",
            "Email Campaign",
            "Trade Show/Event",
            "Partner/Affiliate",
            "WhatsApp",
            "Cold Call",
            "Direct Mail",
            "Other"
        ]
        
        for source in lead_sources:
            existing = Setting.query.filter_by(key="lead_source", value=source).first()
            if not existing:
                setting = Setting(
                    key="lead_source",
                    value=source,
                    display_name=source,
                    is_active=True,
                    sort_order=lead_sources.index(source)
                )
                db.session.add(setting)
        
        # Lead Statuses
        lead_statuses = [
            ("New", "New lead, not yet contacted"),
            ("Contacted", "Initial contact made"),
            ("Interested", "Showed interest in courses"),
            ("Quoted", "Quote/proposal provided"),
            ("Follow-up", "Requires follow-up"),
            ("Converted", "Successfully enrolled"),
            ("Lost", "Lead lost or not interested"),
            ("On Hold", "Temporarily paused")
        ]
        
        for status, description in lead_statuses:
            existing = Setting.query.filter_by(key="lead_status", value=status).first()
            if not existing:
                setting = Setting(
                    key="lead_status",
                    value=status,
                    display_name=status,
                    description=description,
                    is_active=True,
                    sort_order=lead_statuses.index((status, description))
                )
                db.session.add(setting)
        
        # Follow-up Types
        followup_types = [
            "Phone Call",
            "Email",
            "WhatsApp Message",
            "SMS",
            "In-Person Meeting",
            "Video Call",
            "Site Visit"
        ]
        
        for followup_type in followup_types:
            existing = Setting.query.filter_by(key="followup_type", value=followup_type).first()
            if not existing:
                setting = Setting(
                    key="followup_type",
                    value=followup_type,
                    display_name=followup_type,
                    is_active=True,
                    sort_order=followup_types.index(followup_type)
                )
                db.session.add(setting)
        
        # Priority Levels
        priority_levels = [
            ("Low", "Low priority"),
            ("Medium", "Medium priority"),
            ("High", "High priority"),
            ("Urgent", "Urgent - immediate attention required")
        ]
        
        for priority, description in priority_levels:
            existing = Setting.query.filter_by(key="priority_level", value=priority).first()
            if not existing:
                setting = Setting(
                    key="priority_level",
                    value=priority,
                    display_name=priority,
                    description=description,
                    is_active=True,
                    sort_order=priority_levels.index((priority, description))
                )
                db.session.add(setting)
        
        # Meeting Types
        meeting_types = [
            "Consultation",
            "Course Demo",
            "Follow-up Meeting",
            "Contract Signing",
            "Technical Discussion",
            "Price Negotiation",
            "Course Planning",
            "Progress Review"
        ]
        
        for meeting_type in meeting_types:
            existing = Setting.query.filter_by(key="meeting_type", value=meeting_type).first()
            if not existing:
                setting = Setting(
                    key="meeting_type",
                    value=meeting_type,
                    display_name=meeting_type,
                    is_active=True,
                    sort_order=meeting_types.index(meeting_type)
                )
                db.session.add(setting)
        
        # System Settings
        system_settings = [
            ("company_name", "Training Center", "Company Name"),
            ("company_email", "info@trainingcenter.com", "Company Email"),
            ("company_phone", "+1234567890", "Company Phone"),
            ("company_address", "123 Training Street, Education City", "Company Address"),
            ("default_currency", "USD", "Default Currency"),
            ("timezone", "UTC", "Default Timezone"),
            ("leads_per_page", "20", "Leads Per Page"),
            ("auto_followup_days", "3", "Auto Follow-up Days"),
            ("email_notifications", "true", "Email Notifications Enabled"),
            ("sms_notifications", "false", "SMS Notifications Enabled")
        ]
        
        for key, value, display_name in system_settings:
            existing = Setting.query.filter_by(key=key).first()
            if not existing:
                setting = Setting(
                    key=key,
                    value=value,
                    display_name=display_name,
                    is_active=True
                )
                db.session.add(setting)
        
        try:
            db.session.commit()
            print("✓ Default settings created successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating settings: {str(e)}")

if __name__ == "__main__":
    seed_default_settings()