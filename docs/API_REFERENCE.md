# API Reference Document
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
**Type:** Internal Django Views / AJAX Endpoints + CRM Internal API

---

## 1. Overview

Orbit ERP is a server-rendered Django application with AJAX endpoints for dynamic interactions. The system also exposes an internal API endpoint used by the ERP to look up CRM leads.

**Base URL (local):** `http://localhost:8000/`
**Base URL (VPS):** `https://orbittraining.online/`
**CRM URL (local):** `http://localhost:5000/`

**Authentication:** Session-based (`sessionid` cookie) for all Django views.
**CSRF:** Required on all POST requests.
**CRM Internal API:** HMAC Bearer token (`Authorization: Bearer <CRM_SSO_SECRET>`).

---

## 2. Authentication

### `GET /accounts/login/`
Display login form.

### `POST /accounts/login/`
| Parameter | Required | Notes |
|-----------|----------|-------|
| username | Yes | |
| password | Yes | |
| csrfmiddlewaretoken | Yes | |

**Success:** Redirect to `/` · **Side effect:** AuditLog login entry

### `GET /logout/`
Log out. Redirect to login. AuditLog logout entry.

### `GET /crm-jump/`
Generate HMAC SSO token → redirect to CRM auto-login.

### `GET /crm-auth/`
Receive SSO token from CRM, verify, log user in, redirect.

| Query Param | Notes |
|-------------|-------|
| t | HMAC token (required) |
| crm_id | CRM lead ID (optional — triggers registration pre-fill) |
| fn, ln | First/Last name (optional) |
| ph, em | Phone, email (optional) |

---

## 3. User Management

| Method | URL | Access | Notes |
|--------|-----|--------|-------|
| GET | `/signup/` | Admin | Show add-user form (role cards UI) |
| POST | `/signup/` | Admin | Create user; auto-sync sales roles to CRM |
| GET | `/manage/users/` | Admin | User list with roles and actions |
| GET/POST | `/manage/users/<id>/edit/` | Admin | Edit user details and role |
| POST | `/manage/users/<id>/delete/` | Admin | Delete user |
| POST | `/manage/users/<id>/change-password/` | Admin | Set new password |
| GET | `/manage/set-targets/` | Admin | View/set monthly sales targets |

---

## 4. Registrations

| Method | URL | Access | Notes |
|--------|-----|--------|-------|
| GET/POST | `/register/` | All | Individual or corporate registration |
| GET | `/student-dashboard/` | All | Registration list |
| GET/POST | `/edit-registration/<pk>/` | All* | Edit registration (* 1-hr lock for sales_executive) |
| GET/POST | `/edit-corporate-registration/<pk>/` | All* | Edit corporate (* 1-hr lock for sales_executive) |
| POST | `/student/<pk>/status/` | All | Update student status |
| GET | `/registration/<pk>/print/` | All | Printable registration form |
| GET/POST | `/registrations/<pk>/refund/` | All | Initiate refund |
| POST | `/registrations/<pk>/send-cert-request/` | All | Send cert request email to client |

---

## 5. Invoices

| Method | URL | Notes |
|--------|-----|-------|
| GET/POST | `/create_invoice/` | Create sales invoice |
| GET/POST | `/edit_invoice/<pk>/` | Edit invoice |
| POST | `/delete_invoice/<pk>/` | Delete invoice |
| GET | `/invoice/<pk>/` | View/print invoice |
| POST | `/invoice/<pk>/mark-paid/` | Quick mark as paid |
| POST | `/invoices/bulk-action/` | Bulk status update |
| GET/POST | `/invoice/<pk>/payments/add/` | Add payment installment |
| GET/POST | `/create_purchase_invoice/` | Create purchase invoice (corporate mode auto-sets persons=1) |
| GET/POST | `/edit_purchase_invoice/<pk>/` | Edit purchase invoice |
| POST | `/delete_purchase_invoice/<pk>/` | Delete purchase invoice |

---

## 6. Courses

| Method | URL | Notes |
|--------|-----|-------|
| GET | `/courses/` | Course list (zero prices shown as —) |
| GET/POST | `/courses/create/` | Create course |
| GET/POST | `/courses/<pk>/edit/` | Edit course |
| POST | `/courses/<pk>/delete/` | Delete course |
| GET/POST | `/courses/<pk>/content/` | Upload course content |
| GET | `/courses/<pk>/` | Course detail with enrollments |

---

## 7. Certificates

