# Functional Requirements Document (FRD)
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
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
- Create user: `/signup/` — redesigned form extending `base_generic.html` with gradient header, icon-decorated fields, role selection cards, live password match indicator
- Edit user: `/manage/users/<id>/edit/`
- Delete user: `/manage/users/<id>/delete/`
- Change password: `/manage/users/<id>/change-password/`
- Update role: `/manage/users/<id>/role/`
- Sync all users to CRM: `/manage/sync-crm/`

**Business Rules:**
- Only `admin` role or `is_superuser` can manage users
- When role = `sales_manager` or `sales_executive`, account auto-synced to Flask CRM database
- UserProfile auto-created with default role `sales_executive` on user save

### 2.3 Sales Targets

**URL:** `/manage/set-targets/`
**Access:** Admin only

**Input:** User selection, month, target amount (AED), target registration count

**Business Rules:** Unique per (user, month) pair.

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
| Invoice Date | Date | Yes | |
| Due Date | Date | Yes | |
| Class Type | Select | Yes | online/offline/batch/private |
| Level | Select | Yes | intermediate/professional/advanced |
| Status | Select | Yes | Full Payment/Term Payment/Tabby/Tamara |
| Payment Method | Select | Yes | Card/Cash/Account Transfer/Payment Link/Cheque |
| Amount Paid | Decimal | Yes | |
| Discount | Decimal | No | Percentage — enforced cap |
| Number of Persons | Integer | Yes | Default 1 |
| PO Number | Text | No | |

**Business Rules:**
- Invoice number auto-generated: `YY/MM/###` sequential per calendar month
- VAT (5%) added on top of discounted base price per line item
- Discount cap: 20% single-course, 30% multi-course — enforced JS + backend
- `total_amount` = Σ(item base × persons × (1 − discount%) × 1.05)
- Previous Payment Reference section shown only when prior invoice exists for registration

### 3.2 Invoice Payments (Installments)

**URL:** `/invoice/<pk>/payments/add/`

| Field | Type | Notes |
|-------|------|-------|
| Amount | Decimal | |
| Payment Method | Select | cash/card/bank_transfer/cheque/payment_link/other |
| Reference | Text | Cheque number, transfer reference |
| Paid At | Date | |
| Notes | Text | Optional |

---

## 4. Student Registration

### 4.1 Individual Registration

**URL:** `/register/`

**Key Fields:**
- Registration Type, Class Type, Level, Name, DOB, Passport/UID/EmiratesID, Nationality, Education, Phone, Email, Country, Emirates, Consultant, Courses with price/discount

**Auto-generated:**
- `registration_number`: `OT/YY/###` (individual) or `OC/YY/###` (corporate) — resets annually
- `date`: Today
- `created_at`: Now (used by 1-hour edit lock)

**CRM Pre-fill:** `?crm_id=<id>&fn=<first>&ln=<last>&ph=<phone>&em=<email>` pre-populates from CRM lead.

### 4.2 Edit Lock (Sales Executive)

**Applies to:** `edit_registration` and `edit_corporate_registration`

**Rule:** Sales executives can edit a registration only within 1 hour of creation.

```python
if role == 'sales_executive':
    if registration.created_at is None:
        locked = True  # NULL = legacy record, always locked
    else:
        locked = (timezone.now() - registration.created_at).total_seconds() > 3600
```

- If locked: flash error "Registrations can only be edited within 1 hour of creation. Please contact your manager." → redirect to student_dashboard
- Admin, sales_manager, accounts: no lock

### 4.3 Student Status Update

**URL:** `/student/<pk>/status/`

Values: active / completed / dropped / suspended / pending.

---

## 5. Course Management

**Create URL:** `/courses/create/`

**Pricing Fields:** `oo_intermediate`, `oo_professional`, `oo_advanced`, `priv_intermediate`, `priv_professional`, `priv_advanced` + 4 legacy fields.

**Display:** Zero-value level price shows as `—` (not `0`).

