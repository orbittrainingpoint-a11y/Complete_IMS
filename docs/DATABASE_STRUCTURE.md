# Database Structure Document
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
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

| Table | Purpose | Key Change vs v1 |
|-------|---------|-----------------|
| `invoices_client` | Client records | `trn_number` field added |
| `invoices_course` | Courses | 6 level-based price fields added |
| `invoices_coursecontent` | Course materials | Unchanged |
| `invoices_registration` | Student registrations | `level`, `student_status` fields added; number format changed |
| `invoices_registrationcourse` | Course enrolments | Unchanged |
| `invoices_corporateregistration` | Corporate extension | Unchanged |
| `invoices_invoice` | Sales invoices | `level` field added |
| `invoices_invoiceitem` | Invoice line items | `vat_rate` now stored as 0.05 (not 5.00) |
| `invoices_invoicepurchase` | Purchase invoices | Unchanged |
| `invoices_invoicepurchaseitem` | Purchase line items | Unchanged |
| `invoices_quotation` | Quotations | `coupon` FK added |
| `invoices_quotationitem` | Quotation items | Unchanged |
| `invoices_quotationitemoverride` | Custom price per pax | **New table** |
| `invoices_certificate` | Issued certificates | Unchanged |
| `invoices_certificateupload` | Cert file uploads | Unchanged |
| `invoices_formupload` | Form uploads | Unchanged |
| `invoices_proposal` | Training proposals | Unchanged |
| `invoices_trainerprofile` | Trainer profiles | Unchanged |
| `invoices_companyprofile` | Company profiles | Unchanged |
| `invoices_lead` | Sales leads | Unchanged (CRM leads in separate `leads` DB) |
| `invoices_followup` | Lead follow-ups | Unchanged |
| `invoices_comment` | Lead comments | Unchanged |
| `invoices_meeting` | Lead meetings | Unchanged |
| `invoices_pipeline` | Sales pipelines | Unchanged |
| `invoices_pipelinestage` | Pipeline stages | Unchanged |
| `invoices_coupon` | Discount coupons | `expiry_date`, `max_uses`, `used_count` added |
| `invoices_userprofile` | Staff role profiles | **New table** |
| `invoices_salestarget` | Monthly sales targets | **New table** |
| `invoices_notification` | In-app notifications | **New table** |
| `invoices_companyportalrequest` | Company self-reg portal | **New table** |
| `invoices_companyportalattendee` | Portal attendees | **New table** |
| `invoices_studentformlink` | Token registration links | **New table** |
| `invoices_invoicepayment` | Payment installments | **New table** |
| `invoices_trainingschedule` | Training sessions | **New table** |
| `invoices_expense` | Business expenses | **New table** |
| `invoices_auditlog` | Action audit trail | **New table** |
| `invoices_feereminderlog` | Fee reminder records | **New table** |

---

## 3. Complete Table Schemas

### 3.1 `invoices_client` — Client Records

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | | Client/company name |
| email | varchar(254) | NO | | |
| phone | varchar(20) | NO | | |
| address | longtext | NO | | |
| emirates | varchar(100) | NO | | UAE emirate |
| country | varchar(100) | NO | | |
| trn_number | varchar(50) | NO | | Tax Registration Number (blank allowed) |
| user_id | int | NO | FK → auth_user | Owning consultant |

---

### 3.2 `invoices_course` — Training Courses

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | | Course full name |
| code | varchar(10) | NO | UNI | Short code (2-10 chars) |
| rate | decimal(10,2) | NO | | Legacy standard/offline rate |
| batch_rate | decimal(10,2) | NO | | Legacy batch rate |
| online_rate | decimal(10,2) | NO | | Legacy online rate |
| private_rate | decimal(10,2) | NO | | Legacy private rate |
| oo_intermediate | decimal(10,2) | NO | | Online/Offline — Intermediate |
| oo_professional | decimal(10,2) | NO | | Online/Offline — Professional |
| oo_advanced | decimal(10,2) | NO | | Online/Offline — Advanced |
| priv_intermediate | decimal(10,2) | NO | | Private — Intermediate |
| priv_professional | decimal(10,2) | NO | | Private — Professional |
| priv_advanced | decimal(10,2) | NO | | Private — Advanced |

