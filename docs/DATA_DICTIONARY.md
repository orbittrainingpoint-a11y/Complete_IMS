# Data Dictionary
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25

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
| Value | Meaning | Rate Field Used |
|-------|---------|-----------------|
| `online` | Online/virtual delivery | `course.online_rate` |
| `offline` | In-person classroom | `course.rate` |
| `batch` | Group/batch training | `course.batch_rate` |
| `private` | Private 1-on-1 | `course.private_rate` |

### 2.3 Invoice Status
| Value | Meaning |
|-------|---------|
| `Full Payment` | Full amount has been paid |
| `Term Payment` | Partial/instalment payment |
| `Tabby` | Buy-now-pay-later via Tabby |
| `Tamara` | Buy-now-pay-later via Tamara |

### 2.4 Payment Method
| Value | Meaning |
|-------|---------|
| `Card` | Credit/debit card payment |
| `Cash` | Cash payment |
| `Account Transfer` | Bank/wire transfer |
| `Payment Link` | Online payment link |
| `Cheque` | Cheque payment |

### 2.5 Training Venue (Quotation)
| Value | Meaning |
|-------|---------|
| `In-House` | At client's premises |
| `External` | At Orbit Training centre |
| `Online` | Virtual/remote delivery |

### 2.6 Lead Source
| Value | Meaning |
|-------|---------|
| `Website` | Enquiry via website |
| `Referral` | Referred by existing client |
| `Event` | Met at event/exhibition |
| `Other` | Any other source |

### 2.7 Lead Status
| Value | Meaning |
|-------|---------|
| `Interested Highly` | Very interested, ready to proceed |
| `Qualified` | Qualified but decision pending |
| `Register Soon` | Will register in near future |
| `Other` | Unclassified |

### 2.8 Follow-Up Priority
| Value | Meaning |
|-------|---------|
| `Low` | Non-urgent |
| `Medium` | Standard priority |
| `High` | Important |
| `Urgent` | Requires immediate attention |

### 2.9 Follow-Up Status
| Value | Meaning |
|-------|---------|
| `Pending` | Not yet done |
| `Completed` | Follow-up done |
| `Cancelled` | Cancelled, not required |
| `Rescheduled` | Moved to new date |

### 2.10 Certificate Type
| Value | Meaning |
|-------|---------|
| `regular` | Standard Orbit Training certificate |
| `KHDA` | KHDA (Knowledge and Human Development Authority) accredited |

### 2.11 Certificate Grade
| Value | Meaning |
|-------|---------|
| `A+` | Excellent |
| `A` | Very Good |
| `B+` | Good Plus |
| `B` | Good |
| `C+` | Satisfactory Plus |
| `C` | Satisfactory |
| `D` | Pass |

---

## 3. Field Definitions by Table

### 3.1 `invoices_client`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Auto-generated primary key |
| name | varchar | 255 | Full client or company name |
| email | varchar | 254 | Client email address |
| phone | varchar | 20 | Client phone number (with country code) |
| address | longtext | — | Full mailing address |
| country | varchar | 100 | Country of residence/operation |
| emirates | varchar | 100 | UAE emirate (Abu Dhabi, Dubai, Sharjah, etc.) |
| user_id | int | — | FK: Staff member who manages this client |

---

### 3.2 `invoices_course`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Auto-generated primary key |
| name | varchar | 255 | Full course title |
| code | varchar | 10 | Unique short code used in certificate numbering |
| rate | decimal(10,2) | — | Standard/offline delivery rate (AED) |
| batch_rate | decimal(10,2) | — | Group batch rate per person (AED) |
| online_rate | decimal(10,2) | — | Online delivery rate (AED) |
| private_rate | decimal(10,2) | — | Private 1-on-1 rate (AED) |

---

