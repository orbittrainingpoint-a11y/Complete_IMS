# Module Guide
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06

---

## Module Overview

| # | Module | URL Prefix | Key Models | Notes |
|---|--------|-----------|-----------|-------|
| 1 | Authentication | `/accounts/`, `/signup/` | auth_user, UserProfile | Role-based |
| 2 | User Management | `/manage/users/` | UserProfile, SalesTarget | Admin only |
| 3 | Dashboard | `/`, `/dashboard/` | All | KPI overview |
| 4 | Invoices (Sales) | `/create_invoice/`, `/invoice/` | Invoice, InvoiceItem, InvoicePayment | Level-based pricing |
| 5 | Invoices (Purchase) | `/create_purchase_invoice/` | InvoicePurchase, InvoicePurchaseItem | |
| 6 | Registrations | `/register/`, `/student-dashboard/` | Registration, RegistrationCourse | |
| 7 | Corporate | `/corporate-registration/` | CorporateRegistration | |
| 8 | Courses | `/courses/` | Course, CourseContent | 6 level price fields |
| 9 | Certificates | `/certificates/` | Certificate, CertificateUpload, FormUpload | |
| 10 | Quotations | `/quotation/` | Quotation, QuotationItem, QuotationItemOverride | |
| 11 | Proposals | `/proposals/` | Proposal | Logo processing |
| 12 | CRM / Leads | External — Flask CRM app | Lead (Flask model) | SSO bridge |
| 13 | Trainer Profiles | `/trainer-profile/` | TrainerProfile | |
| 14 | Company Profiles | `/company-profile/` | CompanyProfile | |
| 15 | Coupons | `/coupons/` | Coupon | Expiry + max uses |
| 16 | Reports | `/reports/` | (computed) | Revenue, aging, VAT, enrollment |
| 17 | Training Schedule | `/schedule/` | TrainingSchedule | |
| 18 | Expenses | `/expenses/` | Expense | Category tracking |
| 19 | Notifications | `/notifications/` | Notification | In-app |
| 20 | Audit Log | `/audit/` | AuditLog | Admin only |
| 21 | Fee Reminders | `/fee-reminders/` | FeeReminderLog | |
| 22 | Company Portal | `/portal/company/`, `/admin-portal/` | CompanyPortalRequest, CompanyPortalAttendee | |
| 23 | Student Form Links | `/portal/student-links/`, `/portal/student/` | StudentFormLink | Token-based |
| 24 | CRM SSO | `/crm-jump/`, `/crm-auth/` | AuditLog | HMAC bridge |

---

## Module 1: Authentication

### Purpose
User login/logout with audit logging, and admin-only user account management.

### Key Files
- Views: `views.py` — `signup()`, `logout_view()`, `crm_auth()`
- Signals: `signals.py` — `on_user_logged_in()`, `on_user_logged_out()`
- Apps: `apps.py` — `ready()` imports signals
- Forms: `forms.py` — `SignUpForm`

### Business Logic
- Logout and login both write AuditLog entries including IP address
- IP resolved from `X-Forwarded-For` header (behind Apache proxy) then falls back to `REMOTE_ADDR`
- SSO login via `/crm-auth/` validates HMAC token (90-second TTL) before creating Django session

---

## Module 2: User Management

### Purpose
Admin-only user CRUD with role assignment and CRM sync.

### Key Files
- Views: `views.py` — `manage_users()`, `update_user_role()`, `edit_user()`, `delete_user()`, `change_user_password()`, `sync_all_crm_users()`, `set_targets()`

### Business Logic

**Roles:**
```python
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sales_manager', 'Sales Manager'),
        ('accounts', 'Accounts'),
        ('sales_executive', 'Sales Executive'),
    ]
```

**CRM Sync:** When role is `sales_manager` or `sales_executive`, `sync_user_to_crm()` writes to the CRM MySQL database directly using pymysql with werkzeug-compatible password hashing.

**Role mapping to CRM:**
- `sales_manager` → CRM role `sales_manager` (can_view_all_leads=1)
- `sales_executive` → CRM role `consultant` (can_view_all_leads=0)

**Sales Targets:** `SalesTarget` model; unique per (user, month). Stores target_amount (AED) and target_registrations count.

---

## Module 3: Dashboard

### Purpose
Central overview of business metrics and navigation hub.

### Key Files
- Views: `views.py` — `orbit_dashboard()`, `dashboard()`
- Context processor: `context_processors.py` — `sidebar_data()` injects unread notification count and user role

