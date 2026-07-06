# Orbit ERP — Advanced Features & Gap Analysis Roadmap
**Institute Management System | Date: 2026-07-06 | Version: 2.0**

> **Migration Safety Note:** Every feature in this document is designed to be additive — new tables, new columns with defaults, new views. Nothing modifies or removes existing columns, tables, or data that the running system depends on.

---

## Implementation Status Key

| Symbol | Meaning |
|--------|---------|
| DONE | Fully implemented and live |
| PARTIAL | Core implemented; enhancements remain |
| OPEN | Not yet started |
| DEFERRED | Removed from scope |

---

## 1. Critical Code Bugs

### B1 — `__str__` Method Typos — DONE
All model `_str_()` typos have been corrected. Dropdowns and admin panels display correctly.

### B2 — Duplicate Total Calculation Logic — OPEN
`Invoice.calculate_total_amount()` and `Invoice.get_total_amount()` still both exist. Views may call either one inconsistently.

**Fix:** Audit all view calls. Remove `get_total_amount()`, use `calculate_total_amount()` everywhere.
**DB change:** None.

### B3 — Certificate Data Integrity — OPEN
`Certificate.register_number` is a plain string (not FK). If a Registration's `registration_number` changes, certificates become stale.

**Fix:** Add lookup helper; flag mismatches in admin.
**DB change:** None.

### B4 — Admin Hardcode in Legacy View — DONE
`if request.user.username == 'admin':` replaced with `is_admin_user(request.user)` throughout.

---

## 2. Student Lifecycle Management

### S1 — Student Status Tracking — DONE
`Registration.student_status` field implemented with values: `active`, `completed`, `dropped`, `suspended`, `pending`.
- `POST /student/<pk>/status/` endpoint implemented
- Status badge displayed on registration detail page

### S2 — Student Self-Registration Link — DONE
`StudentFormLink` model implemented. Token-based URL allows student to submit their own details (without pricing visibility).
- Generate link at `/portal/student-links/generate/`
- Student submits at `/portal/student/<token>/`

### S3 — Student Portal (Full) — OPEN
Full student-facing portal (login, view own invoices, download certificates).
**Effort:** HIGH | **DB:** New `StudentUser` table or extend existing auth.

### S4 — Attendance Tracking — DEFERRED
Out of scope per project constraint. System already tracks `student_status` as a proxy.

---

## 3. Financial & Accounting

### F1 — Level-Based Pricing — DONE
`Course` model has 6 price fields: `oo_intermediate`, `oo_professional`, `oo_advanced`, `priv_intermediate`, `priv_professional`, `priv_advanced`. `get_rate(class_type, level)` method implemented.

Legacy flat rates (`rate`, `batch_rate`, `online_rate`, `private_rate`) preserved for backward compatibility.

### F2 — VAT Separation — DONE
`vat_rate` stored as `0.05` decimal. Applied additively: `total = subtotal × 1.05`. Never back-calculated into price.

### F3 — Discount Cap Enforcement — DONE
- Single course: max 20%
- Multi-course invoice: max 30%
- Enforced in frontend JS and backend validation

### F4 — Installment Payment Tracking — DONE
`InvoicePayment` model records individual payment installments per invoice.
- `GET /invoice/<pk>/payments/` — view installment history
- `POST /invoice/<pk>/payments/add/` — record new payment

### F5 — Expense Tracking & Input VAT — DONE
`Expense` model with categories: rent, salaries, marketing, software, travel, utilities, other.
- VAT report at `/reports/vat/` compares output VAT (from invoices) vs input VAT (from expenses).

### F6 — Coupon Enhancement — DONE
Added to `Coupon` model: `expiry_date`, `max_uses`, `used_count`. Coupon validation endpoint checks expiry and usage count.

### F7 — Recurring Invoice / Auto-Reminder — PARTIAL
`FeeReminderLog` model and fee reminder dashboard at `/fee-reminders/` implemented.
Actual automated email delivery (cronjob or celery) not confirmed as implemented.

**Remaining:** Add Django management command or Celery task to send daily fee reminder emails.
**DB change:** None.

### F8 — Quotation → Invoice Conversion — OPEN
High-value workflow: "Convert to Invoice" button on quotation detail page, pre-populating invoice form.
**Effort:** MEDIUM | **DB:** None (uses existing Invoice + InvoiceItem models).

### F9 — Quotation Per-Item Price Override — DONE
`QuotationItemOverride` model allows admin to override the computed price per quotation item.

