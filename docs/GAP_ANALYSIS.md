# Gap Analysis — Orbit ERP Institute Management System
**Date:** 2026-07-13 | **Version:** 3.0

---

## Overview

This document tracks feature gaps identified in the initial audit (June 2026) against what has been implemented. Items are categorised as **Completed**, **In Progress**, or **Pending**.

---

## 1. Financial & Invoicing

| Feature | Status | Notes |
|---------|--------|-------|
| Sales invoice creation with VAT | ✅ Completed | Level-based pricing, 5% VAT |
| Purchase invoice creation | ✅ Completed | Individual + corporate modes |
| Corporate PI — candidate count display | ✅ Completed | v3: hides "Number of Persons", shows read-only count |
| Discount cap enforcement (20%/30%) | ✅ Completed | JS + backend |
| Payment installments | ✅ Completed | `InvoicePayment` model |
| Invoice print / PDF | ✅ Completed | Browser @print CSS |
| Previous payment reference on invoice | ✅ Completed | Only shown when prior invoice exists |
| Bulk invoice status update | ✅ Completed | |
| Refund management | ✅ Completed | v3: full lifecycle, email, revenue exclusion |
| Revenue report | ✅ Completed | Excludes refunded |
| VAT report | ✅ Completed | |
| Aging report | ✅ Completed | |
| Expense tracking | ✅ Completed | |
| Fee reminders | ✅ Completed | |
| Coupon / discount codes | ✅ Completed | AJAX validation |
| Proforma invoice | ⏳ Pending | Not yet implemented |
| Receipt generation | ⏳ Pending | No dedicated receipt — invoice serves this purpose |

---

## 2. Student Registration

| Feature | Status | Notes |
|---------|--------|-------|
| Individual registration | ✅ Completed | OT/YY/### numbering |
| Corporate registration | ✅ Completed | OC/YY/### numbering |
| Multi-course per registration | ✅ Completed | |
| Enrolment document upload | ✅ Completed | |
| CRM lead pre-fill | ✅ Completed | `?crm_id=` parameter |
| 1-hour edit lock (sales executive) | ✅ Completed | v3: uses `created_at` field |
| Refunded registration visual state | ✅ Completed | v3: REFUNDED badge, red banner, opacity |
| Registration revenue exclusion on refund | ✅ Completed | v3: `is_refunded` flag |
| Welcome email on registration | ✅ Completed | `welcome_email_sent` flag |
| Attendance tracking | ❌ Excluded | Explicitly excluded from scope |
| Student portal (self-service) | ⏳ Pending | Token-based form link exists but no full portal |

---

## 3. Certificates

| Feature | Status | Notes |
|---------|--------|-------|
| Certificate issuance | ✅ Completed | Auto-numbered |
| Certificate print | ✅ Completed | |
| KHDA certificate upload | ✅ Completed | |
| Certificate delete (admin) | ✅ Completed | v3: confirmation modal |
| Send certificate request to client | ✅ Completed | v3: UUID token email |
| Client completion form (public) | ✅ Completed | v3: date + rating + feedback |
| Admin review and generate from request | ✅ Completed | v3: from/end date + grade → Certificate |
| Class feedback (required textarea) | ✅ Completed | v3: `class_feedback` field |
| Admin feedback display | ✅ Completed | v3: blue box on cert requests + registration detail |
| Bulk certificate generation | ⏳ Pending | Would require import/CSV flow |

---

## 4. CRM & Lead Management

| Feature | Status | Notes |
|---------|--------|-------|
| Flask CRM app | ✅ Completed | Separate service |
| SSO (ERP ↔ CRM) | ✅ Completed | HMAC token, 90s TTL |
| User auto-sync to CRM | ✅ Completed | On add/edit sales roles |
| CRM → ERP registration pre-fill | ✅ Completed | |
| Safe lead delete (no FK crash) | ✅ Completed | v3: explicit child cleanup |
| Lead pipeline stages | ✅ Completed | New/Contacted/Qualified/Proposal/Closed |
| Lead interactions log | ✅ Completed | |
| Lead quotes | ✅ Completed | |
| Meetings | ✅ Completed | |
| Payment links (CRM) | ✅ Completed | |
| CRM notifications | ⏳ Pending | No in-app notification in CRM yet |

