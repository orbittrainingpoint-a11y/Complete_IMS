# Technical Requirements Document (TRD)
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Product:** Orbit ERP Institute Management System
**Status:** Production (orbittraining.online)

---

## 1. System Overview

Orbit ERP consists of two cooperating web applications:

1. **Django ERP** — Core back-office system (registrations, invoices, certificates, reports, user management). Django 5.0.6, Python 3.x.
2. **Flask CRM** — Lead pipeline and sales management. Flask, SQLAlchemy, SQLite/MySQL.

Both applications are deployed on the same VPS, proxied through Apache to the domain `orbittraining.online`.

---

## 2. Technology Stack

### 2.1 Django ERP Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Web Framework | Django | 5.0.6 |
| Language | Python | 3.x |
| ORM | Django ORM | Built-in |
| WSGI Server (Dev) | Django Development Server | port 8000 |
| WSGI Server (Prod) | Gunicorn | port 8001 |
| Web Server (Prod) | Apache (reverse proxy) | — |
| Async Support | ASGI (asgi.py configured) | Django 5.0 |

### 2.2 Flask CRM Backend

| Component | Technology | Notes |
|-----------|------------|-------|
| Web Framework | Flask | — |
| ORM | SQLAlchemy | — |
| Entry point | `leads-management/main.py` | app from `app.py` |
| Dev Port | 5000 | local |
| Prod Port | 5001 | VPS, proxied via Apache |
| Templates | Jinja2 | — |
| Migrations | Alembic | `migrations/versions/` |

### 2.3 Database

| Environment | Engine | Database | Notes |
|-------------|--------|----------|-------|
| Local Dev | MariaDB (XAMPP) | orbit_invoice | MariaDB 10.4+ |
| VPS Production | MySQL 8 | orbit_invoice | MySQL 8.0 |
| CRM (local) | MariaDB/MySQL | leads | Separate schema |
| CRM (VPS) | MySQL 8 | leads | Same server |

Django settings:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'orbit_invoice'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}
```

CRM DB connection (direct pymysql from Django for user sync):
```python
CRM_DB = {
    'host': os.environ.get('CRM_DB_HOST', 'localhost'),
    'user': os.environ.get('CRM_DB_USER', 'root'),
    'password': os.environ.get('CRM_DB_PASSWORD', ''),
    'database': os.environ.get('CRM_DB_NAME', 'leads'),
    'charset': 'utf8mb4',
}
```

### 2.4 Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Template Engine | Django Template Language | Built-in |
| CSS Framework | Bootstrap | 5.1.3 / 5.3.0 |
| Icons | Font Awesome | 5.15.3 / 6.0.0 |
| Icons | Bootstrap Icons | 1.7.2 |
| Font | Google Fonts (Poppins) | — |
| Dropdown Enhancement | Select2 | — |
| JavaScript | Vanilla JS + jQuery | — |

### 2.5 Key Python Libraries

```
Django==5.0.6          # Core web framework
mysqlclient==2.2.4     # MySQL/MariaDB connector
Pillow                 # Image processing (proposal logos)
reportlab              # PDF generation
xhtml2pdf              # HTML-to-PDF conversion
pdfkit                 # wkhtmltopdf wrapper (alternative PDF)
WeasyPrint             # HTML-to-PDF (fallback)
PyPDF2                 # PDF manipulation
pymysql                # CRM DB sync (direct connection)
```

---

## 3. Architecture

### 3.1 Two-Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    Apache Web Server                              │
│              (orbittraining.online — SSL termination)            │
│                                                                   │
│  /             → ProxyPass → Gunicorn :8001  (Django ERP)        │
│  /crm/         → ProxyPass → Gunicorn :5001  (Flask CRM)         │
└──────────┬──────────────────────────┬───────────────────────────┘
           │                          │
┌──────────▼──────────┐  ┌───────────▼──────────────┐
│   Django ERP        │  │   Flask CRM               │
│   Gunicorn :8001    │  │   Gunicorn :5001           │
│   Django 5.0.6      │  │   Flask                    │
│   invoice_project/  │  │   leads-management/        │
└──────────┬──────────┘  └───────────┬──────────────┘
           │                          │
           └─────────────┬────────────┘
                         │
              ┌──────────▼──────────┐
              │   MySQL 8 / MariaDB  │
              │   orbit_invoice DB   │
              │   leads DB           │
              └─────────────────────┘
```