### Data Points

**orbit_dashboard (/):**
- Total registrations and monthly trend
- Individual vs corporate breakdown
- Recent invoices list
- Notification summary
- Sales target progress

**dashboard (/dashboard/) — invoice-focused:**
- Tabbed: Sales Invoices | Purchase Invoices
- Filter controls (number, name, date, status)
- Overdue invoice count and highlighting

---

## Module 4: Invoices (Sales)

### Purpose
Core financial transaction management.

### Key Logic

**Level-Based Pricing:**
```python
# Class type + level determine price
price = course.get_rate(invoice.class_type, invoice.level)
# class_type: online/offline/batch → uses oo_* fields
# class_type: private → uses priv_* fields
# level: intermediate / professional / advanced
```

**VAT Calculation (always added, never included):**
```python
# InvoiceItem
vat_rate = 0.05  # stored as decimal, default 0.05
vat_amount = subtotal * vat_rate  # NOT included in unit_price
total = subtotal + vat_amount
```

**Discount Cap:**
- Single course: max 20%
- Multi-course: max 30%
- Enforced in frontend JS and backend view validation

**Invoice total recalculation:**
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

**Tax Invoice Print:**
- A4 landscape format
- Left column: Terms & Conditions
- Right column: Totals + VAT + Signature blocks
- Previous Payment Reference section: only rendered when a prior invoice exists for the registration

**Payment Installments (InvoicePayment):**
- Multiple partial payment records per invoice
- Methods: cash/card/bank_transfer/cheque/payment_link/other
- Reference field for cheque numbers, transfer IDs

---

## Module 5: Student Registration

### Purpose
Enroll students and link to courses and invoices.

### Key Logic

**Registration Number (changes from prior docs):**
```python
# Format: OT/YY/### (no month — resets annually)
year = timezone.now().strftime('%y')
prefix = 'OC' if self.registration_type == 'OC' else 'OT'
last = Registration.objects.filter(
    registration_number__startswith=f"{prefix}/{year}/"
).order_by('-registration_number').first()
```

**CRM Pre-fill:** When accessed with `?crm_id=<id>`, the registration form fetches lead data from the CRM internal API and pre-fills the form fields.

**Token-based Self-Registration:** Staff generate `StudentFormLink` tokens. Students access `/portal/student/<token>/` and fill in personal details. The consultant name and pre-selected courses are locked by the token.

**Student Status:** `student_status` field: active / completed / dropped / suspended / pending. Updated via `/student/<pk>/status/`.

---

## Module 6: Courses

### Purpose
Manage the training course catalog with structured level pricing.

### Key Logic

**Course Pricing Fields:**

| Field | Description |
|-------|-------------|
| `oo_intermediate` | Online/Offline – Intermediate |
| `oo_professional` | Online/Offline – Professional |
| `oo_advanced` | Online/Offline – Advanced |
| `priv_intermediate` | Private – Intermediate |
| `priv_professional` | Private – Professional |
| `priv_advanced` | Private – Advanced |
| `rate` | Legacy standard rate |
| `batch_rate` | Legacy batch rate |
| `online_rate` | Legacy online rate |
| `private_rate` | Legacy private rate |

**Display rule:** Course list shows `—` (dash) instead of `0` for unset level price fields.

**get_rate() method:**
```python
def get_rate(self, class_type, level='intermediate'):
    level = level or 'intermediate'
    if class_type == 'private':
        return {
            'intermediate': self.priv_intermediate,
            'professional': self.priv_professional,
            'advanced': self.priv_advanced
        }.get(level, self.priv_intermediate)
    else:
        return {
            'intermediate': self.oo_intermediate,
            'professional': self.oo_professional,
            'advanced': self.oo_advanced
        }.get(level, self.oo_intermediate)
```

---

## Module 7: Certificates

### Purpose
Issue and track training completion certificates.

### Key Logic

**Certificate Number Generation:**
```python
# Looks up course by name to get code
course_code = course.code  # e.g., "PM"
# Format: {CODE}{REGISTER_NUMBER}  e.g., "PMOT/26/001"
self.certificate_number = f"{course_code}{self.register_number}"
# Duplicate: append "-1", "-2", etc.
```

**KHDA vs Regular:**
- Regular: Generated via Django form, printable template
- KHDA: Upload pre-issued PDF from KHDA authority
- File stored at: `khda_certificates/{student_name_slug}_{cert_number_slug}{ext}`

