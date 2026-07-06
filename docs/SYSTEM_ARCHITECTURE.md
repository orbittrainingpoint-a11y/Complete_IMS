# System Architecture Document
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06

---

## 1. Architecture Overview

Orbit ERP is a two-application system following a Django + Flask hybrid architecture:

1. **Django ERP** (core back-office) — Monolithic Django application following the Model-View-Template (MVT) pattern.
2. **Flask CRM** (lead pipeline) — Separate Flask application with its own database.

The two applications share user accounts via an HMAC-signed SSO token bridge and are co-deployed on the same VPS behind an Apache reverse proxy.

---

## 2. High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                               │
│                  (Chrome / Firefox / Edge)                         │
└──────────────────────────────┬────────────────────────────────────┘
                               │ HTTPS
                               │
┌──────────────────────────────▼────────────────────────────────────┐
│                Apache Web Server (VPS)                             │
│           orbittraining.online — SSL Termination                  │
│                                                                    │
│  ProxyPass /       → http://127.0.0.1:8001/  (Django ERP)         │
│  ProxyPass /crm/   → http://127.0.0.1:5001/  (Flask CRM)          │
│  X-Forwarded-Proto: https                                         │
└──────────┬───────────────────────────┬────────────────────────────┘
           │                           │
┌──────────▼───────────┐  ┌────────────▼─────────────────────────┐
│   Django ERP          │  │   Flask CRM                           │
│   Gunicorn :8001      │  │   Gunicorn :5001                      │
│   Django 5.0.6        │  │   Flask + SQLAlchemy                  │
│   orbit-system/       │  │   leads-management/                   │
│   invoice_project/    │  │   app.py, routes.py, models.py        │
└──────────┬────────────┘  └────────────┬─────────────────────────┘
           │                            │
           │  ┌─────────────────────────┘
           │  │
┌──────────▼──▼────────────────────────────────────────────────────┐
│                  MySQL 8 / MariaDB                                 │
│                                                                    │
│   orbit_invoice DB  (Django ERP data)                             │
│   leads DB          (Flask CRM data)                              │
└───────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                   File Storage (Local)                            │
│               media/ directory (~200MB+)                         │
│   certificates/, course_contents/, khda_certificates/            │
│   proposal_logos/, proposal_logos_white/                         │
│   registration_forms/, trainer_profiles/, company_profiles/      │
│   portal/trade_license/, portal/vat/                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Django ERP Application Layer

### 3.1 Request-Response Flow

```
Browser Request
     │
     ▼
URL Dispatcher (invoice_project/urls.py)
  ├── /admin/          → Django Admin
  ├── /accounts/       → django.contrib.auth.urls
  └── /               → invoices/urls.py  [135 patterns]
        │
        ▼
   Middleware Stack
   Security → Session → CSRF → Auth → Messages → Clickjacking
        │
        ▼
   View Function (views.py)
        │
        ├── @login_required check → redirect to login if no session
        ├── @user_passes_test(is_admin_user) if admin-only view
        │
        ├── GET:  Query DB via ORM → Build context → Render template → Response
        └── POST: CSRF check → Form validation → Save to DB → Redirect / Re-render
```

### 3.2 Signals and App Startup

```python
# invoices/apps.py
class InvoicesConfig(AppConfig):
    def ready(self):
        import invoices.signals  # Connects login/logout audit signals

# invoices/signals.py
@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    AuditLog.objects.create(action='login', user=user, ip_address=_get_ip(request))

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    AuditLog.objects.create(action='logout', user=user, ip_address=_get_ip(request))
```

`_get_ip()` reads `HTTP_X_FORWARDED_FOR` header first (because Apache proxy adds this header), then falls back to `REMOTE_ADDR`.

### 3.3 Context Processors

`invoices/context_processors.py` — `sidebar_data()` injects into every template:
- `unread_notification_count` — count of unread notifications for current user
- `user_role` — current user's profile role
- Navigation state data

---

## 4. SSO Bridge Architecture

The SSO bridge enables one-click navigation between the two applications without requiring separate logins.

```
ERP User clicks "Open CRM"
     │
     ▼
/crm-jump/ view
  ├── Generate HMAC token:
  │     payload = base64url({"u": username, "t": unix_timestamp})
  │     sig = hmac_sha256(CRM_SSO_SECRET, payload)[:32]
  │     token = f"{payload}.{sig}"
  └── Redirect to: {CRM_URL}/auto-login?t=<token>
     │
     ▼ (CRM verifies token, logs user into Flask session)

CRM User clicks "Register in ERP"
     │
     ▼
CRM generates its own HMAC token → Redirect to ERP /crm-auth/
     │
     ▼
/crm-auth/ view
  ├── Verify token (90-second TTL, HMAC signature)
  ├── Look up ERP User by username
  ├── Call login(request, erp_user)
  └── If crm_id present:
        Fetch lead data from CRM internal API (/api/internal/lead/<id>)
        Redirect to /register/?crm_id=<id>&fn=<first>&ln=<last>&ph=<phone>&em=<email>&ci=<course_id>
      Else:
        Redirect to dashboard or next parameter

Shared secret: CRM_SSO_SECRET (set in both .env.erp and .env.crm)
```

