# User Manual
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Audience:** Staff (Consultants, Operations, Finance, Training Coordinator)

---

## 1. Getting Started

### 1.1 Login

1. Open your browser and go to `http://10.255.254.23:8000/` (or your server address)
2. Enter your **Username** and **Password**
3. Click **Sign In**

> Contact your administrator if you don't have an account or forgot your password.

### 1.2 Navigation

The left sidebar contains all main modules:

| Menu Item | What it Does |
|-----------|-------------|
| Dashboard | Overview of invoices and business stats |
| Registrations | Student and corporate enrollment |
| Invoices | Create and manage invoices |
| Quotations | Create price quotations for clients |
| Proposals | Generate training proposals |
| Certificates | Issue and manage certificates |
| Courses | Manage course catalog |
| CRM / Leads | Track leads and follow-ups |
| Trainers | Manage trainer profiles |
| Company | Manage company profiles |
| Coupons | Create discount coupons |

---

## 2. Invoice Management

### 2.1 Create a New Invoice

1. Click **Invoices** → **Create Invoice**
2. Fill in the form:
   - **Client** — Select existing client or create new
   - **Registration** — (Optional) Link to a student registration
   - **Date** — Invoice date (today by default)
   - **Due Date** — When payment is expected
   - **Class Type** — Online, Offline, Batch, or Private
   - **Payment Method** — Card, Cash, Account Transfer, etc.
   - **Status** — Full Payment, Term Payment, Tabby, or Tamara
   - **Discount** — Percentage discount (optional)
   - **PO Number** — Purchase Order number (for corporate clients)
3. Click **Save** — You will be taken to the Add Items page

### 2.2 Add Invoice Items

After creating the invoice header, add line items:
1. Select **Course** from dropdown
2. Enter **Quantity** (number of people)
3. **Unit Price** auto-fills from course rate; adjust if needed
4. **VAT Rate** defaults to 5% (UAE)
5. Click **Add Item** to add another course
6. Click **Save Items** when done

**The total amount is calculated automatically: Qty × Price + 5% VAT**

### 2.3 Edit an Invoice

1. From the Dashboard, find your invoice
2. Click the **Edit** (pencil) icon
3. Modify fields and click **Save**

### 2.4 Delete an Invoice

> Admin access required

1. Click the **Delete** icon next to the invoice
2. Confirm deletion on the confirmation page

### 2.5 Filter Invoices

On the Invoice Dashboard, use the search bar to filter by:
- Invoice Number
- Registration Number
- Client Name
- Due Date
- Payment Status

---

## 3. Student Registration

### 3.1 Register an Individual Student

1. Click **Registrations** → **New Registration**
2. Select **Registration Type**: Individual (OT)
3. Select **Class Type**: Online, Offline, Batch, or Private
4. Fill in student details:
   - Personal: Name, Date of Birth, Nationality
   - ID Documents: Passport No, UID No, Emirates ID
   - Education: Education level, Company/University
   - Contact: Phone, Alternative Phone, Email
   - Location: Country, Emirates, Address
   - Consultant: Your name
5. **Select Courses**:
   - Search and select course(s)
   - Price auto-fills based on class type
   - Add discount percentage if applicable
6. Click **Register**

**Registration number is auto-generated: OT/YY/MM/###**

### 3.2 Register a Corporate Client

1. Click **Registrations** → **Corporate Registration**
2. Fill in student details (same as individual)
3. Fill in company details:
   - Company Name, Address, Location
   - Company Phone and Email
4. Select courses and prices
5. Click **Register**

**Registration number uses OC prefix: OC/YY/MM/###**

### 3.3 View All Registrations

- **Individual students**: Click **Student Dashboard**
- **Corporate clients**: Click **Corporate Dashboard**

### 3.4 Print Registration Form

1. Find the registration in the dashboard
2. Click **Print** icon
3. Use browser Print (Ctrl+P) to print or save as PDF

### 3.5 Upload Certificate / Form

After a student completes their course:
1. Find registration in Student Dashboard
2. Click **Upload Certificate**
3. Select the certificate PDF/image file
4. Click **Upload**

---

## 4. Course Management

### 4.1 Add a New Course

1. Click **Courses** → **Add Course**
2. Enter:
   - **Name**: Full course name
   - **Code**: Short unique code (2-10 chars, e.g., "PM", "ITIL")
   - **Standard Rate**: Default offline price
   - **Batch Rate**: Group rate
   - **Online Rate**: Online delivery price
   - **Private Rate**: 1-on-1 private rate
3. Click **Save**

### 4.2 Add Course Materials

1. Go to **Courses** → select course → **Add Content**
2. Enter material title
3. Upload file (any format)
4. Click **Upload**

---

## 5. Certificate Management

### 5.1 Issue a Certificate

1. Click **Certificates** → **Create Certificate**
2. Enter:
   - **Register Number**: Student's registration number (e.g., OT/24/06/001)
   - **Student Name**: Full name
   - **Course Name**: Course completed
   - **From Date / End Date**: Training period
   - **Grade**: A+, A, B+, B, C+, C, or D
   - **Certificate Type**: Regular or KHDA
