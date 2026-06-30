# Gap Analysis — Orbit ERP Institute Management System
**Date:** 2026-06-25 | **Version:** 1.0

---

## Executive Summary
The Orbit ERP system covers core workflows (registration, invoicing, leads, quotations) but has several UX, functional, and data gaps. This document categorises every gap by severity so they can be prioritised.

---

## 1. UI / UX Gaps

| # | Area | Gap | Severity |
|---|------|-----|----------|
| U1 | All tables | No search/filter on most list pages | HIGH |
| U2 | All tables | No pagination — all records load at once | HIGH |
| U3 | All tables | No column sorting | MEDIUM |
| U4 | Tables | Inconsistent action button styles across pages | MEDIUM |
| U5 | Leads | Lead table uses Tailwind; rest uses Bootstrap — style inconsistency | MEDIUM |
| U6 | Corporate | Courses displayed as nested `<ul>` inside table cell | LOW |
| U7 | Company/Trainer profiles | Only "Name" column shown — no contact, date, type info | HIGH |
| U8 | Certificates | No filter/search on certificate list | MEDIUM |
| U9 | All | No empty-state illustrations on empty tables | LOW |
| U10 | Invoice detail | Cannot Print/Edit invoice from registration detail page | MEDIUM |
| U11 | Student reg detail | No payment summary / total paid vs outstanding | HIGH |
| U12 | Student reg list | No date filter, no class type filter (fixed in rebuild) | MEDIUM |
| U13 | Quotation list | Table has duplicate "Quotation Number" column | HIGH |
| U14 | General | No breadcrumbs on several pages | LOW |

---

## 2. Functional Gaps

| # | Area | Gap | Severity |
|---|------|-----|----------|
| F1 | Invoices | No TRN field on client for company invoices | FIXED |
| F2 | User Roles | No role-based access — every user sees all data | FIXED |
| F3 | Targets | No monthly target setting for sales executives | FIXED |
| F4 | Certificate | Certificate expiry date not tracked | MEDIUM |
| F5 | Certificate | No batch certificate printing | LOW |
| F6 | Leads | No assignment of leads to specific executives | MEDIUM |
| F7 | Leads | No lead source analytics / conversion funnel | MEDIUM |
| F8 | Registration | No fee structure per course (uses flat rate) | MEDIUM |
| F9 | Registration | No attendance tracking per course | HIGH |
| F10 | Registration | No student portal / login for students | HIGH |
| F11 | Invoice | No recurring invoice / instalment auto-reminder | MEDIUM |
| F12 | Invoice | No bulk payment upload / reconciliation | LOW |
| F13 | Quotation | Quotation acceptance workflow missing (accept/reject) | HIGH |
| F14 | Quotation | No expiry date on quotations | MEDIUM |
| F15 | Quotation | No conversion from quotation → invoice | HIGH |
| F16 | HR | No trainer schedule / availability tracking | MEDIUM |
| F17 | HR | No staff leave management | LOW |
| F18 | Reports | No monthly/quarterly revenue report export | HIGH |
| F19 | Reports | No executive performance report | MEDIUM |
| F20 | Notifications | No email/SMS notifications for due invoices | HIGH |
| F21 | Notifications | No follow-up reminders for leads | MEDIUM |
| F22 | Coupon | No usage count / max-use limit on coupons | MEDIUM |
| F23 | Coupon | No expiry date on coupons | MEDIUM |
| F24 | Course | No course scheduling / calendar view | HIGH |
| F25 | Course | No prerequisite course mapping | LOW |
| F26 | Company | Company profile PDF linked but no contact person fields | MEDIUM |

---

## 3. Data / Model Gaps

| # | Model | Gap | Severity |
|---|-------|-----|----------|
| D1 | Client | No TRN field for company clients | FIXED |
| D2 | Certificate | No expiry_date field | MEDIUM |
| D3 | Coupon | No expiry_date, max_uses, used_count fields | MEDIUM |
| D4 | Quotation | No expiry_date, accepted_at, rejected_at fields | HIGH |
| D5 | Registration | No attendance model | HIGH |
| D6 | Registration | No scholarship / discount_reason field | LOW |
| D7 | TrainerProfile | Only name + PDF — no email, phone, specialization | MEDIUM |
| D8 | CompanyProfile | Only name + PDF — no contact_person, email, phone | MEDIUM |
| D9 | Lead | No utm_source / campaign tracking field | LOW |
| D10 | Invoice | No refund tracking | MEDIUM |

---

## 4. Security Gaps

| # | Area | Gap | Severity |
|---|------|-----|----------|
| S1 | Auth | Admin check uses `username == 'admin'` hardcode in many views | HIGH |
| S2 | Auth | No password policy / expiry | MEDIUM |
| S3 | Auth | No 2FA | LOW |
| S4 | Files | Uploaded files served without auth check | MEDIUM |
| S5 | API | CSRF not enforced on some AJAX endpoints | MEDIUM |
| S6 | Roles | Role check only partially implemented for delete views | MEDIUM |

---

## 5. Performance Gaps

| # | Area | Gap | Severity |
|---|------|-----|----------|
| P1 | Invoice dashboard | Loads ALL invoice items into JS data attributes — slow at scale | HIGH |
| P2 | Registration list | N+1 query on course_status per registration | MEDIUM |
| P3 | All lists | No pagination — full queryset loaded | HIGH |
| P4 | Invoice JSON | `items_json` computed in Python loop not DB aggregation | MEDIUM |

---

## 6. Priority Roadmap

### Immediate (Sprint 1)
- F13: Quotation → Invoice conversion
- F18: Revenue report export
- F24: Course calendar view
- S1: Fix admin check to use `user.profile.role`
- P3: Add pagination to all list views

### Short-term (Sprint 2)
- F9: Attendance tracking
- F20: Invoice due-date email reminders
- D3: Coupon expiry + max uses
- D4: Quotation expiry + acceptance flow
- F6: Lead assignment to executives

### Medium-term (Sprint 3)
- F10: Student self-service portal
- F16: Trainer scheduling
- D2: Certificate expiry tracking
- F12: Bulk payment reconciliation

---

*Generated by Claude Code on 2026-06-25*
