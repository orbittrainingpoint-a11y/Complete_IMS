# System Architecture Document
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25

---

## 1. Architecture Overview

Orbit ERP is a **monolithic Django web application** following the Model-View-Template (MVT) pattern. All business logic, data access, and rendering are handled within a single Django process. There are no microservices, external APIs, or message queues.

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
│              (Chrome / Firefox / Edge)                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/HTTPS Requests
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   WEB LAYER                                       │
│                                                                   │
│   Development:          │   Production:                           │
│   Django Dev Server     │   IIS + wfastcgi                        │
│   (port 8000)           │   (port 80/443)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │ WSGI
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   APPLICATION LAYER (Django 5.0.6)                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Middleware Stack                         │   │
│  │  Security → Session → Common → CSRF → Auth → Messages    │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                          │                                        │
│  ┌───────────┐    ┌──────▼──────┐    ┌──────────────────────┐   │
│  │  URL      │───►│   Views     │───►│    Templates         │   │
│  │  Router   │    │  (68+ fns)  │    │  (78 HTML files)     │   │
│  │ (86 URLs) │    │  views.py   │    │  DTL + Bootstrap 5   │   │
│  └───────────┘    └──────┬──────┘    └──────────────────────┘   │
│                          │                                        │
│                   ┌──────▼──────┐                                │
│                   │   Forms     │                                 │
│                   │  (25 forms) │                                 │
│                   │  forms.py   │                                 │
│                   └──────┬──────┘                                │
│                          │                                        │
│                   ┌──────▼──────┐                                │
│                   │   Models    │                                 │
│                   │  (22 models)│                                 │
│                   │  Django ORM │                                 │
│                   └──────┬──────┘                                │
└──────────────────────────┼──────────────────────────────────────┘
                           │ SQL Queries
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    DATA LAYER                                     │
│                                                                   │
│              MySQL 8.0 / MariaDB 10.4                            │
│              Database: orbit_invoice                             │
│              35 Tables / ~11,000+ Records                        │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  FILE STORAGE LAYER                               │
│                                                                   │
│              Local Filesystem: media/ directory                  │
│              Size: ~193MB                                        │
│              Types: PDF, PNG, Images                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Application Layer Detail

### 3.1 Request-Response Flow

```
Browser Request
     │
     ▼
URL Dispatcher (urls.py)
  ├── invoice_project/urls.py  [root router]
  │     ├── /admin/          → Django Admin
  │     ├── /accounts/       → django.contrib.auth.urls
  │     └── /               → invoices/urls.py
  │
  └── invoices/urls.py  [86 patterns]
        │
        ▼
   View Function (views.py)
        │
        ├── Authentication Check (@login_required)
        ├── Admin Check (@user_passes_test) if needed
        │
        ├── GET Request:
        │     ├── Query database via ORM
        │     ├── Prepare context dict
        │     └── Render template → HTML Response
        │
        └── POST Request:
              ├── Validate CSRF token
              ├── Instantiate Form with POST data
              ├── form.is_valid()
              │     ├── True: Save to DB → Redirect
              │     └── False: Re-render form with errors
              └── Return Response
```

### 3.2 Data Flow for Invoice Creation

```
User fills Invoice Form
     │
     ▼
POST /create_invoice/
     │
     ▼
views.create_invoice()
  ├── InvoiceForm(request.POST)
  ├── form.is_valid()
  ├── Generate invoice_number (YY/MM/###)
  ├── invoice = form.save()
  └── Redirect to /add_invoice_items/{id}/
     │
     ▼
views.add_invoice_items()
  ├── InvoiceItemFormSet(request.POST)
  ├── For each item:
  │     ├── item.invoice = invoice
  │     ├── item.save()
  │     └── Calculate subtotal + VAT
  └── invoice.calculate_total_amount()
  └── invoice.save()
     │
     ▼
  Invoice Complete
```

---

## 4. Module Architecture

