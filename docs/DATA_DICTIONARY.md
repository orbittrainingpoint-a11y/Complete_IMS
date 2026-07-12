# Data Dictionary
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13

---

## 1. Table: `invoices_registration`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | int (PK) | No | Auto-increment |
| registration_number | varchar(50) | No | `OT/YY/###` or `OC/YY/###` |
| registration_type | varchar(20) | No | `individual` / `corporate` |
| student_name | varchar(255) | No | Full legal name |
| date_of_birth | date | Yes | |
| passport_number | varchar(50) | Yes | |
| uid | varchar(50) | Yes | Unified ID number |
| emirates_id | varchar(50) | Yes | |
| nationality | varchar(100) | Yes | |
| education_level | varchar(100) | Yes | |
| phone | varchar(30) | No | |
| email | varchar(255) | Yes | |
| country | varchar(100) | Yes | |
| emirates | varchar(100) | Yes | UAE emirate |
| consultant | varchar(255) | Yes | Name of sales executive |
| class_type | varchar(20) | No | online / offline / batch / private |
| level | varchar(30) | No | intermediate / professional / advanced |
| status | varchar(30) | No | active / completed / dropped / suspended / pending |
| date | date | No | Registration date |
| **created_at** | datetime | Yes | When record was created (used by 1-hr edit lock) |
| **is_refunded** | tinyint(1) | No | Default 0; set to 1 on confirmed refund |
| **welcome_email_sent** | tinyint(1) | No | Default 0 |
| enrolment_doc | varchar(255) | Yes | File path |
| notes | text | Yes | |
| company | varchar(255) | Yes | Company name for corporate |
| crm_lead_id | int | Yes | FK to CRM lead |

Bold = added in v3 migrations.

---

## 2. Table: `invoices_invoice`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| invoice_number | varchar(20) | `YY/MM/###` sequential |
| registration | FK → registration | Nullable |
| client | FK → client | |
| invoice_date | date | |
| due_date | date | |
| class_type | varchar(20) | online/offline/batch/private |
| level | varchar(30) | |
| status | varchar(30) | Full Payment / Term Payment / Tabby / Tamara |
| payment_method | varchar(30) | Card / Cash / Account Transfer / Payment Link / Cheque |
| amount_paid | decimal(10,2) | |
| discount | decimal(5,2) | Percentage — max 20% (single), 30% (multi) |
| number_of_person | int | Default 1; forced to 1 in corporate PI mode |
| total_amount | decimal(10,2) | Includes 5% VAT |
| po_number | varchar(100) | Nullable |
| created_at | datetime | |
| created_by | FK → auth_user | |

---

## 3. Table: `invoices_invoiceitem`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| invoice | FK → invoice | |
| course | FK → course | |
| course_name | varchar(255) | Snapshot at time of invoice |
| price | decimal(10,2) | Unit price |
| quantity | int | |
| discount | decimal(5,2) | |
| vat | decimal(5,2) | Always 5% |
| total | decimal(10,2) | price × qty × (1−discount%) × 1.05 |

---

## 4. Table: `invoices_invoicepayment`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| invoice | FK → invoice | |
| amount | decimal(10,2) | Installment amount |
| payment_method | varchar(30) | |
| reference | varchar(255) | Cheque/transfer ref |
| paid_at | date | |
| notes | text | Nullable |

---

## 5. Table: `invoices_course`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| name | varchar(255) | |
| code | varchar(20) | Used in certificate number prefix |
| duration | varchar(50) | e.g., "3 Days" |
| oo_intermediate | decimal(10,2) | Online/offline intermediate price |
| oo_professional | decimal(10,2) | |
| oo_advanced | decimal(10,2) | |
| priv_intermediate | decimal(10,2) | Private intermediate |
| priv_professional | decimal(10,2) | |
| priv_advanced | decimal(10,2) | |
| description | text | Nullable |
| is_active | tinyint(1) | Default 1 |

Zero-value prices displayed as `—` in course list and invoice forms.

---

## 6. Table: `invoices_certificate`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| registration | FK → registration | Nullable |
| certificate_number | varchar(100) | `{CODE}{REG_NUMBER}` e.g. `PMOT/26/001` |
| course_name | varchar(255) | |
| from_date | date | Course start date |
| end_date | date | Course end date |
| grade | varchar(50) | |
| issued_date | date | |
| certificate_type | varchar(30) | orbit / khda / iko |
| file | FileField | Uploaded cert file |

---

