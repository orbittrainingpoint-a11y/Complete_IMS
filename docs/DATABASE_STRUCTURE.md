# Database Structure Document
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Database:** orbit_invoice  
**Engine:** MySQL 8.0.39  
**Total Tables:** 36

---

## 1. Database Overview

```
Database: orbit_invoice
Character Set: utf8mb4
Collation: utf8mb4_0900_ai_ci
Engine: InnoDB (all tables)
Total Records: ~11,000+ across all tables
```

---

## 2. Entity Relationship Diagram (Text)

```
auth_user ─────────────────────────────────────────────────────────┐
    │                                                               │
    ├──(user_id)──► invoices_client ──(client_id)──► invoices_invoice
    │                                                      │
    ├──(user_id)──► invoices_quotation                     │
    │                                                      │
    ├──(user_id)──► invoices_lead                    invoices_invoiceitem
    │                    │                                 │
    │                    ├──► invoices_followup            └──(course_id)──► invoices_course
    │                    ├──► invoices_comment                              │
    │                    └──► invoices_meeting                              ├──► invoices_registrationcourse
    │                                                                       │
    ├──(user_id)──► invoices_trainerprofile          invoices_registration ─┤
    │                    │                                 │               │
    │                    └──(trainer_id)──► invoices_proposal               └──► invoices_coursecontent
    │
    ├──(user_id)──► invoices_companyprofile
    │
    ├──(user_id)──► invoices_invoicepurchase ──► invoices_invoicepurchaseitem
    │
    └──(created_by_id)──► invoices_coupon

invoices_registration ──OneToOne──► invoices_corporateregistration
invoices_registration ──OneToOne──► invoices_certificateupload
invoices_registration ──OneToOne──► invoices_formupload

invoices_pipeline ──(pipeline_id)──► invoices_pipelinestage ──(pipeline_stage_id)──► invoices_lead

invoices_quotation ──(quotation_id)──► invoices_quotationitem ──(course_id)──► invoices_course
```

---

## 3. All Tables — Complete Schema

### 3.1 Django System Tables

---

#### `auth_user` — System Users
*Django built-in. 54 records.*

| Column | Type | Null | Key | Default | Extra |
|--------|------|------|-----|---------|-------|
| id | int | NO | PRI | — | AUTO_INCREMENT |
| password | varchar(128) | NO | | | |
| last_login | datetime(6) | YES | | NULL | |
| is_superuser | tinyint(1) | NO | | | |
| username | varchar(150) | NO | UNI | | |
| first_name | varchar(150) | NO | | | |
| last_name | varchar(150) | NO | | | |
| email | varchar(254) | NO | | | |
| is_staff | tinyint(1) | NO | | | |
| is_active | tinyint(1) | NO | | | |
| date_joined | datetime(6) | NO | | | |

---

#### `auth_group` — Permission Groups
*Django built-in.*

| Column | Type | Null | Key |
|--------|------|------|-----|
| id | int | NO | PRI AUTO_INCREMENT |
| name | varchar(150) | NO | UNI |

---

#### `auth_permission` — System Permissions
*Django built-in. 128 records.*

| Column | Type | Null | Key |
|--------|------|------|-----|
| id | int | NO | PRI AUTO_INCREMENT |
| name | varchar(255) | NO | |
| content_type_id | int | NO | FK → django_content_type |
| codename | varchar(100) | NO | UNI(content_type_id, codename) |

---

#### `auth_group_permissions` — Group-Permission Junction

| Column | Type | Key |
|--------|------|-----|
| id | bigint | PRI |
| group_id | int | FK → auth_group |
| permission_id | int | FK → auth_permission |
| | | UNI(group_id, permission_id) |

---

#### `auth_user_groups` — User-Group Junction

| Column | Type | Key |
|--------|------|-----|
| id | bigint | PRI |
| user_id | int | FK → auth_user |
| group_id | int | FK → auth_group |
| | | UNI(user_id, group_id) |

---

#### `auth_user_user_permissions` — User-Permission Direct Assignment

| Column | Type | Key |
|--------|------|-----|
| id | bigint | PRI |
| user_id | int | FK → auth_user |
| permission_id | int | FK → auth_permission |
| | | UNI(user_id, permission_id) |

---

#### `django_content_type` — Model Registry
*32 records.*

