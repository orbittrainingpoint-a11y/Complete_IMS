# Orbit ERP — Advanced Features & Gap Analysis Roadmap
**Institute Management System | Date: 2026-07-13 | Version: 3.0**

> **Migration Safety Note:** Every feature in this document is designed to be additive — new tables, new columns with defaults, new views. Nothing modifies or removes existing columns, tables, or data that the running system depends on.

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Completed and deployed |
| 🔄 | In progress |
| ⏳ | Planned — not yet started |
| ❌ | Excluded from scope |

---

## Completed in v3 (July 2026)

All items below were completed during the 2026-07-06 to 2026-07-13 sprint:

| Feature | Description |
|---------|-------------|
| ✅ Refund Management | Full lifecycle: initiate → confirm/cancel; email; revenue exclusion via `is_refunded` flag |
| ✅ Certificate Request Flow | UUID token email → public client form → admin review → auto-generate certificate |
| ✅ Class Feedback (required) | `class_feedback` text field on cert request; required before submit; shown in admin |
| ✅ Institute Settings | Singleton settings page: company info, branding uploads, banking, social links |
| ✅ Safe Lead Delete | CRM delete_lead clears child FK records before deleting parent |
| ✅ Corporate PI Fix | Number of Persons hidden in corporate PI mode; read-only candidate count shown |
| ✅ PI Button Removed | Removed PI button from quotation table — cannot create PI from quotation |
| ✅ Redesigned Add-User Form | Role cards, gradient hero, live password match indicator |
| ✅ Proposal UI Redesign | Dashboard, create, edit pages match system design language |
| ✅ 1-Hour Edit Lock | Sales executives blocked from editing registrations after 60 minutes |
| ✅ Refunded Registration State | REFUNDED badge, opacity, red banner; excluded from all revenue queries |
| ✅ Certificate Delete (Admin) | Admin can delete certificates from dashboard with confirmation modal |
| ✅ Previous Payment Reference | Shown on invoice form only when a prior invoice exists for the registration |
| ✅ CRM SSO | HMAC bidirectional auto-login between ERP and CRM |
| ✅ User→CRM Sync | Sales roles auto-synced to CRM database on create/edit |

---

## Phase 1 — High Priority (Next Sprint)

### 1.1 Login Rate Limiting
- **What:** Block brute-force login attempts after N failures
- **How:** Install `django-axes`; configure `AXES_FAILURE_LIMIT = 5`, `AXES_COOLOFF_TIME = 1` hour
- **DB change:** Adds `axes_*` tables (new — safe)

### 1.2 Certificate Request Token Expiry
- **What:** Public cert-request links expire after 7 days
- **How:** Add `expires_at` DateTimeField to `CertificationRequest`; check in `cert_request_form` view
- **DB change:** `AddField` on `CertificationRequest` — safe

### 1.3 Automated Database Backups
- **What:** Nightly `mysqldump` to `/backups/` with 30-day retention
- **How:** Cron job on VPS: `0 2 * * * mysqldump orbit_invoice > /backups/orbit_$(date +\%Y\%m\%d).sql`
- **DB change:** None

### 1.4 Password Policy
- **What:** Enforce minimum 8 characters, require complexity on signup and password change
- **How:** Add `AUTH_PASSWORD_VALIDATORS` in `settings.py`; update error messages in templates
- **DB change:** None

### 1.5 Receipt Generation
- **What:** Dedicated printable receipt (simpler than invoice — just amount paid + reference)
- **How:** New template `invoices/receipt_print.html`; new URL `/invoice/<pk>/receipt/`
- **DB change:** None

---

## Phase 2 — Medium Priority

### 2.1 Bulk Certificate Generation (CSV Import)
- **What:** Upload a CSV of students to auto-generate multiple certificates
- **How:** New view + template; parse CSV; create Certificate rows; download report of results
- **DB change:** None (creates Certificate records using existing model)

### 2.2 Quotation Expiry Date
- **What:** Quotations auto-expire after a configurable number of days
- **How:** `AddField expires_at` to `Quotation`; visual warning when near/past expiry; filter in quotation list
- **DB change:** `AddField` on `Quotation` — safe

### 2.3 Proposal → PDF Export (Server-Side)
- **What:** Generate a proper PDF instead of browser print
- **How:** Install `weasyprint` or `xhtml2pdf`; add `/print_proposal/<pk>/pdf/` URL returning `application/pdf`
- **DB change:** None

### 2.4 Sales Executive Leaderboard
- **What:** Performance comparison across executives — registrations, revenue, target %
- **How:** New report view using existing `SalesTarget` and Registration data
- **DB change:** None

### 2.5 CRM In-App Notifications
- **What:** Notify CRM users when a lead is assigned or a follow-up is due
- **How:** Add `crm_notification` table in leads_db; show bell icon in CRM nav
- **DB change:** New table in leads_db — safe

---

## Phase 3 — Lower Priority / Future

### 3.1 Multi-Factor Authentication (MFA)
- **What:** TOTP for admin and accounts roles
- **How:** Install `django-otp` + `qrcode`; add setup/verify views; enforce on admin logins
- **DB change:** Adds `otp_*` tables — safe

### 3.2 Student Self-Service Portal
- **What:** Students view their own registration, invoices, certificate status
- **How:** Token-based access (extend existing StudentFormLink pattern); read-only views
- **DB change:** Possible `AddField` for portal token on Registration — safe

### 3.3 Scheduled Report Emails
- **What:** Email revenue/enrollment summary to managers weekly
- **How:** Celery + Redis worker; cron-style periodic tasks
- **DB change:** Adds Celery task result tables — safe

### 3.4 Quotation → Proposal Auto-Population
- **What:** Pre-fill proposal from a confirmed quotation
- **How:** New view that reads quotation data and creates Proposal with fields mapped
- **DB change:** None

### 3.5 Multi-Language Support
- **What:** Arabic language option for printed documents (invoices, certificates)
- **How:** Django i18n; separate Arabic PDF templates; RTL CSS
- **DB change:** None

### 3.6 Payment Gateway Integration
- **What:** Tabby and Tamara payment links generated from invoice page
- **How:** New `PaymentGateway` model; API integration with provider SDKs; webhook handler
- **DB change:** New `invoices_paymentgateway` table — safe

---

## Permanently Excluded

| Feature | Reason |
|---------|--------|
| Attendance tracking | Explicitly excluded from scope by stakeholder |
| Payroll module | Out of scope — handled separately |
| HR management | Out of scope |

---

## Technical Debt to Address

| Item | Priority |
|------|---------|
| Split `views.py` (2000+ lines) into module files | Medium — maintainability |
| Add automated test suite | Medium — currently no tests |
| Separate `settings_local.py` from `settings.py` | Low — secrets management |
| Move to `django-environ` for env-based config | Low — quality of life |
| Upgrade gunicorn worker count based on VPS CPU | Low |

---

*Document updated: 2026-07-13*
*Version 3.0 — marks all v3 features as completed; updated roadmap phases; added technical debt section*
