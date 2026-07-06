# Functional Requirements Document (FRD)
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Product:** Orbit ERP Institute Management System
**Status:** Production

---

## 1. Introduction

This document defines the detailed functional requirements for the Orbit ERP system. It describes the specific behavior, inputs, outputs, and business rules for each functional module.

---

## 2. System Authentication

### 2.1 Login

**URL:** `/accounts/login/`

**Process:**
1. Validate credentials against `auth_user` table
2. Create session on success
3. Log login event to AuditLog (with IP address)
4. Redirect to `/` (main dashboard)

**Business Rules:**
- All pages except login are protected; unauthenticated requests redirect to login
- Session persists until explicit logout or session expiry
- Login via CRM SSO token (`/crm-auth/?t=<token>`) is also supported — validates HMAC token (90-second TTL), then creates Django session

### 2.2 User Management (Admin Only)

**URL:** `/manage/users/`
**Access:** Admin role only

**Functions:**
- Create user: `/signup/`
- Edit user: `/manage/users/<id>/edit/`
- Delete user: `/manage/users/<id>/delete/`
- Change password: `/manage/users/<id>/change-password/`
- Update role: `/manage/users/<id>/role/`
- Sync all users to CRM: `/manage/sync-crm/`

**Business Rules:**
- Only `admin` role or `is_superuser` can manage users
- When a user's role is set to `sales_manager` or `sales_executive`, their account is automatically synced to the Flask CRM database using a werkzeug-compatible password hash
- UserProfile is auto-created (default role: `sales_executive`) when a User is saved

### 2.3 Sales Targets

**URL:** `/manage/set-targets/`
**Access:** Admin only

**Input:**
- User selection, month, target amount (AED), target registration count

**Business Rules:**
- Unique per (user, month) pair
- Displayed on dashboards for tracking

### 2.4 Logout

**URL:** `/logout/`

**Process:** Call `logout()`, log logout event to AuditLog, redirect to login page.

---

## 3. Invoice Management

### 3.1 Create Sales Invoice

**URL:** `/create_invoice/`

**Input Form Fields:**
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Registration | Select | No | Links to existing registration |
| Client | Select | Yes | From invoices_client |
| Course | Select | No | Header course reference |
| Invoice Date | Date | Yes | |
| Due Date | Date | Yes | |
| Class Type | Select | Yes | online/offline/batch/private |
| Level | Select | Yes | intermediate/professional/advanced |
| Status | Select | Yes | Full Payment/Term Payment/Tabby/Tamara |
| Payment Method | Select | Yes | Card/Cash/Account Transfer/Payment Link/Cheque |
| Total Amount | Decimal | Auto | Calculated from items |
| Amount Paid | Decimal | Yes | |
| Discount | Decimal | No | Percentage — enforced cap |
| Number of Persons | Integer | Yes | Default 1 |
| PO Number | Text | No | Purchase order reference |

**Business Rules:**
- Invoice number auto-generated: `YY/MM/###` (sequential per calendar month)
- VAT (5%) is added on top of the discounted base price per line item
- Discount cap: 20% for single-course invoices, 30% for multi-course invoices — enforced in both JS and server
- `total_amount` = Σ(item base × persons × (1 − discount%) × 1.05 VAT)
- Previous Payment Reference section on the tax invoice is shown only when a prior invoice exists for the same registration

### 3.2 Invoice Line Items

**URL:** `/add_invoice_items/<invoice_id>/`

**Input per line item:**
| Field | Type | Notes |
|-------|------|-------|
| Course | Select | From invoices_course |
| Quantity | Integer | Number of persons or units |
| Unit Price | Decimal | Auto-filled from course.get_rate(class_type, level); editable |
| VAT Rate | Decimal | Default 0.05 (5%); stored as decimal, not percent |

**Calculations per item:**
- Subtotal = Quantity × Unit Price
- VAT Amount = Subtotal × vat_rate
- Item Total = Subtotal + VAT Amount