```
invoices/ (Django App)
├── models.py
│   ├── Authentication Models (via auth_user FK)
│   ├── Core Business Models
│   │   ├── Client
│   │   ├── Course ──────────────────────────────┐
│   │   └── CourseContent                        │
│   │                                            │
│   ├── Registration Models                      │
│   │   ├── Registration ←───────────────────────┤
│   │   ├── RegistrationCourse (M2M through)      │
│   │   ├── CorporateRegistration (1-to-1)        │
│   │   ├── CertificateUpload (1-to-1)            │
│   │   └── FormUpload (1-to-1)                   │
│   │                                            │
│   ├── Financial Models                         │
│   │   ├── Invoice ←───────────────────────────┤
│   │   ├── InvoiceItem                          │
│   │   ├── InvoicePurchase                      │
│   │   ├── InvoicePurchaseItem                  │
│   │   ├── Quotation ←──────────────────────────┤
│   │   └── QuotationItem                        │
│   │                                            │
│   ├── Document Models                          │
│   │   ├── Certificate                          │
│   │   ├── Proposal ←───────────────────────────┤
│   │   ├── TrainerProfile                       │
│   │   └── CompanyProfile                       │
│   │                                            │
│   ├── CRM Models                               │
│   │   ├── Lead ←───────────────────────────────┘
│   │   ├── FollowUp
│   │   ├── Comment
│   │   ├── Meeting
│   │   ├── Pipeline
│   │   └── PipelineStage
│   │
│   └── Utility Models
│       └── Coupon
│
├── views.py (68+ functions grouped by domain)
│   ├── auth_views: signup, logout_view
│   ├── dashboard_views: dashboard, orbit_dashboard
│   ├── invoice_views: create_invoice, edit_invoice, ...
│   ├── registration_views: registration_form, edit_registration, ...
│   ├── course_views: course_list, course_create, ...
│   ├── certificate_views: certificate_dashboard, ...
│   ├── quotation_views: create_quotation, ...
│   ├── proposal_views: create_proposal, ...
│   ├── lead_views: lead_dashboard, create_lead, ...
│   ├── profile_views: create_trainer_profile, ...
│   ├── coupon_views: coupon_list, validate_coupon, ...
│   └── ajax_views: get_course_details, get_registration_details, ...
│
├── forms.py (25 form classes)
│   ├── ModelForms (most forms)
│   └── Custom validation logic
│
├── urls.py (86 URL patterns)
│
└── templatetags/
    └── custom_filters.py (10 filters + 3 tags)
```

---

## 5. Database Layer

### 5.1 ORM Query Patterns

**Standard CRUD:**
```python
# Create
invoice = Invoice.objects.create(...)

# Read (single)
invoice = Invoice.objects.get(pk=pk)

# Read (filtered list)
invoices = Invoice.objects.filter(
    user=request.user,
    status='Full Payment'
).order_by('-date')

# Update
invoice.status = 'Full Payment'
invoice.save()

# Delete
invoice.delete()
```

**Aggregation (Dashboard):**
```python
from django.db.models import Sum, Count
total_revenue = Invoice.objects.filter(
    date__month=current_month
).aggregate(total=Sum('total_amount'))['total']
```

**Related Objects:**
```python
# Get all courses for a registration
courses = registration.registrationcourse_set.all()

# Get invoice with client info (JOIN)
invoices = Invoice.objects.select_related('client', 'registration')
```

### 5.2 Transaction Safety

Django wraps each view in an implicit transaction. For multi-step operations (invoice + items), Django's `atomic()` should be used:

```python
from django.db import transaction

with transaction.atomic():
    invoice = Invoice.objects.create(...)
    for item_data in items:
        InvoiceItem.objects.create(invoice=invoice, **item_data)
    invoice.calculate_total_amount()
    invoice.save()
```

---

## 6. Frontend Architecture

### 6.1 Template Hierarchy

```
base_generic.html (main layout)
├── head section (Bootstrap, Font Awesome, Poppins)
├── sidebar navigation
│   ├── Dashboard links
│   ├── Module links
│   └── User info
├── main content area
│   └── {% block content %}
│         └── (page-specific content)
│         {% endblock %}
├── message display
└── scripts (jQuery, Bootstrap JS, Select2)
    └── {% block extra_scripts %}
          └── (page-specific JS)
          {% endblock %}
```

### 6.2 AJAX Pattern