| Column | Type | Key |
|--------|------|-----|
| id | int | PRI AUTO_INCREMENT |
| app_label | varchar(100) | UNI(app_label, model) |
| model | varchar(100) | |

---

#### `django_migrations` — Migration History
*68 records.*

| Column | Type |
|--------|------|
| id | bigint PRI AUTO_INCREMENT |
| app | varchar(255) |
| name | varchar(255) |
| applied | datetime(6) |

---

#### `django_session` — User Sessions

| Column | Type | Key |
|--------|------|-----|
| session_key | varchar(40) | PRI |
| session_data | longtext | |
| expire_date | datetime(6) | IDX |

---

#### `django_admin_log` — Admin Action Log

| Column | Type | Key |
|--------|------|-----|
| id | int | PRI AUTO_INCREMENT |
| action_time | datetime(6) | |
| object_id | longtext | NULL |
| object_repr | varchar(200) | |
| action_flag | smallint unsigned | CHECK ≥ 0 |
| change_message | longtext | |
| content_type_id | int | NULL FK → django_content_type |
| user_id | int | FK → auth_user |

---

### 3.2 Business Application Tables

---

#### `invoices_client` — Client Records
*1,694 records. AUTO_INCREMENT: 1694*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | | Client/company name |
| email | varchar(254) | NO | | |
| phone | varchar(20) | NO | | |
| address | longtext | NO | | |
| country | varchar(100) | NO | | |
| emirates | varchar(100) | NO | | UAE emirate (Abu Dhabi, Dubai, etc.) |
| user_id | int | NO | FK → auth_user | Owning consultant |

---

#### `invoices_course` — Training Courses
*239 records. AUTO_INCREMENT: 239*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | | Course full name |
| code | varchar(10) | NO | UNI | Short code (2-10 chars) used in cert numbers |
| rate | decimal(10,2) | NO | | Standard/offline rate |
| batch_rate | decimal(10,2) | NO | | Group/batch rate |
| online_rate | decimal(10,2) | NO | | Online delivery rate |
| private_rate | decimal(10,2) | NO | | Private/1-on-1 rate |

---

#### `invoices_coursecontent` — Course Materials
*68 records. AUTO_INCREMENT: 68*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| title | varchar(255) | NO | | Material title |
| file | varchar(100) | NO | | Path: media/course_contents/ |
| upload_date | datetime(6) | NO | | Auto-set on upload |
| course_id | bigint | NO | FK → invoices_course | |

---

#### `invoices_registration` — Student Registrations
*853 records. AUTO_INCREMENT: 853*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_number | varchar(20) | NO | UNI | OT/YY/MM/### or OC/YY/MM/### |
| registration_type | varchar(2) | NO | | 'OT' (individual) or 'OC' (corporate) |
| date | date | NO | | Registration date |
| first_name | varchar(100) | NO | | |
| last_name | varchar(100) | NO | | |
| date_of_birth | date | YES | NULL | |
| passport_no | varchar(100) | NO | | |
| uid_no | varchar(100) | NO | | UAE UID number |
| emirates_id_no | varchar(100) | NO | | UAE Emirates ID |
| nationality | varchar(100) | NO | | |
| education | varchar(100) | NO | | Highest education level |
| phone_no | varchar(20) | NO | | Primary phone |
| alternative_no | varchar(20) | NO | | Optional secondary phone |
| email | varchar(254) | NO | | |
| country | varchar(100) | NO | | |
| emirates | varchar(100) | NO | | UAE emirate |
| address | longtext | NO | | Full address |
| company_or_university_name | varchar(100) | NO | | |
| consultant_name | varchar(100) | NO | | Responsible consultant |
| class_type | varchar(10) | NO | | online/offline/batch/private |

---

#### `invoices_registrationcourse` — Registration-Course Junction (ManyToMany)
*1,878 records. AUTO_INCREMENT: 1878*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_id | bigint | NO | FK → invoices_registration | |
| course_id | bigint | NO | FK → invoices_course | |
| price | decimal(10,2) | NO | | Agreed price for this course |
| discount | decimal(5,2) | NO | | Discount % (0.00–100.00) |
| | | | UNI(registration_id, course_id) | |

---

#### `invoices_corporateregistration` — Corporate Registration Extension
*43 records. AUTO_INCREMENT: 43*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_id | bigint | NO | UNI FK → invoices_registration | OneToOne |
| company_name | varchar(255) | NO | | |
| company_address | longtext | NO | | |
| company_location | varchar(255) | NO | | |
| company_phone | varchar(20) | NO | | |
| company_email | varchar(254) | NO | | |