### F10 — Quotation Acceptance Workflow — OPEN
Add `status` field to `Quotation`: draft/sent/accepted/rejected/expired. "Mark Accepted" button records acceptance date and auto-creates invoice.
**Effort:** MEDIUM | **DB:** Add `status`, `accepted_at` columns to Quotation (new columns, no structural change).

### F11 — Quotation Expiry Date — OPEN
Add `expiry_date` to `Quotation` model. Show "Expired" badge if past due.
**Effort:** LOW | **DB:** New nullable column.

### F12 — Bulk Payment Upload / Reconciliation — OPEN
Import a CSV of bank transactions and auto-match to invoices.
**Effort:** HIGH | **DB:** New `BankImport` table.

---

## 4. Academic Operations

### A1 — Training Schedule — DONE (partial)
`TrainingSchedule` model with fields: `registration`, `course`, `trainer`, `location`, `start_date`, `end_date`, `status`.
- CRUD at `/schedule/`
- No calendar/Gantt view yet

**Remaining:** Add calendar view (FullCalendar.js integration).
**Effort:** MEDIUM | **DB:** None.

### A2 — Trainer Conflict Detection — OPEN
Check for double-booked trainer/room when creating a TrainingSchedule.
**Effort:** MEDIUM | **DB:** None (logic only).

### A3 — Course Prerequisite Mapping — OPEN
**Effort:** LOW | **DB:** New `CoursePrerequisite` junction table.

---

## 5. HR & Trainer Management

### H1 — Trainer Profile — DONE
`TrainerProfile` model with PDF upload. List at `/trainer-profile/list/`.

### H2 — Staff Leave Management — OPEN
**Effort:** HIGH | **DB:** New `LeaveRequest` table.

---

## 6. Reporting & Business Intelligence

### R1 — Revenue Report — DONE
`/reports/revenue/` with date range, consultant, and class type filters. CSV export at `/reports/revenue/export/`.

### R2 — Receivables Aging Report — DONE
`/reports/aging/` groups overdue invoices by 0–15, 16–30, 31–60, 61–90, 90+ days.

### R3 — VAT Report — DONE
`/reports/vat/` compares output VAT (invoices) vs input VAT (expenses).

### R4 — Enrollment Report — DONE
`/reports/enrollment/` by period, consultant, course, class type.

### R5 — Certificate Report — DONE
`/reports/certificates/` by period, type, course.

### R6 — Executive Performance Report — PARTIAL
Revenue report can filter by consultant. Dedicated target vs actual report not implemented.

**Remaining:** Build target-vs-actual dashboard: compare `SalesTarget.target_amount` with actual invoiced amount per consultant per month.
**DB change:** None.

### R7 — Report Exports (CSV/PDF) — PARTIAL
Revenue report has CSV export. Aging, VAT, enrollment reports do not have export.
**Effort:** LOW (each) | **DB:** None.

---

## 7. Notifications & Communication

### N1 — In-App Notifications — DONE
`Notification` model. Bell icon in sidebar shows unread count (via context processor). Read/read-all endpoints implemented.

### N2 — Email Notifications for Due Invoices — PARTIAL
`FeeReminderLog` model tracks reminder history. Dashboard at `/fee-reminders/` shows due invoices.

**Remaining:** Django management command (`python manage.py send_fee_reminders`) that sends emails and logs to `FeeReminderLog`. Schedule via cron.
**DB change:** None.

### N3 — SMS Notifications — OPEN
**Effort:** MEDIUM | **DB:** Add `sms_sent` flag to `FeeReminderLog`.

---

## 8. Payments & Integrations

### P1 — Online Payment Gateway — OPEN
Tabby and Tamara are tracked as payment method strings on Invoice. No actual gateway integration.
**Effort:** HIGH | **DB:** New `PaymentGatewayTransaction` table.

### P2 — WhatsApp Notification — OPEN
Send invoice/reminder via WhatsApp API.
**Effort:** MEDIUM | **DB:** Log to `FeeReminderLog` channel field.

---

## 9. Security & Compliance

### SC1 — Audit Log (Login/Logout) — DONE
`AuditLog` model. Signals auto-log login and logout with IP address (reads X-Forwarded-For).

### SC2 — Role-Based Access Control — DONE
`UserProfile.role` with values: `admin`, `sales_manager`, `accounts`, `sales_executive`. `is_admin_user()` gating on admin views.

### SC3 — Audit Log (Model Changes) — OPEN
Currently only login/logout are auto-logged. Create/update/delete of Invoices, Registrations, etc. are not logged.