### 3.3 `invoices_registration`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Auto-generated primary key |
| registration_number | varchar | 20 | Unique. Format: OT/YY/MM/### or OC/YY/MM/### |
| registration_type | varchar | 2 | 'OT' (individual) or 'OC' (corporate) |
| date | date | — | Date of registration |
| first_name | varchar | 100 | Student first name |
| last_name | varchar | 100 | Student last name |
| date_of_birth | date | — | Optional. Student DOB |
| passport_no | varchar | 100 | Passport number |
| uid_no | varchar | 100 | UAE Unified Identity Number |
| emirates_id_no | varchar | 100 | UAE Emirates ID card number |
| nationality | varchar | 100 | Student nationality |
| education | varchar | 100 | Highest education qualification |
| phone_no | varchar | 20 | Primary contact number |
| alternative_no | varchar | 20 | Secondary contact number |
| email | varchar | 254 | Email address |
| country | varchar | 100 | Country of residence |
| emirates | varchar | 100 | UAE emirate of residence |
| address | longtext | — | Full residential address |
| company_or_university_name | varchar | 100 | Current employer or institution |
| consultant_name | varchar | 100 | Staff member who handled registration |
| class_type | varchar | 10 | Delivery mode: online/offline/batch/private |

---

### 3.4 `invoices_registrationcourse`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Primary key |
| registration_id | bigint | FK to invoices_registration |
| course_id | bigint | FK to invoices_course |
| price | decimal(10,2) | Agreed course price in AED |
| discount | decimal(5,2) | Discount applied to this course (%) |

*Unique constraint: (registration_id, course_id) — student cannot enroll in same course twice.*

---

### 3.5 `invoices_invoice`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| invoice_number | varchar | 50 | Unique. Format: YY/MM/### |
| date | date | — | Invoice creation date |
| due_date | date | — | Payment due date |
| total_amount | decimal(10,2) | — | Total inc. VAT minus discount (AED) |
| amount_paid | decimal(10,2) | — | Amount received so far (AED) |
| discount | decimal(5,2) | — | Invoice-level discount percentage |
| number_of_person | int | — | Number of people on this invoice |
| status | varchar | 20 | Payment status (see §2.3) |
| payment | varchar | 20 | Payment method (see §2.4) |
| class_type | varchar | 10 | Delivery mode (see §2.2) |
| po_number | varchar | 100 | Purchase Order number from client |
| client_id | bigint | — | FK to invoices_client |
| user_id | int | — | FK to auth_user (staff member) |
| registration_id | bigint | — | Optional FK to invoices_registration |
| course_id | bigint | — | Optional FK to invoices_course (header) |

---

### 3.6 `invoices_invoiceitem`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Primary key |
| invoice_id | bigint | FK to invoices_invoice |
| course_id | bigint | Optional FK to invoices_course |
| description | longtext | Course name or description |
| quantity | int | Number of units/persons |
| unit_price | decimal(10,2) | Price per unit (AED) |
| vat_rate | decimal(4,2) | VAT percentage (default: 5.00) |

*Calculated fields (not stored):*
- Subtotal = quantity × unit_price
- VAT Amount = subtotal × (vat_rate / 100)
- Line Total = subtotal + VAT Amount

---

### 3.7 `invoices_quotation`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| quotation_number | varchar | 20 | Unique. Format: YY/MM/### |
| client_name | varchar | 255 | Client company or person name |
| schedule | varchar | 255 | Proposed training schedule dates |
| training_venue | varchar | 50 | In-House / External / Online |
| discount | decimal(10,2) | — | Overall discount amount (AED) |
| consultant_name | varchar | 20 | Staff contact name |
| consultant_position | varchar | 255 | Staff job title |
| consultant_number | varchar | 20 | Staff phone number |
| consultant_email | varchar | 254 | Staff email address |
| created_at | datetime(6) | — | Creation timestamp |
| user_id | int | — | FK to auth_user |

---

### 3.8 `invoices_certificate`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| certificate_number | varchar | 50 | Unique. Format: {CODE}/YY/### |
| register_number | varchar | 20 | Student's registration number (text reference) |
| certificate_type | varchar | 20 | 'regular' or 'KHDA' |
| student_name | varchar | 100 | Full student name on certificate |
| course_name | varchar | 100 | Course name on certificate |
| from_date | date | — | Training start date |
| end_date | date | — | Training end date |
| grade | varchar | 2 | Grade: A+, A, B+, B, C+, C, D |
| uploaded_certificate | varchar | 100 | File path if cert was uploaded |
| created_at | datetime(6) | — | Issue timestamp |

---

