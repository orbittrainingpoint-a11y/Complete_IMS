# Functional Requirements Document (FRD)
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Product:** Orbit ERP Institute Management System  
**Status:** Production

---

## 1. Introduction

This document defines the detailed functional requirements for the Orbit ERP system. It describes the specific behavior, inputs, outputs, and business rules for each functional module.

---

## 2. System Authentication

### 2.1 Login

**Function:** Authenticate users to access the system

**Input:**
- Username (text)
- Password (text)

**Process:**
1. Validate credentials against `auth_user` table
2. Create session on success
3. Redirect to dashboard on success; show error on failure

**Output:**
- Success: Redirect to `/dashboard/`
- Failure: Error message "Invalid credentials"

**Business Rules:**
- All pages except login are protected; unauthenticated requests redirect to login
- Session persists until explicit logout or session expiry

### 2.2 User Registration (Admin Only)

**Function:** Create new system user accounts

**Access:** Admin/superuser only (`is_staff = True OR is_superuser = True`)

**Input:**
- Username, Password, First Name, Last Name, Email

**Process:**
1. Validate admin access
2. Validate form fields
3. Create `auth_user` record
4. Redirect to dashboard with success message

**Business Rules:**
- Only admins can create new user accounts
- Regular staff cannot self-register

### 2.3 Logout

**Function:** Terminate user session

**Process:** Call `logout()`, redirect to login page

---

## 3. Invoice Management

### 3.1 Create Sales Invoice

**Function:** Generate a new sales invoice

**URL:** `/create_invoice/`  
**Access:** Login required

**Input Form Fields:**
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Registration Number | Select/Text | No | Links to existing registration |
| Client | Select | Yes | From invoices_client |
| Course | Select | No | From invoices_course |
| Invoice Date | Date | Yes | |
| Due Date | Date | Yes | |
| Class Type | Select | Yes | online/offline/batch/private |
| Status | Select | Yes | Full Payment/Term Payment/Tabby/Tamara |
| Payment Method | Select | Yes | Card/Cash/Account Transfer/Payment Link/Cheque |
| Total Amount | Decimal | Auto | Calculated from items |
| Amount Paid | Decimal | Yes | |
| Discount | Decimal | No | Percentage |
| Number of Persons | Integer | Yes | Default 1 |
| PO Number | Text | No | Purchase order reference |

**Business Rules:**
- Invoice number auto-generated: `YY/MM/###` (e.g., `24/06/001`)
- Number resets per year/month prefix
- VAT (5%) is calculated per line item automatically
- `total_amount` = sum of all item totals including VAT
- Can be linked to a registration OR be standalone (client-only)
- Discount is applied at invoice level; VAT applied at item level

**Process Flow:**
1. User fills invoice header form
2. System auto-generates invoice number
3. User saves → redirected to add items
4. User adds invoice items (courses + quantities + prices)
5. System calculates subtotal + VAT per item
6. System updates invoice `total_amount`

### 3.2 Invoice Line Items

**Function:** Add course items to an invoice

**URL:** `/add_invoice_items/<invoice_id>/`

**Input per line item:**
| Field | Type | Notes |
|-------|------|-------|
| Course | Select | From invoices_course |
| Quantity | Integer | Number of persons or units |
| Unit Price | Decimal | Auto-filled from course rate; editable |
| VAT Rate | Decimal | Default 5%; editable |

**Calculations per item:**
- Subtotal = Quantity × Unit Price
- VAT Amount = Subtotal × (VAT Rate / 100)
- Item Total = Subtotal + VAT Amount

**Invoice Total:**
- Total Amount = Σ(Item Totals) − Invoice Discount

### 3.3 Edit Invoice

**URL:** `/invoice/<id>/edit/`

**Business Rules:**
- All fields editable except invoice number
- Recalculates totals on save
- Updates linked registration payment status if applicable

### 3.4 Delete Invoice

**URL:** `/invoice/<id>/delete/`

**Business Rules:**
- Requires admin access
- Confirmation required (separate confirm page)
- Cascades to delete InvoiceItems

### 3.5 Invoice Dashboard / List

**URL:** `/dashboard/`

**Features:**
- Tabbed view: Sales Invoices | Purchase Invoices
- Filter by: invoice number, registration number, client name, due date, payment status
- Sortable columns
- Shows: Invoice #, Client, Amount, Status, Due Date, Payment Method

### 3.6 Purchase Invoice

**Function:** Record purchase/expense invoices from vendors

**Fields:** Same as sales invoice plus:
- `advance_amount` — advance payment made

**Business Rules:**
- Numbered separately from sales invoices
- Same item calculation logic (VAT 5%)