---

#### `invoices_invoice` — Sales Invoices
*1,123 records. AUTO_INCREMENT: 1123*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_number | varchar(50) | NO | UNI | YY/MM/### format |
| date | date | NO | | Invoice date |
| due_date | date | NO | | Payment due date |
| total_amount | decimal(10,2) | NO | | Sum of all items + VAT |
| amount_paid | decimal(10,2) | NO | | Amount received |
| discount | decimal(5,2) | NO | | Invoice-level discount % |
| number_of_person | int | NO | | |
| status | varchar(20) | NO | | Full Payment/Term Payment/Tabby/Tamara |
| payment | varchar(20) | NO | | Card/Cash/Account Transfer/Payment Link/Cheque |
| class_type | varchar(10) | NO | | online/offline/batch/private |
| po_number | varchar(100) | NO | | Purchase order number |
| client_id | bigint | NO | FK → invoices_client | |
| user_id | int | NO | FK → auth_user | |
| registration_id | bigint | YES | NULL FK → invoices_registration | Optional link |
| course_id | bigint | YES | NULL FK → invoices_course | Optional header course |

---

#### `invoices_invoiceitem` — Invoice Line Items
*1,824 records. AUTO_INCREMENT: 1824*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_id | bigint | NO | FK → invoices_invoice | |
| course_id | bigint | YES | NULL FK → invoices_course | |
| description | longtext | NO | | Course name/description |
| quantity | int | NO | | |
| unit_price | decimal(10,2) | NO | | |
| vat_rate | decimal(4,2) | NO | | Default 5.00 |

*Calculated (not stored):*
- subtotal = quantity × unit_price
- vat_amount = subtotal × (vat_rate / 100)
- total = subtotal + vat_amount

---

#### `invoices_invoicepurchase` — Purchase/Expense Invoices
*33 records. AUTO_INCREMENT: 33*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| invoice_number | varchar(50) | NO | UNI | |
| date | date | NO | | |
| due_date | date | NO | | |
| total_amount | decimal(10,2) | NO | | |
| advance_amount | decimal(10,2) | NO | | |
| number_of_person | int | NO | | |
| discount | decimal(5,2) | NO | Default: 0.00 | |
| status | varchar(20) | NO | | |
| payment | varchar(20) | NO | | |
| po_number | varchar(100) | NO | | |
| client_id | bigint | NO | FK → invoices_client | |
| course_id | bigint | YES | NULL FK → invoices_course | |
| user_id | int | NO | FK → auth_user | |

---

#### `invoices_invoicepurchaseitem` — Purchase Invoice Line Items
*69 records. AUTO_INCREMENT: 69*

| Column | Type | Null | Key |
|--------|------|------|-----|
| id | bigint | NO | PRI AUTO_INCREMENT |
| invoice_id | bigint | NO | FK → invoices_invoicepurchase |
| course_id | bigint | YES | NULL FK → invoices_course |
| description | longtext | NO | |
| quantity | int | NO | |
| unit_price | decimal(10,2) | NO | |
| vat_rate | decimal(4,2) | NO | |

---

#### `invoices_quotation` — Client Quotations
*217 records. AUTO_INCREMENT: 217*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| quotation_number | varchar(20) | NO | UNI | YY/MM/### format |
| client_name | varchar(255) | NO | | |
| schedule | varchar(255) | NO | | Proposed schedule dates |
| training_venue | varchar(50) | NO | | In-House/External/Online |
| discount | decimal(10,2) | NO | | |
| consultant_name | varchar(20) | NO | | |
| consultant_position | varchar(255) | NO | | |
| consultant_number | varchar(20) | NO | | |
| consultant_email | varchar(254) | NO | | |
| created_at | datetime(6) | NO | | |
| user_id | int | NO | FK → auth_user | |

---

#### `invoices_quotationitem` — Quotation Line Items
*1,175 records. AUTO_INCREMENT: 1175*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| quotation_id | bigint | NO | FK → invoices_quotation | |
| course_id | bigint | NO | FK → invoices_course | |
| duration | decimal(10,2) | NO | | Hours or days |
| number_of_persons | int unsigned | NO | CHECK ≥ 0 | |

---

