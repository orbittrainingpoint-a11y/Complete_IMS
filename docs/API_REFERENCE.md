# API Reference Document
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Type:** Internal Django Views / AJAX Endpoints + CRM Internal API

---

## 1. Overview

Orbit ERP is a server-rendered Django application with AJAX endpoints for dynamic interactions. The system also exposes an internal API endpoint used by the ERP to look up CRM leads.

**Base URL (local):** `http://localhost:8000/`
**Base URL (VPS):** `https://orbittraining.online/`
**CRM URL (local):** `http://localhost:5000/`
**CRM URL (VPS):** proxied via Apache

**Authentication:** Session-based (`sessionid` cookie) for all Django views.
**CSRF:** Required on all POST requests (`csrfmiddlewaretoken` in form or `X-CSRFToken` header for AJAX).
**CRM Internal API:** HMAC Bearer token (`Authorization: Bearer <CRM_SSO_SECRET>`).

---

## 2. Authentication Endpoints

### `GET /accounts/login/`
Display login form.

### `POST /accounts/login/`
Authenticate user.

| Parameter | Type | Required |
|-----------|------|----------|
| username | string | Yes |
| password | string | Yes |
| csrfmiddlewaretoken | string | Yes |

**Success:** Redirect to `/` (302)
**Failure:** Login form with error message
**Side effect:** Writes AuditLog entry (action=login, ip_address recorded)

### `GET /logout/`
Log out current user.
**Response:** Redirect to login page (302)
**Side effect:** Writes AuditLog entry (action=logout)

### `GET /signup/`
**Access:** Admin role only
Display user creation form.

### `POST /signup/`
**Access:** Admin role only
Create new user account. Auto-creates UserProfile with default role.

### `GET /crm-jump/`
**Access:** Login required
Generate HMAC SSO token and redirect to CRM dashboard.
**Response:** Redirect to `{CRM_URL}/auto-login?t=<token>`

### `GET /crm-auth/?t=<token>[&crm_id=<id>&fn=<first>&ln=<last>&ph=<phone>&em=<email>]`
Receive SSO token from CRM and log user into ERP.
**Token TTL:** 90 seconds
**Success with crm_id:** Redirect to `/register/?crm_id=<id>&fn=<first>&ln=<last>...`
**Success without crm_id:** Redirect to dashboard or `next` parameter
**Failure:** Redirect to login with error message

---

## 3. User Management Endpoints (Admin Only)

### `GET /manage/users/`
List all users with roles and targets.

### `GET/POST /manage/users/<id>/edit/`
Edit user details.

### `POST /manage/users/<id>/role/`
Update user role. Triggers CRM sync for sales roles.

### `POST /manage/users/<id>/delete/`
Delete user account.

### `POST /manage/users/<id>/change-password/`
Change user password.

### `GET/POST /manage/set-targets/`
Set monthly sales targets per user.

### `POST /manage/sync-crm/`
Batch-sync all sales role users to Flask CRM database.

---

## 4. Dashboard Endpoints

### `GET /`
Main orbit dashboard.
**Response:** HTML — registration stats, revenue KPIs, target progress, notification count.

### `GET /dashboard/`
Invoice dashboard with tabbed invoice lists.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| invoice_number | string | Filter by invoice number |
| registration_number | string | Filter by registration number |
| name | string | Filter by client name |
| due_date | date | Filter by due date |
| payment_status | string | Filter by payment status |

---

## 5. Invoice Endpoints

### `GET/POST /create_invoice/`
Create new sales invoice.

**POST Form Data:**
| Field | Type | Required |
|-------|------|----------|
| registration | integer | No |
| client | integer | Yes |
| course | integer | No |
| date | date | Yes |
| due_date | date | Yes |
| class_type | string | Yes |
| level | string | Yes — intermediate/professional/advanced |
| status | string | Yes |
| payment | string | Yes |
| total_amount | decimal | Yes (0 initially) |
| amount_paid | decimal | Yes |
| discount | decimal | No (max 20% single / 30% multi) |
| number_of_person | integer | Yes |
| po_number | string | No |