---

## 4. Student Registration

### 4.1 Individual Registration

**URL:** `/register/`  
**Access:** Login required

**Input Form Fields:**
| Field | Type | Required |
|-------|------|----------|
| Registration Type | Radio | Yes — OT (Individual) or OC (Corporate) |
| Class Type | Select | Yes — online/offline/batch/private |
| First Name | Text | Yes |
| Last Name | Text | Yes |
| Date of Birth | Date | No |
| Passport No | Text | Yes |
| UID No | Text | Yes |
| Emirates ID No | Text | Yes |
| Nationality | Text | Yes |
| Education | Text | Yes |
| Phone No | Text | Yes |
| Alternative No | Text | No |
| Email | Email | Yes |
| Country | Select | Yes |
| Emirates | Select | Yes (if UAE) |
| Address | Textarea | Yes |
| Company/University | Text | No |
| Consultant Name | Text | Yes |
| Courses | Multi-select | Yes — 1+ courses |
| Price per course | Decimal | Auto-filled; editable |
| Discount per course | Decimal | No — percentage |

**Auto-generated Fields:**
- `registration_number`: `OT/YY/MM/###` (individual) or `OC/YY/MM/###` (corporate)
- `date`: Today's date

**Business Rules:**
- Must select at least one course
- Course price auto-fills based on class type:
  - online → `course.online_rate`
  - offline → `course.rate`
  - batch → `course.batch_rate`
  - private → `course.private_rate`
- Each course can have individual discount percentage
- Unique constraint on (registration, course) — can't enroll in same course twice
- Registration number is unique and sequential per month

### 4.2 Corporate Registration

**URL:** `/corporate-registration/`

**Additional Fields beyond individual:**
| Field | Type | Required |
|-------|------|----------|
| Company Name | Text | Yes |
| Company Address | Textarea | Yes |
| Company Location | Text | Yes |
| Company Phone | Text | Yes |
| Company Email | Email | Yes |

**Business Rules:**
- Creates both a `Registration` record (type=OC) and `CorporateRegistration` record (OneToOne)
- Registration number uses OC prefix

### 4.3 Student Dashboard

**URL:** `/student-dashboard/`

**Displays:**
- All individual registrations (type=OT)
- Search/filter by name, registration number
- Links to: edit, delete, print, view invoice, upload certificate/form

### 4.4 Corporate Dashboard

**URL:** `/corporate_dashboard/`

**Displays:**
- All corporate registrations (type=OC) with company details
- Same actions as student dashboard

### 4.5 Print Registration

**URL:** `/print-registration/<id>/`

**Output:** Printable A4 HTML template with:
- Registration details
- Course enrollment list
- Pricing breakdown
- Total fees

---

## 5. Course Management

### 5.1 Course CRUD

**Create URL:** `/courses/create/`  
**List URL:** `/courses/`

**Input Fields:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Name | Text | Yes | |
| Code | Text | Yes | 2-10 chars, UNIQUE |
| Standard Rate | Decimal | Yes | |
| Batch Rate | Decimal | Yes | |
| Online Rate | Decimal | Yes | |
| Private Rate | Decimal | Yes | |

**Business Rules:**
- Course code must be unique (enforced at DB level)
- Code is used to prefix certificate numbers: `{CODE}/YY/###`
- Cannot delete course if it has active registrations or invoices (FK constraint)

### 5.2 Course Content Upload

**URL:** `/courses/<id>/content/create/`

**Input:**
- Title (text)
- File (FileField — any format)

**Storage:** `media/course_contents/`

**Business Rules:**
- Multiple content files per course
- Files stored with original names

---

## 6. Certificate Management

### 6.1 Create Certificate

**URL:** `/certificates/create/`

**Input Fields:**
| Field | Type | Required |
|-------|------|----------|
| Register Number | Text | Yes — must match existing registration |
| Student Name | Text | Yes |
| Course Name | Text | Yes |
| From Date | Date | No |
| End Date | Date | No |
| Grade | Select | Yes — A+, A, B+, B, C+, C, D |
| Certificate Type | Select | Yes — regular or KHDA |

**Auto-generated:**
- `certificate_number`: `{COURSE_CODE}/YY/###`

**Business Rules:**
- Certificate number is unique
- Sequential numbering per course code per year
- Grade displayed on printed certificate

### 6.2 KHDA Certificate

**URL:** `/certificates/khda-form/`

**Function:** Upload pre-issued KHDA certificate file against a registration

**Input:**
- Registration number (to link)
- Certificate file (PDF/image upload)

**Storage:** `media/khda_certificates/`

### 6.3 Print Certificate

