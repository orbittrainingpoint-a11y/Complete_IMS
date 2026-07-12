# Module Guide
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13

---

## Module Overview

| # | Module | URL Prefix | Key Models | Notes |
|---|--------|-----------|-----------|-------|
| 1 | Authentication | `/accounts/`, `/signup/` | auth_user, UserProfile | Role-based |
| 2 | User Management | `/manage/users/` | UserProfile, SalesTarget | Admin only |
| 3 | Dashboard | `/`, `/dashboard/` | All | KPI overview |
| 4 | Invoices (Sales) | `/create_invoice/`, `/invoice/` | Invoice, InvoiceItem, InvoicePayment | Level-based pricing |
| 5 | Invoices (Purchase) | `/create_purchase_invoice/` | InvoicePurchase, InvoicePurchaseItem | Corporate mode hides Number of Persons |
| 6 | Registrations | `/register/`, `/student-dashboard/` | Registration, RegistrationCourse | 1-hr edit lock for sales_executive |
| 7 | Corporate | `/corporate-registration/` | CorporateRegistration | |
| 8 | Courses | `/courses/` | Course, CourseContent | 6 level price fields |
| 9 | Certificates | `/certificates/` | Certificate, CertificateUpload, FormUpload, CertificationRequest | Request flow + admin delete |
| 10 | Quotations | `/quotation/` | Quotation, QuotationItem, QuotationItemOverride | No PI button from quotation page |
| 11 | Proposals | `/proposals/` | Proposal | Redesigned UI |
| 12 | CRM / Leads | External — Flask CRM app | Lead (Flask model) | SSO bridge; safe lead delete |
| 13 | Trainer Profiles | `/trainer-profile/` | TrainerProfile | |
| 14 | Company Profiles | `/company-profile/` | CompanyProfile | |
| 15 | Coupons | `/coupons/` | Coupon | Expiry + max uses |
| 16 | Reports | `/reports/` | (computed) | Revenue/aging/VAT/enrollment; excludes refunded |
| 17 | Training Schedule | `/schedule/` | TrainingSchedule | |
| 18 | Expenses | `/expenses/` | Expense | Category tracking |
| 19 | Notifications | `/notifications/` | Notification | In-app |
| 20 | Audit Log | `/audit/` | AuditLog | Admin only |
| 21 | Fee Reminders | `/fee-reminders/` | FeeReminderLog | |
| 22 | Company Portal | `/portal/company/`, `/admin-portal/` | CompanyPortalRequest, CompanyPortalAttendee | |
| 23 | Student Form Links | `/portal/student-links/`, `/portal/student/` | StudentFormLink | Token-based |
| 24 | CRM SSO | `/crm-jump/`, `/crm-auth/` | AuditLog | HMAC bridge |
| 25 | **Refunds** | `/registrations/<pk>/refund/`, `/refunds/` | Refund | **v3 — new** |
| 26 | **Certificate Requests** | `/cert-request/`, `/cert-requests/` | CertificationRequest | **v3 — new** |
| 27 | **Institute Settings** | `/settings/` | InstituteSetting | **v3 — new, admin only** |

---

## Module 1: Authentication

### Purpose
User login/logout with audit logging, and admin-only user account management.

### Key Files
- Views: `views.py` — `signup()`, `logout_view()`, `crm_auth()`
- Signals: `signals.py` — `on_user_logged_in()`, `on_user_logged_out()`
- Apps: `apps.py` — `ready()` imports signals
- Forms: `forms.py` — `SignUpForm`
- Template: `registration/signup.html` — extends `base_generic.html`; gradient hero banner; role selection cards with descriptions; live password match indicator

### Business Logic
- Logout and login both write AuditLog entries including IP address
- IP resolved from `X-Forwarded-For` header then falls back to `REMOTE_ADDR`
- SSO login via `/crm-auth/` validates HMAC token (90-second TTL) before creating Django session
- Add User form uses role cards (Sales Executive / Sales Manager / Accounts / Admin) instead of plain dropdown

---

## Module 2: User Management

### Purpose
Admin-only user CRUD with role assignment and CRM sync.

### Key Files
- Views: `manage_users()`, `update_user_role()`, `edit_user()`, `delete_user()`, `change_user_password()`, `sync_all_crm_users()`, `set_targets()`

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

### Data Points

**orbit_dashboard (/):**
- Total registrations and monthly trend
- Individual vs corporate breakdown
- Recent invoices list
- Notification summary
- Sales target progress
- All revenue figures exclude `is_refunded=True` registrations

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
price = course.get_rate(invoice.class_type, invoice.level)
# class_type: online/offline/batch → uses oo_* fields
# class_type: private → uses priv_* fields
# level: intermediate / professional / advanced
```

**VAT (always added, never included):**
```python
vat_amount = subtotal * 0.05
total = subtotal + vat_amount
```

**Discount Cap:** 20% single-course, 30% multi-course — enforced JS + server.

**Revenue exclusion:**
```python
# All revenue queries add:
.exclude(registration__is_refunded=True)
```

---

## Module 5: Student Registration

### Purpose
Enroll students and link to courses and invoices.

### 1-Hour Edit Lock (Sales Executive)
```python
if role == 'sales_executive':
    if registration.created_at is None:
        locked = True  # legacy records with no created_at are always locked
    else:
        locked = (timezone.now() - registration.created_at).total_seconds() > 3600
    if locked:
        messages.error(request, "Registrations can only be edited within 1 hour...")
        return redirect('student_dashboard')