Note: `oo_*` and `priv_*` fields default to 0. Course list displays `—` (dash) for zero values.

---

### 3.3 `invoices_registration` — Student Registrations

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_number | varchar(20) | NO | UNI | OT/YY/### or OC/YY/### |
| registration_type | varchar(2) | NO | | 'OT' or 'OC' |
| class_type | varchar(10) | NO | | online/offline/batch/private |
| level | varchar(20) | NO | | intermediate/professional/advanced |
| student_status | varchar(20) | NO | | active/completed/dropped/suspended/pending |
| date | date | NO | | Registration date |
| first_name | varchar(100) | NO | | |
| last_name | varchar(100) | NO | | |
| date_of_birth | date | YES | NULL | Optional |
| passport_no | varchar(100) | NO | | Blank allowed |
| uid_no | varchar(100) | NO | | Blank allowed |
| emirates_id_no | varchar(100) | NO | | Blank allowed |
| nationality | varchar(100) | NO | | Blank allowed |
| education | varchar(100) | NO | | Blank allowed |
| phone_no | varchar(20) | NO | | |
| alternative_no | varchar(20) | NO | | Blank allowed |
| email | varchar(254) | NO | | |
| emirates | varchar(100) | NO | | Blank allowed |
| country | varchar(100) | NO | | |
| address | longtext | NO | | Blank allowed |
| company_or_university_name | varchar(100) | NO | | Blank allowed |
| consultant_name | varchar(100) | NO | | |

**Registration Number Format Change:** Format is `OT/YY/###` (year only, no month). Resets annually. Previous docs incorrectly stated `OT/YY/MM/###`.

---

### 3.4 `invoices_registrationcourse` — Registration-Course Junction

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_id | bigint | NO | FK → invoices_registration | |
| course_id | bigint | NO | FK → invoices_course | |
| price | decimal(10,2) | NO | | Agreed price |
| discount | decimal(5,2) | NO | | Discount % |
| | | | UNI(registration_id, course_id) | |

---

### 3.5 `invoices_invoice` — Sales Invoices

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_number | varchar(50) | NO | UNI | YY/MM/### |
| date | date | NO | | Invoice date |
| due_date | date | NO | | Payment due date |
| total_amount | decimal(10,2) | NO | | Sum of items after discount + VAT |
| amount_paid | decimal(10,2) | NO | | Amount received |
| discount | decimal(5,2) | NO | | Invoice-level discount % |
| number_of_person | int | NO | | |
| level | varchar(20) | NO | | intermediate/professional/advanced |
| status | varchar(20) | NO | | Full Payment/Term Payment/Tabby/Tamara |
| payment | varchar(20) | NO | | Card/Cash/Account Transfer/Payment Link/Cheque |
| class_type | varchar(10) | NO | | online/offline/batch/private |
| po_number | varchar(100) | NO | | Blank allowed |
| client_id | bigint | NO | FK → invoices_client | |
| user_id | int | NO | FK → auth_user | |
| registration_id | bigint | YES | NULL FK → invoices_registration | Optional link |
| course_id | bigint | YES | NULL FK → invoices_course | Optional header course |

---

### 3.6 `invoices_invoiceitem` — Invoice Line Items

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_id | bigint | NO | FK → invoices_invoice | |
| course_id | bigint | YES | NULL FK → invoices_course | |
| description | longtext | NO | | Course name/description |
| quantity | int | NO | | |
| unit_price | decimal(10,2) | NO | | |
| vat_rate | decimal(4,2) | NO | | Stored as 0.05 (decimal), default 0.05 |

*Calculated (not stored):*
- subtotal = quantity × unit_price
- vat_amount = subtotal × vat_rate
- total = subtotal + vat_amount

**Note:** `vat_rate` is stored as a decimal (0.05), not as a percentage (5.00). The model's `get_vat_amount()` multiplies by `self.vat_rate` directly.

---