### 3.3 Invoice Payments (Installments)

**URL:** `/invoice/<pk>/payments/`, `/invoice/<pk>/payments/add/`

**Purpose:** Record multiple payment installments against an invoice (InvoicePayment model).

**Input:**
| Field | Type | Notes |
|-------|------|-------|
| Amount | Decimal | Payment amount |
| Payment Method | Select | cash/card/bank_transfer/cheque/payment_link/other |
| Reference | Text | Cheque number, transfer reference |
| Paid At | Date | Payment date |
| Notes | Text | Optional notes |

**Business Rules:**
- Multiple payments allowed per invoice
- Payment history shows on invoice detail

### 3.4 Tax Invoice Print

**URL:** `/invoice/<id>/` (or print action from dashboard)

**Layout:** A4 landscape

**Structure:**
- Left column: Terms and Conditions
- Right column: Invoice totals, VAT breakdown, signature blocks
- Previous Payment Reference: only renders if the registration has a prior invoice

### 3.5 Mark Invoice Paid

**URL:** `/invoice/<pk>/mark-paid/`

Quick action that sets invoice `amount_paid = total_amount` and status to "Full Payment".

### 3.6 Bulk Invoice Actions

**URL:** `/invoices/bulk-action/`

Supports bulk status updates on multiple selected invoices.

### 3.7 Purchase Invoice

**URL:** `/create_purchase_invoice/`

**Additional fields:** `advance_amount` (advance payment made).

**Business Rules:** Numbered separately from sales invoices using same `YY/MM/###` format within their own sequence.

---

## 4. Student Registration

### 4.1 Individual Registration

**URL:** `/register/`

**Input Form Fields:**
| Field | Type | Notes |
|-------|------|-------|
| Registration Type | Radio | OT (Individual) or OC (Corporate) |
| Class Type | Select | online/offline/batch/private |
| Level | Select | intermediate/professional/advanced |
| First Name, Last Name | Text | Required |
| Date of Birth | Date | Optional |
| Passport No | Text | Optional |
| UID No | Text | Optional |
| Emirates ID No | Text | Optional |
| Nationality | Text | Optional |
| Education | Text | Optional |
| Phone No | Text | Required |
| Alternative No | Text | Optional |
| Email | Email | Required |
| Country | Select | Required |
| Emirates | Select | Optional (UAE) |
| Address | Textarea | Optional |
| Company/University | Text | Optional |
| Consultant Name | Text | Required |
| Courses | Multi-select | Required — 1+ courses |
| Price per course | Decimal | Auto-filled from get_rate(class_type, level) |
| Discount per course | Decimal | Percentage |

**Auto-generated:**
- `registration_number`: `OT/YY/###` (individual) — resets annually, not monthly
- `date`: Today's date

**CRM Pre-fill:** If accessed via `/register/?crm_id=<id>&fn=<first>&ln=<last>&ph=<phone>&em=<email>`, the form is pre-populated from the CRM lead.

**Business Rules:**
- Registration number increments within the current year (not month)
- Course price auto-fills based on class type AND level using `course.get_rate(class_type, level)`
- Each course can have individual discount percentage
- Unique constraint on (registration, course) — cannot enroll in same course twice
- `student_status` defaults to 'active'

### 4.2 Corporate Registration

**URL:** `/corporate-registration/`

Additional fields: Company Name, Address, Location, Phone, Email.

Creates both `Registration` (type=OC) and `CorporateRegistration` (OneToOne) records.

### 4.3 Student Status Update

**URL:** `/student/<pk>/status/`

Updates `registration.student_status` to: active / completed / dropped / suspended / pending.

### 4.4 Token-Based Student Self-Registration

**URL:** `/portal/student/<token>/`

A staff member generates a token link (`/portal/student-links/generate/`) that pre-selects courses and locks the consultant name. The student fills in personal details without seeing pricing.

