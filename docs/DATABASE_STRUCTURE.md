# Database Structure Document
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
**Database:** orbit_invoice
**Engine:** MariaDB (local dev) / MySQL 8.0 (VPS production)

---

## 1. Database Overview

```
Database: orbit_invoice
Character Set: utf8mb4
Collation: utf8mb4_0900_ai_ci (MySQL 8) / utf8mb4_general_ci (MariaDB)
Engine: InnoDB (all tables)
```

**Constraint:** No existing columns, tables, or data may be modified or removed. All schema changes are additive only.

---

## 2. Application Table Inventory

### 2.1 Django System Tables (unchanged)
- `auth_user`, `auth_group`, `auth_permission`
- `auth_group_permissions`, `auth_user_groups`, `auth_user_user_permissions`
- `django_content_type`, `django_migrations`, `django_session`, `django_admin_log`

### 2.2 Business Application Tables

| Table | Purpose | Added In |
|-------|---------|---------|
| `invoices_client` | Client records | v1 |
| `invoices_course` | Courses + level pricing | v2 |
| `invoices_coursecontent` | Course materials uploads | v2 |
| `invoices_registration` | Student registrations | v1 |
| `invoices_registrationcourse` | Course enrolments per registration | v1 |
| `invoices_corporateregistration` | Corporate extension fields | v1 |
| `invoices_invoice` | Sales invoices | v1 |
| `invoices_invoiceitem` | Invoice line items | v1 |
| `invoices_invoicepurchase` | Purchase invoices | v1 |
| `invoices_invoicepurchaseitem` | Purchase invoice line items | v1 |
| `invoices_quotation` | Client quotations | v2 |
| `invoices_quotationitem` | Quotation line items | v2 |
| `invoices_quotationitemoverride` | Custom price override per item | v2 |
| `invoices_certificate` | Issued certificates | v1 |
| `invoices_certificateupload` | Uploaded certificate files | v2 |
| `invoices_formupload` | Enrolment document uploads | v2 |
| `invoices_proposal` | Training proposals | v2 |
| `invoices_trainerprofile` | Trainer PDF profiles | v2 |
| `invoices_companyprofile` | Company PDF profiles | v2 |
| `invoices_lead` | Sales leads (ERP-side) | v2 |
| `invoices_followup` | Lead follow-ups | v2 |
| `invoices_comment` | Lead comments | v2 |
| `invoices_meeting` | Lead meetings | v2 |
| `invoices_coupon` | Discount coupons | v2 |
| `invoices_userprofile` | Staff role profiles (OneToOne with auth_user) | v2 |
| `invoices_salestarget` | Monthly sales targets | v2 |
| `invoices_notification` | In-app notifications | v2 |
| `invoices_companyportalrequest` | Company self-reg portal | v2 |
| `invoices_companyportalattendee` | Portal attendees | v2 |
| `invoices_studentformlink` | Token registration links | v2 |
| `invoices_invoicepayment` | Payment installments | v2 |
| `invoices_trainingschedule` | Training sessions | v2 |
| `invoices_expense` | Business expenses | v2 |
| `invoices_auditlog` | Action audit trail | v2 |
| `invoices_feereminderlog` | Fee reminder records | v2 |
| `invoices_certificationrequest` | Certificate request flow | **v3** |
| `invoices_institutesetting` | System-wide institute config | **v3** |
| `invoices_refund` | Refund records | **v3** |

---

## 3. Complete Table Schemas

### 3.1 `invoices_client` — Client Records

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | Auto increment |
| name | varchar(255) | NO | Client/company name |
| email | varchar(254) | NO | |
| phone | varchar(20) | NO | |
| address | longtext | NO | |
| emirates | varchar(100) | NO | UAE emirate |
| country | varchar(100) | NO | |
| trn_number | varchar(50) | NO | Tax Registration Number (blank allowed) |
| user_id | int | NO FK→auth_user | Owning consultant |

---