### 3.7 `invoices_quotation` — Client Quotations

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| quotation_number | varchar(20) | NO | UNI | YY/MM/### |
| client_name | varchar(255) | NO | | |
| schedule | varchar(255) | NO | | Proposed schedule text |
| training_venue | varchar(50) | NO | | See venue choices below |
| discount | decimal(10,2) | NO | | |
| coupon_id | bigint | YES | NULL FK → invoices_coupon | |
| consultant_name | varchar(20) | NO | | |
| consultant_position | varchar(255) | NO | | |
| consultant_number | varchar(20) | NO | | |
| consultant_email | varchar(254) | NO | | |
| created_at | datetime(6) | NO | | |
| user_id | int | NO | FK → auth_user | |

**Venue choices:** `Orbit Training (In-House)`, `Company Premises (External)`, `online`

---

### 3.8 `invoices_quotationitemoverride` — Custom Quotation Pricing

**New table** — allows admin/sales_manager to override course rate for a specific quotation item.

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| item_id | bigint | NO | UNI FK → invoices_quotationitem | OneToOne |
| custom_price | decimal(10,2) | NO | | Price per pax override |

---

### 3.9 `invoices_coupon` — Discount Coupons

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| code | varchar(50) | NO | UNI | |
| discount_percentage | decimal(5,2) | NO | | 0.00–100.00 |
| is_active | tinyint(1) | NO | | |
| expiry_date | date | YES | NULL | Optional expiry |
| max_uses | int | YES | NULL | NULL = unlimited |
| used_count | int | NO | | Default 0 |
| created_at | datetime(6) | NO | | |
| created_by_id | int | NO | FK → auth_user | |

---

### 3.10 `invoices_userprofile` — Staff Role Profiles

**New table** — OneToOne extension of auth_user for role and phone.

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| user_id | int | NO | UNI FK → auth_user | OneToOne |
| role | varchar(20) | NO | | admin/sales_manager/accounts/sales_executive |
| phone | varchar(20) | NO | | Blank allowed |

**Auto-created:** `post_save` signal on User creates UserProfile with default role `sales_executive`.

---

### 3.11 `invoices_salestarget` — Monthly Sales Targets

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| user_id | int | NO | FK → auth_user | |
| month | date | NO | | First day of the target month |
| target_amount | decimal(12,2) | NO | | Target revenue (AED) |
| target_registrations | int | NO | | Target registration count |
| created_by_id | int | YES | NULL FK → auth_user | |
| created_at | datetime(6) | NO | | |
| updated_at | datetime(6) | NO | | |
| | | | UNI(user_id, month) | |

---

### 3.12 `invoices_notification` — In-App Notifications

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| recipient_id | int | NO | FK → auth_user | |
| notif_type | varchar(30) | NO | | invoice_due/overdue_invoice/certificate_ready/registration_new/target_alert/system |
| title | varchar(200) | NO | | |
| message | longtext | NO | | |
| link | varchar(200) | NO | | URL to navigate on click |
| is_read | tinyint(1) | NO | | Default 0 |
| created_at | datetime(6) | NO | | Ordered by -created_at |

---

### 3.13 `invoices_companyportalrequest` — Company Self-Registration Portal

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| token | varchar(64) | NO | UNI | Random URL-safe token |
| generated_by_id | int | YES | NULL FK → auth_user | |
| company_name | varchar(255) | NO | | |
| trade_license_number | varchar(100) | NO | | Blank allowed |
| trade_license_doc | varchar(100) | YES | NULL | File: portal/trade_license/ |
| vat_number | varchar(50) | NO | | Blank allowed |
| vat_certificate | varchar(100) | YES | NULL | File: portal/vat/ |
| contact_person | varchar(150) | NO | | |
| designation | varchar(100) | NO | | Blank allowed |
| email | varchar(254) | NO | | |
| phone | varchar(30) | NO | | |
| address | longtext | NO | | Blank allowed |
| emirate | varchar(100) | NO | | Blank allowed |
| status | varchar(20) | NO | | pending/approved/rejected |
| submitted_at | datetime(6) | YES | NULL | |
| created_at | datetime(6) | NO | | |
| notes | longtext | NO | | Blank allowed |

---

