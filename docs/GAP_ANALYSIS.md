# Gap Analysis — Orbit ERP Institute Management System
**Date:** 2026-07-06 | **Version:** 2.0

---

## Executive Summary

Since the original gap analysis (v1.0, 2026-06-25), significant development has occurred. Multiple FIXED items now reflect implemented features. This document updates every finding with current status and identifies new gaps introduced by the expanded feature set.

---

## 1. UI / UX Gaps

| # | Area | Gap | Severity | Status |
|---|------|-----|----------|--------|
| U1 | All tables | No search/filter on most list pages | HIGH | PARTIAL — student dashboard, invoice dashboard have filters; others still lack them |
| U2 | All tables | No pagination — all records load at once | HIGH | OPEN |
| U3 | All tables | No column sorting | MEDIUM | OPEN |
| U4 | Tables | Inconsistent action button styles | MEDIUM | PARTIAL |
| U5 | CRM section | Lead table used Tailwind; rest uses Bootstrap | MEDIUM | RESOLVED — CRM is now a separate Flask app; Django no longer has a lead UI |
| U6 | Corporate | Courses displayed as nested `<ul>` in table cell | LOW | OPEN |
| U7 | Company/Trainer profiles | Only Name column shown | HIGH | OPEN |
| U8 | Certificates | No filter/search on certificate list | MEDIUM | OPEN |
| U9 | All | No empty-state illustrations on empty tables | LOW | OPEN |
| U10 | Invoice detail | Cannot print/edit invoice from registration detail page | MEDIUM | OPEN |
| U11 | Student reg detail | No payment summary / total paid vs outstanding | HIGH | PARTIAL — InvoicePayment model added; UI integration unclear |
| U12 | Student reg list | No date filter, no class type filter | MEDIUM | PARTIAL |
| U13 | Quotation list | Duplicate "Quotation Number" column | HIGH | OPEN |
| U14 | General | No breadcrumbs on several pages | LOW | OPEN |
| U15 (NEW) | Notifications | Bell icon shows unread count but dropdown UX is basic | MEDIUM | OPEN |
| U16 (NEW) | Training Schedule | No calendar/Gantt view — list only | MEDIUM | OPEN |
| U17 (NEW) | Audit Log | No live filtering — full page reload per filter | LOW | OPEN |

---

## 2. Functional Gaps

| # | Area | Gap | Severity | Status |
|---|------|-----|----------|--------|
| F1 | Invoices | No TRN field on client | HIGH | FIXED — `trn_number` field added to Client |
| F2 | User Roles | No role-based access | HIGH | FIXED — UserProfile model + `is_admin_user()` check |
| F3 | Targets | No monthly target setting | HIGH | FIXED — SalesTarget model + management view |
| F4 | Certificate | Certificate expiry date not tracked | MEDIUM | OPEN |
| F5 | Certificate | No batch certificate printing | LOW | OPEN |
| F6 | Coupons | No usage count / max-use limit | MEDIUM | FIXED — `used_count`, `max_uses` added to Coupon |
| F7 | Coupons | No expiry date on coupons | MEDIUM | FIXED — `expiry_date` added to Coupon |
| F8 | Registration | No fee structure per course (flat rate only) | MEDIUM | FIXED — 6 level-based price fields on Course + `get_rate()` method |
| F9 | Registration | No attendance tracking per course | HIGH | OPEN (excluded from scope per constraint) |
| F10 | Registration | No student portal / login for students | HIGH | PARTIAL — StudentFormLink allows token-based self-registration without pricing; full student portal not implemented |
| F11 | Invoice | No recurring invoice / instalment auto-reminder | MEDIUM | PARTIAL — FeeReminderLog and fee reminder dashboard added; auto-send not implemented |
| F12 | Invoice | No bulk payment upload / reconciliation | LOW | OPEN |
| F13 | Quotation | Quotation acceptance workflow missing | HIGH | OPEN |
| F14 | Quotation | No expiry date on quotations | MEDIUM | OPEN |
| F15 | Quotation | No conversion from quotation → invoice | HIGH | OPEN |
| F16 | HR | No trainer schedule / availability tracking | MEDIUM | PARTIAL — TrainingSchedule model tracks course/trainer/dates; no availability conflict detection |
| F17 | HR | No staff leave management | LOW | OPEN |
| F18 | Reports | No monthly/quarterly revenue report export | HIGH | FIXED — Revenue report + CSV export at `/reports/revenue/` |
| F19 | Reports | No executive performance report | MEDIUM | PARTIAL — Revenue report filters by consultant |
| F20 | Notifications | No email/SMS for due invoices | HIGH | PARTIAL — Fee reminder dashboard + FeeReminderLog; actual email delivery not confirmed |
| F21 | Notifications | No follow-up reminders for leads | MEDIUM | OPEN — follow-up management is in Flask CRM |
| F22 | Discount | No discount cap enforcement | HIGH | FIXED — 20% single course / 30% multi-course, enforced frontend + backend |
| F23 | VAT | VAT calculation not separated from price | HIGH | FIXED — vat_rate stored as 0.05 decimal; applied additively on top of price |
| F24 | Course | No course scheduling / calendar view | HIGH | PARTIAL — TrainingSchedule list view only; no calendar UI |
| F25 | Course | No prerequisite course mapping | LOW | OPEN |
| F26 (NEW) | Registration | No student status lifecycle management | HIGH | FIXED — `student_status` field (active/completed/dropped/suspended/pending) + update endpoint |
| F27 (NEW) | Company Portal | No corporate self-registration portal | MEDIUM | FIXED — CompanyPortalRequest + CompanyPortalAttendee models + token portal |
| F28 (NEW) | Audit | No audit trail for data changes | HIGH | FIXED — AuditLog model, login/logout auto-logged via signals |
| F29 (NEW) | Notifications | No in-app notification system | HIGH | FIXED — Notification model + bell icon + read/unread endpoints |
| F30 (NEW) | Expenses | No expense tracking / input VAT | MEDIUM | FIXED — Expense model + VAT report (output vs input VAT) |
| F31 (NEW) | Payments | No installment payment tracking on invoices | HIGH | FIXED — InvoicePayment model + payment history view |
| F32 (NEW) | Quotation | No per-item price override capability | MEDIUM | FIXED — QuotationItemOverride model |
| F33 (NEW) | Quotation | Conversion from quotation → invoice | HIGH | OPEN |
| F34 (NEW) | CRM Integration | No lead-to-registration pipeline | HIGH | FIXED — SSO bridge; CRM "Register in ERP" pre-fills registration form |

