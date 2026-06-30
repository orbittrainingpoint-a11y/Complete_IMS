"""
Utility functions for Training Center CRM
"""
import json
import os
import re
import uuid
from datetime import datetime, date, timedelta
from flask import current_app
import logging
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def generate_slug(text):
    """Generate a URL-friendly slug from text"""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[-\s]+', '-', text)
    return text

def format_currency(amount):
    """Format amount as currency"""
    if amount is None:
        return "AED 0.00"
    return f"AED{amount:,.2f}"

def format_phone(phone):
    """Format phone number for display"""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Format as (XXX) XXX-XXXX if 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    return phone

def calculate_conversion_rate(total_leads, converted_leads):
    """Calculate conversion rate percentage"""
    if total_leads == 0:
        return 0
    return round((converted_leads / total_leads) * 100, 2)

def get_lead_status_color(status):
    """Get Bootstrap color class for lead status"""
    status_colors = {
        'New': 'primary',
        'Contacted': 'warning', 
        'Interested': 'info',
        'Quoted': 'secondary',
        'Converted': 'success',
        'Lost': 'danger'
    }
    return status_colors.get(status, 'secondary')

def get_meeting_status_color(status):
    """Get Bootstrap color class for meeting status"""
    status_colors = {
        'Scheduled': 'primary',
        'Completed': 'success',
        'Cancelled': 'danger',
        'No Show': 'warning'
    }
    return status_colors.get(status, 'secondary')

def allowed_file(filename, allowed_extensions=None):
    """Check if file has allowed extension"""
    if allowed_extensions is None:
        allowed_extensions = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'gif'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder='uploads'):
    """Save uploaded file and return filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid filename conflicts
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{int(datetime.now().timestamp())}{ext}"
        
        # Ensure upload directory exists
        upload_path = os.path.join(current_app.instance_path, upload_folder)
        os.makedirs(upload_path, exist_ok=True)
        
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        return filename
    return None

def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return None
    
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def get_next_business_day(start_date=None, days_ahead=1):
    """Get next business day (Monday-Friday)"""
    if start_date is None:
        start_date = date.today()
    
    next_day = start_date + timedelta(days=days_ahead)
    
    # If it's weekend, move to Monday
    while next_day.weekday() > 4:  # 5 = Saturday, 6 = Sunday
        next_day += timedelta(days=1)
    
    return next_day

def send_email(to_email, subject, body, html_body=None):
    """Send email using configured SMTP settings"""
    try:
        from app import mail
        from flask_mail import Message
        
        msg = Message(
            subject=subject,
            recipients=[to_email],
            body=body,
            html=html_body
        )
        
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False

def generate_invoice_number():
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:8].upper()
    return f"INV-{timestamp}-{random_suffix}"

def validate_email(email):
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    # Check if it's 10 digits (US format)
    return len(digits) == 10

def calculate_bulk_discount(base_price, quantity, discount_tiers=None):
    """Calculate bulk discount based on quantity"""
    if discount_tiers is None:
        discount_tiers = [
            (10, 0.05),   # 5% discount for 10+ students
            (20, 0.10),   # 10% discount for 20+ students
            (50, 0.15),   # 15% discount for 50+ students
            (100, 0.20),  # 20% discount for 100+ students
        ]
    
    discount_rate = 0
    for min_qty, rate in sorted(discount_tiers, reverse=True):
        if quantity >= min_qty:
            discount_rate = rate
            break
    
    total_price = base_price * quantity
    discount_amount = total_price * discount_rate
    final_price = total_price - discount_amount
    
    return {
        'original_price': total_price,
        'discount_rate': discount_rate,
        'discount_amount': discount_amount,
        'final_price': final_price
    }

def get_financial_year_dates(year=None):
    """Get financial year start and end dates"""
    if year is None:
        year = date.today().year
    
    # Assuming financial year starts April 1st
    start_date = date(year, 4, 1)
    end_date = date(year + 1, 3, 31)
    
    return start_date, end_date

def format_duration(duration_value, duration_type):
    """Format duration for display"""
    if not duration_value or not duration_type:
        return ""
    
    duration_map = {
        'days': 'day' if duration_value == 1 else 'days',
        'weeks': 'week' if duration_value == 1 else 'weeks',
        'months': 'month' if duration_value == 1 else 'months'
    }
    
    unit = duration_map.get(duration_type, duration_type)
    return f"{duration_value} {unit}"

def create_notification(user_id, title, message, notification_type='info'):
    """Create a notification for a user"""
    # This would typically save to a notifications table
    # For now, we'll just log it
    current_app.logger.info(f"Notification for user {user_id}: {title} - {message}")
    return True

def get_time_greeting():
    """Get appropriate greeting based on current time"""
    current_hour = datetime.now().hour
    
    if 5 <= current_hour < 12:
        return "Good morning"
    elif 12 <= current_hour < 17:
        return "Good afternoon"
    elif 17 <= current_hour < 22:
        return "Good evening"
    else:
        return "Good night"

def truncate_text(text, max_length=50, suffix="..."):
    """Truncate text to specified length"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def get_progress_color(percentage):
    """Get color class based on progress percentage"""
    if percentage >= 80:
        return 'success'
    elif percentage >= 60:
        return 'info'
    elif percentage >= 40:
        return 'warning'
    else:
        return 'danger'

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def generate_student_id():
    """Generate unique student ID"""
    year = datetime.now().year
    timestamp = datetime.now().strftime("%m%d%H%M")
    return f"STU{year}{timestamp}"

