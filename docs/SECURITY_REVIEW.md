# Security Review Document
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Review Type:** Internal Code Audit

---

## 1. Executive Summary

The Orbit ERP system implements basic Django security features (CSRF, session auth, login required) but has several configuration-level security issues that should be addressed before exposing the system beyond the internal network.

**Overall Risk Level: MEDIUM** (acceptable for internal LAN use; high risk if internet-facing)

---

## 2. Security Findings

### 2.1 CRITICAL Issues

#### SEC-01: Debug Mode Enabled in Production
**File:** `settings.py`  
**Line:** `DEBUG = True`

**Risk:** Full stack traces exposed to users on errors — reveals code, file paths, database structure, and configuration secrets.

**Fix:**
```python
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
```

---

#### SEC-02: Hardcoded Secret Key
**File:** `settings.py`
```python
SECRET_KEY = 'django-insecure--fysd-4zp5l@8+e+!...'
```

**Risk:** Session tokens, CSRF tokens, and signed cookies can be forged if key is known.

**Fix:**
```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError('DJANGO_SECRET_KEY environment variable not set')
```

---

#### SEC-03: Hardcoded Database Password
**File:** `settings.py`
```python
'PASSWORD': 'Orbit20232024',
```

**Risk:** Anyone with access to the source code has full database credentials.

**Fix:**
```python
'PASSWORD': os.environ.get('DB_PASSWORD', ''),
```

---

### 2.2 HIGH Issues

#### SEC-04: Root Database User
**Current:** Using `root` MySQL user with full privileges

**Risk:** A SQL injection vulnerability would have full access to all databases.

**Fix:**
```sql
CREATE USER 'orbit_app'@'localhost' IDENTIFIED BY 'StrongPassword123!';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbit_invoice.* TO 'orbit_app'@'localhost';
FLUSH PRIVILEGES;
```

---

#### SEC-05: ALLOWED_HOSTS Insufficient for Production
**Current:** `ALLOWED_HOSTS = ['10.255.254.23']`

**Risk:** If DEBUG=False and hostname not in ALLOWED_HOSTS, app returns 400. But current setting is IP-only which may break if accessed by hostname.

**Fix:**
```python
ALLOWED_HOSTS = [
    '10.255.254.23',
    'orbit.yourcompany.com',
    'localhost',
    '127.0.0.1',
]
```

---

#### SEC-06: Wrong Timezone Setting
**Current:** `TIME_ZONE = 'UTC'`

**Impact:** All timestamps stored/displayed in UTC, not UAE time (UTC+4). Invoice dates, certificate dates, and follow-up schedules will be off by 4 hours.

**Fix:**
```python
TIME_ZONE = 'Asia/Dubai'
```

---

### 2.3 MEDIUM Issues

#### SEC-07: No Rate Limiting on Login
Django's built-in auth has no brute-force protection.

**Fix:** Add `django-axes` or `django-ratelimit`:
```bash
pip install django-axes
```
```python
INSTALLED_APPS += ['axes']
MIDDLEWARE += ['axes.middleware.AxesMiddleware']
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
```

---

#### SEC-08: No HTTPS Enforcement
No HTTPS redirect or HSTS headers configured.

**Fix (production):**
```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

#### SEC-09: Admin Interface Exposed at Default Path
`/admin/` is accessible at the default Django admin URL.

**Fix:** Change admin URL path:
```python
# urls.py
urlpatterns = [
    path('secure-admin-orbit/', admin.site.urls),
    ...
]
```

---

#### SEC-10: File Upload — No MIME Type Validation
File uploads (certificates, forms, logos) validate file extension but not MIME type.

**Current:** ProposalForm validates `.png` extension and image dimensions. Other uploads have no type restriction.

**Risk:** Malicious files could be uploaded as PDFs.

**Fix:** Add server-side MIME type validation:
```python
import magic

def validate_file_type(file, allowed_types):
    file_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)
    if file_type not in allowed_types:
        raise ValidationError(f'Invalid file type: {file_type}')
```

---

### 2.4 LOW Issues

#### SEC-11: No Content Security Policy Header
**Fix:**
```python
# Using django-csp
pip install django-csp
MIDDLEWARE += ['csp.middleware.CSPMiddleware']
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "fonts.googleapis.com")
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")
```

---

#### SEC-12: Error Log Contains Sensitive Data
`debug.log` is in the application directory and may log sensitive request data.

**Fix:** Move log outside web root and restrict access.

---

#### SEC-13: No Account Lockout
Unlimited failed login attempts allowed.

**Fix:** See SEC-07 (django-axes).

---

## 3. Security Features Already Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| CSRF Protection | ✅ Active | `CsrfViewMiddleware` in middleware |
| Session Authentication | ✅ Active | Cookie-based sessions |
| Login Required | ✅ Active | `@login_required` on all views |
| Admin-Only Controls | ✅ Active | `@user_passes_test(is_admin_user)` |
| XSS Prevention | ✅ Active | Django auto-escapes template variables |
| SQL Injection | ✅ Protected | Django ORM uses parameterized queries |
| Clickjacking | ✅ Protected | `XFrameOptionsMiddleware` |
| Password Hashing | ✅ Active | Django's PBKDF2+SHA256 |

---

## 4. Priority Action List

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P1 | SEC-01: DEBUG=False | 30 min | Critical |
| P1 | SEC-02: Env var for SECRET_KEY | 30 min | Critical |
| P1 | SEC-03: Env var for DB password | 30 min | Critical |
| P2 | SEC-04: Dedicated DB user | 1 hour | High |
| P2 | SEC-06: Timezone to Asia/Dubai | 5 min | High |
| P3 | SEC-07: Rate limiting (django-axes) | 2 hours | Medium |
| P3 | SEC-08: HTTPS + HSTS | 2 hours | Medium |
| P3 | SEC-09: Admin URL rename | 10 min | Low |
| P4 | SEC-10: MIME validation | 4 hours | Medium |
| P4 | SEC-11: CSP headers | 2 hours | Low |

---

## 5. Quick Security Hardening Script

```python
# settings_production.py — import this instead of settings.py in production
import os
from .settings import *

DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

DATABASES['default']['PASSWORD'] = os.environ['DB_PASSWORD']
DATABASES['default']['USER'] = os.environ.get('DB_USER', 'orbit_app')

TIME_ZONE = 'Asia/Dubai'

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
```

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