#### `invoices_certificate` — Issued Certificates
*254 records. AUTO_INCREMENT: 254*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| certificate_number | varchar(50) | NO | UNI | {CODE}/YY/### |
| register_number | varchar(20) | NO | | Links to registration (text, not FK) |
| certificate_type | varchar(20) | NO | | 'regular' or 'KHDA' |
| student_name | varchar(100) | NO | | |
| course_name | varchar(100) | NO | | |
| from_date | date | YES | NULL | |
| end_date | date | YES | NULL | |
| grade | varchar(2) | NO | | A+, A, B+, B, C+, C, D |
| uploaded_certificate | varchar(100) | YES | NULL | File path if uploaded |
| created_at | datetime(6) | NO | | |

---

#### `invoices_certificateupload` — Certificate File Uploads
*3 records. AUTO_INCREMENT: 3*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_id | bigint | NO | UNI FK → invoices_registration | OneToOne |
| certificate_file | varchar(100) | NO | | Path: media/certificates/ |
| upload_date | datetime(6) | NO | | |

---

#### `invoices_formupload` — Registration Form Uploads

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| registration_id | bigint | NO | UNI FK → invoices_registration | OneToOne |
| form_file | varchar(100) | NO | | Path: media/registration_forms/ |
| upload_date | datetime(6) | NO | | |

---

#### `invoices_proposal` — Training Proposals
*90 records. AUTO_INCREMENT: 90*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| proposal_number | varchar(20) | NO | UNI | PROP-YYYY-#### |
| client_name | varchar(255) | NO | | |
| presenter_title | varchar(255) | NO | | |
| date | date | NO | | |
| location | varchar(255) | NO | | |
| logo | varchar(100) | YES | NULL | Path: media/proposal_logos/ |
| logo_white_url | varchar(255) | YES | NULL | Path: media/proposal_logos_white/ |
| created_at | datetime(6) | NO | | |
| course_id | bigint | NO | FK → invoices_course | |
| trainer_id | bigint | YES | NULL | FK → invoices_trainerprofile (soft ref) |

---

#### `invoices_trainerprofile` — Trainer Profiles
*10 records. AUTO_INCREMENT: 10*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | UNI | |
| profile_pdf | varchar(100) | NO | | Path: media/trainer_profiles/ |
| created_at | datetime(6) | NO | | |
| user_id | int | NO | FK → auth_user | |

---

#### `invoices_companyprofile` — Company Profiles
*12 records. AUTO_INCREMENT: 12*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| name | varchar(255) | NO | | |
| company_pdf | varchar(100) | NO | | Path: media/company_profiles/ |
| created_at | datetime(6) | NO | | |
| user_id | int | NO | FK → auth_user | |

---

#### `invoices_lead` — Sales Leads (CRM)
*18 records. AUTO_INCREMENT: 18*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| full_name | varchar(100) | NO | | |
| email | varchar(254) | NO | UNI | Unique in system |
| phone | varchar(20) | YES | NULL | With country code |
| source | varchar(50) | NO | | Website/Referral/Event/Other |
| status | varchar(20) | NO | | Interested Highly/Qualified/Register Soon/Other |
| notes | longtext | YES | NULL | |
| follow_up_date | date | YES | NULL | |
| follow_up_status | varchar(20) | YES | NULL | |
| quote_amount | decimal(10,2) | YES | NULL | |
| created_at | datetime(6) | NO | | |
| interested_course_id | bigint | YES | NULL FK → invoices_course | |
| user_id | int | NO | FK → auth_user | Assigned consultant |
| pipeline_stage_id | bigint | YES | NULL FK → invoices_pipelinestage | |

---

#### `invoices_followup` — Lead Follow-Up Tasks

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| lead_id | bigint | NO | FK → invoices_lead | |
| user_id | int | NO | FK → auth_user | |
| contact_date | date | NO | | Scheduled date |
| contact_time | time(6) | NO | | Scheduled time |
| priority | varchar(20) | YES | NULL | Low/Medium/High/Urgent |
| status | varchar(20) | NO | | Pending/Completed/Cancelled/Rescheduled |
| notes | longtext | NO | | |
| created_at | datetime(6) | NO | | |

---

#### `invoices_comment` — Lead Comments/Notes
*30 records. AUTO_INCREMENT: 30*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| lead_id | bigint | NO | FK → invoices_lead | |
| user_id | int | NO | FK → auth_user | |
| text | longtext | NO | | |
| timestamp | datetime(6) | NO | | Auto-set |
| is_flagged | tinyint(1) | NO | | Default False |