### 3.14 `invoices_companyportalattendee` — Portal Training Attendees

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| portal_request_id | bigint | NO | FK → invoices_companyportalrequest | |
| full_name | varchar(200) | NO | | |
| email | varchar(254) | NO | | Blank allowed |
| phone | varchar(30) | NO | | Blank allowed |
| designation | varchar(100) | NO | | Blank allowed |
| emirates_id | varchar(50) | NO | | Blank allowed |
| nationality | varchar(100) | NO | | Blank allowed |
| course_name | varchar(200) | NO | | Blank allowed |
| added_at | datetime(6) | NO | | |

---

### 3.15 `invoices_studentformlink` — Token Registration Links

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| token | varchar(64) | NO | UNI | Random URL-safe token |
| consultant_id | int | YES | NULL FK → auth_user | |
| consultant_name_locked | varchar(150) | NO | | Immutable consultant name |
| is_active | tinyint(1) | NO | | |
| expires_at | datetime(6) | YES | NULL | Optional expiry |
| created_at | datetime(6) | NO | | |
| use_count | int unsigned | NO | | Default 0 |
| notes | varchar(300) | NO | | Blank allowed |

`pre_selected_courses` is a ManyToMany through a junction table to `invoices_course`.

---

### 3.16 `invoices_invoicepayment` — Payment Installments

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_id | bigint | NO | FK → invoices_invoice | |
| amount | decimal(10,2) | NO | | |
| payment_method | varchar(30) | NO | | cash/card/bank_transfer/cheque/payment_link/other |
| reference | varchar(100) | NO | | Cheque #, transfer ref |
| paid_at | date | NO | | |
| recorded_by_id | int | YES | NULL FK → auth_user | |
| notes | varchar(300) | NO | | Blank allowed |
| created_at | datetime(6) | NO | | Ordered by paid_at |

---

### 3.17 `invoices_trainingschedule` — Training Sessions

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| course_id | bigint | NO | FK → invoices_course | |
| title | varchar(200) | NO | | Session name |
| class_type | varchar(20) | NO | | online/offline/batch/private |
| start_date | date | NO | | |
| end_date | date | NO | | |
| start_time | time(6) | YES | NULL | |
| end_time | time(6) | YES | NULL | |
| venue | varchar(200) | NO | | Blank allowed |
| max_capacity | int unsigned | NO | | Default 0 |
| instructor | varchar(100) | NO | | Blank allowed |
| notes | longtext | NO | | Blank allowed |
| status | varchar(20) | NO | | upcoming/ongoing/completed/cancelled |
| created_by_id | int | YES | NULL FK → auth_user | |
| created_at | datetime(6) | NO | | Ordered by start_date |

---

### 3.18 `invoices_expense` — Business Expenses

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| category | varchar(30) | NO | | venue/materials/instructor/marketing/utilities/software/travel/salary/other |
| description | varchar(300) | NO | | |
| amount | decimal(10,2) | NO | | Base amount excl. VAT |
| vat_amount | decimal(10,2) | NO | | VAT portion (default 0) |
| vendor | varchar(200) | NO | | Blank allowed |
| expense_date | date | NO | | |
| payment_method | varchar(30) | NO | | cash/card/bank_transfer/cheque/other |
| receipt_ref | varchar(100) | NO | | Blank allowed |
| course_id | bigint | YES | NULL FK → invoices_course | Optional link to course |
| recorded_by_id | int | YES | NULL FK → auth_user | |
| created_at | datetime(6) | NO | | Ordered by -expense_date |

---

### 3.19 `invoices_auditlog` — Action Audit Trail

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| user_id | int | YES | NULL FK → auth_user | NULL if user deleted |
| action | varchar(20) | NO | | create/update/delete/payment/status_change/export/login/logout/view |
| model_name | varchar(50) | NO | | Model class name |
| object_id | varchar(50) | NO | | PK of affected object |
| object_repr | varchar(300) | NO | | String representation |
| changes | longtext | NO | | Description of changes |
| ip_address | char(39) | YES | NULL | IPv4 or IPv6 |
| timestamp | datetime(6) | NO | | Ordered by -timestamp |

**Auto-populated:** Login and logout events written automatically via `signals.py`.

---

### 3.20 `invoices_feereminderlog` — Fee Reminder Records

