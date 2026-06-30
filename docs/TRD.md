# Technical Requirements Document (TRD)
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Product:** Orbit ERP Institute Management System  
**Status:** Production

---

## 1. System Overview

Orbit ERP is a monolithic Django web application serving as the complete back-office ERP for Orbit Training Point. The application runs on Windows Server with IIS as the production web server and MySQL 8.0 as the database.

---

## 2. Technology Stack

### 2.1 Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Web Framework | Django | 5.0.6 |
| Language | Python | 3.x |
| ORM | Django ORM | Built-in |
| WSGI Server (Dev) | Django Development Server | Built-in |
| WSGI Handler (Prod) | wfastcgi | 3.0.0 |
| Web Server (Prod) | IIS (Internet Information Services) | — |
| Async Support | ASGI (asgi.py configured) | Django 5.0 |

### 2.2 Database

| Component | Technology | Version |
|-----------|------------|---------|
| Database Engine | MySQL | 8.0.39 |
| Django DB Backend | django.db.backends.mysql | — |
| MySQL Driver | mysqlclient | 2.2.4 |
| Default Charset | utf8mb4 | — |
| Collation | utf8mb4_0900_ai_ci | — |
| Storage Engine | InnoDB | All tables |

### 2.3 Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Template Engine | Django Template Language | Built-in |
| CSS Framework | Bootstrap | 5.1.3 / 5.3.0 |
| Icons | Font Awesome | 5.15.3 / 6.0.0 |
| Icons | Bootstrap Icons | 1.7.2 |
| Font | Google Fonts (Poppins) | — |
| Dropdown Enhancement | Select2 | — |
| JavaScript | Vanilla JS + jQuery | — |

### 2.4 Libraries & Dependencies

```
art==6.2            # ASCII art for CLI output
asgiref==3.8.1      # ASGI utilities for Django
Django==5.0.6       # Core web framework
mysqlclient==2.2.4  # MySQL database connector
sqlparse==0.5.0     # SQL statement parser (Django dependency)
tzdata==2024.1      # Timezone data
wfastcgi==3.0.0     # FastCGI handler for IIS deployment
```

**Additional runtime dependencies (not in requirements file):**
- Pillow / PIL — image processing for logo manipulation
- WeasyPrint — HTML-to-PDF generation
- ReportLab — PDF document toolkit
- PyPDF2 — PDF file manipulation

---

## 3. Architecture

### 3.1 Application Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Browser                        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/HTTPS
┌──────────────────────▼──────────────────────────────────┐
│          IIS (Production) / Django Dev Server            │
└──────────────────────┬──────────────────────────────────┘
                       │ WSGI
┌──────────────────────▼──────────────────────────────────┐
│              Django Application (WSGI)                    │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │  URLs    │  │  Views   │  │  Forms   │  │ Admin  │  │
│  │  (86)    │  │  (68+)   │  │  (25)    │  │        │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┘  │
│       │              │              │                     │
│  ┌────▼──────────────▼──────────────▼─────────────────┐  │
│  │              Django ORM / Models (22)               │  │
│  └─────────────────────────┬───────────────────────────┘  │
└────────────────────────────┼────────────────────────────┘
                             │ SQL
┌────────────────────────────▼────────────────────────────┐
│              MySQL 8.0 (orbit_invoice DB)                 │
│                    36 Tables                             │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Django Project Structure

```
invoice_project/                    # Django project root
├── invoice_project/                # Project configuration package
│   ├── settings.py                 # All Django configuration
│   ├── urls.py                     # Root URL dispatcher
│   ├── wsgi.py                     # WSGI entry point
│   ├── asgi.py                     # ASGI entry point
│   ├── static/                     # Project-level static files
│   └── templatetags/               # Global template tags
├── invoices/                       # Single application (monolithic)
│   ├── models.py                   # 22 data models (617 lines)
│   ├── views.py                    # 68+ view functions (2053 lines)
│   ├── forms.py                    # 25 Django forms (807 lines)
│   ├── urls.py                     # 86 URL patterns
│   ├── admin.py                    # Admin configuration
│   ├── apps.py                     # App configuration
│   ├── migrations/                 # 45 database migration files
│   ├── templates/                  # 78 HTML templates
│   ├── static/css/                 # App-level CSS
│   └── templatetags/
│       └── custom_filters.py       # 10 custom template filters/tags
├── manage.py                       # Django management CLI
├── static/                         # Collected static files (6.5MB)
├── staticfiles/                    # Additional static (4.2MB)
├── media/                          # User-uploaded files (193MB)
│   ├── certificates/
│   ├── course_contents/
│   ├── khda_certificates/
│   ├── proposal_logos/
│   ├── proposal_logos_white/
│   ├── registration_forms/
│   ├── trainer_profiles/
│   └── company_profiles/
├── server_requirements.txt         # Python dependencies
├── web.config                      # IIS configuration
└── debug.log                       # Error log file
```

---

## 4. Database Configuration

