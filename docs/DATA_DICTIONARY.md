# Data Dictionary
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06

---

## 1. Overview

This document defines the meaning, purpose, and allowed values for all fields across all database tables in the Orbit ERP system.

---

## 2. Enumeration Values

### 2.1 Registration Type
| Code | Meaning |
|------|---------|
| `OT` | Individual student registration |
| `OC` | Corporate (company-sponsored) registration |

### 2.2 Class Type
| Value | Meaning | Rate Fields Used |
|-------|---------|-----------------|
| `online` | Online/virtual delivery | `course.oo_*` fields |
| `offline` | In-person classroom | `course.oo_*` fields |
| `batch` | Group/batch training | `course.oo_*` fields |
| `private` | Private 1-on-1 | `course.priv_*` fields |

### 2.3 Level
| Value | Meaning | Price Fields Used |
|-------|---------|-----------------|
| `intermediate` | Intermediate level | `oo_intermediate` or `priv_intermediate` |
| `professional` | Professional level | `oo_professional` or `priv_professional` |
| `advanced` | Advanced level | `oo_advanced` or `priv_advanced` |

### 2.4 Invoice Status
| Value | Meaning |
|-------|---------|
| `Full Payment` | Full amount has been paid |
| `Term Payment` | Partial/instalment payment |
| `Tabby` | Buy-now-pay-later via Tabby |
| `Tamara` | Buy-now-pay-later via Tamara |

### 2.5 Payment Method (Invoices)
| Value | Meaning |
|-------|---------|
| `Card` | Credit/debit card payment |
| `Cash` | Cash payment |
| `Account Transfer` | Bank/wire transfer |
| `Payment Link` | Online payment link |
| `Cheque` | Cheque payment |

### 2.6 Payment Method (InvoicePayment installments)
| Value | Meaning |
|-------|---------|
| `cash` | Cash |
| `card` | Card |
| `bank_transfer` | Bank/wire transfer |
| `cheque` | Cheque |
| `payment_link` | Online payment link |
| `other` | Other method |

### 2.7 Training Venue (Quotation)
| Value | Meaning |
|-------|---------|
| `Orbit Training (In-House)` | At Orbit Training premises |
| `Company Premises (External)` | At client's premises |
| `online` | Virtual/remote delivery |

### 2.8 Lead Source
| Value | Meaning |
|-------|---------|
| `Website` | Enquiry via website |
| `Referral` | Referred by existing client |
| `Event` | Met at event/exhibition |
| `Other` | Any other source |

### 2.9 Lead Status
| Value | Meaning |
|-------|---------|
| `Interested Highly` | Very interested, ready to proceed |
| `Qualified` | Qualified but decision pending |
| `Register Soon` | Will register in near future |
| `Other` | Unclassified |

### 2.10 Follow-Up Priority
| Value | Meaning |
|-------|---------|
| `Low` | Non-urgent |
| `Medium` | Standard priority |
| `High` | Important |
| `Urgent` | Requires immediate attention |

### 2.11 Follow-Up Status
| Value | Meaning |
|-------|---------|
| `Pending` | Not yet done |
| `Completed` | Follow-up done |
| `Cancelled` | Cancelled, not required |
| `Rescheduled` | Moved to new date |

### 2.12 Certificate Type
| Value | Meaning |
|-------|---------|
| `regular` | Standard Orbit Training certificate |
| `khda` | KHDA (Knowledge and Human Development Authority) accredited |

### 2.13 Certificate Grade
| Value | Meaning |
|-------|---------|
| `A+` | Excellent |
| `A` | Very Good |
| `B+` | Good Plus |
| `B` | Good |
| `C+` | Satisfactory Plus |
| `C` | Satisfactory |
| `D` | Pass |

### 2.14 Student Status
| Value | Meaning |
|-------|---------|
| `active` | Currently enrolled |
| `completed` | All courses completed |
| `dropped` | Dropped out |
| `suspended` | Temporarily suspended |
| `pending` | Registration pending confirmation |