**get_rate():**
```python
def get_rate(self, class_type, level='intermediate'):
    if class_type == 'private':
        return {'intermediate': self.priv_intermediate, ...}.get(level)
    else:
        return {'intermediate': self.oo_intermediate, ...}.get(level)
```

---

## 6. Certificate Management

### 6.1 Create Certificate

**URL:** `/certificates/create/`

Certificate number: `{COURSE_CODE}{REG_NUMBER}` (e.g., `PMOT/26/001`). Duplicates appended `-1`, `-2`.

### 6.2 Delete Certificate

**URL:** `/certificates/<pk>/delete/` (POST)
**Access:** Admin only

Confirmation modal on dashboard before submitting. Certificate record deleted from DB. No cascade to registration — registration persists.

### 6.3 Certificate Request Flow

#### Step 1 — Send Request

**URL:** `/registrations/<pk>/send-cert-request/` (POST)

- Creates `CertificationRequest` record with UUID token, status=`pending`
- Sends email to client with public form link
- Button appears on registration detail page

#### Step 2 — Client Form (Public — No Login)

**URL:** `/cert-request/<uuid:token>/`

Client fills:
- Course completion status (Completed / Not Completed)
- If Completed:
  - Course completion date (required)
  - Class rating (required radio: Excellent / Good / Average / Poor)
  - Write about the class (required textarea — `class_feedback`)
  - Additional comments (optional — `client_notes`)

**Submit button** disabled until all three required fields (date + rating + feedback) are filled.

**Not Completed:** Shows blocking red message; submit button stays disabled.

#### Step 3 — Admin Review

**URL:** `/cert-requests/?status=submitted`

Admin sees: student name, registration number, course, completion date, class rating (with stars), class feedback (blue highlighted box), client notes.

Actions available:
- **Generate Certificate** — enter From Date, End Date, Grade → creates Certificate record → sets request status `approved`
- **Reject** — sets status `rejected`

#### Status Pills (Registration Detail)

| CertificationRequest.status | Pill shown |
|---|---|
| `pending` | "Cert Request Sent" |
| `submitted` | "Submitted by Client" |
| `approved` | "Certificate Generated" |
| `rejected` | "Request Rejected" |
| No request | "Certificate Pending" |

---

## 7. Refund Management

### 7.1 Initiate Refund

**URL:** `/registrations/<pk>/refund/`
**Access:** All authenticated roles (admin/manager can refund; exec visible too)

**Input:**
| Field | Notes |
|-------|-------|
| Reason | Text — required |
| Document | File upload — optional |
| Amount | Decimal — refund amount |

### 7.2 Confirm Refund

**URL:** `/refunds/<pk>/confirm/`

POST with `action=confirm`:
1. Sets `refund.status = 'confirmed'`, `confirmed_at = now()`, `confirmed_by = request.user`
2. Sets `registration.is_refunded = True`
3. Sends refund notification email to client

POST with `action=cancel`:
1. Sets `refund.status = 'cancelled'`

**Two-step confirmation:** Confirmation page shows refund details → user clicks "Confirm Refund" in a modal to POST.

### 7.3 Refund List

**URL:** `/refunds/`
**Access:** Admin / Accounts roles

Filter tabs: Pending Confirmation | Confirmed & Processed | Cancelled | All

### 7.4 Visual State of Refunded Registrations

- Student dashboard: row has 45% opacity, light-red background, REFUNDED badge next to registration number
- Registration detail: red REFUNDED banner at top; "Refund" button hidden
- Revenue/reports: all queries add `.exclude(registration__is_refunded=True)` or `AND r.is_refunded = 0` in raw SQL

---

## 8. Institute Settings

**URL:** `/settings/`
**Access:** Admin only

**Tabs:**
1. **Company Info** — name, trade license, VAT number, address, phone, email, website
2. **Branding & Stamps** — company logo, stamp, authorization logo, signature (all image uploads)
3. **Banking** — bank name, account name, account number, IBAN, SWIFT code
4. **Social** — Facebook, Instagram, LinkedIn, Twitter URLs