### 3.2 `invoices_course` — Training Courses

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| name | varchar(255) | NO | |
| code | varchar(10) | NO UNI | Short code 2-10 chars |
| rate | decimal(10,2) | NO | Legacy standard/offline rate |
| batch_rate | decimal(10,2) | NO | Legacy batch rate |
| online_rate | decimal(10,2) | NO | Legacy online rate |
| private_rate | decimal(10,2) | NO | Legacy private rate |
| oo_intermediate | decimal(10,2) | NO | Online/Offline — Intermediate |
| oo_professional | decimal(10,2) | NO | Online/Offline — Professional |
| oo_advanced | decimal(10,2) | NO | Online/Offline — Advanced |
| priv_intermediate | decimal(10,2) | NO | Private — Intermediate |
| priv_professional | decimal(10,2) | NO | Private — Professional |
| priv_advanced | decimal(10,2) | NO | Private — Advanced |

Display rule: Course list shows `—` for zero-value level fields, not `0`.

---

### 3.3 `invoices_registration` — Student Registrations

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| registration_number | varchar(20) | NO UNI | OT/YY/### or OC/YY/### |
| registration_type | varchar(2) | NO | 'OT' or 'OC' |
| class_type | varchar(10) | NO | online/offline/batch/private |
| level | varchar(20) | NO | intermediate/professional/advanced |
| student_status | varchar(20) | NO | active/completed/dropped/suspended/pending |
| date | date | NO | Registration date |
| first_name | varchar(100) | NO | |
| last_name | varchar(100) | NO | |
| date_of_birth | date | YES | |
| passport_no | varchar(100) | NO | Blank allowed |
| uid_no | varchar(100) | NO | Blank allowed |
| emirates_id_no | varchar(100) | NO | Blank allowed |
| nationality | varchar(100) | NO | Blank allowed |
| education | varchar(100) | NO | Blank allowed |
| phone_no | varchar(20) | NO | |
| alternative_no | varchar(20) | NO | Blank allowed |
| email | varchar(254) | NO | |
| emirates | varchar(100) | NO | Blank allowed |
| country | varchar(100) | NO | |
| address | longtext | NO | Blank allowed |
| company_or_university_name | varchar(100) | NO | Blank allowed |
| consultant_name | varchar(100) | NO | |
| created_at | datetime(6) | YES | Set on save; NULL for legacy records |
| welcome_email_sent | tinyint(1) | NO | Default 0 |
| is_refunded | tinyint(1) | NO | Default 0 — drives revenue exclusion |

**Note:** `is_refunded = 1` excludes the registration from all revenue, dashboard, and report queries.

---

### 3.4 `invoices_registrationcourse` — Course Enrolments

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| registration_id | bigint | NO FK→invoices_registration | |
| course_id | bigint | NO FK→invoices_course | |
| price | decimal(10,2) | NO | Agreed price |
| discount | decimal(5,2) | NO | Discount % |
| | | UNI(registration_id, course_id) | |

---

### 3.5 `invoices_invoice` — Sales Invoices

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| invoice_number | varchar(50) | NO UNI | YY/MM/### |
| date | date | NO | |
| due_date | date | NO | |
| total_amount | decimal(10,2) | NO | |
| amount_paid | decimal(10,2) | NO | |
| discount | decimal(5,2) | NO | |
| number_of_person | int | NO | |
| level | varchar(20) | NO | intermediate/professional/advanced |
| status | varchar(20) | NO | Full Payment/Term Payment/Tabby/Tamara |
| payment | varchar(20) | NO | Card/Cash/Account Transfer/Payment Link/Cheque |
| class_type | varchar(10) | NO | online/offline/batch/private |
| po_number | varchar(100) | NO | Blank allowed |
| client_id | bigint | NO FK→invoices_client | |
| user_id | int | NO FK→auth_user | |
| registration_id | bigint | YES FK→invoices_registration | Optional |
| course_id | bigint | YES FK→invoices_course | Optional header course |

---

### 3.6 `invoices_invoiceitem` — Invoice Line Items

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| invoice_id | bigint | NO FK→invoices_invoice | |
| course_id | bigint | YES FK→invoices_course | |
| description | longtext | NO | |
| quantity | int | NO | |
| unit_price | decimal(10,2) | NO | |
| vat_rate | decimal(4,2) | NO | Stored as 0.05 (decimal, NOT percent) |

Calculated (not stored): subtotal = qty × unit_price; vat = subtotal × vat_rate; total = subtotal + vat.