## 7. Table: `invoices_certificationrequest` *(v3)*

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| registration | FK → registration | |
| token | char(32) | UUID4, unique — public form link key |
| status | varchar(20) | pending / submitted / approved / rejected |
| sent_at | datetime | When email was sent |
| submitted_at | datetime | When client filled form |
| completion_date | date | Client-entered course completion date |
| class_rating | varchar(20) | excellent / good / average / poor |
| **class_feedback** | text | Required — client's written feedback about the class |
| client_notes | text | Optional additional comments from client |
| generated_certificate | FK → certificate | Nullable — set on approve |

Bold = added migration 0069.

---

## 8. Table: `invoices_refund` *(v3)*

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| registration | FK → registration | OneToOne — one refund per registration |
| reason | text | Required — why refund was requested |
| document | FileField | Optional supporting document |
| amount | decimal(10,2) | Refund amount |
| status | varchar(20) | pending / confirmed / cancelled |
| requested_at | datetime | When refund was initiated |
| confirmed_at | datetime | Nullable — when confirmed |
| confirmed_by | FK → auth_user | Nullable — who confirmed |
| notes | text | Admin notes |

When `status = 'confirmed'`: `registration.is_refunded` is set to `True`.

---

## 9. Table: `invoices_institutesetting` *(v3 — singleton)*

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | Always 1 — singleton |
| company_name | varchar(255) | |
| trade_license | varchar(100) | |
| vat_number | varchar(50) | |
| address | text | |
| phone | varchar(30) | |
| email | varchar(255) | |
| website | varchar(255) | |
| company_logo | ImageField | `institute/logo/` |
| stamp | ImageField | `institute/stamp/` |
| authorization_logo | ImageField | `institute/auth_logo/` |
| signature | ImageField | `institute/signature/` |
| bank_name | varchar(255) | |
| account_name | varchar(255) | |
| account_number | varchar(100) | |
| iban | varchar(50) | |
| swift | varchar(20) | |
| facebook | URLField | |
| instagram | URLField | |
| linkedin | URLField | |
| twitter | URLField | |

All fields `blank=True`. Access via `InstituteSetting.get()`.

---

## 10. Table: `invoices_userprofile`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user | OneToOne → auth_user | |
| role | varchar(30) | admin / sales_manager / accounts / sales_executive |
| phone | varchar(30) | |
| profile_picture | ImageField | |
| is_active | tinyint(1) | Default 1 |

---

## 11. Table: `invoices_salestarget`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user | FK → auth_user | |
| month | date | First day of month |
| target_amount | decimal(12,2) | Target revenue in AED |
| target_registrations | int | Target registration count |

Unique together: (user, month).

---

## 12. Table: `invoices_coupon`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| code | varchar(50) | Unique — case-insensitive lookup |
| discount_percentage | decimal(5,2) | Applied to invoice total |
| max_uses | int | 0 = unlimited |
| current_uses | int | Incremented on use |
| expiry_date | date | Nullable — no expiry if NULL |
| is_active | tinyint(1) | |

Validation: code lookup → check `is_active`, `current_uses < max_uses` (or max_uses=0), `expiry_date >= today`.

---

## 13. Table: `invoices_auditlog`

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user | FK → auth_user | Nullable |
| action | varchar(100) | e.g. `login`, `logout`, `create_invoice` |
| description | text | Human-readable detail |
| ip_address | varchar(45) | From X-Forwarded-For or REMOTE_ADDR |
| timestamp | datetime | |

---

## 14. CRM Tables (Flask — `leads_db`)

### `leads` (Lead)

| Column | Notes |
|--------|-------|
| id | PK |
| full_name | Lead's full name |
| phone | Contact phone |
| email | |
| status | New / Contacted / Qualified / Proposal / Closed Won / Closed Lost |
| source | Where lead came from |
| interested_course | |
| assigned_to | FK → crm_users |
| created_at | |

### `lead_interactions` (LeadInteraction)

| Column | Notes |
|--------|-------|
| id | PK |
| lead_id | FK → leads (delete=cascade-safe via explicit delete in route) |
| type | call / email / meeting / note |
| note | |
| created_at | |

### `lead_quotes` (LeadQuote)

| Column | Notes |
|--------|-------|
| id | PK |
| lead_id | FK → leads |
| course | |
| amount | |
| created_at | |

### `meetings`

| Column | Notes |
|--------|-------|
| id | PK |
| lead_id | FK → leads (nullable — set to NULL on lead delete) |
| title | |
| scheduled_at | |

### `crm_users`

| Column | Notes |
|--------|-------|
| id | PK |
| username | Synced from ERP on user create/edit |
| email | |
| role | sales_manager / consultant |
| password_hash | werkzeug-compatible |
| can_view_all_leads | 0 or 1 |

---

*Document updated: 2026-07-13*
*Version 3.0 — adds CertificationRequest, Refund, InstituteSetting; updated registration with v3 columns; CRM table details*