### 3.2 Django ERP Project Structure

```
orbit-system/invoice_project/           # Django project root
├── invoice_project/                    # Project configuration package
│   ├── settings.py                     # All configuration (env-var driven)
│   ├── urls.py                         # Root URL dispatcher
│   ├── wsgi.py                         # WSGI entry point
│   └── asgi.py                         # ASGI entry point
├── invoices/                           # Single Django application
│   ├── models.py                       # 22+ data models
│   ├── views.py                        # 100+ view functions
│   ├── forms.py                        # 25+ Django forms
│   ├── urls.py                         # 135 URL patterns
│   ├── admin.py                        # Admin configuration
│   ├── apps.py                         # App config — imports signals
│   ├── signals.py                      # Login/logout → AuditLog
│   ├── context_processors.py           # sidebar_data context processor
│   ├── migrations/                     # Database migration files
│   ├── templates/                      # HTML templates
│   └── templatetags/
│       └── custom_filters.py           # Custom template filters/tags
├── manage.py
├── static/                             # Collected static files
├── staticfiles/                        # Source static files
└── media/                              # User-uploaded files
    ├── certificates/
    ├── course_contents/
    ├── khda_certificates/
    ├── proposal_logos/
    ├── proposal_logos_white/
    ├── registration_forms/
    ├── trainer_profiles/
    ├── company_profiles/
    └── portal/
        ├── trade_license/
        └── vat/
```

### 3.3 Flask CRM Project Structure

```
leads-management/
├── app.py                   # Flask app factory / main application
├── routes.py                # All route handlers
├── models.py                # SQLAlchemy models
├── forms.py                 # WTForms
├── extensions.py            # db, login_manager, etc.
├── main.py                  # Entry point (runs on port 5000 dev)
├── utils.py                 # Helper functions
├── templates/               # Jinja2 templates
├── static/                  # CSS, JS, images
├── migrations/              # Alembic migrations
│   └── versions/
└── requirements.txt
```

---

## 4. Settings Configuration

All sensitive settings are environment-variable driven. The `.env.erp` and `.env.crm` files on the VPS (`/var/www/html/orbit/`) are loaded by the systemd services.

```python
# settings.py — key settings
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '<insecure-dev-default>')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

_default_hosts = 'localhost,127.0.0.1,orbittraining.online,www.orbittraining.online'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', _default_hosts).split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'https://orbittraining.online,https://www.orbittraining.online'
).split(',')

# CRM Integration
CRM_SSO_SECRET = os.environ.get('CRM_SSO_SECRET', 'orbit-erp-crm-sso-bridge-2024-x9q3mz')
CRM_URL = os.environ.get('CRM_URL', 'http://localhost:5000')
ERP_URL = os.environ.get('ERP_URL', 'http://localhost:8000')
```

**VPS env files:**
- `/var/www/html/orbit/.env.erp` — ERP environment variables
- `/var/www/html/orbit/.env.crm` — CRM environment variables

---

## 5. Authentication & Authorization

### 5.1 Authentication

- Django's built-in `django.contrib.auth` system
- Session-based authentication (cookie)
- Login required via `@login_required` decorator on all protected views
- Session stored in MySQL (`django_session` table)
- Audit log captures every login and logout event with IP address

### 5.2 Role System

```python
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sales_manager', 'Sales Manager'),
        ('accounts', 'Accounts'),
        ('sales_executive', 'Sales Executive'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales_executive')

def is_admin_user(user):
    try:
        return user.profile.role in ('admin',) or user.is_superuser
    except Exception:
        return user.is_superuser
```

`@user_passes_test(is_admin_user)` guards sensitive operations (deletions, user management, audit log, targets).

### 5.3 CRM SSO Bridge

HMAC-SHA256 token signed with shared secret `CRM_SSO_SECRET`. Token payload:
```json
{"u": "username", "t": 1234567890}
```
Token TTL: 90 seconds. Verified by both apps. Encoded as `base64url(json).sig[:32]`.

---

## 6. URL Routing