**Success:** Redirect to `/add_invoice_items/{id}/`

### `GET/POST /add_invoice_items/<invoice_id>/`
Add line items to invoice.

**Formset Data:**
| Field | Type | Notes |
|-------|------|-------|
| form-{n}-course | integer | FK to Course |
| form-{n}-description | string | |
| form-{n}-quantity | integer | |
| form-{n}-unit_price | decimal | |
| form-{n}-vat_rate | decimal | 0.05 default |

### `GET/POST /invoice/<id>/edit/`
Edit invoice.

### `GET/POST /invoice/<id>/delete/`
**Access:** Admin role
Delete invoice and all line items.

### `POST /invoice/<pk>/mark-paid/`
Quick action: set amount_paid = total_amount, status = Full Payment.

### `POST /invoices/bulk-action/`
Bulk status update on multiple invoices.

### `GET /invoice/<pk>/payments/`
View payment installments for an invoice.

### `POST /invoice/<pk>/payments/add/`
Record a new payment installment.

**POST Form Data:**
| Field | Type |
|-------|------|
| amount | decimal |
| payment_method | string (cash/card/bank_transfer/cheque/payment_link/other) |
| reference | string |
| paid_at | date |
| notes | string |

---

## 6. Purchase Invoice Endpoints

### `GET/POST /create_purchase_invoice/`
Create purchase invoice.

### `GET/POST /invoice_purchase/<id>/edit/`
Edit purchase invoice.

### `GET/POST /invoice_purchase/<id>/delete/`
**Access:** Admin role
Delete purchase invoice.

---

## 7. Registration Endpoints

### `GET/POST /register/`
Create student registration.

**Key Query Parameters (for CRM pre-fill):**
| Parameter | Source |
|-----------|--------|
| crm_id | CRM lead ID |
| fn | First name |
| ln | Last name |
| ph | Phone |
| em | Email |
| ci | Interested course ID |

### `GET /student-dashboard/`
List all individual registrations with filters.

### `GET /corporate_dashboard/`
List all corporate registrations.

### `GET/POST /edit-registration/<id>/`
Edit registration.

### `GET/POST /delete-registration/<id>/`
**Access:** Admin role

### `GET /print-registration/<id>/`
Print-optimized registration form.

### `GET /corporate-invoice-detail/<registration_id>/`
Corporate registration detail with invoices.

### `GET /registration/<registration_id>/`
Registration invoice detail page.

### `POST /student/<pk>/status/`
Update student status (active/completed/dropped/suspended/pending).

---

## 8. AJAX Data Endpoints

### `GET /get_course_details/`
Get course pricing by course ID and class type.

**Query Parameters:**
| Parameter | Type |
|-----------|------|
| course_id | integer |
| class_type | string |
| level | string (optional, default: intermediate) |

**Response:**
```json
{
    "rate": "1500.00",
    "batch_rate": "1200.00",
    "online_rate": "1000.00",
    "private_rate": "2000.00",
    "oo_intermediate": "1500.00",
    "oo_professional": "2000.00",
    "oo_advanced": "2500.00",
    "priv_intermediate": "2000.00",
    "priv_professional": "2500.00",
    "priv_advanced": "3000.00"
}
```

### `GET /get_registration_details/`
Get registration details including linked invoice.

**Query Parameters:** `registration_id` (integer)

**Response:**
```json
{
    "registration_number": "OT/26/001",
    "student_name": "John Doe",
    "invoice_id": 123,
    "invoice_number": "26/07/001",
    "total_amount": "1575.00",
    "amount_paid": "500.00"
}
```

### `GET /get_invoice_details/`
Get invoice line items as JSON.

**Query Parameters:** `invoice_id` (integer)

**Response:**
```json
{
    "items": [
        {
            "course_name": "Project Management",
            "quantity": 1,
            "unit_price": "1500.00",
            "vat_rate": "0.05",
            "subtotal": "1500.00",
            "vat_amount": "75.00",
            "total": "1575.00"
        }
    ]
}
```