### 4.1 Connection Settings

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'orbit_invoice',
        'USER': 'root',
        'PASSWORD': 'Orbit20232024',
        'HOST': 'localhost',
        'PORT': '',           # Default MySQL port: 3306
    }
}
```

### 4.2 Database Schema Overview

| Category | Tables | Records (approx.) |
|----------|--------|-------------------|
| Django Auth | auth_user, auth_group, auth_permission (+ 3 junction) | 54 users |
| Django Core | django_content_type, django_migrations, django_session, django_admin_log | System |
| Clients | invoices_client | 1,694 |
| Courses | invoices_course, invoices_coursecontent | 239 courses |
| Registrations | invoices_registration, invoices_registrationcourse, invoices_corporateregistration | 853 |
| Invoices | invoices_invoice, invoices_invoiceitem, invoices_invoicepurchase, invoices_invoicepurchaseitem | 1,156 |
| Quotations | invoices_quotation, invoices_quotationitem | 217 |
| Certificates | invoices_certificate, invoices_certificateupload, invoices_formupload | 254 |
| Proposals | invoices_proposal | 90 |
| CRM | invoices_lead, invoices_followup, invoices_comment, invoices_meeting, invoices_pipeline, invoices_pipelinestage | 18 leads |
| Profiles | invoices_trainerprofile, invoices_companyprofile | 22 |
| Coupons | invoices_coupon | 5 |

**Total: ~36 tables**

---

## 5. Authentication & Authorization

### 5.1 Authentication
- Django's built-in `django.contrib.auth` system
- Session-based authentication
- Login required via `@login_required` decorator on all protected views
- Session stored in MySQL (`django_session` table)

### 5.2 Authorization
```python
def is_admin_user(user):
    """Custom admin check — user must have is_staff OR is_superuser flag"""
    return user.is_staff or user.is_superuser
```

- `@login_required` — used on all business views
- `@user_passes_test(is_admin_user)` — used on sensitive operations (user creation, deletions)
- Standard Django admin at `/admin/` (configured but minimal use)

### 5.3 Login Flow
```
GET /accounts/login/ → Login Form → POST credentials →
Django auth.authenticate() → Session created → Redirect to /dashboard/
```

---

## 6. URL Routing

### 6.1 Root URL Configuration (`invoice_project/urls.py`)
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('invoices.urls')),
]
```

### 6.2 App URL Patterns (86 paths in `invoices/urls.py`)

**URL naming pattern:** `app_name:view_name` (no namespacing currently)

| Category | Path Prefix | Count |
|----------|-------------|-------|
| Dashboard | `dashboard/`, `` | 2 |
| Auth | `signup/`, `logout/` | 2 |
| Invoices | `create_invoice/`, `invoice/` | 7 |
| Purchase Invoices | `create_purchase_invoice/`, `invoice_purchase/` | 5 |
| Quotations | `quotation/` | 6 |
| Registrations | `register/`, `student-dashboard/`, `edit-registration/` | 8 |
| Corporate | `corporate-registration/`, `corporate_dashboard/` | 6 |
| Courses | `courses/` | 7 |
| Certificates | `certificates/`, `upload-certificate/`, `upload-form/` | 7 |
| Proposals | `proposals/` | 6 |
| Trainer Profile | `trainer-profile/` | 4 |
| Company Profile | `company-profile/` | 4 |
| Leads | `lead/`, `leads/` | 13 |
| Coupons | `coupons/`, `validate-coupon/` | 5 |
| AJAX Endpoints | `get_course_details/`, `get_registration_details/`, etc. | 3 |
| Other | `subscription/`, `payment-link/` | 2 |

---

## 7. Key Technical Implementations

### 7.1 Auto-Numbering System

All business documents use auto-generated sequential numbers:

```python
# Invoice: YY/MM/### (e.g., 24/06/001)
last_invoice = Invoice.objects.filter(
    invoice_number__startswith=prefix
).order_by('-invoice_number').first()
next_number = int(last_invoice.invoice_number.split('/')[-1]) + 1
invoice_number = f"{prefix}/{next_number:03d}"

# Registration: OT/YY/MM/### or OC/YY/MM/###
# Certificate: {COURSE_CODE}/YY/### (e.g., PM/24/001)
# Proposal: PROP-YYYY-#### (e.g., PROP-2024-0001)
```

### 7.2 VAT Calculation (5%)

```python
# InvoiceItem model methods
def get_subtotal(self):
    return self.quantity * self.unit_price

def get_vat_amount(self):
    return self.get_subtotal() * (self.vat_rate / 100)

def get_total(self):
    return self.get_subtotal() + self.get_vat_amount()
```

### 7.3 Logo Processing (Proposals)

```python
# PNG logo validation: 800x300px required
# Auto-generates white version by replacing dark pixels
# Saved to separate media/proposal_logos_white/ directory
```