**Business Rules:**
- Token can have expiry date
- Usage count tracked
- Can be deactivated

### 4.5 Company Portal (Corporate Self-Registration)

**URL:** `/portal/company/<token>/`

An admin generates a token link for a company (`/admin-portal/generate/`). The company fills in their details (trade license, VAT certificate, contact person) and adds their training attendees.

**Admin approval:** `/admin-portal/<pk>/approve/`

---

## 5. Course Management

### 5.1 Course CRUD

**Create URL:** `/courses/create/`
**List URL:** `/courses/`

**Pricing Fields:**

| Field | Notes |
|-------|-------|
| oo_intermediate | Online/Offline — Intermediate level |
| oo_professional | Online/Offline — Professional level |
| oo_advanced | Online/Offline — Advanced level |
| priv_intermediate | Private — Intermediate level |
| priv_professional | Private — Professional level |
| priv_advanced | Private — Advanced level |
| rate | Legacy standard/offline rate |
| batch_rate | Legacy batch rate |
| online_rate | Legacy online rate |
| private_rate | Legacy private rate |

**Business Rules:**
- Course code must be unique (enforced at DB level)
- Code used in certificate numbering
- Course list displays dash (—) for zero-value level prices, not "0"
- Legacy rate fields kept so existing invoices and quotations remain valid

---

## 6. Certificate Management

### 6.1 Create Certificate

**URL:** `/certificates/create/`

**Certificate Number Generation:**
- Looks up Course by name to get course code
- Format: `{COURSE_CODE}{REGISTER_NUMBER}` (e.g., `PMOT/26/001`)
- Handles duplicates by appending `-1`, `-2`, etc.

### 6.2 KHDA Certificate Upload

**URL:** `/certificates/khda-form/` and `/certificates/create-khda/`

Upload pre-issued KHDA certificate PDF.
File stored with slug of student name + certificate number in path.

---

## 7. Quotation Management

### 7.1 Training Venue Options

| Value | Meaning |
|-------|---------|
| `Orbit Training (In-House)` | At Orbit Training premises |
| `Company Premises (External)` | At client's premises |
| `online` | Virtual delivery |

### 7.2 Price Override

An admin or sales manager can set a `QuotationItemOverride` (custom price per pax) that overrides the course rate on the printed PDF.

### 7.3 Coupon on Quotation

A Coupon can be linked to a Quotation at creation time.

---

## 8. CRM SSO Bridge

### 8.1 ERP → CRM Jump

**URL:** `/crm-jump/`

1. Generates HMAC token: `base64url({"u": username, "t": timestamp}).sig`
2. Redirects to: `{CRM_URL}/auto-login?t=<token>`

### 8.2 CRM → ERP Auth

**URL:** `/crm-auth/`

1. Receives `?t=<token>` from CRM
2. Verifies HMAC signature and token age (90-second TTL)
3. Logs user into ERP via Django auth
4. If `crm_id` parameter present, redirects to `/register/?crm_id=<id>&fn=<first>&ln=<last>...`
5. Otherwise redirects to main dashboard or `next` parameter

### 8.3 CRM Lead Lookup

**URL:** `/api/crm-lead/<lead_id>/`

Fetches lead data from CRM internal API for registration form auto-fill:
```
GET {CRM_URL}/api/internal/lead/<id>
Authorization: Bearer <CRM_SSO_SECRET>
```

---

## 9. Reporting

### 9.1 Revenue Report

**URL:** `/reports/revenue/`

- Filter by date range, consultant, class type
- CSV export: `/reports/revenue/export/`

### 9.2 Receivables Aging Report

**URL:** `/reports/aging/`

Groups overdue invoices: 0-15, 16-30, 31-60, 61-90, 90+ days overdue.

### 9.3 VAT Report

**URL:** `/reports/vat/`