**URL:** `/certificates/print/<id>/`

**Output:** Styled HTML template rendered for printing with:
- Student name
- Course name
- Dates
- Grade
- Certificate number
- Institute branding

### 6.4 Upload Certificate

**URL:** `/upload-certificate/<registration_id>/`

**Function:** Upload pre-issued certificate PDF against a registration

**Business Rules:**
- OneToOne: One uploaded certificate per registration
- Replaces existing upload if re-uploaded

---

## 7. Quotation Management

### 7.1 Create Quotation

**URL:** `/quotation/create/`

**Input Fields:**
| Field | Type | Required |
|-------|------|----------|
| Client Name | Text | Yes |
| Training Schedule | Text | Yes |
| Training Venue | Select | Yes — In-House/External/Online |
| Discount | Decimal | No |
| Consultant Name | Text | Yes |
| Consultant Position | Text | Yes |
| Consultant Phone | Text | Yes |
| Consultant Email | Email | Yes |
| Courses | Formset | Yes — 1+ items |

**Per Course Item:**
| Field | Type |
|-------|------|
| Course | Select from invoices_course |
| Duration | Decimal (hours/days) |
| Number of Persons | Integer |

**Auto-generated:**
- `quotation_number`: `YY/MM/###`

**Business Rules:**
- Quotation numbers are sequential per month/year
- No VAT calculation at quotation stage (prices are estimates)
- Discount is applied to total

### 7.2 Quotation Detail (Print)

**URL:** `/quotation_detail/<id>/`

**Output:** Professional quotation layout for client delivery including:
- Quotation number and date
- Client name
- Course list with durations and person counts
- Pricing breakdown
- Consultant signature block
- Institute letterhead

---

## 8. Proposal Management

### 8.1 Create Proposal

**URL:** `/proposals/create/`

**Input Fields:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Client Name | Text | Yes | |
| Course | Select | Yes | From invoices_course |
| Presenter Title | Text | Yes | |
| Date | Date | Yes | |
| Location | Text | Yes | |
| Trainer | Select | No | From invoices_trainerprofile |
| Logo | PNG Image | No | Must be exactly 800×300px |

**Auto-generated:**
- `proposal_number`: `PROP-YYYY-####`
- `logo_white_url`: Path to auto-generated white version of logo

**Business Rules:**
- Logo must be PNG format, exactly 800×300px
- System auto-generates an inverted/white version of the logo for dark-background pages
- White version stored in `media/proposal_logos_white/`
- One logo per proposal; can be removed independently

### 8.2 Print Proposal

**URL:** `/proposals/<id>/print/`

**Output:** Branded multi-page proposal including:
- Cover page with logo and client details
- Course outline section
- Trainer profile (if linked)
- Pricing and schedule
- Company branding (logo + white logo)

---

## 9. Lead Management (CRM)

### 9.1 Create Lead

**URL:** `/lead/create/`

**Input Fields:**
| Field | Type | Required |
|-------|------|----------|
| Full Name | Text | Yes |
| Email | Email | Yes — UNIQUE |
| Phone | Text | No — includes country code |
| Interested Course | Select | No |
| Source | Select | Yes — Website/Referral/Event/Other |
| Status | Select | Yes — Interested Highly/Qualified/Register Soon/Other |
| Notes | Textarea | No |
| Follow-up Date | Date | No |
| Follow-up Status | Select | No |
| Quote Amount | Decimal | No |

**Business Rules:**
- Email must be unique — duplicate email raises validation error
- Country code selector included (all 200+ countries)
- Phone format: `+{country_code} {number}`
- Lead assigned to logged-in user (`user_id`)

### 9.2 Lead Dashboard

**URL:** `/lead/`

**Features:**
- List of all leads with status indicators
- Filter by: status, source, date range, course
- KPI cards: Total Leads, Qualified, Register Soon, Converted
- Link to follow-up history and comments

### 9.3 Follow-Up Management

**URL:** `/lead/follow-up/<lead_id>/`

**Input Fields:**
| Field | Type | Required |
|-------|------|----------|
| Contact Date | Date | Yes |
| Contact Time | Time | Yes |
| Priority | Select | No — Low/Medium/High/Urgent |
| Status | Select | Yes — Pending/Completed/Cancelled/Rescheduled |
| Notes | Textarea | Yes |

**Business Rules:**
- Multiple follow-ups per lead
- Sorted by date/time

### 9.4 Comments

**URL:** `/leads/<lead_id>/add_comment/`

**Input:** Text comment

**Features:**
- Multiple comments per lead
- Timestamps
- Flag/unflag comments for attention (`is_flagged`)
- AJAX loading without page refresh