### 2.15 User Role
| Value | Meaning | CRM Access |
|-------|---------|-----------|
| `admin` | Full system access, user management | Not synced to CRM |
| `sales_manager` | Lead management, team oversight | Synced as `sales_manager` |
| `accounts` | Invoice and financial access | Not synced to CRM |
| `sales_executive` | Lead management, registration | Synced as `consultant` |

### 2.16 Training Schedule Status
| Value | Meaning |
|-------|---------|
| `upcoming` | Scheduled, not started |
| `ongoing` | Currently in progress |
| `completed` | Finished |
| `cancelled` | Cancelled |

### 2.17 Expense Category
| Value | Meaning |
|-------|---------|
| `venue` | Venue / Facility rental |
| `materials` | Training materials, printing |
| `instructor` | Instructor/trainer fee |
| `marketing` | Advertising, events |
| `utilities` | Electricity, internet |
| `software` | SaaS tools, licenses |
| `travel` | Transport, accommodation |
| `salary` | Staff salary costs |
| `other` | Miscellaneous |

### 2.18 Audit Action
| Value | Meaning |
|-------|---------|
| `create` | Record created |
| `update` | Record updated |
| `delete` | Record deleted |
| `payment` | Payment recorded |
| `status_change` | Status field changed |
| `export` | Data exported |
| `login` | User logged in |
| `logout` | User logged out |
| `view` | Sensitive record viewed |

### 2.19 Notification Type
| Value | Meaning |
|-------|---------|
| `invoice_due` | Invoice due date approaching |
| `overdue_invoice` | Invoice past due date |
| `certificate_ready` | Certificate issued |
| `registration_new` | New student registered |
| `target_alert` | Sales target milestone |
| `system` | System message |

### 2.20 Fee Reminder Channel
| Value | Meaning |
|-------|---------|
| `system` | In-app notification sent |
| `email` | Email sent to client |
| `manual` | Staff manually contacted client |

### 2.21 Company Portal Status
| Value | Meaning |
|-------|---------|
| `pending` | Awaiting admin review |
| `approved` | Approved by admin |
| `rejected` | Rejected by admin |

---

## 3. Field Definitions by Table

### 3.1 `invoices_client`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Auto-generated primary key |
| name | varchar | 255 | Full client or company name |
| email | varchar | 254 | Client email address |
| phone | varchar | 20 | Client phone number |
| address | longtext | — | Full mailing address |
| country | varchar | 100 | Country |
| emirates | varchar | 100 | UAE emirate |
| trn_number | varchar | 50 | Tax Registration Number (blank if individual) |
| user_id | int | — | FK: Staff member who manages this client |

---

### 3.2 `invoices_course`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Auto-generated primary key |
| name | varchar(255) | Full course title |
| code | varchar(10) | Unique short code (2-10 chars); used in certificate numbering |
| rate | decimal(10,2) | Legacy standard/offline rate (AED) — retained for backward compat |
| batch_rate | decimal(10,2) | Legacy batch rate (AED) — retained |
| online_rate | decimal(10,2) | Legacy online rate (AED) — retained |
| private_rate | decimal(10,2) | Legacy private rate (AED) — retained |
| oo_intermediate | decimal(10,2) | Online/Offline pricing – Intermediate level (AED) |
| oo_professional | decimal(10,2) | Online/Offline pricing – Professional level (AED) |
| oo_advanced | decimal(10,2) | Online/Offline pricing – Advanced level (AED) |
| priv_intermediate | decimal(10,2) | Private pricing – Intermediate level (AED) |
| priv_professional | decimal(10,2) | Private pricing – Professional level (AED) |
| priv_advanced | decimal(10,2) | Private pricing – Advanced level (AED) |

Zero (`0.00`) values for `oo_*` and `priv_*` fields display as `—` on the course list, not as `0`.

---