### 3.9 `invoices_lead`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| full_name | varchar | 100 | Lead's full name |
| email | varchar | 254 | Email — UNIQUE in system |
| phone | varchar | 20 | Phone with country code |
| source | varchar | 50 | Lead origin (see §2.6) |
| status | varchar | 20 | Lead status (see §2.7) |
| notes | longtext | — | Internal notes about lead |
| follow_up_date | date | — | Next scheduled contact date |
| follow_up_status | varchar | 20 | Status of latest follow-up |
| quote_amount | decimal(10,2) | — | Quoted training fee (AED) |
| created_at | datetime(6) | — | Lead creation timestamp |
| interested_course_id | bigint | — | FK to invoices_course |
| user_id | int | — | FK to auth_user (assigned consultant) |
| pipeline_stage_id | bigint | — | FK to invoices_pipelinestage |

---

### 3.10 `invoices_followup`

| Field | Type | Description |
|-------|------|-------------|
| id | bigint | Primary key |
| lead_id | bigint | FK to invoices_lead |
| user_id | int | FK to auth_user |
| contact_date | date | Scheduled follow-up date |
| contact_time | time(6) | Scheduled follow-up time |
| priority | varchar(20) | Low / Medium / High / Urgent |
| status | varchar(20) | Pending / Completed / Cancelled / Rescheduled |
| notes | longtext | Notes from/for the follow-up |
| created_at | datetime(6) | Record creation timestamp |

---

### 3.11 `invoices_proposal`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| proposal_number | varchar | 20 | Unique. Format: PROP-YYYY-#### |
| client_name | varchar | 255 | Target client name |
| presenter_title | varchar | 255 | Presenter's job title |
| date | date | — | Proposal date |
| location | varchar | 255 | Proposed training location |
| logo | varchar | 100 | File path: media/proposal_logos/ |
| logo_white_url | varchar | 255 | File path: media/proposal_logos_white/ |
| created_at | datetime(6) | — | Creation timestamp |
| course_id | bigint | — | FK to invoices_course |
| trainer_id | bigint | — | Optional FK to invoices_trainerprofile |

---

### 3.12 `invoices_coupon`

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| id | bigint | — | Primary key |
| code | varchar | 50 | Unique coupon code string (e.g., "SAVE10") |
| discount_percentage | decimal(5,2) | — | Discount percentage (0.00–100.00) |
| is_active | tinyint(1) | — | 1=active, 0=inactive |
| created_at | datetime(6) | — | Creation timestamp |
| created_by_id | int | — | FK to auth_user |

---

## 4. Auto-Generated Values

| Table | Field | Pattern | Example |
|-------|-------|---------|---------|
| invoices_invoice | invoice_number | YY/MM/### | 24/06/001 |
| invoices_invoicepurchase | invoice_number | YY/MM/### | 24/06/001 |
| invoices_quotation | quotation_number | YY/MM/### | 24/06/001 |
| invoices_registration | registration_number | OT/YY/MM/### | OT/24/06/001 |
| invoices_registration | registration_number | OC/YY/MM/### | OC/24/06/001 |
| invoices_certificate | certificate_number | {CODE}/YY/### | PM/24/001 |
| invoices_proposal | proposal_number | PROP-YYYY-#### | PROP-2024-0001 |

---

## 5. File Fields

| Table | Field | Upload Directory | Allowed Types |
|-------|-------|-----------------|---------------|
| invoices_trainerprofile | profile_pdf | media/trainer_profiles/ | PDF |
| invoices_companyprofile | company_pdf | media/company_profiles/ | PDF |
| invoices_proposal | logo | media/proposal_logos/ | PNG only, 800×300px |
| invoices_proposal | logo_white_url | media/proposal_logos_white/ | Auto-generated PNG |
| invoices_coursecontent | file | media/course_contents/ | Any |
| invoices_certificateupload | certificate_file | media/certificates/ | PDF/Image |
| invoices_formupload | form_file | media/registration_forms/ | PDF/Image |
| invoices_certificate | uploaded_certificate | media/khda_certificates/ | PDF/Image |

---

## 6. Calculated Fields (Not Stored in DB)

| Model | Method | Calculation |
|-------|--------|-------------|
| InvoiceItem | get_subtotal() | quantity × unit_price |
| InvoiceItem | get_vat_amount() | subtotal × (vat_rate / 100) |
| InvoiceItem | get_total() | subtotal + vat_amount |
| Invoice | calculate_total_amount() | Σ item totals |
| RegistrationCourse | total_price | price × (1 − discount/100) |

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