---

### 3.7 `invoices_invoicepurchase` — Purchase Invoices

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| invoice_number | varchar(50) | NO UNI | YY/MM/### (own sequence) |
| date | date | NO | |
| due_date | date | NO | |
| client_name | varchar(255) | NO | |
| client_country | varchar(100) | NO | |
| client_emirates | varchar(100) | NO | |
| total_amount | decimal(10,2) | NO | |
| advance_amount | decimal(10,2) | NO | |
| discount | decimal(5,2) | NO | |
| number_of_person | int | NO | |
| payment | varchar(20) | NO | |
| po_number | varchar(100) | NO | |
| user_id | int | NO FK→auth_user | |
| registration_id | bigint | YES FK→invoices_registration | |

---

### 3.8 `invoices_quotation` — Client Quotations

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| quotation_number | varchar(20) | NO UNI | YY/MM/### |
| client_name | varchar(255) | NO | |
| schedule | varchar(255) | NO | |
| training_venue | varchar(50) | NO | Orbit Training/Company Premises/online |
| discount | decimal(10,2) | NO | |
| coupon_id | bigint | YES FK→invoices_coupon | |
| consultant_name | varchar(20) | NO | |
| consultant_position | varchar(255) | NO | |
| consultant_number | varchar(20) | NO | |
| consultant_email | varchar(254) | NO | |
| created_at | datetime(6) | NO | |
| user_id | int | NO FK→auth_user | |

---

### 3.9 `invoices_quotationitemoverride` — Custom Quotation Pricing

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| item_id | bigint | NO UNI FK→invoices_quotationitem | OneToOne |
| custom_price | decimal(10,2) | NO | Price per pax override |

---

### 3.10 `invoices_coupon` — Discount Coupons

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| code | varchar(50) | NO UNI | |
| discount_percentage | decimal(5,2) | NO | 0–100 |
| is_active | tinyint(1) | NO | |
| expiry_date | date | YES | Optional |
| max_uses | int | YES | NULL = unlimited |
| used_count | int | NO | Default 0 |
| created_at | datetime(6) | NO | |
| created_by_id | int | NO FK→auth_user | |

---

### 3.11 `invoices_userprofile` — Staff Role Profiles

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| user_id | int | NO UNI FK→auth_user | OneToOne |
| role | varchar(20) | NO | admin/sales_manager/accounts/sales_executive |
| phone | varchar(20) | NO | Blank allowed |

Auto-created via `post_save` signal on User with default role `sales_executive`.

---

### 3.12 `invoices_salestarget` — Monthly Sales Targets

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| user_id | int | NO FK→auth_user | |
| month | date | NO | First day of target month |
| target_amount | decimal(12,2) | NO | AED |
| target_registrations | int | NO | |
| created_by_id | int | YES FK→auth_user | |
| created_at | datetime(6) | NO | |
| updated_at | datetime(6) | NO | |
| | | UNI(user_id, month) | |

---

### 3.13 `invoices_notification` — In-App Notifications

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| recipient_id | int | NO FK→auth_user | |
| notif_type | varchar(30) | NO | invoice_due/overdue_invoice/certificate_ready/registration_new/target_alert/system |
| title | varchar(200) | NO | |
| message | longtext | NO | |
| link | varchar(200) | NO | URL |
| is_read | tinyint(1) | NO | Default 0 |
| created_at | datetime(6) | NO | |

---

### 3.14 `invoices_companyportalrequest` — Company Self-Registration Portal

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| token | varchar(64) | NO UNI | Random URL-safe token |
| generated_by_id | int | YES FK→auth_user | |
| company_name | varchar(255) | NO | |
| trade_license_number | varchar(100) | NO | Blank allowed |
| trade_license_doc | varchar(100) | YES | portal/trade_license/ |
| vat_number | varchar(50) | NO | Blank allowed |
| vat_certificate | varchar(100) | YES | portal/vat/ |
| contact_person | varchar(150) | NO | |
| designation | varchar(100) | NO | Blank allowed |
| email | varchar(254) | NO | |
| phone | varchar(30) | NO | |
| address | longtext | NO | Blank allowed |
| emirate | varchar(100) | NO | Blank allowed |
| status | varchar(20) | NO | pending/approved/rejected |
| submitted_at | datetime(6) | YES | |
| created_at | datetime(6) | NO | |
| notes | longtext | NO | Blank allowed |