---

## 3. Technical / Architecture Gaps

| # | Area | Gap | Severity | Status |
|---|------|-----|----------|--------|
| T1 | Settings | Debug mode hardcoded True | CRITICAL | FIXED — env-var driven |
| T2 | Settings | Secret key hardcoded | CRITICAL | FIXED — env-var driven |
| T3 | Settings | DB password hardcoded | CRITICAL | FIXED — env-var driven |
| T4 | DB | Root database user in production | HIGH | FIXED — dedicated `orbit_app` user |
| T5 | Code | `__str__` typos (`_str_()`) in models | MEDIUM | FIXED |
| T6 | Code | Admin username hardcoded in views | MEDIUM | FIXED — `is_admin_user()` function |
| T7 | Code | Duplicate total calculation methods | MEDIUM | OPEN — verify `get_total_amount()` vs `calculate_total_amount()` |
| T8 | Deployment | IIS/wfastcgi production server | HIGH | FIXED — replaced with Gunicorn + Apache on Ubuntu VPS |
| T9 | Security | No brute-force protection on login | MEDIUM | OPEN |
| T10 | Security | Session timeout not configured | MEDIUM | OPEN |
| T11 | Performance | No pagination on list views | HIGH | OPEN |
| T12 | Performance | No caching layer | LOW | OPEN |
| T13 | Architecture | ERP directly writes to CRM DB (pymysql) | MEDIUM | OPEN — recommend CRM API endpoint |
| T14 (NEW) | Security | Media files for sensitive docs publicly accessible | MEDIUM | OPEN |
| T15 (NEW) | Collation | MariaDB (local) vs MySQL 8 (VPS) collation mismatch | LOW | Known — not causing errors, review if migrating fresh data |

---

## 4. Data Quality Gaps

| # | Area | Gap | Severity | Status |
|---|------|-----|----------|--------|
| D1 | Certificate | `register_number` is plain string, not FK | MEDIUM | OPEN — lookup helper not implemented |
| D2 | Certificate | `course_name` is plain string, not FK | MEDIUM | OPEN |
| D3 | Registration | Duplicate registration detection not enforced | MEDIUM | OPEN |
| D4 | Client | Duplicate client detection by email | LOW | OPEN |

---

## 5. Newly Identified Gaps (v2.0)

These gaps emerged from the expanded system and were not visible in v1.0:

| # | Area | Gap | Severity |
|---|------|-----|----------|
| N1 | Notifications | No email delivery for in-app notifications | MEDIUM |
| N2 | Fee Reminders | No automated email sending (manual dashboard only) | MEDIUM |
| N3 | Training Schedule | No conflict detection (double-booked trainer/room) | MEDIUM |
| N4 | Company Portal | No email notification when portal submission approved | LOW |
| N5 | Student Form Link | Link does not expire or deactivate after use | LOW |
| N6 | Audit Log | Only login/logout logged via signals; model-level changes not auto-logged | MEDIUM |
| N7 | CRM | User sync is one-way only (ERP → CRM); CRM-originated user updates not synced back | LOW |
| N8 | Reports | Aging report has no export | LOW |
| N9 | Quotation | No PDF/print view for quotation | MEDIUM |

---

## 6. Priority Summary

### Immediate Action (OPEN HIGH)

1. Pagination on all list views (U2) — performance risk with large datasets
2. Quotation → Invoice conversion (F33) — key workflow gap
3. Quotation acceptance workflow (F13) — business process gap
4. Brute-force login protection (T9) — security gap
5. Session timeout (T10) — security gap

### Short-term (OPEN MEDIUM)

1. Email delivery for fee reminders (N2)
2. Certificate expiry tracking (F4)
3. Training schedule conflict detection (N3)
4. Audit log for model-level changes (N6)
5. Media file access control for sensitive docs (T14)

### Low Priority / Backlog

1. Student portal for self-service (F10)
2. Batch certificate printing (F5)
3. Lead source analytics (open in CRM)
4. Staff leave management (F17)

---

*Document updated: 2026-07-06*