### 3.3 `invoices_registration`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Auto-generated primary key |
| registration_number | varchar | 20 | Unique. Format: OT/YY/### (individual) or OC/YY/### (corporate). Resets annually, not monthly. |
| registration_type | varchar | 2 | 'OT' or 'OC' |
| class_type | varchar | 10 | Delivery mode: online/offline/batch/private |
| level | varchar | 20 | Pricing level: intermediate/professional/advanced |
| student_status | varchar | 20 | active/completed/dropped/suspended/pending |
| date | date | — | Date of registration |
| first_name | varchar | 100 | Student first name |
| last_name | varchar | 100 | Student last name |
| date_of_birth | date | — | Optional |
| passport_no | varchar | 100 | Passport number (optional) |
| uid_no | varchar | 100 | UAE Unified Identity Number (optional) |
| emirates_id_no | varchar | 100 | UAE Emirates ID card number (optional) |
| nationality | varchar | 100 | Student nationality (optional) |
| education | varchar | 100 | Highest education qualification (optional) |
| phone_no | varchar | 20 | Primary contact number |
| alternative_no | varchar | 20 | Secondary contact number (optional) |
| email | varchar | 254 | Email address |
| country | varchar | 100 | Country of residence |
| emirates | varchar | 100 | UAE emirate (optional) |
| address | longtext | — | Full residential address (optional) |
| company_or_university_name | varchar | 100 | Current employer or institution (optional) |
| consultant_name | varchar | 100 | Staff member who handled registration |

---

### 3.4 `invoices_invoice`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| invoice_number | varchar | 50 | Unique. Format: YY/MM/### (resets monthly) |
| date | date | — | Invoice creation date |
| due_date | date | — | Payment due date |
| total_amount | decimal(10,2) | — | Total inc. VAT minus discount (AED). Recalculated on save. |
| amount_paid | decimal(10,2) | — | Amount received so far (AED) |
| discount | decimal(5,2) | — | Invoice-level discount percentage. Cap: 20% single course, 30% multi. |
| number_of_person | int | — | Number of people on this invoice |
| level | varchar | 20 | Pricing level: intermediate/professional/advanced |
| status | varchar | 20 | Payment status (see §2.4) |
| payment | varchar | 20 | Payment method (see §2.5) |
| class_type | varchar | 10 | Delivery mode (see §2.2) |
| po_number | varchar | 100 | Purchase Order number from client |
| client_id | bigint | — | FK to invoices_client |
| user_id | int | — | FK to auth_user (staff member) |
| registration_id | bigint | — | Optional FK to invoices_registration |
| course_id | bigint | — | Optional FK to invoices_course (header reference) |

---

### 3.5 `invoices_invoiceitem`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Primary key |
| invoice_id | bigint | FK to invoices_invoice |
| course_id | bigint | Optional FK to invoices_course |
| description | longtext | Course name or description |
| quantity | int | Number of units/persons |
| unit_price | decimal(10,2) | Price per unit (AED) |
| vat_rate | decimal(4,2) | VAT as decimal: 0.05 = 5% (default 0.05) |

*Calculated fields (not stored):*
- Subtotal = quantity × unit_price
- VAT Amount = subtotal × vat_rate
- Line Total = subtotal + VAT Amount

---

### 3.6 `invoices_invoicepayment`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Primary key |
| invoice_id | bigint | FK to invoices_invoice |
| amount | decimal(10,2) | Payment amount (AED) |
| payment_method | varchar(30) | See §2.6 |
| reference | varchar(100) | Cheque number, bank reference, etc. |
| paid_at | date | Date payment was received |
| recorded_by_id | int | FK to auth_user (staff who recorded) |
| notes | varchar(300) | Optional notes |
| created_at | datetime(6) | Record creation time |

---