---

### 3.15 `invoices_companyportalattendee` — Portal Attendees

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| portal_request_id | bigint | NO FK→invoices_companyportalrequest | |
| full_name | varchar(200) | NO | |
| email | varchar(254) | NO | Blank allowed |
| phone | varchar(30) | NO | Blank allowed |
| designation | varchar(100) | NO | Blank allowed |
| emirates_id | varchar(50) | NO | Blank allowed |
| nationality | varchar(100) | NO | Blank allowed |
| course_name | varchar(200) | NO | Blank allowed |
| added_at | datetime(6) | NO | |

---

### 3.16 `invoices_studentformlink` — Token Registration Links

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| token | varchar(64) | NO UNI | |
| consultant_id | int | YES FK→auth_user | |
| consultant_name_locked | varchar(150) | NO | Immutable |
| is_active | tinyint(1) | NO | |
| expires_at | datetime(6) | YES | |
| created_at | datetime(6) | NO | |
| use_count | int unsigned | NO | Default 0 |
| notes | varchar(300) | NO | Blank allowed |

`pre_selected_courses`: M2M to `invoices_course` via junction table.

---

### 3.17 `invoices_invoicepayment` — Payment Installments

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| invoice_id | bigint | NO FK→invoices_invoice | |
| amount | decimal(10,2) | NO | |
| payment_method | varchar(30) | NO | cash/card/bank_transfer/cheque/payment_link/other |
| reference | varchar(100) | NO | Blank allowed |
| paid_at | date | NO | |
| recorded_by_id | int | YES FK→auth_user | |
| notes | varchar(300) | NO | Blank allowed |
| created_at | datetime(6) | NO | |

---

### 3.18 `invoices_trainingschedule` — Training Sessions

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| course_id | bigint | NO FK→invoices_course | |
| title | varchar(200) | NO | |
| class_type | varchar(20) | NO | |
| start_date | date | NO | |
| end_date | date | NO | |
| start_time | time(6) | YES | |
| end_time | time(6) | YES | |
| venue | varchar(200) | NO | Blank allowed |
| max_capacity | int unsigned | NO | Default 0 |
| instructor | varchar(100) | NO | Blank allowed |
| notes | longtext | NO | Blank allowed |
| status | varchar(20) | NO | upcoming/ongoing/completed/cancelled |
| created_by_id | int | YES FK→auth_user | |
| created_at | datetime(6) | NO | |

---

### 3.19 `invoices_expense` — Business Expenses

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| category | varchar(30) | NO | venue/materials/instructor/marketing/utilities/software/travel/salary/other |
| description | varchar(300) | NO | |
| amount | decimal(10,2) | NO | Base excl. VAT |
| vat_amount | decimal(10,2) | NO | Default 0 |
| vendor | varchar(200) | NO | Blank allowed |
| expense_date | date | NO | |
| payment_method | varchar(30) | NO | |
| receipt_ref | varchar(100) | NO | Blank allowed |
| course_id | bigint | YES FK→invoices_course | Optional |
| recorded_by_id | int | YES FK→auth_user | |
| created_at | datetime(6) | NO | |

---

### 3.20 `invoices_auditlog` — Action Audit Trail

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| user_id | int | YES FK→auth_user | NULL if user deleted |
| action | varchar(20) | NO | create/update/delete/payment/status_change/export/login/logout/view |
| model_name | varchar(50) | NO | |
| object_id | varchar(50) | NO | PK of affected object |
| object_repr | varchar(300) | NO | |
| changes | longtext | NO | |
| ip_address | char(39) | YES | IPv4 or IPv6 |
| timestamp | datetime(6) | NO | |

Login/logout auto-written via `signals.py`.

---

