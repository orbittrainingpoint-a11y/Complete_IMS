# Technical Requirements Document (TRD)
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
**Status:** Production

---

## 1. Technology Stack

### 1.1 Backend

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | Django | 5.0.6 |
| Language | Python | 3.14 |
| ORM | Django ORM (+ raw SQL for complex reports) | — |
| Database | MariaDB (MySQL-compatible) | Latest on XAMPP |
| Database driver | mysqlclient | — |
| CRM sync | pymysql (direct DB write) | — |
| Password hashing (CRM) | werkzeug | — |
| File uploads | django.core.files, Pillow | — |
| Email | Django SMTP email (`smtp.gmail.com`, TLS port 587) | — |
| Auth | `django.contrib.auth` + custom `UserProfile` | — |

### 1.2 Flask CRM

| Component | Technology |
|-----------|-----------|
| Framework | Flask |
| ORM | SQLAlchemy |
| Auth | Flask-Login |
| Database | MySQL via SQLAlchemy |
| ERP sync | pymysql direct write |

### 1.3 Frontend

| Component | Technology |
|-----------|-----------|
| CSS | Bootstrap 5 + custom CSS variables |
| Icons | Font Awesome 6 |
| JS | Vanilla JS + jQuery |
| Template engine | Django templates |
| Date picker | Flatpickr |
| Charts | Chart.js |
| PDF printing | Browser @print CSS |

---

## 2. Project Structure

```
orbit-system/
  invoice_project/
    invoice_project/        ← Django project config
      settings.py
      urls.py
      wsgi.py
    invoices/               ← Main app (all logic)
      models.py
      views.py
      urls.py
      forms.py
      signals.py            ← AuditLog on login/logout
      apps.py               ← imports signals in ready()
      migrations/           ← 0001 → 0069+
      templates/
        invoices/
        certificates/
        registration/
        proposal/
        quotation/
        studentregistration/
        crm/
      templatetags/
        custom_filters.py
      static/
        css/style.css
        js/
    manage.py
    media/                  ← Uploaded files
    venv314/                ← Local Python 3.14 venv

leads-management/           ← Flask CRM app
  routes.py
  models.py
  templates/
  static/
  app.py

docs/                       ← Documentation
```

---

## 3. Django Settings Key Configuration

### 3.1 Database

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'orbit_invoice',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

### 3.2 Email

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'orbittrainingpoint@gmail.com'
EMAIL_HOST_PASSWORD = '<gmail app password>'
DEFAULT_FROM_EMAIL = 'Orbit Training Point <orbittrainingpoint@gmail.com>'
```

### 3.3 Static / Media

```python
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'invoices/static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### 3.4 Security

```python
SECRET_KEY = '<long random key>'
DEBUG = False          # True locally only
ALLOWED_HOSTS = ['orbittraining.online', '127.0.0.1', 'localhost']
```

### 3.5 CRM Integration

```python
CRM_SSO_SECRET = '<shared HMAC secret>'
CRM_URL = 'http://localhost:5000'
CRM_DB_HOST = '127.0.0.1'
CRM_DB_NAME = 'leads_db'
CRM_DB_USER = 'root'
CRM_DB_PASSWORD = ''
```

---

## 4. Migration Strategy

### 4.1 Constraint

**Never alter existing columns or tables.** Only additive changes:
- `migrations.AddField` — allowed
- `migrations.CreateModel` — allowed
- `migrations.AlterField` on existing — **NOT permitted**
- `migrations.RenameField` / `migrations.DeleteField` — **NOT permitted**

### 4.2 Known Migration Issue (InstituteSetting)

`InstituteSetting` uses a `_setting_upload(field)` closure factory. Django cannot serialize closures:

```
ValueError: Could not find function _path in invoices.models.
```

**Fix:** Write migrations manually — include only the `AddField` operations needed. Do not run `makemigrations` when `InstituteSetting` is in scope.

**Manual migration template:**
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('invoices', '0069_certificationrequest_class_feedback')]
    operations = [
        migrations.AddField(
            model_name='targetmodel',
            name='new_field',
            field=models.TextField(blank=True),
        ),
    ]
```

### 4.3 Migration History (v3 additions)

| Migration | Change |
|-----------|--------|
| 0065 | Added `registration.created_at`, `welcome_email_sent`, `is_refunded` |
| 0066 | Added `CertificationRequest` model |
| 0067 | Added `Refund` model |
| 0068 | Added `CertificationRequest.class_rating` |
| 0069 | Added `CertificationRequest.class_feedback` (manual) |

---

## 5. Model Architecture Summary

| Model | Key Fields |
|-------|-----------|
| UserProfile | user (FK), role, phone, profile_picture |
| Registration | registration_number, student_name, created_at, is_refunded |
| Invoice | invoice_number, registration (FK), total_amount, status |
| InvoicePurchase | corporate mode purchase invoice |
| Certificate | certificate_number, registration (FK), course_name |
| CertificationRequest | token (UUID), status, class_feedback, class_rating |
| Refund | registration (FK), amount, status, confirmed_by, confirmed_at |
| InstituteSetting | pk=1 singleton; logo, stamp, banking |
| Course | 6 level price fields (oo_*, priv_*) |
| Coupon | code, discount_percentage, max_uses, expiry_date |

### Singleton Pattern

```python
class InstituteSetting(models.Model):
    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

---

## 6. Role-Based Access Control

### Role Matrix

| Feature | Admin | Sales Manager | Accounts | Sales Executive |
|---------|-------|--------------|----------|----------------|
| User management | ✓ | — | — | — |
| Audit log | ✓ | — | — | — |
| Settings | ✓ | — | — | — |
| Delete certificates | ✓ | — | — | — |
| Delete proposals | ✓ | — | — | — |
| Refund confirm | ✓ | — | ✓ | — |
| Revenue reports | ✓ | ✓ | ✓ | — |
| Edit registration (>1hr) | ✓ | ✓ | ✓ | — |
| All registrations | ✓ | ✓ | ✓ | own only |

### Edit Lock (Sales Executive)

```python
if role == 'sales_executive':
    if registration.created_at is None:
        locked = True  # legacy records
    else:
        locked = (timezone.now() - registration.created_at).total_seconds() > 3600
```

---

## 7. File Upload Paths

| Model Field | Upload Path |
|-------------|------------|
| InstituteSetting.company_logo | `institute/logo/` |
| InstituteSetting.stamp | `institute/stamp/` |
| InstituteSetting.authorization_logo | `institute/auth_logo/` |
| InstituteSetting.signature | `institute/signature/` |
| Proposal.logo | `proposals/logos/` |
| CertificationRequest.document | `cert_requests/docs/` |
| Refund.document | `refunds/docs/` |
| TrainerProfile.photo | `trainers/photos/` |

---

## 8. Email Triggers

| Trigger | Subject |
|---------|---------|
| Cert request sent | "Your Certificate is Ready — Please Confirm Your Course Completion" |
| Refund confirmed | "Refund Processed — {registration_number}" |
| Welcome email | "Welcome to Orbit Training Point" |
| Fee reminder | "Payment Reminder — Invoice {invoice_number}" |

All sent from `orbittrainingpoint@gmail.com` via Gmail SMTP app password.

---

*Document updated: 2026-07-13*
*Version 3.0 — updated stack, migration history, model list, role matrix, settings patterns*