### 9.5 Meeting Scheduling

**URL:** `/create_meeting/`

**Input Fields:**
| Field | Type | Required |
|-------|------|----------|
| Lead | Select | Yes |
| Contact Date | Date | Yes |
| Contact Time | Time | Yes |
| Notes | Textarea | No |

### 9.6 Quote Update

**URL:** `/leads/<lead_id>/update_quote/`

**Function:** AJAX endpoint to update quoted amount on lead

**Business Rules:**
- Quote amount stored on Lead record
- Updated via inline form on dashboard

### 9.7 Dashboard Statistics (AJAX)

**URL:** `/lead/dashboard-stats/`

**Returns JSON:**
```json
{
    "total_leads": 18,
    "interested_highly": 5,
    "qualified": 8,
    "register_soon": 3,
    "other": 2
}
```

---

## 10. Trainer & Company Profile Management

### 10.1 Trainer Profile

**URL:** `/trainer-profile/create/`

**Input:**
- Name (Text, UNIQUE)
- Profile PDF (FileField)

**Storage:** `media/trainer_profiles/`

**Business Rules:**
- Trainer name must be unique
- PDF is the trainer's CV/bio for proposal attachment
- Can be assigned to multiple proposals

### 10.2 Company Profile

**URL:** `/company-profile/create/`

**Input:**
- Name (Text)
- Company PDF (FileField)

**Storage:** `media/company_profiles/`

**Business Rules:**
- When company profile is deleted, the PDF file is also deleted from disk (via `os.remove()`)

---

## 11. Coupon Management

### 11.1 Create Coupon

**URL:** `/coupons/create/`

**Input:**
| Field | Type | Required |
|-------|------|----------|
| Code | Text | Yes — UNIQUE |
| Discount Percentage | Decimal | Yes — 0.00–100.00 |
| Is Active | Checkbox | Yes |

**Business Rules:**
- Code must be unique
- Created by logged-in user (tracked)
- Only active coupons can be applied

### 11.2 Validate Coupon (AJAX)

**URL:** `/validate-coupon/`  
**Method:** POST

**Input:** `{ "code": "SAVE10" }`

**Returns:**
```json
{
    "valid": true,
    "discount_percentage": "10.00",
    "message": "Coupon applied: 10% discount"
}
```
or:
```json
{
    "valid": false,
    "message": "Invalid or inactive coupon"
}
```

---

## 12. Dashboard & Reporting

### 12.1 Main Invoice Dashboard

**URL:** `/dashboard/`

**Displays:**
- Tab 1: Sales Invoices list
  - Invoice #, Registration #, Client, Class Type, Amount, Paid, Status, Due Date, Payment
  - Filters: by number, name, date, status
- Tab 2: Purchase Invoices list

**KPI Cards:**
- Total Registrations (current month)
- Total Invoices (current month)
- Amount Due Today

### 12.2 Orbit Admin Dashboard

**URL:** `/` (root)

**Displays:**
- Total Registrations
- Monthly Registration breakdown
- Individual vs Corporate split
- Revenue summary
- Leads overview
- Recent activities

### 12.3 Student Dashboard

**URL:** `/student-dashboard/`

**Displays:**
- All individual student registrations
- Registration details with course list
- Invoice links
- Certificate upload status

### 12.4 Corporate Dashboard

**URL:** `/corporate_dashboard/`

**Displays:**
- All corporate registrations with company info
- Same links as student dashboard

---

## 13. Payment Link

**URL:** `/payment-link/`

**Function:** Display a payment request page for clients

**Business Rules:**
- Used for Payment Link payment method
- Shows amount due and payment instructions

---

## 14. Subscription

**URL:** `/subscription/`

**Function:** Display subscription/plan information page

---

## 15. Business Rules Summary

| Rule | Description |
|------|-------------|
| VAT Rate | 5% applied to all invoice line items |
| Currency | AED (UAE Dirhams) throughout system |
| Invoice Numbering | YY/MM/### sequential, resets monthly |
| Registration Numbering | OT/YY/MM/### (individual), OC/YY/MM/### (corporate) |
| Certificate Numbering | {COURSE_CODE}/YY/### sequential |
| Proposal Numbering | PROP-YYYY-#### sequential |
| Class Types | online, offline, batch, private — each has separate course rate |
| Logo Requirements | PNG format, exactly 800×300px for proposals |
| Lead Email | Must be unique in system |
| Course Code | Must be unique, 2-10 characters |
| Trainer Name | Must be unique |
| Certificate per Registration | OneToOne — one uploaded cert file per registration |
| Admin Actions | user creation, bulk deletes require is_staff or is_superuser |

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