Tax collected by period; shows input VAT (expenses) vs output VAT (invoices).

### 9.4 Enrollment Report

**URL:** `/reports/enrollment/`

Registrations by period, consultant, course, class type.

### 9.5 Certificate Report

**URL:** `/reports/certificates/`

Certificates issued by period, type (regular/KHDA), course.

### 9.6 Expense Report

**URL:** `/expenses/report/`

Expenses by category, vendor, date range.

---

## 10. Notifications

### 10.1 Notification Types

| Type | Trigger |
|------|---------|
| `invoice_due` | Invoice due date approaching |
| `overdue_invoice` | Invoice past due date |
| `certificate_ready` | Certificate issued for registration |
| `registration_new` | New student registered (admin/manager) |
| `target_alert` | Sales target milestone reached |
| `system` | System-generated messages |

### 10.2 AJAX Endpoints

- `GET /notifications/` — list unread notifications
- `POST /notifications/<id>/read/` — mark one as read
- `POST /notifications/read-all/` — mark all as read

---

## 11. Training Schedule

**URL:** `/schedule/`

**Input Fields:**
| Field | Type |
|-------|------|
| Course | FK to Course |
| Title | Text |
| Class Type | online/offline/batch/private |
| Start Date | Date |
| End Date | Date |
| Start/End Time | Time (optional) |
| Venue | Text |
| Max Capacity | Integer |
| Instructor | Text |
| Status | upcoming/ongoing/completed/cancelled |

---

## 12. Expense Tracking

**URL:** `/expenses/`

**Categories:** Venue/Facility, Training Materials, Instructor Fee, Marketing, Utilities, Software & Tools, Travel & Transport, Salary/Staff, Other.

**Fields:** Category, description, amount, VAT amount (tracked separately), vendor, date, payment method, receipt reference, course link (optional).

---

## 13. Audit Log

**URL:** `/audit/`
**Access:** Admin only

**Recorded Events:**
- User login (via signals.py)
- User logout (via signals.py)
- Create / Update / Delete on key models
- Payment recording
- Status changes
- Export actions

**Each record stores:** user, action, model_name, object_id, object_repr, changes (text), ip_address, timestamp.

---

## 14. Fee Reminder Dashboard

**URL:** `/fee-reminders/`

Shows outstanding and overdue invoices with reminder logging. Staff can log that a reminder was sent (FeeReminderLog model), tracking: channel (system/email/manual), sent_by, note.

---

## 15. Global Search

**URL:** `/search/`

Searches across registrations, invoices, courses, certificates in a single AJAX call.

---

## 16. Business Rules Summary

| Rule | Description |
|------|-------------|
| VAT Rate | 5% added on top of discounted price (never back-calculated) |
| Currency | AED (UAE Dirhams) throughout system |
| Invoice Numbering | YY/MM/### sequential, resets monthly |
| Registration Numbering | OT/YY/### (individual), OC/YY/### (corporate) — resets annually |
| Certificate Numbering | {COURSE_CODE}{REG_NUMBER} — handles duplicates with suffix |
| Proposal Numbering | PROP-YYYY-#### sequential |
| Discount Cap (single course) | Maximum 20% — enforced frontend + backend |
| Discount Cap (multi-course) | Maximum 30% — enforced frontend + backend |
| Level Pricing | Intermediate / Professional / Advanced × Online/Offline or Private |
| Class Types | online, offline, batch, private — each uses oo_ or priv_ price fields |
| Lead Email | Must be unique in CRM system |
| Course Code | Must be unique, 2-10 characters |
| Trainer Name | Must be unique |
| Certificate per Registration | OneToOne for uploaded cert files |
| Admin Actions | Require admin role (UserProfile.role == 'admin') or is_superuser |
| SSO Token TTL | 90 seconds — short-lived HMAC token for CRM↔ERP navigation |
| Student Status | Defaults to 'active'; updated manually or auto-completed |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