### 3.21 `invoices_feereminderlog` — Fee Reminder Records

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| invoice_id | bigint | YES FK→invoices_invoice | |
| client_name | varchar(200) | NO | Denormalized |
| invoice_number | varchar(50) | NO | Denormalized |
| amount_due | decimal(10,2) | NO | |
| due_date | date | NO | |
| days_overdue | int | NO | Negative = days until due |
| channel | varchar(10) | NO | system/email/manual |
| sent_by_id | int | YES FK→auth_user | |
| note | longtext | NO | Blank allowed |
| sent_at | datetime(6) | NO | |

---

### 3.22 `invoices_certificationrequest` — Certificate Request Flow *(v3)*

Token-based form sent to client to confirm course completion before certificate is generated.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| registration_id | bigint | NO FK→invoices_registration | |
| course_name | varchar(200) | NO | Captured at send time |
| token | char(32) | NO UNI | UUID4, URL-safe |
| sent_at | datetime(6) | NO | Auto on create |
| sent_by_id | int | YES FK→auth_user | |
| completion_date | date | YES | Filled by client |
| course_completed | tinyint(1) | YES | NULL until client submits |
| class_rating | varchar(20) | NO | Blank allowed; excellent/good/average/poor |
| class_feedback | longtext | NO | Blank allowed; written feedback required at submit time |
| client_notes | longtext | NO | Optional additional comments |
| submitted_at | datetime(6) | YES | Timestamp of client submission |
| status | varchar(20) | NO | pending/submitted/approved/rejected |
| generated_certificate_id | bigint | YES FK→invoices_certificate | Set when cert generated |

**Status lifecycle:** `pending` → (client submits) → `submitted` → (admin generates) → `approved`  
or (admin rejects) → `rejected`

**Public form rules:**
- Client selects completion status; selecting "Not Completed" blocks submission
- `class_rating` and `class_feedback` are both required before submit button enables
- Submit button JS-disabled until all three fields (date + rating + feedback) filled

---

### 3.23 `invoices_institutesetting` — Institute Configuration *(v3)*

Singleton table (always pk=1). Stores all configurable institute-wide settings.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | Always 1 (singleton) |
| company_name | varchar(255) | NO | Blank allowed |
| trade_license_number | varchar(100) | NO | Blank allowed |
| vat_number | varchar(50) | NO | Blank allowed |
| address | longtext | NO | Blank allowed |
| phone | varchar(30) | NO | Blank allowed |
| email | varchar(254) | NO | Blank allowed |
| website | varchar(200) | NO | Blank allowed |
| bank_name | varchar(200) | NO | Blank allowed |
| account_name | varchar(200) | NO | Blank allowed |
| account_number | varchar(100) | NO | Blank allowed |
| iban | varchar(50) | NO | Blank allowed |
| swift_code | varchar(20) | NO | Blank allowed |
| facebook | varchar(200) | NO | Blank allowed |
| instagram | varchar(200) | NO | Blank allowed |
| linkedin | varchar(200) | NO | Blank allowed |
| twitter | varchar(200) | NO | Blank allowed |
| company_logo | varchar(100) | YES | company_settings/logo{ext} |
| stamp | varchar(100) | YES | company_settings/stamp{ext} |
| authorization_logo | varchar(100) | YES | company_settings/auth_logo{ext} |
| signature | varchar(100) | YES | company_settings/signature{ext} |

Accessed via `InstituteSetting.get()` classmethod which calls `get_or_create(pk=1)`.

---

### 3.24 `invoices_refund` — Refund Records *(v3)*

OneToOne with Registration. One refund per registration maximum.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint | NO PRI | |
| registration_id | bigint | NO UNI FK→invoices_registration | OneToOne |
| reason | longtext | NO | Required |
| document | varchar(100) | YES | refund_docs/{reg_number}{ext} |
| amount | decimal(12,2) | NO | Default 0 |
| refund_reference | varchar(100) | NO | Blank allowed |
| status | varchar(20) | NO | pending/confirmed/cancelled |
| initiated_by_id | int | YES FK→auth_user | |
| confirmed_by_id | int | YES FK→auth_user | |
| initiated_at | datetime(6) | NO | Auto on create |
| confirmed_at | datetime(6) | YES | Set when confirmed |
| admin_notes | longtext | NO | Blank allowed |

**On confirmation:** `registration.is_refunded` set to `True`. Refund confirmation email sent to client.

---