### 6.1 Root URL Configuration

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('invoices.urls')),
]
```

### 6.2 URL Pattern Summary (135 paths in `invoices/urls.py`)

| Category | Path Prefix | Notes |
|----------|-------------|-------|
| Dashboard | `/`, `/dashboard/` | Orbit dashboard + Invoice dashboard |
| User Mgmt | `/manage/users/`, `/manage/set-targets/` | Admin only |
| Invoices | `/create_invoice/`, `/invoice/` | Sales invoices |
| Purchase Invoices | `/create_purchase_invoice/` | Purchase invoices |
| Quotations | `/quotation/` | Quotation CRUD |
| Registrations | `/register/`, `/student-dashboard/` | Individual |
| Corporate | `/corporate-registration/`, `/corporate_dashboard/` | Corporate |
| Courses | `/courses/` | Course CRUD + content |
| Certificates | `/certificates/`, `/upload-certificate/` | Certs |
| Proposals | `/proposals/` | Proposal CRUD |
| Trainer Profile | `/trainer-profile/` | Trainer CRUD |
| Company Profile | `/company-profile/` | Company CRUD |
| Coupons | `/coupons/`, `/validate-coupon/` | Coupon CRUD |
| Reports | `/reports/revenue/`, `/reports/aging/`, `/reports/vat/`, `/reports/enrollment/`, `/reports/certificates/` | Reports |
| Notifications | `/notifications/` | Read, mark-read |
| Training Schedule | `/schedule/` | Schedule CRUD |
| Expenses | `/expenses/`, `/expenses/report/` | Expense CRUD |
| Audit Log | `/audit/` | Admin only |
| Fee Reminders | `/fee-reminders/` | Reminder dashboard |
| CRM SSO | `/crm-jump/`, `/crm-auth/` | SSO bridge |
| Company Portal | `/portal/company/<token>/`, `/admin-portal/` | Self-reg portal |
| Student Form Links | `/portal/student-links/`, `/portal/student/<token>/` | Token reg |
| AJAX | `/get_course_details/`, `/get_registration_details/`, `/get_invoice_details/` | JSON |
| Search | `/search/` | Global search |
| Invoice Payments | `/invoice/<pk>/payments/` | Payment installments |
| Bulk Actions | `/invoices/bulk-action/` | Bulk invoice ops |
| Mark Paid | `/invoice/<pk>/mark-paid/` | Quick action |
| Auth | `/signup/`, `/logout/` | ERP auth |
| Other | `/subscription/`, `/payment-link/` | Misc |

---

## 7. Key Technical Implementations

### 7.1 Auto-Numbering System

| Document | Format | Example |
|----------|--------|---------|
| Invoice (sales) | YY/MM/### | 26/07/001 |
| Invoice (purchase) | YY/MM/### | 26/07/001 |
| Quotation | YY/MM/### | 26/07/001 |
| Registration (Individual) | OT/YY/### | OT/26/001 |
| Registration (Corporate) | OC/YY/### | OC/26/001 |
| Certificate | {CODE}{REG_NUM} | PMOT/26/001 |
| Proposal | PROP-YYYY-#### | PROP-2026-0001 |

**Note:** Registration numbering resets annually (YY), not monthly. Invoice numbering resets monthly.

### 7.2 Level-Based Course Pricing

```python
class Course(models.Model):
    # Legacy flat rates (kept for backward compatibility)
    rate         = models.DecimalField(...)  # standard/offline
    batch_rate   = models.DecimalField(...)
    online_rate  = models.DecimalField(...)
    private_rate = models.DecimalField(...)

    # Structured level pricing (current)
    oo_intermediate  = models.DecimalField(...)  # Online/Offline – Intermediate
    oo_professional  = models.DecimalField(...)  # Online/Offline – Professional
    oo_advanced      = models.DecimalField(...)  # Online/Offline – Advanced
    priv_intermediate = models.DecimalField(...) # Private – Intermediate
    priv_professional = models.DecimalField(...) # Private – Professional
    priv_advanced     = models.DecimalField(...) # Private – Advanced

    def get_rate(self, class_type, level='intermediate'):
        if class_type == 'private':
            return {'intermediate': self.priv_intermediate,
                    'professional': self.priv_professional,
                    'advanced':     self.priv_advanced}.get(level, self.priv_intermediate)
        else:  # online, offline, batch
            return {'intermediate': self.oo_intermediate,
                    'professional': self.oo_professional,
                    'advanced':     self.oo_advanced}.get(level, self.oo_intermediate)