3. Click **Create** — Certificate number auto-generated

### 5.2 Print a Certificate

1. Find certificate in the Certificate Dashboard
2. Click **Print**
3. Use browser Print (Ctrl+P)

### 5.3 KHDA Certificate

For KHDA-accredited certificates:
1. Click **Certificates** → **KHDA Certificate**
2. Enter registration number
3. Upload the KHDA-issued PDF
4. Click **Submit**

---

## 6. Quotations

### 6.1 Create a Quotation

1. Click **Quotations** → **Create Quotation**
2. Enter:
   - **Client Name**: Company or individual name
   - **Schedule**: Proposed training dates/times
   - **Training Venue**: In-House, External, or Online
   - **Discount**: Overall discount percentage
   - **Consultant Details**: Your name, position, phone, email
3. Add courses:
   - Select course
   - Enter duration (hours/days)
   - Enter number of persons
   - Click **Add Another** for multiple courses
4. Click **Save**

**Quotation number auto-generated: YY/MM/###**

### 6.2 Print / Share Quotation

1. Find quotation in Quotation Dashboard
2. Click **View** to open the print-ready format
3. Use browser Print to generate PDF

---

## 7. Proposals

### 7.1 Create a Training Proposal

1. Click **Proposals** → **Create Proposal**
2. Enter:
   - **Client Name**
   - **Course**: Select from catalog
   - **Presenter Title**: Your title (e.g., "Training Manager")
   - **Date**: Proposal date
   - **Location**: Training location
   - **Trainer**: Select trainer (optional)
   - **Logo**: Upload company logo (PNG, exactly 800×300 pixels)
3. Click **Save**

> Logo must be PNG format at exactly 800×300 pixels. The system automatically creates a white version for dark backgrounds.

### 7.2 Print Proposal

1. Find proposal in Proposals list
2. Click **Print** to view the branded proposal
3. Use browser Print to save/share

---

## 8. Lead Management (CRM)

### 8.1 Add a New Lead

1. Click **CRM** → **Create Lead**
2. Enter:
   - **Full Name**
   - **Email**: Must be unique in the system
   - **Phone**: Select country code + enter number
   - **Interested Course**: Select from catalog
   - **Source**: Website, Referral, Event, or Other
   - **Status**: Interested Highly, Qualified, Register Soon, or Other
   - **Notes**: Any additional information
   - **Follow-up Date**: When to contact next
3. Click **Save**

### 8.2 Manage Follow-Ups

1. Find lead in CRM Dashboard
2. Click **Follow-Up**
3. Enter:
   - Date and Time to contact
   - Priority: Low, Medium, High, or Urgent
   - Status: Pending, Completed, Cancelled, Rescheduled
   - Notes about the follow-up
4. Click **Save**

### 8.3 Add Comments to a Lead

1. Find lead in CRM Dashboard
2. Click on the lead to expand
3. Type comment in the comment box
4. Click **Add Comment**
5. Flag important comments with the flag icon

### 8.4 Update Quote Amount

1. In the lead detail view
2. Enter the quoted training price
3. Click **Update Quote**

### 8.5 Schedule a Meeting

1. Click **CRM** → **Create Meeting**
2. Select the lead
3. Enter date, time, and notes
4. Click **Save**

---

## 9. Trainer Profiles

### 9.1 Add a Trainer

1. Click **Trainers** → **Add Trainer**
2. Enter trainer name (must be unique)
3. Upload trainer CV/profile as PDF
4. Click **Save**

Trainer profiles can be linked to proposals.

---

## 10. Coupons

### 10.1 Create a Coupon Code

1. Click **Coupons** → **Create Coupon**
2. Enter:
   - **Code**: Unique coupon code (e.g., "SAVE20")
   - **Discount %**: Percentage discount (e.g., 20)
   - **Active**: Check to make it available
3. Click **Save**

### 10.2 Apply a Coupon

Coupons can be validated via the `/validate-coupon/` endpoint during the registration/invoice process.

---

## 11. User Management (Admin Only)

### 11.1 Create a New User

1. Click **Signup** (visible to admins only)
2. Enter username, password, and name
3. Click **Create**

> Only administrators can create new user accounts.

---

## 12. Tips & Best Practices

| Tip | Details |
|-----|---------|
| Invoice numbering | Never manually edit invoice numbers — they are auto-generated |
| Course codes | Keep course codes short (2-3 chars) and meaningful |
| Registration first | Create student registration before creating their invoice |
| VAT | Always 5% — don't change unless tax rate changes |
| Logo size | Proposals require exactly 800×300px PNG logos |
| Lead emails | Each lead must have a unique email address |
| Print | Use Ctrl+P or browser print for all documents |
| Corporate | Use Corporate Registration for company-sponsored students |

---

## 13. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+P | Print current page |
| Ctrl+F | Search on current page |
| Browser Back | Return to previous page |

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