### 7.4 AJAX Endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/get_course_details/` | GET | Course rates JSON |
| `/get_registration_details/` | GET | Registration + invoice data JSON |
| `/get_invoice_details/` | GET | Invoice items JSON |
| `/lead/<id>/` | GET | Lead details JSON |
| `/lead/<id>/comments/` | GET | Comments JSON |
| `/lead/dashboard-stats/` | GET | CRM statistics JSON |
| `/validate-coupon/` | POST | Coupon validity + discount JSON |

### 7.5 PDF Generation

Two methods used:
1. **Print via browser** — Django renders HTML template, user uses browser print (`window.print()`)
2. **WeasyPrint** — Server-side HTML-to-PDF for programmatic generation

Templates have dedicated print stylesheets (`@media print`) that hide navigation.

### 7.6 File Upload Handling

```python
# Media storage configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Upload paths per model
profile_pdf = models.FileField(upload_to='trainer_profiles/')
certificate_file = models.FileField(upload_to='certificates/')
logo = models.ImageField(upload_to='proposal_logos/', null=True)
file = models.FileField(upload_to='course_contents/')
```

### 7.7 Custom Template Filters

```python
# templatetags/custom_filters.py
@register.filter
def multiply(value, arg):        # {{ price|multiply:qty }}
def subtract(value, arg):        # {{ total|subtract:discount }}
def add(value, arg):             # {{ a|add:b }}
def divide(value, arg):          # {{ total|divide:count }}
def calculate_course_price():    # Apply discount + VAT
def get_item(lst, index):        # {{ list|get_item:0 }}
def subtract_percentage():       # {{ amount|subtract_percentage:10 }}

@register.simple_tag
def calculate_total_price(registration):   # Sum of all course prices
def calculate_running_due(invoice, ...):   # Running balance tracker
def calculate_total_vat(registration):     # Total VAT amount
```

---

## 8. Configuration & Settings

### 8.1 Django Settings Summary

```python
DEBUG = True                          # WARNING: Should be False in production
ALLOWED_HOSTS = ['10.255.254.23']     # Only local network IP

SECRET_KEY = 'django-insecure-...'   # WARNING: Hardcoded insecure key

TIME_ZONE = 'UTC'                     # Should be 'Asia/Dubai' for UAE
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'staticfiles')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### 8.2 Middleware Stack (in order)

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',        # CSRF protection enabled
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 8.3 Logging

```python
LOGGING = {
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
        },
    },
}
```

---

## 9. Deployment Architecture (Production)

### 9.1 Current Setup
- **OS:** Windows Server
- **Web Server:** IIS (Internet Information Services)
- **WSGI:** wfastcgi (FastCGI bridge for Python/Django on IIS)
- **Database:** MySQL 8.0 on localhost
- **Python:** Virtual environment at `orbit-system/myenv/`
- **Config:** `web.config` for IIS handler mapping

### 9.2 Server Commands

```bash
# Development server
cd orbit-system/invoice_project
myenv\Scripts\python manage.py runserver 0.0.0.0:8000

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input

# Create superuser
python manage.py createsuperuser

# Load SQL database
mysql -u root -p orbit_invoice < orbiterp.sql
```

---

## 10. Security Considerations

### 10.1 Current State
| Item | Status | Risk |
|------|--------|------|
| `DEBUG = True` in production | ⚠️ Warning | High — exposes tracebacks |
| Hardcoded `SECRET_KEY` | ⚠️ Warning | High — should use env variable |
| Root MySQL user | ⚠️ Warning | Medium — should use dedicated DB user |
| Hardcoded DB password | ⚠️ Warning | Medium — should use env variable |
| `ALLOWED_HOSTS` = internal IP only | ✅ OK | Low |
| CSRF protection | ✅ Enabled | — |
| Login required on all views | ✅ Implemented | — |
| Admin-only actions protected | ✅ Implemented | — |
| XFrame options | ✅ Enabled | — |

### 10.2 Recommended Security Improvements

```python
# Use environment variables for secrets
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
DATABASES['default']['PASSWORD'] = os.environ.get('DB_PASSWORD')

# Production settings
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Use dedicated MySQL user with limited permissions
# CREATE USER 'orbit_app'@'localhost' IDENTIFIED BY 'strong_password';
# GRANT SELECT, INSERT, UPDATE, DELETE ON orbit_invoice.* TO 'orbit_app'@'localhost';
```

---

## 11. Performance Characteristics

| View Type | Typical Queries | Notes |
|-----------|-----------------|-------|
| Dashboard | 10-15 | Aggregation queries for KPIs |
| Invoice List | 3-5 | Paginated, with filters |
| Registration Form | 2-3 | Course list + registration data |
| Certificate Print | 2-3 | Template rendering |
| Lead Dashboard | 5-8 | Stats + lead list |

**No caching layer is implemented.** All requests hit MySQL directly.

---

## 12. Migration History

- **Total migrations:** 45 (as of current database state)
- **Migration file location:** `invoices/migrations/`
- **68 migration records** in `django_migrations` table (includes Django auth + app migrations)
- Initial migration covers all core models
- Subsequent migrations added: CRM features, pipeline stages, coupon system, purchase invoices

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