```

### 7.3 VAT Calculation (5%)

VAT is always added on top; never back-calculated from a price.

```python
# InvoiceItem model
def get_subtotal(self): return self.quantity * self.unit_price
def get_vat_amount(self): return self.get_subtotal() * self.vat_rate  # vat_rate default=0.05
def get_total(self): return self.get_subtotal() + self.get_vat_amount()
```

Invoice total uses level-based rates:
```python
def calculate_total_amount(self):
    subtotal = Decimal('0.00')
    for item in self.items.all():
        course_total = item.course.get_rate(self.class_type, self.level) * item.quantity * self.number_of_person
        discounted_total = course_total * (1 - Decimal(self.discount) / 100)
        subtotal += discounted_total
    vat = subtotal * Decimal('0.05')
    return (subtotal + vat).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
```

### 7.4 Discount Cap Enforcement

- Single-course invoice: max 20% discount
- Multi-course invoice: max 30% discount
- Enforced in both frontend JavaScript and backend view validation

### 7.5 Audit Logging (signals.py)

```python
# invoices/signals.py — connected via apps.py ready()
@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    AuditLog.objects.create(
        user=user, action='login', model_name='User',
        object_id=str(user.pk), object_repr=user.username,
        ip_address=_get_ip(request),  # reads X-Forwarded-For then REMOTE_ADDR
    )

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    AuditLog.objects.create(user=user, action='logout', ...)
```

### 7.6 CRM User Sync

When a user's role changes to `sales_manager` or `sales_executive`, Django directly writes to the CRM's MySQL database using pymysql:

```python
def sync_user_to_crm(user, password=None, role=None):
    role_map = {'sales_manager': 'sales_manager', 'sales_executive': 'consultant'}
    # INSERT or UPDATE into leads.user table
    # Generates werkzeug pbkdf2:sha256 password hash for Flask compatibility
```

### 7.7 Context Processors

```python
# invoices/context_processors.py
def sidebar_data(request):
    # Injects unread notification count and user role into all templates
```

### 7.8 Custom Template Filters

`invoices/templatetags/custom_filters.py`:

| Filter/Tag | Usage |
|------------|-------|
| `multiply` | `{{ qty\|multiply:price }}` |
| `subtract` | `{{ total\|subtract:discount }}` |
| `add` | `{{ a\|add:b }}` |
| `divide` | `{{ total\|divide:count }}` |
| `calculate_course_price` | Apply discount + VAT |
| `get_item` | List index access |
| `subtract_percentage` | `amount × (1 - pct/100)` |
| `json_script` | Serialize invoice items to JSON |
| `quotation_json_script` | Serialize quotation items |
| `{% calculate_total_price %}` | Sum RegistrationCourse prices |
| `{% calculate_running_due %}` | Running balance tracker |
| `{% calculate_total_vat %}` | Total VAT on registration |

---

## 8. Middleware Stack

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

---

## 9. Logging

```python
LOGGING = {
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.environ.get('DJANGO_LOG_FILE', os.path.join(BASE_DIR, 'debug.log')),
        },
    },
}
```

Log file path is configurable via `DJANGO_LOG_FILE` environment variable.

---

## 10. Production Services

### 10.1 systemd Service Files

**orbit-erp.service** — Django ERP:
```ini
[Service]
WorkingDirectory=/path/to/orbit-system/invoice_project
EnvironmentFile=/var/www/html/orbit/.env.erp
ExecStart=/path/to/venv/bin/gunicorn invoice_project.wsgi:application --bind 127.0.0.1:8001
Restart=on-failure
```

**orbit-crm.service** — Flask CRM:
```ini
[Service]
WorkingDirectory=/path/to/leads-management
EnvironmentFile=/var/www/html/orbit/.env.crm
ExecStart=/path/to/venv/bin/gunicorn main:app --bind 127.0.0.1:5001
Restart=on-failure
```

### 10.2 Apache Proxy Configuration

```apache
<VirtualHost *:443>
    ServerName orbittraining.online
    SSLEngine on

    # ERP (main app)
    ProxyPass / http://127.0.0.1:8001/
    ProxyPassReverse / http://127.0.0.1:8001/
    RequestHeader set X-Forwarded-Proto https

    # CRM (separate location if needed)
</VirtualHost>
```

---

## 11. Performance Characteristics

| View Type | Typical Queries |
|-----------|-----------------|
| Dashboard | 10-15 (aggregation for KPIs) |
| Invoice List | 3-5 (paginated, with filters) |
| Registration Form | 2-3 (course list) |
| Reports | 5-20 (aggregation queries) |

**No caching layer is implemented.** All requests hit MySQL/MariaDB directly.

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