---

#### `invoices_meeting` — Lead Meetings
*7 records. AUTO_INCREMENT: 7*

| Column | Type | Null | Key |
|--------|------|------|-----|
| id | bigint | NO | PRI AUTO_INCREMENT |
| lead_id | bigint | NO | FK → invoices_lead |
| user_id | int | NO | FK → auth_user |
| contact_date | date | NO | |
| contact_time | time(6) | NO | |
| notes | longtext | YES | NULL |
| created_at | datetime(6) | NO | |
| updated_at | datetime(6) | NO | |

---

#### `invoices_pipeline` — Sales Pipelines
*2 records. AUTO_INCREMENT: 2*

| Column | Type | Null | Key |
|--------|------|------|-----|
| id | bigint | NO | PRI AUTO_INCREMENT |
| name | varchar(100) | NO | |
| description | longtext | NO | |
| created_at | datetime(6) | NO | |
| updated_at | datetime(6) | NO | |

---

#### `invoices_pipelinestage` — Pipeline Stages
*2 records. AUTO_INCREMENT: 2*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| pipeline_id | bigint | NO | FK → invoices_pipeline | |
| name | varchar(100) | NO | | Stage name |
| order | int unsigned | NO | CHECK ≥ 0 | Display order |
| description | longtext | NO | | |
| is_won_stage | tinyint(1) | NO | | True = deal won |
| is_lost_stage | tinyint(1) | NO | | True = deal lost |

---

#### `invoices_coupon` — Discount Coupons
*5 records. AUTO_INCREMENT: 5*

| Column | Type | Null | Key | Notes |
|--------|------|------|-----|-------|
| id | bigint | NO | PRI AUTO_INCREMENT | |
| code | varchar(50) | NO | UNI | Coupon code string |
| discount_percentage | decimal(5,2) | NO | | 0.00–100.00 |
| is_active | tinyint(1) | NO | | Active flag |
| created_at | datetime(6) | NO | | |
| created_by_id | int | NO | FK → auth_user | |

---

## 4. All Foreign Key Relationships

| # | Table | Column | References | On Delete |
|---|-------|--------|-----------|-----------|
| 1 | auth_group_permissions | group_id | auth_group(id) | CASCADE |
| 2 | auth_group_permissions | permission_id | auth_permission(id) | CASCADE |
| 3 | auth_permission | content_type_id | django_content_type(id) | CASCADE |
| 4 | auth_user_groups | user_id | auth_user(id) | CASCADE |
| 5 | auth_user_groups | group_id | auth_group(id) | CASCADE |
| 6 | auth_user_user_permissions | user_id | auth_user(id) | CASCADE |
| 7 | auth_user_user_permissions | permission_id | auth_permission(id) | CASCADE |
| 8 | django_admin_log | content_type_id | django_content_type(id) | SET NULL |
| 9 | django_admin_log | user_id | auth_user(id) | CASCADE |
| 10 | invoices_client | user_id | auth_user(id) | CASCADE |
| 11 | invoices_comment | lead_id | invoices_lead(id) | CASCADE |
| 12 | invoices_comment | user_id | auth_user(id) | CASCADE |
| 13 | invoices_companyprofile | user_id | auth_user(id) | CASCADE |
| 14 | invoices_corporateregistration | registration_id | invoices_registration(id) | CASCADE |
| 15 | invoices_coupon | created_by_id | auth_user(id) | CASCADE |
| 16 | invoices_coursecontent | course_id | invoices_course(id) | CASCADE |
| 17 | invoices_followup | lead_id | invoices_lead(id) | CASCADE |
| 18 | invoices_followup | user_id | auth_user(id) | CASCADE |
| 19 | invoices_formupload | registration_id | invoices_registration(id) | CASCADE |
| 20 | invoices_invoice | client_id | invoices_client(id) | CASCADE |
| 21 | invoices_invoice | course_id | invoices_course(id) | SET NULL |
| 22 | invoices_invoice | registration_id | invoices_registration(id) | SET NULL |
| 23 | invoices_invoice | user_id | auth_user(id) | CASCADE |
| 24 | invoices_invoiceitem | course_id | invoices_course(id) | SET NULL |
| 25 | invoices_invoiceitem | invoice_id | invoices_invoice(id) | CASCADE |
| 26 | invoices_invoicepurchase | client_id | invoices_client(id) | CASCADE |
| 27 | invoices_invoicepurchase | course_id | invoices_course(id) | SET NULL |
| 28 | invoices_invoicepurchase | user_id | auth_user(id) | CASCADE |
| 29 | invoices_invoicepurchaseitem | course_id | invoices_course(id) | SET NULL |
| 30 | invoices_invoicepurchaseitem | invoice_id | invoices_invoicepurchase(id) | CASCADE |
| 31 | invoices_lead | interested_course_id | invoices_course(id) | SET NULL |
| 32 | invoices_lead | pipeline_stage_id | invoices_pipelinestage(id) | SET NULL |
| 33 | invoices_lead | user_id | auth_user(id) | CASCADE |
| 34 | invoices_meeting | lead_id | invoices_lead(id) | CASCADE |
| 35 | invoices_meeting | user_id | auth_user(id) | CASCADE |
| 36 | invoices_pipelinestage | pipeline_id | invoices_pipeline(id) | CASCADE |
| 37 | invoices_proposal | course_id | invoices_course(id) | CASCADE |
| 38 | invoices_quotation | user_id | auth_user(id) | CASCADE |
| 39 | invoices_quotationitem | course_id | invoices_course(id) | CASCADE |
| 40 | invoices_quotationitem | quotation_id | invoices_quotation(id) | CASCADE |
| 41 | invoices_registrationcourse | course_id | invoices_course(id) | CASCADE |
| 42 | invoices_registrationcourse | registration_id | invoices_registration(id) | CASCADE |
| 43 | invoices_certificateupload | registration_id | invoices_registration(id) | CASCADE |
| 44 | invoices_trainerprofile | user_id | auth_user(id) | CASCADE |