## 4. Key Foreign Keys (v3 additions)

| Table | Column | References | On Delete |
|-------|--------|-----------|-----------|
| invoices_registration | (no new FKs) | — | — |
| invoices_certificationrequest | registration_id | invoices_registration(id) | CASCADE |
| invoices_certificationrequest | sent_by_id | auth_user(id) | SET NULL |
| invoices_certificationrequest | generated_certificate_id | invoices_certificate(id) | SET NULL |
| invoices_refund | registration_id | invoices_registration(id) | CASCADE |
| invoices_refund | initiated_by_id | auth_user(id) | SET NULL |
| invoices_refund | confirmed_by_id | auth_user(id) | SET NULL |

---

## 5. Unique Constraints

| Table | Unique Column(s) |
|-------|-----------------|
| invoices_certificate | certificate_number |
| invoices_certificateupload | registration_id |
| invoices_certificationrequest | token |
| invoices_corporateregistration | registration_id |
| invoices_coupon | code |
| invoices_course | code |
| invoices_formupload | registration_id |
| invoices_institutesetting | id (singleton pk=1) |
| invoices_invoice | invoice_number |
| invoices_invoicepurchase | invoice_number |
| invoices_lead | email |
| invoices_proposal | proposal_number |
| invoices_quotation | quotation_number |
| invoices_quotationitemoverride | item_id |
| invoices_refund | registration_id |
| invoices_registration | registration_number |
| invoices_registrationcourse | (registration_id, course_id) |
| invoices_salestarget | (user_id, month) |
| invoices_studentformlink | token |
| invoices_companyportalrequest | token |
| invoices_trainerprofile | name |
| invoices_userprofile | user_id |

---

## 6. File Upload Directories

| Table | Field | Directory Pattern |
|-------|-------|-----------|
| invoices_trainerprofile | profile_pdf | `trainer_profiles/{name_slug}{ext}` |
| invoices_companyprofile | company_pdf | `company_profiles/{name_slug}{ext}` |
| invoices_proposal | logo | `proposal_logos/` |
| invoices_proposal | logo_white_url | `proposal_logos_white/` |
| invoices_coursecontent | file | `course_contents/` |
| invoices_certificateupload | certificate_file | `certificates/{name}_{reg_number}{ext}` |
| invoices_formupload | form_file | `registration_forms/{name}_{reg_number}{ext}` |
| invoices_certificate | uploaded_certificate | `khda_certificates/{student_slug}_{cert_num}{ext}` |
| invoices_companyportalrequest | trade_license_doc | `portal/trade_license/{company_slug}_trade_license{ext}` |
| invoices_companyportalrequest | vat_certificate | `portal/vat/{company_slug}_vat{ext}` |
| invoices_refund | document | `refund_docs/{registration_number}{ext}` |
| invoices_institutesetting | company_logo | `company_settings/logo{ext}` |
| invoices_institutesetting | stamp | `company_settings/stamp{ext}` |
| invoices_institutesetting | authorization_logo | `company_settings/auth_logo{ext}` |
| invoices_institutesetting | signature | `company_settings/signature{ext}` |

---

## 7. Migration History (v3 additions)

| Migration | Change |
|-----------|--------|
| 0065 | Add `invoices_certificationrequest` model |
| 0066 | Add `invoices_institutesetting` model |
| 0067 | Add `is_refunded` to `invoices_registration`; add `invoices_refund` model; add `created_at`, `welcome_email_sent` to `invoices_registration` |
| 0068 | Add `class_rating` to `invoices_certificationrequest` |
| 0069 | Add `class_feedback` to `invoices_certificationrequest` |

---

## 8. Database Setup (Local Development)

```sql
CREATE DATABASE IF NOT EXISTS orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
```

```powershell
# XAMPP import
"C:\xampp\mysql\bin\mysql.exe" -u root orbit_invoice < "D:\Insittute management system\orbiterp.sql"
```

If you see `Unknown collation: 'utf8mb4_0900_ai_ci'`, replace with `utf8mb4_general_ci` before importing.

---

*Document updated: 2026-07-13*
*Version 3.0 — adds CertificationRequest, InstituteSetting, Refund tables; is_refunded/created_at on Registration*