**Effort:** MEDIUM | **DB:** None (AuditLog model already exists).
**Approach:** Add `post_save`/`post_delete` signals for key models, or use a library like `django-simple-history`.

### SC4 — Brute-Force Login Protection — OPEN
**Effort:** LOW | **DB:** None.
**Approach:** Install `django-axes`, configure 10-attempt lockout with 15-minute reset.

### SC5 — Session Timeout — OPEN
**Effort:** LOW | **DB:** None.
**Approach:** Set `SESSION_COOKIE_AGE = 43200` in settings.

---

## 10. System Administration

### SA1 — User Management Panel — DONE
`/manage/users/` — list, edit, role assignment, password change, delete.
`/manage/set-targets/` — monthly target setting per user.
`/manage/sync-crm/` — batch sync of sales users to Flask CRM.

### SA2 — CRM SSO Bridge — DONE
`/crm-jump/` and `/crm-auth/` endpoints with HMAC token bridge. Token TTL 90 seconds.

### SA3 — Company Portal — DONE
`CompanyPortalRequest` + `CompanyPortalAttendee` models.
- Admin generates link at `/admin-portal/generate/`
- Company submits at `/portal/company/<token>/`
- Admin reviews and approves at `/admin-portal/<id>/approve/`

### SA4 — Global Search — DONE
`/search/` endpoint searches registrations, invoices, courses, certificates.

---

## 11. UI / UX Enhancements

### UX1 — Pagination on List Views — OPEN
All major lists (registrations, invoices, certificates, expenses, schedules) load all records.
**Effort:** LOW (per view) | **DB:** None.

### UX2 — Calendar View for Training Schedule — OPEN
Integrate FullCalendar.js into `/schedule/` for drag-and-drop scheduling.
**Effort:** MEDIUM | **DB:** None.

### UX3 — Quotation PDF Print View — OPEN
Currently quotations have no print/PDF template.
**Effort:** LOW | **DB:** None.

### UX4 — Column Sorting on Tables — OPEN
**Effort:** LOW (JS, django-tables2, or manual) | **DB:** None.

### UX5 — Empty State Illustrations — OPEN
**Effort:** LOW | **DB:** None.

---

## 12. Priority Matrix

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| P1 | Quotation → Invoice conversion (F8) | Medium | High |
| P1 | Pagination on list views (UX1) | Low | High |
| P1 | Brute-force login protection (SC4) | Low | High |
| P2 | Fee reminder email automation (N2) | Medium | High |
| P2 | Training schedule conflict detection (A2) | Medium | Medium |
| P2 | Audit log for model changes (SC3) | Medium | High |
| P2 | Session timeout config (SC5) | Low | Medium |
| P2 | Quotation acceptance workflow (F10) | Medium | Medium |
| P3 | Revenue report: target vs actual (R6) | Medium | Medium |
| P3 | Report CSV exports for aging/VAT (R7) | Low | Low |
| P3 | Quotation expiry date (F11) | Low | Low |
| P3 | Calendar view for schedule (UX2) | Medium | Medium |
| P4 | Student full portal (S3) | High | Medium |
| P4 | Online payment gateway (P1) | High | High |
| P4 | Staff leave management (H2) | High | Low |

---

## 13. Implementation Phases (Updated)

### Phase 1 — COMPLETED
- User roles and targets
- Level-based pricing
- Coupon enhancement
- Expense tracking
- Fee reminder foundation
- In-app notifications
- Audit log (login/logout)
- Training schedule
- Student status
- Company portal
- Student form links
- Installment payments
- Revenue / Aging / VAT / Enrollment reports
- CRM SSO bridge

### Phase 2 — NEXT (3–4 weeks)
- Pagination on all list views
- Brute-force login protection (django-axes)
- Session timeout configuration
- Fee reminder email automation (management command + cron)
- Quotation → Invoice conversion
- Audit log for model-level changes

### Phase 3 — MEDIUM TERM (1–3 months)
- Quotation acceptance workflow and expiry
- Training schedule conflict detection + calendar view
- Executive target-vs-actual report
- Report CSV exports (aging, VAT)
- Media file auth for sensitive documents

### Phase 4 — LONG TERM
- Student portal (login, view invoices, download certificates)
- Online payment gateway integration
- WhatsApp notification integration
- Staff leave management

---

*Document updated: 2026-07-06*
*Phase 1 reflects all features implemented as of 2026-07-06*