def calculate_payment_schedule(total_amount, installments=1, start_date=None):
    """Calculate payment schedule for installments"""
    if start_date is None:
        start_date = date.today()
    
    if installments <= 1:
        return [{'amount': total_amount, 'due_date': start_date}]
    
    amount_per_installment = total_amount / installments
    schedule = []
    
    for i in range(installments):
        due_date = start_date + timedelta(days=i * 30)  # Monthly installments
        schedule.append({
            'amount': amount_per_installment,
            'due_date': due_date,
            'installment_number': i + 1
        })
    
    return schedule

class DateTimeUtils:
    """Utility class for date and time operations"""
    
    @staticmethod
    def get_week_dates(date_obj=None):
        """Get start and end dates of the week"""
        if date_obj is None:
            date_obj = date.today()
        
        start_of_week = date_obj - timedelta(days=date_obj.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        return start_of_week, end_of_week
    
    @staticmethod
    def get_month_dates(date_obj=None):
        """Get start and end dates of the month"""
        if date_obj is None:
            date_obj = date.today()
        
        start_of_month = date_obj.replace(day=1)
        
        # Get last day of month
        if date_obj.month == 12:
            end_of_month = date_obj.replace(year=date_obj.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = date_obj.replace(month=date_obj.month + 1, day=1) - timedelta(days=1)
        
        return start_of_month, end_of_month
    
    @staticmethod
    def is_business_day(date_obj):
        """Check if date is a business day (Monday-Friday)"""
        return date_obj.weekday() < 5

class ValidationUtils:
    """Utility class for validation functions"""
    
    @staticmethod
    def is_valid_url(url):
        """Validate URL format"""
        url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        return re.match(url_pattern, url) is not None
    
    @staticmethod
    def is_strong_password(password):
        """Check if password meets strength requirements"""
        if len(password) < 8:
            return False
        
        # Check for at least one uppercase, lowercase, digit, and special character
        patterns = [
            r'[A-Z]',      # Uppercase
            r'[a-z]',      # Lowercase
            r'\d',         # Digit
            r'[!@#$%^&*(),.?":{}|<>]'  # Special character
        ]
        
        return all(re.search(pattern, password) for pattern in patterns)
    
# Payment Provider API Integration

def create_vault_payment_link(amount, currency="AED", description="", customer_info=None, callback_url=None):
    """
    Create a payment link using Vault Pay API
    Documentation: https://docs.vaultpay.com/api/payment-links
    """
    try:
        if not requests:
            return {"success": False, "error": "Requests library not available"}
        # Vault Pay API endpoint
        api_url = "https://api.vaultpay.com/v1/payment-links"
        
        # API credentials (should be stored in environment variables)
        api_key = current_app.config.get('VAULT_API_KEY')
        if not api_key:
            logger.error("Vault API key not configured")
            return {"success": False, "error": "API key not configured"}
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Payment link data
        payment_data = {
            "amount": float(amount),
            "currency": currency,
            "description": description,
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
            "metadata": {
                "source": "training_center_crm",
                "created_at": datetime.now().isoformat()
            }
        }
        
        # Add customer information if provided
        if customer_info:
            payment_data["customer"] = {
                "name": customer_info.get("name", ""),
                "email": customer_info.get("email", ""),
                "phone": customer_info.get("phone", "")
            }
        
        # Add callback URL if provided
        if callback_url:
            payment_data["callback_url"] = callback_url
        
        # Make API request
        response = requests.post(api_url, headers=headers, json=payment_data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            return {
                "success": True,
                "payment_link": result.get("url"),
                "payment_id": result.get("id"),
                "expires_at": result.get("expires_at")
            }
        else:
            logger.error(f"Vault API error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Vault API connection error: {str(e)}")
        return {"success": False, "error": "Connection error"}
    except Exception as e:
        logger.error(f"Vault payment link creation error: {str(e)}")
        return {"success": False, "error": "Payment link creation failed"}

def create_tabby_payment_link(amount, currency="AED", description="", customer_info=None, callback_url=None):
    """
    Create a payment link using Tabby API
    Documentation: https://docs.tabby.ai/docs/checkout-api
    """
    try:
        if not requests:
            return {"success": False, "error": "Requests library not available"}
        # Tabby API endpoint
        api_url = "https://api.tabby.ai/api/v2/checkout"
        
        # API credentials
        api_key = current_app.config.get('TABBY_API_KEY')
        if not api_key:
            logger.error("Tabby API key not configured")
            return {"success": False, "error": "API key not configured"}
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Payment data for Tabby
        checkout_data = {
            "payment": {
                "amount": str(amount),
                "currency": currency,
                "description": description
            },
            "order": {
                "tax_amount": "0.00",
                "shipping_amount": "0.00",
                "discount_amount": "0.00",
                "reference_id": f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "items": [{
                    "title": description or "Training Course",
                    "description": description or "Training course payment",
                    "quantity": 1,
                    "unit_price": str(amount),
                    "category": "Education"
                }]
            },
            "order_history": [],
            "meta": {
                "order_id": f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "customer": {}
            }
        }
        
        # Add customer information
        if customer_info:
            checkout_data["order"]["shipping_address"] = {
                "city": "Dubai",
                "country": "AE",
                "line1": "Training Center",
                "zip": "00000"
            }
            checkout_data["order"]["buyer"] = {
                "phone": customer_info.get("phone", ""),
                "email": customer_info.get("email", ""),
                "name": customer_info.get("name", "")
            }
        
        # Add callback URLs
        if callback_url:
            checkout_data["merchant_urls"] = {
                "success": f"{callback_url}?status=success",
                "cancel": f"{callback_url}?status=cancel",
                "failure": f"{callback_url}?status=failure"
            }
        
        # Make API request
        response = requests.post(api_url, headers=headers, json=checkout_data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            return {
                "success": True,
                "payment_link": result.get("web_url"),
                "payment_id": result.get("id"),
                "expires_at": result.get("expires_at")
            }
        else:
            logger.error(f"Tabby API error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Tabby API connection error: {str(e)}")
        return {"success": False, "error": "Connection error"}
    except Exception as e:
        logger.error(f"Tabby payment link creation error: {str(e)}")
        return {"success": False, "error": "Payment link creation failed"}

def create_tamara_payment_link(amount, currency="AED", description="", customer_info=None, callback_url=None):
    """
    Create a payment link using Tamara API
    Documentation: https://docs.tamara.co/docs/api-checkout
    """
    try:
        if not requests:
            return {"success": False, "error": "Requests library not available"}
        # Tamara API endpoint
        api_url = "https://api.tamara.co/checkout"
        
        # API credentials
        api_token = current_app.config.get('TAMARA_API_TOKEN')
        if not api_token:
            logger.error("Tamara API token not configured")
            return {"success": False, "error": "API token not configured"}
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        # Payment data for Tamara
        checkout_data = {
            "order_reference_id": f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_number": f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "total_amount": {
                "amount": float(amount),
                "currency": currency
            },
            "description": description or "Training course payment",
            "country_code": "AE",
            "payment_type": "PAY_BY_INSTALMENTS",
            "instalments": 3,
            "locale": "en_US",
            "items": [{
                "name": description or "Training Course",
                "type": "Digital",
                "reference_id": f"item_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "sku": "TRAINING_001",
                "quantity": 1,
                "unit_price": {
                    "amount": float(amount),
                    "currency": currency
                },
                "total_amount": {
                    "amount": float(amount),
                    "currency": currency
                }
            }],
            "consumer": {
                "first_name": "Customer",
                "last_name": "Name",
                "phone_number": "971500000000",
                "email": "customer@example.com"
            },
            "shipping_address": {
                "first_name": "Customer",
                "last_name": "Name",
                "line1": "Training Center",
                "city": "Dubai",
                "country_code": "AE"
            },
            "billing_address": {
                "first_name": "Customer", 
                "last_name": "Name",
                "line1": "Training Center",
                "city": "Dubai",
                "country_code": "AE"
            }
        }
        
        # Update customer information if provided
        if customer_info:
            name_parts = customer_info.get("name", "Customer Name").split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else "Name"
            
            consumer_data = {
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": customer_info.get("phone", "971500000000"),
                "email": customer_info.get("email", "customer@example.com")
            }
            
            checkout_data["consumer"] = consumer_data
            checkout_data["shipping_address"].update({
                "first_name": first_name,
                "last_name": last_name
            })
            checkout_data["billing_address"].update({
                "first_name": first_name,
                "last_name": last_name
            })
        
        # Add callback URLs
        if callback_url:
            checkout_data["merchant_url"] = {
                "success": f"{callback_url}?status=success",
                "failure": f"{callback_url}?status=failure",
                "cancel": f"{callback_url}?status=cancel"
            }
        
        # Make API request
        response = requests.post(api_url, headers=headers, json=checkout_data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            return {
                "success": True,
                "payment_link": result.get("checkout_url"),
                "payment_id": result.get("order_id"),
                "expires_at": None  # Tamara doesn't provide expiry in response
            }
        else:
            logger.error(f"Tamara API error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Tamara API connection error: {str(e)}")
        return {"success": False, "error": "Connection error"}
    except Exception as e:
        logger.error(f"Tamara payment link creation error: {str(e)}")
        return {"success": False, "error": "Payment link creation failed"}

def create_payment_link(provider, amount, currency="AED", description="", customer_info=None, callback_url=None):
    """
    Create a payment link using the specified provider
    
    Args:
        provider (str): Payment provider ('vault', 'tabby', 'tamara')
        amount (float): Payment amount
        currency (str): Currency code (default: 'AED')
        description (str): Payment description
        customer_info (dict): Customer information (name, email, phone)
        callback_url (str): Callback URL for payment notifications
    
    Returns:
        dict: Payment link creation result
    """
    if provider.lower() == 'vault':
        return create_vault_payment_link(amount, currency, description, customer_info, callback_url)
    elif provider.lower() == 'tabby':
        return create_tabby_payment_link(amount, currency, description, customer_info, callback_url)
    elif provider.lower() == 'tamara':
        return create_tamara_payment_link(amount, currency, description, customer_info, callback_url)
    else:
        return {"success": False, "error": f"Unsupported payment provider: {provider}"}

def verify_payment_status(provider, payment_id):
    """
    Verify payment status with the provider
    
    Args:
        provider (str): Payment provider ('vault', 'tabby', 'tamara')
        payment_id (str): Payment ID to verify
    
    Returns:
        dict: Payment status information
    """
    try:
        if provider.lower() == 'vault':
            api_key = current_app.config.get('VAULT_API_KEY')
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(f"https://api.vaultpay.com/v1/payment-links/{payment_id}", headers=headers)
            
        elif provider.lower() == 'tabby':
            api_key = current_app.config.get('TABBY_API_KEY')
            if not api_key:
                return {"success": False, "error": "API key not configured"}
            
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(f"https://api.tabby.ai/api/v2/checkout/{payment_id}", headers=headers)
            
        elif provider.lower() == 'tamara':
            api_token = current_app.config.get('TAMARA_API_TOKEN')
            if not api_token:
                return {"success": False, "error": "API token not configured"}
            
            headers = {"Authorization": f"Bearer {api_token}"}
            response = requests.get(f"https://api.tamara.co/orders/{payment_id}", headers=headers)
        else:
            return {"success": False, "error": f"Unsupported payment provider: {provider}"}
        
        if response.status_code == 200:
            result = response.json()
            return {"success": True, "status": result.get("status", "unknown"), "data": result}
        else:
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        return {"success": False, "error": "Payment verification failed"}