---

## Module 8: Quotations

### Purpose
Generate professional price quotations.

### Key Logic

**Venue Options:**
- `Orbit Training (In-House)` — at Orbit premises
- `Company Premises (External)` — at client site
- `online` — virtual delivery

**Price Override:** `QuotationItemOverride` (OneToOne to QuotationItem) allows admin/sales_manager to set a custom price per pax that overrides the course rate on the printed PDF.

**Coupon:** A `Coupon` FK can be linked to a quotation.

---

## Module 9: Proposals

### Purpose
Create branded training proposals for corporate clients.

### Key Logic

**Logo processing:**
```python
# Validates PNG format
# validates() check raises ValidationError if not .png extension
# Auto-generates white version for dark-background pages
# White logo stored at media/proposal_logos_white/
```

**Proposal Number:** `PROP-YYYY-####` (sequential per calendar year).

---

## Module 10: CRM / Lead Management

### Purpose
The CRM is a separate Flask application at `leads-management/`. It handles lead capture, follow-ups, meetings, and pipeline management. Integration with the Django ERP is via HMAC-signed SSO tokens.

### Key Integration Points

**ERP → CRM:** `/crm-jump/` generates token → redirects to CRM `/auto-login?t=<token>`.

**CRM → ERP Registration:** CRM generates token → redirects to ERP `/crm-auth/?t=<token>&crm_id=<id>&fn=<first>&ln=<last>&ph=<phone>&em=<email>` → ERP logs user in and pre-fills registration form.

**Lead Data Lookup:** ERP calls `GET {CRM_URL}/api/internal/lead/<id>` with `Authorization: Bearer <CRM_SSO_SECRET>` to fetch lead data for form pre-fill.

**User Sync:** Sales role users are synced from Django ERP to Flask CRM database on role change.

---

## Module 11: Trainer & Company Profiles

### Purpose
Maintain PDF profiles for trainers and companies to attach to proposals.

### Key Logic

**Company profile deletion:** Overrides `delete()` to also remove the PDF file from disk using `os.remove()`.

**Upload paths:** Slugified names used in upload paths:
- Trainer: `trainer_profiles/{name_slug}{ext}`
- Company: `company_profiles/{name_slug}{ext}`

---

## Module 12: Coupons

### Purpose
Create and manage discount coupon codes.

### Enhanced Fields

```python
class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateField(null=True, blank=True)   # NEW
    max_uses = models.IntegerField(null=True, blank=True)   # NEW
    used_count = models.IntegerField(default=0)             # NEW
    created_by = models.ForeignKey(User, ...)
```

**AJAX Validation:** `POST /validate-coupon/` returns `{valid, discount_percentage, message}`.

---

## Module 13: Reports

### Purpose
Business intelligence and financial reporting.

### Available Reports

| Report | URL | Key Data |
|--------|-----|----------|
| Revenue | `/reports/revenue/` | Revenue by period/consultant, CSV export |
| Aging | `/reports/aging/` | Overdue invoices grouped by age bracket |
| VAT | `/reports/vat/` | Output VAT collected vs input VAT on expenses |
| Enrollment | `/reports/enrollment/` | Registrations by period/consultant/course |
| Certificates | `/reports/certificates/` | Issued certs by period/type |
| Expenses | `/expenses/report/` | Expenses by category/vendor/date |

---

## Module 14: Training Schedule

### Purpose
Plan and track upcoming training sessions.

### TrainingSchedule Model

| Field | Type | Notes |
|-------|------|-------|
| course | FK | Linked course |
| title | Text | Batch/session name |
| class_type | Select | online/offline/batch/private |
| start_date, end_date | Date | Session period |
| start_time, end_time | Time | Optional |
| venue | Text | Location |
| max_capacity | Integer | Max students |
| instructor | Text | Instructor name |
| status | Select | upcoming/ongoing/completed/cancelled |

---

## Module 15: Expense Tracking

### Purpose
Record and categorize business expenses for financial reporting.

### Expense Model

| Category | Examples |
|----------|---------|
| venue | Room rental, facility hire |
| materials | Printed materials, equipment |
| instructor | Trainer fees |
| marketing | Ads, events |
| utilities | Electricity, internet |
| software | SaaS tools |
| travel | Transport, accommodation |
| salary | Staff costs |
| other | Miscellaneous |