**Save:** POST to `/settings/`. All fields optional. InstituteSetting singleton (`pk=1`) updated.

**Accessing in code:**
```python
setting = InstituteSetting.get()  # get_or_create(pk=1)
```

---

## 9. Purchase Invoice — Corporate Mode Fix

**URL:** `/create_purchase_invoice/`

**Problem solved:** In corporate mode, course qty is already set to `candidate_count`. The "Number of Persons" field was confusing users who entered the candidate count a second time, causing double-multiplication.

**Behavior:**
- Corporate mode: `#wrap_number_of_person` hidden; replaced by read-only "Total Candidates: X persons" info box; `#id_number_of_person` forced to 1
- Individual mode: "Number of Persons" visible and editable as before

---

## 10. Quotation — PI Button Removed

The "PI" button previously visible in the quotation table row actions has been removed. The `goToPurchaseInvoice()` JS function has also been deleted. Quotation numbers cannot directly create a purchase invoice.

---

## 11. CRM SSO Bridge

### 11.1 ERP → CRM Jump

**URL:** `/crm-jump/`

1. Generates HMAC token: `base64url({"u": username, "t": timestamp}).sig`
2. Redirects to: `{CRM_URL}/auto-login?t=<token>`

### 11.2 CRM → ERP Auth

**URL:** `/crm-auth/`

1. Receives `?t=<token>` from CRM
2. Verifies HMAC signature and token age (90-second TTL)
3. Logs user into ERP
4. If `crm_id` present, redirects to `/register/?crm_id=<id>&...`

---

## 12. Reporting

All revenue-related reports and aggregations apply:
```python
.exclude(registration__is_refunded=True)
```

| Report | URL | Key Filter |
|--------|-----|------------|
| Revenue | `/reports/revenue/` | Date range, consultant; excludes refunded |
| Aging | `/reports/aging/` | 0-15, 16-30, 31-60, 61-90, 90+ days |
| VAT | `/reports/vat/` | Period |
| Enrollment | `/reports/enrollment/` | Period/consultant/course |
| Certificates | `/reports/certificates/` | Period/type |
| Expenses | `/expenses/report/` | Category/vendor/date |

---

## 13. Business Rules Summary

| Rule | Description |
|------|-------------|
| VAT Rate | 5% added on top of discounted price (never back-calculated) |
| Currency | AED (UAE Dirhams) throughout |
| Invoice Numbering | YY/MM/### sequential, resets monthly |
| Registration Numbering | OT/YY/### (individual), OC/YY/### (corporate) — resets annually |
| Certificate Numbering | {COURSE_CODE}{REG_NUMBER} — handles duplicates with suffix |
| Proposal Numbering | PROP-YYYY-#### sequential |
| Discount Cap (single) | Maximum 20% — enforced frontend + backend |
| Discount Cap (multi) | Maximum 30% — enforced frontend + backend |
| Level Pricing | Intermediate / Professional / Advanced × Online/Offline or Private |
| Edit Lock | Sales executives: 1-hour window from `created_at`; NULL `created_at` = always locked |
| Refund Exclusion | `is_refunded=True` registrations excluded from all revenue, dashboard, reports |
| Corp PI Persons | `number_of_person` forced to 1 in corporate PI mode (qty already = candidate count) |
| Schema Constraint | Never alter existing columns/tables — additive changes only |
| SSO Token TTL | 90 seconds |
| Cert Request | class_rating + class_feedback + completion_date all required before submit |
| Admin Actions | Require `UserProfile.role == 'admin'` or `is_superuser` |
| Institute Settings | Singleton — always pk=1, accessed via `InstituteSetting.get()` |

---

*Document updated: 2026-07-13*
*Version 3.0 — adds Refund, Certificate Request, Institute Settings, edit lock, corporate PI fix, safe lead delete*