### `GET /api/search-registrations/`
Autocomplete search for registrations (used in invoice form).

### `GET /search/`
Global search across registrations, invoices, courses, certificates.

---

## 9. CRM Internal API

Used by ERP to fetch lead data for registration form auto-fill.

### `GET /api/crm-lead/<lead_id>/`
**ERP endpoint** — proxies request to CRM internal API.
**Access:** Login required

**Calls internally:** `GET {CRM_URL}/api/internal/lead/<lead_id>`
**Authorization:** `Bearer <CRM_SSO_SECRET>` header

**Response (from CRM):**
```json
{
    "id": 42,
    "full_name": "Jane Smith",
    "status": "Qualified",
    "phone": "+971501234567",
    "email": "jane@example.com",
    "interested_course": "Project Management"
}
```

**Error responses:**
- `404` — Lead not found in CRM
- `502` — CRM not reachable or returned error

---

## 10. Report Endpoints

### `GET /reports/revenue/`
Revenue report with date and consultant filters.

### `GET /reports/revenue/export/`
CSV export of revenue report.

### `GET /reports/aging/`
Receivables aging: groups overdue invoices by 0-15, 16-30, 31-60, 61-90, 90+ days.

### `GET /reports/vat/`
VAT report: output VAT from invoices vs input VAT from expenses.

### `GET /reports/enrollment/`
Enrollment report by period, consultant, course, class type.

### `GET /reports/certificates/`
Certificate report: issued certs by period, type, course.

### `GET /expenses/report/`
Expense report by category, vendor, date range.

---

## 11. Notification Endpoints

### `GET /notifications/`
**AJAX endpoint**
Return unread notifications for current user.

**Response:**
```json
{
    "notifications": [
        {
            "id": 1,
            "type": "invoice_due",
            "title": "Invoice Due Tomorrow",
            "message": "Invoice 26/07/001 is due on 2026-07-07",
            "link": "/invoice/123/",
            "is_read": false,
            "created_at": "2026-07-06T10:00:00"
        }
    ],
    "unread_count": 3
}
```

### `POST /notifications/<id>/read/`
Mark a single notification as read.

**Response:** `{"success": true}`

### `POST /notifications/read-all/`
Mark all notifications for current user as read.

---

## 12. Certificate Endpoints

### `GET /certificates/`
List all certificates.

### `GET/POST /certificates/create/`
Create new certificate.

### `GET /certificates/print/<id>/`
Print-optimized certificate.

### `GET/POST /certificates/khda-form/`
KHDA certificate upload form.

### `POST /certificates/create-khda/`
Create KHDA certificate record.

### `GET/POST /upload-certificate/<registration_id>/`
Upload certificate file for a registration.

### `GET/POST /upload-form/<registration_id>/`
Upload registration form document.

---

## 13. Quotation Endpoints

### `GET/POST /quotation/create/`
Create quotation with item formset.

### `GET /quotation/`
List all quotations.

### `GET /quotation_detail/<id>/`
View/print quotation detail.

### `GET/POST /quotation/<id>/edit/`
Edit quotation.

### `GET/POST /quotation/<id>/delete/`
Delete quotation.

---

## 14. Proposal Endpoints

### `GET /proposals/`
List all proposals.

### `GET/POST /proposals/create/`
Create proposal with optional logo upload.

**POST Form Data (multipart/form-data):**
| Field | Type | Notes |
|-------|------|-------|
| client_name | string | |
| course | integer | FK to Course |
| presenter_title | string | |
| date | date | |
| location | string | |
| trainer | integer | Optional FK |
| logo | file | PNG only |

### `GET/POST /proposals/<id>/edit/`
Edit proposal.

### `GET /proposals/<id>/print/`
View/print branded proposal.

### `POST /remove_logo/<proposal_id>/`
Remove logo from proposal.

---

## 15. Training Schedule Endpoints

### `GET /schedule/`
List all training schedules.

### `GET/POST /schedule/create/`
Create training schedule.

### `GET/POST /schedule/<id>/edit/`
Edit schedule.