**New table**

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_id | bigint | YES | NULL FK → invoices_invoice | |
| client_name | varchar(200) | NO | | Denormalized |
| invoice_number | varchar(50) | NO | | Denormalized |
| amount_due | decimal(10,2) | NO | | |
| due_date | date | NO | | |
| days_overdue | int | NO | | Negative = days until due |
| channel | varchar(10) | NO | | system/email/manual |
| sent_by_id | int | YES | NULL FK → auth_user | |
| note | longtext | NO | | Blank allowed |
| sent_at | datetime(6) | NO | | Ordered by -sent_at |

---

### 3.21 Previously Documented Tables (Unchanged)

The following tables are unchanged from v1 documentation. See v1 DATABASE_STRUCTURE.md for full column details:

- `invoices_corporateregistration`
- `invoices_invoicepurchase`
- `invoices_invoicepurchaseitem`
- `invoices_quotationitem`
- `invoices_certificate`
- `invoices_certificateupload`
- `invoices_formupload`
- `invoices_proposal`
- `invoices_trainerprofile`
- `invoices_companyprofile`
- `invoices_lead`
- `invoices_followup`
- `invoices_comment`
- `invoices_meeting`
- `invoices_pipeline`
- `invoices_pipelinestage`
- `invoices_coursecontent`

---

## 4. Key Foreign Key Additions (v2)

| Table | Column | References | On Delete |
|-------|--------|-----------|-----------|
| invoices_quotation | coupon_id | invoices_coupon(id) | SET NULL |
| invoices_quotationitemoverride | item_id | invoices_quotationitem(id) | CASCADE |
| invoices_userprofile | user_id | auth_user(id) | CASCADE |
| invoices_salestarget | user_id | auth_user(id) | CASCADE |
| invoices_salestarget | created_by_id | auth_user(id) | SET NULL |
| invoices_notification | recipient_id | auth_user(id) | CASCADE |
| invoices_companyportalrequest | generated_by_id | auth_user(id) | SET NULL |
| invoices_companyportalattendee | portal_request_id | invoices_companyportalrequest(id) | CASCADE |
| invoices_studentformlink | consultant_id | auth_user(id) | SET NULL |
| invoices_invoicepayment | invoice_id | invoices_invoice(id) | CASCADE |
| invoices_invoicepayment | recorded_by_id | auth_user(id) | SET NULL |
| invoices_trainingschedule | course_id | invoices_course(id) | CASCADE |
| invoices_trainingschedule | created_by_id | auth_user(id) | SET NULL |
| invoices_expense | course_id | invoices_course(id) | SET NULL |
| invoices_expense | recorded_by_id | auth_user(id) | SET NULL |
| invoices_auditlog | user_id | auth_user(id) | SET NULL |
| invoices_feereminderlog | invoice_id | invoices_invoice(id) | CASCADE |
| invoices_feereminderlog | sent_by_id | auth_user(id) | SET NULL |

---

## 5. Unique Constraints

| Table | Unique Column(s) |
|-------|-----------------|
| invoices_certificate | certificate_number |
| invoices_certificateupload | registration_id |
| invoices_corporateregistration | registration_id |
| invoices_coupon | code |
| invoices_course | code |
| invoices_formupload | registration_id |
| invoices_invoice | invoice_number |
| invoices_invoicepurchase | invoice_number |
| invoices_lead | email |
| invoices_proposal | proposal_number |
| invoices_quotation | quotation_number |
| invoices_quotationitemoverride | item_id |
| invoices_registration | registration_number |
| invoices_registrationcourse | (registration_id, course_id) |
| invoices_salestarget | (user_id, month) |
| invoices_studentformlink | token |
| invoices_companyportalrequest | token |
| invoices_trainerprofile | name |
| invoices_userprofile | user_id |

---

## 6. File Upload Directories

| Table | Field | Directory |
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

---

## 7. Database Setup (Local Development)

```sql
CREATE DATABASE IF NOT EXISTS orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;  -- use this collation for MariaDB
```

```powershell
# XAMPP import
C:\xampp\mysql\bin\mysql.exe -u root orbit_invoice < "D:\Insittute management system\orbiterp.sql"
```

If you get `Unknown collation: 'utf8mb4_0900_ai_ci'`, replace it with `utf8mb4_general_ci` in the SQL file before importing (MySQL 8 collation not supported by older MariaDB).

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