### 4.1 CRM Internal API Call

```python
# views.py — api_crm_lead_lookup()
url = f"{CRM_URL}/api/internal/lead/{lead_id}"
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {CRM_SSO_SECRET}'})
# Returns: {"id", "full_name", "status", "phone", "email", "interested_course"}
```

---

## 5. Model Architecture

```
invoices/ (Django App — models.py)
│
├── Core Business
│   ├── Client (TRN field added)
│   ├── Course (6 level-based price fields + 4 legacy fields)
│   └── CourseContent
│
├── Registration
│   ├── Registration (level, student_status fields added)
│   ├── RegistrationCourse (M2M through)
│   ├── CorporateRegistration (1:1)
│   ├── CertificateUpload (1:1)
│   ├── FormUpload (1:1)
│   ├── StudentFormLink (token-based self-registration)
│   ├── CompanyPortalRequest (corporate self-registration)
│   └── CompanyPortalAttendee
│
├── Financial
│   ├── Invoice (level field added)
│   ├── InvoiceItem
│   ├── InvoicePayment (NEW — installment records)
│   ├── InvoicePurchase
│   ├── InvoicePurchaseItem
│   ├── Quotation (coupon FK added)
│   ├── QuotationItem
│   └── QuotationItemOverride (NEW)
│
├── Documents
│   ├── Certificate
│   ├── Proposal
│   ├── TrainerProfile
│   └── CompanyProfile
│
├── Operations
│   ├── TrainingSchedule (NEW)
│   ├── Expense (NEW)
│   └── FeeReminderLog (NEW)
│
├── Users & Access
│   ├── UserProfile (NEW — role, phone)
│   └── SalesTarget (NEW)
│
├── Notifications & Audit
│   ├── Notification (NEW)
│   └── AuditLog (NEW — auto-populated via signals)
│
├── CRM (Legacy — Django CRM was superseded by Flask CRM)
│   ├── Lead
│   ├── FollowUp
│   ├── Comment
│   ├── Meeting
│   ├── Pipeline
│   └── PipelineStage
│
└── Utility
    └── Coupon (expiry_date, max_uses, used_count added)
```

---

## 6. Frontend Architecture

### 6.1 Template Hierarchy

```
base_generic.html (main layout)
├── <head>: Bootstrap, Font Awesome, Poppins, Select2
├── sidebar navigation
│   ├── Dashboard, Registrations, Invoices...
│   ├── Notification bell (unread count from context processor)
│   └── User info and role badge
├── main content area — {% block content %}
├── message display (Django messages framework)
└── scripts — {% block extra_scripts %}
```

### 6.2 Level-Based Pricing JS Flow

```javascript
// On class_type or level change in invoice/registration form:
// 1. Fetch course pricing via AJAX
fetch('/get_course_details/?course_id=<id>&class_type=<type>&level=<level>')
// 2. Populate unit_price with appropriate oo_* or priv_* value
// 3. Recalculate totals

// Discount cap enforcement (frontend):
const maxDiscount = itemCount > 1 ? 30 : 20;
if (discountValue > maxDiscount) {
    showError(`Discount cannot exceed ${maxDiscount}%`);
    discountField.value = maxDiscount;
}
```

### 6.3 CSS Framework Usage

| Framework | Version | Usage |
|-----------|---------|-------|
| Bootstrap | 5.1.3 / 5.3.0 | Grid, components, utilities |
| Font Awesome | 5.15.3 / 6.0.0 | Action icons |
| Bootstrap Icons | 1.7.2 | Additional icons |
| Select2 | Latest CDN | Enhanced dropdowns |
| Google Fonts | — | Poppins typeface |

---

## 7. Security Architecture

### 7.1 Authentication Flow

```
HTTP Request
     │
     ▼
@login_required
  │
  ├── No session → Redirect to /accounts/login/?next=<url>
  │
  └── Valid session
        │
        ▼
        @user_passes_test(is_admin_user)  [if admin-only view]
          │
          ├── Not admin → Redirect with permission error
          │
          └── Admin confirmed → Execute view
```

`is_admin_user()`:
```python
def is_admin_user(user):
    try:
        return user.profile.role in ('admin',) or user.is_superuser
    except Exception:
        return user.is_superuser
```

### 7.2 CSRF Protection

All HTML forms: `{% csrf_token %}`. AJAX: `X-CSRFToken` header.

### 7.3 SSO Token Security