| Method | URL | Notes |
|--------|-----|-------|
| GET | `/certificates/` | Certificate dashboard |
| GET/POST | `/certificates/create/` | Issue new certificate |
| POST | `/certificates/<pk>/delete/` | Delete certificate (Admin only) |
| GET | `/certificates/<pk>/print/` | Print certificate |
| GET/POST | `/certificates/khda-form/` | KHDA certificate upload form |
| POST | `/certificates/create-khda/` | Create KHDA certificate |
| **GET** | **`/cert-request/<uuid:token>/`** | **Public — no login — client completion form** |
| **POST** | **`/cert-request/<uuid:token>/`** | **Client submits completion details** |
| **GET** | **`/cert-requests/`** | **Admin review list (?status=submitted/pending/approved/rejected/all)** |
| **POST** | **`/cert-requests/<pk>/generate/`** | **Admin generates certificate from request** |
| **POST** | **`/cert-requests/<pk>/reject/`** | **Admin rejects certificate request** |

---

## 8. Quotations

| Method | URL | Notes |
|--------|-----|-------|
| GET | `/quotation/` | Quotation dashboard (no PI button) |
| GET/POST | `/create_quotation/` | Create quotation |
| GET/POST | `/edit_quotation/<pk>/` | Edit quotation |
| POST | `/delete_quotation/<pk>/` | Delete quotation (Admin only) |
| GET | `/quotation_detail/<pk>/` | Print/view quotation |
| POST | `/validate-coupon/` | AJAX — validate coupon code |

---

## 9. Proposals

| Method | URL | Notes |
|--------|-----|-------|
| GET | `/proposals/` | Proposal dashboard (redesigned table UI) |
| GET/POST | `/create_proposal/` | Create proposal (sectioned form) |
| GET/POST | `/edit_proposal/<pk>/` | Edit proposal (shows current logo + remove option) |
| POST | `/delete_proposal/<pk>/` | Delete proposal (Admin only) |
| GET | `/print_proposal/<pk>/` | Print proposal |

---

## 10. Refunds *(v3)*

| Method | URL | Access | Notes |
|--------|-----|--------|-------|
| GET/POST | `/registrations/<pk>/refund/` | All | Initiate refund (reason + doc + amount) |
| GET | `/refunds/<pk>/confirm/` | Admin/Accounts | Show confirmation page |
| POST | `/refunds/<pk>/confirm/` | Admin/Accounts | `action=confirm` or `action=cancel` |
| GET | `/refunds/` | Admin/Accounts | Refund list with filter tabs |

---

## 11. Institute Settings *(v3)*

| Method | URL | Access | Notes |
|--------|-----|--------|-------|
| GET | `/settings/` | Admin | View settings (tabbed: Company/Branding/Banking/Social) |
| POST | `/settings/` | Admin | Save settings (partial saves allowed) |

---

## 12. Reporting

| Method | URL | Notes |
|--------|-----|-------|
| GET | `/reports/revenue/` | Revenue report; excludes refunded |
| GET | `/reports/revenue/export/` | CSV export |
| GET | `/reports/aging/` | Receivables aging |
| GET | `/reports/vat/` | VAT report |
| GET | `/reports/enrollment/` | Enrollment report |
| GET | `/reports/certificates/` | Certificate report |
| GET | `/expenses/report/` | Expense report |
| GET | `/fee-reminders/` | Fee reminder dashboard |

---

## 13. AJAX / Internal Endpoints

| Method | URL | Notes |
|--------|-----|-------|
| POST | `/validate-coupon/` | `{code}` → `{valid, discount_percentage, message}` |
| GET | `/api/crm-lead/<int:lead_id>/` | Fetch CRM lead data for form pre-fill |
| GET | `/api/corporate-pi-data/` | Corporate PI data `?company_id=` or `?company_name=` |
| GET | `/api/search-corporate-companies/` | Autocomplete `?q=` → `{results:[{id,name}]}` |
| GET | `/api/search-registrations/` | Registration lookup for invoice form |
| GET | `/api/clients/` | Client autocomplete |
| GET | `/notifications/` | Unread notifications JSON |
| POST | `/notifications/<id>/read/` | Mark notification read |
| POST | `/notifications/read-all/` | Mark all read |
| GET | `/search/` | Global search across registrations/invoices/courses/certs |

---

## 14. Public (No Login Required) Endpoints

| URL | Notes |
|-----|-------|
| `/accounts/login/` | Login page |
| `/cert-request/<uuid:token>/` | Client certificate completion form |
| `/portal/company/<token>/` | Company self-registration portal |
| `/portal/company/<token>/attendees/` | Add company attendees |
| `/portal/student/<token>/` | Student self-registration |

---

## 15. CRM Internal API (Flask → Django)

Called by ERP to fetch lead data:

```
GET {CRM_URL}/api/internal/lead/<id>
Authorization: Bearer <CRM_SSO_SECRET>
```

**Response:**
```json
{
  "id": 42,
  "full_name": "Ali Hassan",
  "status": "Qualified",
  "phone": "+971501234567",
  "email": "ali@example.com",
  "interested_course": "Project Management"
}
```

---

*Document updated: 2026-07-13*
*Version 3.0 — adds Refund, Certificate Request, Institute Settings, and all v3 endpoints*