```javascript
// Example: Validate coupon
fetch('/validate-coupon/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ code: couponCode })
})
.then(response => response.json())
.then(data => {
    if (data.valid) {
        applyDiscount(data.discount_percentage);
    }
});
```

### 6.3 CSS Framework Usage

| Framework | Version | Usage |
|-----------|---------|-------|
| Bootstrap | 5.1.3 / 5.3.0 | Grid, components, utilities |
| Font Awesome | 5.15.3 / 6.0.0 | Action icons |
| Bootstrap Icons | 1.7.2 | Additional icons |
| Select2 | Latest | Enhanced dropdowns |
| Google Fonts | — | Poppins typeface |

---

## 7. Security Architecture

### 7.1 Authentication Flow

```
Request
  │
  ▼
@login_required decorator
  │
  ├── No session → Redirect to /accounts/login/?next=<url>
  │
  └── Valid session
        │
        ▼
        @user_passes_test(is_admin_user)  [if admin-only view]
          │
          ├── Not admin → Redirect with 403 message
          │
          └── Admin confirmed → Execute view
```

### 7.2 CSRF Protection

All HTML forms include `{% csrf_token %}`. AJAX POST requests send `X-CSRFToken` header.

### 7.3 Input Validation

1. **Django Form validation** — type checking, required fields, custom validators
2. **Model-level constraints** — unique keys, FK constraints, check constraints
3. **Template escaping** — Django auto-escapes all template variables (XSS prevention)

---

## 8. File Storage Architecture

```
media/  (MEDIA_ROOT)
├── certificates/          ← invoices_certificateupload.certificate_file
├── course_contents/       ← invoices_coursecontent.file
├── khda_certificates/     ← invoices_certificate.uploaded_certificate (KHDA)
├── proposal_logos/        ← invoices_proposal.logo
├── proposal_logos_white/  ← invoices_proposal.logo_white_url
├── registration_forms/    ← invoices_formupload.form_file
├── trainer_profiles/      ← invoices_trainerprofile.profile_pdf
└── company_profiles/      ← invoices_companyprofile.company_pdf
```

**File Access:** Via `/media/<path>` URL (served by Django in development, by IIS/nginx in production)

---

## 9. Auto-Numbering System

All business documents use the same pattern:

```python
def generate_number(prefix, model_class, field_name):
    from datetime import datetime
    now = datetime.now()
    # prefix = YY/MM for invoices, PROP-YYYY for proposals
    
    last = model_class.objects.filter(
        **{f'{field_name}__startswith': prefix}
    ).order_by(f'-{field_name}').first()
    
    if last:
        last_seq = int(getattr(last, field_name).split('/')[-1])
        next_seq = last_seq + 1
    else:
        next_seq = 1
    
    return f"{prefix}/{next_seq:03d}"
```

| Document | Format | Example |
|----------|--------|---------|
| Invoice | YY/MM/### | 24/06/001 |
| Purchase Invoice | YY/MM/### | 24/06/001 |
| Quotation | YY/MM/### | 24/06/001 |
| Registration (Individual) | OT/YY/MM/### | OT/24/06/001 |
| Registration (Corporate) | OC/YY/MM/### | OC/24/06/001 |
| Certificate | {CODE}/YY/### | PM/24/001 |
| Proposal | PROP-YYYY-#### | PROP-2024-0001 |

---

## 10. Scalability Considerations

### Current Limitations

| Limitation | Impact | Solution |
|------------|--------|---------|
| Single database server | No read replicas | Add read replica |
| No caching layer | All requests hit DB | Add Redis/Memcached |
| Local file storage | No CDN | Move to S3/Azure Blob |
| Monolithic architecture | Cannot scale modules independently | Modularize or microservices |
| No background tasks | Long operations block requests | Add Celery + Redis |
| No connection pooling | DB connections per request | Add PgBouncer/MySQL Proxy |

### Recommended Improvements

```
Current:    Browser → Django → MySQL (single server)

Improved:   Browser → Nginx (static files)
                    → Load Balancer
                    → Django App (multiple instances)
                    → Redis (cache + session)
                    → MySQL Primary + Replica
                    → S3 (media files)
```

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