### `POST /schedule/<id>/delete/`
Delete schedule.

---

## 16. Expense Endpoints

### `GET /expenses/`
List all expenses.

### `GET/POST /expenses/create/`
Create expense record.

### `GET/POST /expenses/<id>/edit/`
Edit expense.

### `POST /expenses/<id>/delete/`
Delete expense.

### `GET /expenses/report/`
Expense summary report.

---

## 17. Audit Log Endpoint

### `GET /audit/`
**Access:** Admin role only
View audit log with filters (user, action, model, date range).

---

## 18. Fee Reminder Endpoint

### `GET /fee-reminders/`
Fee reminder dashboard showing overdue/upcoming invoices.

---

## 19. Company Portal Endpoints

### `GET/POST /portal/company/<token>/`
Company self-registration portal (public — no login required).

### `GET /portal/company/<token>/success/`
Success page after portal submission.

### `GET/POST /portal/company/<token>/attendees/`
Add training attendees to a portal registration.

### `GET /admin-portal/`
**Access:** Admin only
Manage all company portal requests.

### `POST /admin-portal/generate/`
Generate a new company portal link.

### `POST /admin-portal/<id>/approve/`
Approve a company portal request.

---

## 20. Student Form Link Endpoints

### `GET /portal/student-links/`
**Access:** Login required
List all student form links for current user.

### `POST /portal/student-links/generate/`
Generate a new student self-registration link.

### `GET/POST /portal/student/<token>/`
Student self-registration form (public — no login required).

---

## 21. Coupon Endpoints

### `GET /coupons/`
List all coupons.

### `GET/POST /coupons/create/`
Create coupon.

### `GET/POST /coupons/<id>/edit/`
Edit coupon.

### `POST /coupons/<id>/delete/`
Delete coupon.

### `POST /validate-coupon/`
**AJAX endpoint** — Validate coupon code.

**POST Body:** `{ "code": "SAVE20" }`

**Success:**
```json
{
    "valid": true,
    "discount_percentage": "20.00",
    "message": "Coupon applied: 20% discount"
}
```

**Failure:**
```json
{
    "valid": false,
    "message": "Invalid or inactive coupon code"
}
```

---

## 22. Course Endpoints

### `GET /courses/`
List all courses.

### `GET/POST /courses/create/`
Create course.

### `GET /courses/<id>/`
Course detail with enrolled students and content.

### `GET/POST /courses/<id>/update/`
Update course.

### `GET/POST /courses/<id>/delete/`
Delete course.

### `GET/POST /courses/<id>/content/create/`
Upload course material.

### `POST /content/<id>/delete/`
Delete course material.

---

## 23. Profile Endpoints

### `GET/POST /trainer-profile/create/`
Create trainer profile.

### `GET/POST /trainer-profile/<id>/edit/`
Edit trainer profile.

### `GET /trainer-profile/list/`
List trainer profiles.

### `POST /trainer-profile/<id>/delete/`
Delete trainer profile.

### `GET/POST /company-profile/create/`
Create company profile.

### `GET/POST /company-profile/<id>/edit/`
Edit company profile.

### `GET /company-profile/list/`
List company profiles.

### `POST /company-profile/<id>/delete/`
Delete company profile and associated PDF file.

---

## 24. Error Handling

| Status | Cause | Response |
|--------|-------|---------|
| 302 | Unauthenticated access | Redirect to `/accounts/login/?next={url}` |
| 302 | Invalid SSO token | Redirect to login with error message |
| 403 | Non-admin attempts admin action | Redirect with permission error |
| 404 | Object not found | Django 404 page |
| 502 | CRM not reachable | JSON `{"error": "CRM error <code>"}` |
| 500 | Server error | Django error page (or debug log in production) |

---

## 25. CSRF Token Usage

**HTML forms:**
```html
<form method="post">
    {% csrf_token %}
    ...
</form>
```

**AJAX POST requests:**
```javascript
const csrftoken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? '';
fetch('/validate-coupon/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ code: couponCode })
});
```

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