```
Lock applies to both `edit_registration` and `edit_corporate_registration`.

### Registration Number Format
`OT/YY/###` (individual) — resets annually, not monthly.
`OC/YY/###` (corporate) — same pattern.

### CRM Pre-fill
`?crm_id=<id>` triggers live lookup from CRM internal API and pre-populates the form.

### Refunded Registrations
- Shown with 45% opacity, light-red background, REFUNDED badge in student dashboard
- Red banner on registration detail page
- Excluded from all revenue totals and executive performance metrics

---

## Module 6: Corporate Registration & Purchase Invoices

### Corporate PI — Number of Persons
In corporate mode on the create purchase invoice page:
- `#wrap_number_of_person` is **hidden**
- A read-only blue info box shows "Total Candidates: X persons" calculated from linked company candidates
- `#id_number_of_person` is forced to `1` to prevent double-multiplication
- In individual mode the field shows normally

**Rationale:** Corporate PI qty per course is already set to `candidate_count`. If Number of Persons were left editable and set to e.g. 5, totals would multiply by 5 again.

---

## Module 7: Certificates

### Purpose
Issue and track training completion certificates.

### Certificate Number Generation
```python
# Format: {COURSE_CODE}{REGISTER_NUMBER}  e.g., PMOT/26/001
# Duplicates appended with -1, -2, etc.
```

### Admin Delete
Admin can delete a certificate from the certificate dashboard using the trash button (POST to `/certificates/<pk>/delete/`). Requires admin role. Confirmation modal shown before submission.

### Certificate Request Flow (v3)

```
Staff → Registration Detail → "Send Certificate Request" button
  → Sends token link to client email
  → Client opens /cert-request/<uuid:token>/
  → Client selects: Completed / Not Completed
  → If Completed: fills date, rates class (radio), writes class feedback (required textarea)
  → Submit → admin notified
  → Admin reviews at /cert-requests/?status=submitted
  → Admin enters From Date, End Date, Grade → Generate Certificate
```

**Status Pills on Registration Detail:**
- `pending` → "Cert Request Sent"
- `submitted` → "Submitted by Client"
- `approved` → "Certificate Generated"
- `rejected` → "Request Rejected"
- No request → "Certificate Pending" (fallback)

**`class_feedback` field:** Required textarea on public form. Submit button stays disabled until date + rating + feedback all filled. Admin sees feedback highlighted in blue on both the cert requests admin page and the registration detail.

---

## Module 8: Quotations

### Purpose
Generate professional price quotations.

### Venue Options
- `Orbit Training (In-House)` — at Orbit premises
- `Company Premises (External)` — at client site
- `online` — virtual delivery

### Price Override
`QuotationItemOverride` (OneToOne to QuotationItem) allows admin/sales_manager to set a custom price per pax.

### PI Button Removed
The "PI" button that previously appeared in the quotation table actions has been removed. Quotation numbers cannot be used to create a purchase invoice directly.

---

## Module 9: Proposals

### Purpose
Create branded training proposals for corporate clients.

### Redesigned UI (v3)
- `proposal_dashboard.html` — new-style table with search, Print/Edit/Delete action buttons, empty state, pagination
- `create_proposal.html` — sectioned card form (Client & Course, Proposal Details, Logo)
- `edit_proposal.html` — same layout; shows current logo with remove checkbox; Print shortcut button

### Proposal Number
`PROP-YYYY-####` sequential per calendar year.

---

## Module 10: Refunds (v3)

### Purpose
Manage full refund lifecycle with document tracking, email notification, and revenue exclusion.

### Flow
```
Registration Detail → "Refund" button (red outline, hidden when already refunded)
  → /registrations/<pk>/refund/ — fill reason + optional doc + amount
  → Confirmation modal (two-step)
  → POST confirm_refund → registration.is_refunded = True
  → Refund email sent to client
  → Registration: REFUNDED banner + disabled styling
  → Refund record at /refunds/ (filter: Pending / Confirmed / Cancelled)
```

### Revenue Impact
Every revenue and performance query excludes refunded registrations:
```python
# ORM queries:
.exclude(registration__is_refunded=True)

# Raw SQL in _revenue_for_user:
AND r.is_refunded = 0
```

---

## Module 11: Institute Settings (v3)

### Purpose
Centralized configuration for the training institute — company identity, branding assets, banking details, social links.

### Key Details
- URL: `/settings/` — admin only
- Singleton pattern: `InstituteSetting.get()` calls `get_or_create(pk=1)`
- Tabbed UI: Company Info | Branding & Stamps | Banking | Documents | Social
- Image uploads: company_logo, stamp, authorization_logo, signature
- All fields `blank=True` — no field is required; partial saves are safe

---

## Module 12: CRM / Lead Management (Flask)

### Purpose
Separate Flask application at `leads-management/`. Lead capture, follow-ups, meetings, pipeline management.

### Safe Lead Delete (v3)
`delete_lead` now cleans child records before deleting to prevent FK IntegrityError:
```python
LeadInteraction.query.filter_by(lead_id=id).delete()
LeadQuote.query.filter_by(lead_id=id).delete()
Meeting.query.filter(Meeting.lead_id == id).update({'lead_id': None})
Student.query.filter(Student.lead_id == id).update({'lead_id': None})
PaymentLink.query.filter(PaymentLink.lead_id == id).update({'lead_id': None})
db.session.delete(lead)
db.session.commit()
```

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

*Document updated: 2026-07-13*
*Version 3.0 — adds Refunds (25), Certificate Requests (26), Institute Settings (27); safe lead delete; corporate PI fix; role-card signup; proposal UI redesign*