- Algorithm: HMAC-SHA256
- Signature truncated to 32 hex chars
- Payload: base64url-encoded JSON `{"u": username, "t": unix_timestamp}`
- TTL: 90 seconds (verified on receipt)
- `hmac.compare_digest()` used for constant-time comparison

### 7.4 IP Address Resolution

```python
def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or None
```

Django is configured with `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` to trust Apache's forwarded headers.

---

## 8. Data Flow for Key Operations

### 8.1 Invoice Creation with Level-Based Pricing

```
User selects: Course + Class Type + Level
     │
     ▼
AJAX: GET /get_course_details/?course_id=X&class_type=online&level=professional
     │
     ▼
Returns: course.oo_professional (AED price)
     │
     ▼
User fills invoice header → POST /create_invoice/
  Invoice.save() → auto-generate invoice_number YY/MM/###
                 → total_amount = 0 initially
     │
     ▼
POST /add_invoice_items/{id}/
  For each item:
    item.unit_price = course.get_rate(class_type, level)
    item.vat_rate = 0.05
  invoice.calculate_total_amount()
    = Σ(get_rate × qty × persons × (1 − disc%)) × 1.05
  invoice.save()
```

### 8.2 CRM → ERP Registration Flow

```
Staff on CRM lead page → "Register in ERP" button
     │
     ▼
CRM: generate SSO token with {u: username, t: now}
     → redirect to ERP /crm-auth/?t=<token>&crm_id=42&fn=John&ln=Doe...
     │
     ▼
ERP /crm-auth/ view:
  1. Verify HMAC token (90s TTL)
  2. login(request, user)
  3. Return redirect to /register/?crm_id=42&fn=John&ln=Doe...
     │
     ▼
Registration form loads:
  GET /api/crm-lead/42/ → ERP proxies to CRM API → returns lead data
  Form auto-filled: name, phone, email, course
     │
     ▼
Staff completes form, submits → new Registration created
```

### 8.3 Audit Log Flow

```
User logs in via POST /accounts/login/
     │
     ▼
Django auth sends user_logged_in signal
     │
     ▼
signals.py on_user_logged_in():
  AuditLog.objects.create(
    user=user, action='login',
    model_name='User', object_id=user.pk,
    object_repr=user.username,
    ip_address=X-Forwarded-For or REMOTE_ADDR
  )
```

---

## 9. File Storage Architecture

```
media/  (MEDIA_ROOT = orbit-system/invoice_project/media/)
├── certificates/               ← CertificateUpload (student-named)
├── course_contents/            ← CourseContent files
├── khda_certificates/          ← Certificate.uploaded_certificate (KHDA)
├── proposal_logos/             ← Proposal.logo (PNG only)
├── proposal_logos_white/       ← Auto-generated white version
├── registration_forms/         ← FormUpload (student-named)
├── trainer_profiles/           ← TrainerProfile.profile_pdf (name-slugged)
├── company_profiles/           ← CompanyProfile.company_pdf (name-slugged)
└── portal/
    ├── trade_license/          ← CompanyPortalRequest.trade_license_doc
    └── vat/                    ← CompanyPortalRequest.vat_certificate
```

**File Access:** Via `/media/<path>` URL. In development, Django serves media files (configured in root urls.py). In production, Apache serves them directly.

---

## 10. Auto-Numbering Architecture

All business document numbers are generated in model `.save()` methods:

```python
# Example: Invoice (YY/MM/### — resets monthly)
now = timezone.now()
year, month = now.strftime('%y'), now.strftime('%m')
last = Invoice.objects.filter(
    invoice_number__startswith=f"{year}/{month}/"
).order_by('-invoice_number').first()
new_number = (int(last.invoice_number.split('/')[-1]) + 1) if last else 1
self.invoice_number = f"{year}/{month}/{new_number:03d}"

# Registration (OT/YY/### — resets annually, no month)
year = timezone.now().strftime('%y')
last = Registration.objects.filter(
    registration_number__startswith=f"OT/{year}/"
).order_by('-registration_number').first()
new_number = (int(last.registration_number.split('/')[-1]) + 1) if last else 1
self.registration_number = f"OT/{year}/{new_number:03d}"
```

---

## 11. Production Deployment Summary

| Component | Local Dev | VPS Production |
|-----------|-----------|----------------|
| Django ERP port | 8000 | 8001 (Gunicorn) |
| Flask CRM port | 5000 | 5001 (Gunicorn) |
| Web server | Django dev server | Apache reverse proxy |
| Domain | localhost | orbittraining.online (HTTPS) |
| Database | MariaDB (XAMPP) | MySQL 8 |
| Env config | Local settings | `/var/www/html/orbit/.env.erp` and `.env.crm` |
| Services | Manual start | `orbit-erp.service`, `orbit-crm.service` (systemd) |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