---

## 5. Quotations & Proposals

| Feature | Status | Notes |
|---------|--------|-------|
| Quotation creation and print | ✅ Completed | |
| Quotation discount / price override | ✅ Completed | `QuotationItemOverride` |
| Coupon validation on quotation | ✅ Completed | AJAX endpoint |
| PI button on quotation (removed) | ✅ Completed | v3: removed — quotations cannot create PI |
| Proposal creation with logo | ✅ Completed | |
| Proposal redesigned UI | ✅ Completed | v3: new card-based layout |
| Proposal → PDF export | ⏳ Pending | Browser print only — no server-side PDF |
| Quotation expiry | ⏳ Pending | No expiry field on quotations |

---

## 6. User Management & Settings

| Feature | Status | Notes |
|---------|--------|-------|
| Role-based user management | ✅ Completed | admin/sales_manager/accounts/sales_executive |
| Redesigned add-user form | ✅ Completed | v3: role cards, gradient header, live password match |
| Sales targets | ✅ Completed | Monthly per-user targets |
| Audit log | ✅ Completed | Login/logout with IP |
| Institute settings — company info | ✅ Completed | v3: singleton settings page |
| Institute settings — branding/stamps | ✅ Completed | v3: logo/stamp/auth-logo/signature uploads |
| Institute settings — banking | ✅ Completed | v3: bank details for invoice footer |
| Institute settings — social links | ✅ Completed | v3: Facebook/Instagram/LinkedIn/Twitter |
| User 2FA / MFA | ⏳ Pending | Recommended but not yet implemented |
| Password policy enforcement | ⏳ Pending | No minimum length/complexity enforcement |

---

## 7. Reporting

| Feature | Status | Notes |
|---------|--------|-------|
| Revenue report (with refund exclusion) | ✅ Completed | |
| Revenue CSV export | ✅ Completed | |
| Aging report | ✅ Completed | |
| VAT report | ✅ Completed | |
| Enrollment report | ✅ Completed | |
| Certificate report | ✅ Completed | |
| Expense report | ✅ Completed | |
| Dashboard KPIs | ✅ Completed | |
| Sales target progress tracking | ✅ Completed | |
| Executive performance comparison | ⏳ Pending | No side-by-side leaderboard |
| Report scheduling / email export | ⏳ Pending | |

---

## 8. Infrastructure & Non-Functional

| Feature | Status | Notes |
|---------|--------|-------|
| HTTPS on VPS | ✅ Completed | Let's Encrypt via Certbot |
| Systemd services (auto-restart) | ✅ Completed | orbit-erp.service, crm.service |
| Nginx reverse proxy | ✅ Completed | |
| Email notifications | ✅ Completed | Cert requests, refunds, welcome, fee reminders |
| In-app notifications | ✅ Completed | |
| Login rate limiting | ⏳ Pending | Recommended (django-axes) |
| Automated DB backups | ⏳ Pending | Manual mysqldump in place |
| Cert request token expiry | ⏳ Pending | Currently no TTL on public tokens |

---

## Summary

| Category | Completed | Pending / Excluded |
|----------|-----------|-------------------|
| Financial / Invoicing | 15 | 2 |
| Registration | 9 | 2 (+1 excluded) |
| Certificates | 9 | 1 |
| CRM & Leads | 10 | 1 |
| Quotations & Proposals | 6 | 2 |
| User Management | 7 | 2 |
| Reporting | 8 | 2 |
| Infrastructure | 6 | 3 |
| **Total** | **70** | **15** |

---

*Document updated: 2026-07-13*
*Version 3.0 — reflects all v3 completions: refund, cert requests, institute settings, safe lead delete, corporate PI fix, proposal UI, add-user form*