### 3.7 `invoices_auditlog`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| user_id | int | — | FK to auth_user. NULL if user deleted. |
| action | varchar | 20 | See §2.18 |
| model_name | varchar | 50 | Django model class name (e.g., 'Invoice', 'User') |
| object_id | varchar | 50 | Primary key of the affected object |
| object_repr | varchar | 300 | String representation of the object |
| changes | longtext | — | Text description of what changed |
| ip_address | char | 39 | Resolved from X-Forwarded-For or REMOTE_ADDR. IPv4 or IPv6. |
| timestamp | datetime(6) | — | Auto-set on creation |

---

### 3.8 `invoices_userprofile`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| user_id | int | — | OneToOne FK to auth_user |
| role | varchar | 20 | See §2.15 |
| phone | varchar | 20 | Staff mobile phone (optional) |

Auto-created by `post_save` signal when a new User is created. Default role: `sales_executive`.

---

### 3.9 `invoices_expense`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| category | varchar | 30 | See §2.17 |
| description | varchar | 300 | Expense description |
| amount | decimal(10,2) | — | Base amount excluding VAT (AED) |
| vat_amount | decimal(10,2) | — | VAT portion (AED). Default 0. |
| vendor | varchar | 200 | Supplier/vendor name |
| expense_date | date | — | Date of expense |
| payment_method | varchar | 30 | cash/card/bank_transfer/cheque/other |
| receipt_ref | varchar | 100 | Receipt or reference number |
| course_id | bigint | — | Optional FK to invoices_course |
| recorded_by_id | int | — | FK to auth_user |

---

## 4. Auto-Generated Values

| Table | Field | Pattern | Example | Resets |
|-------|-------|---------|---------|--------|
| invoices_invoice | invoice_number | YY/MM/### | 26/07/001 | Monthly |
| invoices_invoicepurchase | invoice_number | YY/MM/### | 26/07/001 | Monthly |
| invoices_quotation | quotation_number | YY/MM/### | 26/07/001 | Monthly |
| invoices_registration | registration_number | OT/YY/### | OT/26/001 | Annually |
| invoices_registration | registration_number | OC/YY/### | OC/26/001 | Annually |
| invoices_certificate | certificate_number | {CODE}{REG_NUMBER} | PMOT/26/001 | Never |
| invoices_proposal | proposal_number | PROP-YYYY-#### | PROP-2026-0001 | Never |
| invoices_companyportalrequest | token | 64-char URL-safe | — | Never |
| invoices_studentformlink | token | 64-char URL-safe | — | Never |

---

## 5. Key Business Rules on Fields

| Field | Rule |
|-------|------|
| `invoice.discount` | Max 20% if invoice has 1 course; max 30% if 2+ courses. Enforced frontend + backend. |
| `invoiceitem.vat_rate` | Stored as decimal (0.05 = 5%). VAT is always added on top; never included in unit_price. |
| `invoice.level` | Determines which `oo_*` or `priv_*` field is used from Course |
| `registration.registration_number` | Auto-generated, not editable after creation. Resets annually (no month component). |
| `certificate.register_number` | Stored as plain text, not FK. Cross-referenced against Registration for display. |
| `client.trn_number` | Tax Registration Number. Blank for individual clients. |
| `coupon.discount_percentage` | 0.00 to 100.00 range |
| `coupon.expiry_date` | NULL = no expiry |
| `coupon.max_uses` | NULL = unlimited uses |
| `salestarget.month` | First day of month (e.g., 2026-07-01 for July 2026) |

---

## 6. Calculated Fields (Not Stored in DB)

| Model | Method | Calculation |
|-------|--------|-------------|
| InvoiceItem | get_subtotal() | quantity × unit_price |
| InvoiceItem | get_vat_amount() | subtotal × vat_rate (0.05) |
| InvoiceItem | get_total() | subtotal + vat_amount |
| Invoice | calculate_total_amount() | Σ(course.get_rate × qty × persons × (1−disc%)) × 1.05 |
| InvoicePurchaseItem | get_subtotal() | quantity × unit_price |
| InvoicePurchaseItem | get_vat_amount() | subtotal × vat_rate |
| Expense | total_with_vat() | amount + vat_amount |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