VAT tracked separately (`vat_amount` field). Can be linked to a specific course.

---

## Module 16: Notifications

### Purpose
In-app notification center for staff.

### Notification Types
- `invoice_due` — upcoming due dates
- `overdue_invoice` — past due invoices
- `certificate_ready` — certificate issued
- `registration_new` — new student registered
- `target_alert` — sales target milestone
- `system` — system messages

**Delivery:** Notifications stored in `Notification` model. Unread count injected into every page via `sidebar_data` context processor. Staff see bell icon with badge.

---

## Module 17: Audit Log

### Purpose
Compliance and traceability — record who did what and when.

### AuditLog Model

```python
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Created'), ('update', 'Updated'), ('delete', 'Deleted'),
        ('payment', 'Payment Recorded'), ('status_change', 'Status Changed'),
        ('export', 'Exported'), ('login', 'Login'), ('logout', 'Logout'), ('view', 'Viewed'),
    ]
    user = models.ForeignKey(User, ...)
    action = models.CharField(...)
    model_name = models.CharField(...)
    object_id = models.CharField(...)
    object_repr = models.CharField(...)
    changes = models.TextField(...)
    ip_address = models.GenericIPAddressField(...)
    timestamp = models.DateTimeField(auto_now_add=True)
```

**Auto-logging:** Login/logout events captured automatically via Django signals in `signals.py`. `apps.py` imports signals in `ready()` so signals are connected at startup.

**Admin view:** `/audit/` — paginated, filterable log. Admin role required.

---

## Module 18: Company Portal

### Purpose
Allow corporate clients to self-register their company details and add training attendees after a deal is closed.

### Flow

1. Admin generates portal link: `/admin-portal/generate/` → creates `CompanyPortalRequest` with secure random token
2. Company accesses: `/portal/company/<token>/` — fills in company details (trade license, VAT cert, contact)
3. Company adds attendees: `/portal/company/<token>/attendees/`
4. Admin reviews and approves: `/admin-portal/<pk>/approve/`

### File Uploads

- Trade license: `portal/trade_license/{company_name_slug}_trade_license{ext}`
- VAT certificate: `portal/vat/{company_name_slug}_vat{ext}`

---

## Module 19: Student Form Links

### Purpose
Generate shareable, token-based links for student self-registration without exposing pricing.

### StudentFormLink Model

| Field | Notes |
|-------|-------|
| token | 64-char random URL-safe token |
| consultant | Locked consultant (FK to User) |
| consultant_name_locked | Stored name (immutable on the form) |
| pre_selected_courses | M2M to Course — pre-selected on form |
| is_active | Can be deactivated |
| expires_at | Optional expiry datetime |
| use_count | Incremented on each registration |

---

## Module 20: Fee Reminders

### Purpose
Track and log reminders sent to clients for overdue or upcoming invoices.

### FeeReminderLog Model

| Field | Notes |
|-------|-------|
| invoice | FK to Invoice (optional) |
| client_name, invoice_number | Denormalized for history |
| amount_due | Outstanding amount |
| due_date | Invoice due date |
| days_overdue | Negative = days until due |
| channel | system / email / manual |
| sent_by | FK to User |
| note | Optional note |

---

## Custom Template Filters Reference

`invoices/templatetags/custom_filters.py`:

### Filters (used with `|`)

| Filter | Usage | Description |
|--------|-------|-------------|
| `multiply` | `{{ qty\|multiply:price }}` | qty × price |
| `subtract` | `{{ total\|subtract:discount }}` | total − discount |
| `add` | `{{ a\|add:b }}` | a + b |
| `divide` | `{{ total\|divide:count }}` | total ÷ count |
| `calculate_course_price` | `{{ price\|calculate_course_price:discount }}` | Apply discount |
| `get_item` | `{{ list\|get_item:0 }}` | List index access |
| `subtract_percentage` | `{{ amount\|subtract_percentage:10 }}` | amount × 0.90 |
| `json_script` | `{{ items\|json_script }}` | Invoice items → JSON |
| `quotation_json_script` | `{{ items\|quotation_json_script }}` | Quotation items → JSON |

### Simple Tags (used with `{% %}`)

| Tag | Description |
|-----|-------------|
| `{% calculate_total_price registration %}` | Sum all RegistrationCourse prices |
| `{% calculate_running_due invoice ... %}` | Running balance tracker for installments |
| `{% calculate_total_vat registration %}` | Total VAT on registration courses |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