---

## 5. Unique Constraints

| Table | Unique Column(s) |
|-------|-----------------|
| auth_user | username |
| auth_group | name |
| auth_permission | (content_type_id, codename) |
| auth_group_permissions | (group_id, permission_id) |
| auth_user_groups | (user_id, group_id) |
| auth_user_user_permissions | (user_id, permission_id) |
| django_content_type | (app_label, model) |
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
| invoices_registration | registration_number |
| invoices_registrationcourse | (registration_id, course_id) |
| invoices_trainerprofile | name |

---

## 6. Data Volumes (Current)

| Table | Records |
|-------|---------|
| auth_user | 54 |
| invoices_client | 1,694 |
| invoices_course | 239 |
| invoices_coursecontent | 68 |
| invoices_registration | 853 |
| invoices_registrationcourse | 1,878 |
| invoices_corporateregistration | 43 |
| invoices_invoice | 1,123 |
| invoices_invoiceitem | 1,824 |
| invoices_invoicepurchase | 33 |
| invoices_invoicepurchaseitem | 69 |
| invoices_quotation | 217 |
| invoices_quotationitem | 1,175 |
| invoices_certificate | 254 |
| invoices_certificateupload | 3 |
| invoices_proposal | 90 |
| invoices_lead | 18 |
| invoices_followup | — |
| invoices_comment | 30 |
| invoices_meeting | 7 |
| invoices_pipeline | 2 |
| invoices_pipelinestage | 2 |
| invoices_coupon | 5 |
| invoices_companyprofile | 12 |
| invoices_trainerprofile | 10 |
| **Total (approx.)** | **~11,000+** |

---

## 7. Installation Instructions

### 7.1 Install SQL on Localhost (MySQL)

```sql
-- Step 1: Create database
CREATE DATABASE IF NOT EXISTS orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- Step 2: Import SQL dump
-- Run from command line:
mysql -u root -p orbit_invoice < "D:\Insittute management system\orbiterp.sql"
```

### 7.2 Via MySQL Workbench
1. Open MySQL Workbench
2. Connect to localhost
3. Server → Data Import
4. Select "Import from Self-Contained File"
5. Browse to `D:\Insittute management system\orbiterp.sql`
6. Set Target Schema to `orbit_invoice`
7. Click "Start Import"

### 7.3 Via Command Line (XAMPP)
```bash
# If using XAMPP:
C:\xampp\mysql\bin\mysql.exe -u root -p orbit_invoice < "D:\Insittute management system\orbiterp.sql"
```

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
