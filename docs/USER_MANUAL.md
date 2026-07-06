# User Manual
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Audience:** All Staff (Consultants, Operations, Finance, Admin, Training Coordinators)

---

## 1. Getting Started

### 1.1 Login

1. Open your browser and go to `https://orbittraining.online/` (production) or `http://localhost:8000/` (local)
2. Enter your **Username** and **Password**
3. Click **Sign In**

> Contact your administrator if you don't have an account or forgot your password.

Your login and logout are recorded in the audit log automatically.

### 1.2 Navigation

The left sidebar contains all modules. What you see depends on your role.

| Menu Item | What it Does |
|-----------|-------------|
| Dashboard | Overview of registrations, revenue, and target progress |
| Registrations | Student and corporate enrollment |
| Invoices | Create and manage sales invoices |
| Quotations | Create price quotations for clients |
| Proposals | Generate training proposals |
| Certificates | Issue and manage certificates |
| Courses | Manage course catalogue |
| Trainer Profiles | Trainer CVs and profiles |
| Company Profiles | Company/corporate client profiles |
| Schedule | Training schedule calendar |
| Expenses | Track operational expenses |
| Reports | Revenue, aging, VAT, enrollment reports |
| Notifications | In-app notification inbox |
| Audit Log | Login/action history (Admin only) |
| User Management | Manage staff accounts and roles (Admin only) |
| CRM | Jump to the leads management CRM |
| Coupons | Manage discount coupons |

### 1.3 User Roles

| Role | Access Level |
|------|-------------|
| Admin | Full access to all modules, users, audit log |
| Sales Manager | Registrations, invoices, quotations, reports, schedules |
| Accounts | Invoices, expenses, reports, payments |
| Sales Executive | Registrations, quotations, own client data |

### 1.4 Notifications Bell

The bell icon in the top-right of the sidebar shows your unread notification count. Click it to see your latest notifications. You can mark individual notifications as read, or mark all as read at once.

---

## 2. Registration Management

### 2.1 Create a New Registration

1. Click **Registrations** → **New Registration**
2. Fill in the student details:
   - **First / Last Name, Email, Phone, Nationality**
   - **Date of Birth**
   - **Course(s)** — select one or more courses
   - **Class Type** — Online, Offline, Batch, or Private
   - **Level** — Intermediate, Professional, or Advanced
   - **Consultant** — assigned sales executive
3. For corporate registrations, tick **Corporate** and fill in the company section
4. Click **Save**

The system auto-generates a **Registration Number** in format `OT/YY/###` (e.g., `OT/26/047`). The counter resets each calendar year.

### 2.2 Pre-filled Registration from CRM

When a consultant clicks "Register in ERP" from the CRM lead page, the registration form opens with the student's name, phone, email, and course pre-filled from the CRM lead record. Review and complete the remaining fields before saving.

### 2.3 Update Student Status

On any registration detail page, use the **Status** dropdown or quick-action button to update the student's progression:

| Status | Meaning |
|--------|---------|
| Pending | Application received, not yet started |
| Active | Currently enrolled and attending |
| Completed | Finished training |
| Dropped | Withdrew before completion |
| Suspended | Temporarily paused |

### 2.4 Student Dashboard (List View)

Go to **Registrations** → **All Students** to see all registrations with search and filter options.

**Available filters:**
- Student name
- Registration number
- Course
- Class type
- Consultant
- Date range

### 2.5 Corporate Registrations

Go to **Registrations** → **Corporate** to see all corporate/company registrations. Click a registration to view the linked invoice and attendee details.

---

## 3. Invoice Management

### 3.1 Create a New Invoice

1. Click **Invoices** → **Create Invoice**
2. Fill in the invoice header:
   - **Client** — select existing or create new
   - **Registration** — (optional) link to a student registration
   - **Date** — invoice date
   - **Due Date** — payment due date
   - **Class Type** — Online, Offline, Batch, or Private
   - **Level** — Intermediate, Professional, or Advanced (controls price lookup)
   - **Payment Method** — Card, Cash, Account Transfer, Cheque, Online Link, etc.
   - **Status** — Full Payment, Term Payment, Tabby, or Tamara
   - **Discount** — percentage discount (see caps below)
   - **PO Number** — Purchase Order number (for corporate clients)
3. Click **Save** — you are taken to the Add Items page

**Discount caps:**
- Single course: maximum **20%**
- Multiple courses on same invoice: maximum **30%**

The system prevents saving an invoice that exceeds these caps.

### 3.2 Add Invoice Items

After the invoice header is saved, add line items:

1. Select **Course** from the dropdown
2. Enter **Description**, **Quantity**, **Unit Price**
3. VAT (5%) is applied automatically — do not add VAT to the unit price
4. Add additional rows for multiple courses
5. Click **Save Items**

Invoice totals are calculated as:
```
Subtotal = Σ(unit_price × qty × persons × (1 − discount%))
VAT      = Subtotal × 5%
Total    = Subtotal + VAT
```

### 3.3 Level-Based Pricing (Auto-Lookup)

When you change **Class Type** or **Level** on the invoice form, the unit price is automatically populated from the course's price table:

| Class Type | Level | Price Field |
|-----------|-------|-------------|
| Online/Offline/Batch | Intermediate | oo_intermediate |
| Online/Offline/Batch | Professional | oo_professional |
| Online/Offline/Batch | Advanced | oo_advanced |
| Private | Intermediate | priv_intermediate |
| Private | Professional | priv_professional |
| Private | Advanced | priv_advanced |

You can still manually override the populated price.

### 3.4 Mark Invoice as Paid

From the invoice list or invoice detail page, click the **Mark as Paid** action to instantly set `amount_paid = total_amount` and status to Full Payment.

### 3.5 Record Payment Installments

For partial/installment payments:
1. Open the invoice detail page
2. Click **View Payments** or **Add Payment**
3. Fill in: Amount, Payment Method, Reference, Date, Notes
4. Click **Save Payment**

A full payment history is shown on the invoice detail page.

### 3.6 Invoice Dashboard

**Invoices** → **Dashboard** shows invoices grouped by status. Use the filters to search by:
- Invoice number
- Registration number
- Client name
- Due date
- Payment status

### 3.7 Tax Invoice (Print)

Click **Print Invoice** on any invoice to open the A4 landscape tax invoice PDF layout:
- Left column: Terms and Conditions
- Right column: Totals table + Signature block
- **Previous Payment Reference** section only appears if a prior invoice exists for the same registration

---

## 4. Quotations

### 4.1 Create a Quotation

1. **Quotations** → **Create Quotation**
2. Fill in client details, quotation date, validity period
3. Add line items: course, description, quantity, unit price
4. Apply coupon code if applicable
5. Click **Save**

A quotation number is auto-generated.

### 4.2 View / Print a Quotation

Click a quotation in the list to open the detail page. Use the **Print** button for a printable version.

### 4.3 Coupons on Quotations

If you have a valid coupon code, enter it in the **Coupon** field when creating or editing a quotation. The system validates:
- Coupon is active
- Expiry date has not passed
- Usage count has not exceeded max uses

---

## 5. Proposals

### 5.1 Create a Training Proposal

1. **Proposals** → **Create Proposal**
2. Fill in: Client Name, Course, Presenter Title, Date, Location, Trainer (optional)
3. Upload a **Logo** (PNG only) — this appears on the proposal cover page
4. Click **Save**

### 5.2 Print a Proposal

Open the proposal and click **View Proposal** to open the branded print layout. Use your browser's print function (Ctrl+P) to print or save as PDF.

### 5.3 Remove a Logo

On the proposal detail page, click **Remove Logo** to delete the uploaded logo from the proposal.

---

## 6. Certificates

### 6.1 Issue a Certificate

1. **Certificates** → **Create Certificate**
2. Fill in: Student Name, Registration Number, Course, Issue Date
3. Click **Save**

### 6.2 Upload a Certificate File

For courses with external certificate files:
1. Go to the registration detail page
2. Click **Upload Certificate**
3. Select the certificate PDF/image file
4. Click **Upload**

### 6.3 KHDA Certificates

For KHDA-regulated courses:
1. **Certificates** → **KHDA Certificate Upload**
2. Fill in KHDA details and upload the file
3. Click **Save**

### 6.4 Print a Certificate

Open a certificate and click **Print Certificate** to open the print layout.

---

## 7. Course Management

### 7.1 View Courses

**Courses** → **All Courses** shows the course catalogue with prices. A dash (`—`) is displayed instead of 0 for any price field that has not been set.

### 7.2 Create / Edit a Course

Courses have the following pricing fields:

| Field | Description |
|-------|-------------|
| Rate | Legacy flat rate |
| Batch Rate | Legacy batch rate |
| Online Rate | Legacy online rate |
| Private Rate | Legacy private rate |
| OO Intermediate | Online/Offline — Intermediate level price |
| OO Professional | Online/Offline — Professional level price |
| OO Advanced | Online/Offline — Advanced level price |
| Priv Intermediate | Private — Intermediate level price |
| Priv Professional | Private — Professional level price |
| Priv Advanced | Private — Advanced level price |

Fill in the level-based prices for new courses. Legacy fields can be left blank for new entries.

### 7.3 Upload Course Materials

On a course detail page, click **Add Content** to upload study materials or documents for that course.

---

## 8. Training Schedule

### 8.1 View Schedule

**Schedule** → **All Schedules** shows a list of all training sessions.

### 8.2 Create a Schedule Entry

1. **Schedule** → **Create Schedule**
2. Fill in: Registration, Course, Trainer, Location, Start Date, End Date, Notes
3. Set Status: Scheduled, In Progress, Completed, Cancelled
4. Click **Save**

### 8.3 Edit / Cancel a Schedule

Open a schedule entry and click **Edit** to update details. Change Status to **Cancelled** if the session is cancelled.

---

## 9. Expenses

### 9.1 Record an Expense

1. **Expenses** → **New Expense**
2. Fill in:
   - **Date** — expense date
   - **Category** — Rent, Salaries, Marketing, Software, Travel, Utilities, or Other
   - **Vendor** — supplier/payee name
   - **Description** — what the expense was for
   - **Amount** — AED amount (excluding VAT)
   - **VAT Amount** — VAT component (if applicable)
   - **Reference** — receipt or invoice number
3. Click **Save**

### 9.2 View Expense Report

**Expenses** → **Report** shows a summary broken down by category and date range. The VAT report at **Reports** → **VAT** compares:
- **Output VAT** — VAT collected from your invoices
- **Input VAT** — VAT paid on your expenses
- **Net VAT payable** = Output VAT − Input VAT

---

## 10. Reports

### 10.1 Revenue Report

**Reports** → **Revenue**

Filters: Date range, Consultant, Class Type

Shows: Total invoiced, total paid, outstanding balance per period.

**Export:** Click **Export CSV** to download.

### 10.2 Receivables Aging Report

**Reports** → **Aging**

Shows overdue invoices grouped by:
- 0–15 days overdue
- 16–30 days
- 31–60 days
- 61–90 days
- 90+ days

### 10.3 VAT Report

**Reports** → **VAT**

Shows output VAT from sales invoices vs input VAT from expenses for a selected period. Use this for UAE VAT return filing.

### 10.4 Enrollment Report

**Reports** → **Enrollment**

Shows number of registrations by period, consultant, course, and class type.

### 10.5 Certificate Report

**Reports** → **Certificates**

Shows certificates issued by period, type, and course.

---

## 11. Fee Reminders

**Fee Reminders** → Dashboard shows invoices that are overdue or coming due soon.

For each overdue invoice, you can view the student's contact information and the amount outstanding. Use this dashboard to manually follow up with clients.

---

## 12. CRM — Leads Management

### 12.1 Jump to CRM

Click **CRM** in the sidebar. You will be automatically logged into the CRM with your ERP credentials (single sign-on — no separate password needed).

### 12.2 Register a CRM Lead in ERP

From the CRM lead detail page, click **Register in ERP**. You will be redirected back to the ERP registration form with the lead's name, phone, email, and course pre-filled.

---

## 13. Notifications

### 13.1 View Notifications

Click the bell icon in the sidebar to see your unread notifications. The number badge shows how many unread notifications you have.

### 13.2 Mark as Read

- Click an individual notification to mark it as read and follow its link
- Click **Mark all as read** to clear the badge

Notifications are generated for events such as invoice due dates, registration updates, and system alerts.

---

## 14. User Management (Admin Only)

### 14.1 Create a New User

1. **User Management** → **Create User** (or `/signup/`)
2. Fill in: Username, First Name, Last Name, Email, Password
3. Assign **Role**: Admin, Sales Manager, Accounts, or Sales Executive
4. Click **Save**

The new user can log in immediately.

### 14.2 Edit a User / Change Password

1. **User Management** → **All Users**
2. Click the user's name
3. Click **Edit** to update details, or **Change Password** to reset their password

### 14.3 Assign Sales Targets

1. **User Management** → **Set Targets**
2. Select the user and month
3. Enter the target revenue amount (AED)
4. Click **Save**

Targets are tracked against actual invoiced revenue on the dashboard.

### 14.4 Sync Users to CRM

When a user's role is set to Sales Manager or Sales Executive, they are automatically synced to the CRM so they can log in there.

To manually sync all sales users at once:
- **User Management** → **Sync to CRM**

---

## 15. Company Portal

### 15.1 Generate a Company Portal Link

1. **Admin Portal** → **Generate New Link**
2. Enter the company name and details
3. Click **Generate** — a unique URL is created

Share the URL with the corporate client.

### 15.2 Company Submits Registration

The company accesses the portal URL, fills in their details (company name, trade licence, VAT certificate upload), and adds their attendees. The submission is recorded and visible in the admin portal.

### 15.3 Review and Approve

1. **Admin Portal** → click the pending submission
2. Review company details and uploaded documents
3. Click **Approve** — the request is marked as approved and a registration can be created

---

## 16. Student Form Links

### 16.1 Generate a Student Form Link

1. **Registrations** → **Student Form Links** (or `/portal/student-links/`)
2. Click **Generate New Link**
3. Select the course to pre-fill

A token URL is generated. Share with the prospective student.

### 16.2 Student Submits the Form

The student opens the link in their browser, fills in their personal details, and submits. No pricing information is visible to the student. The submission creates a draft registration in the system.

---

## 17. Audit Log (Admin Only)

**Audit Log** in the sidebar shows a chronological log of system activity.

**Filter by:**
- User
- Action (login / logout / create / update / delete)
- Model
- Date range
- IP address

Use this to investigate unusual activity or verify when specific actions occurred.

---

## 18. Profile Management

### 18.1 Trainer Profiles

**Trainer Profiles** → **Create Profile** — upload a trainer's PDF profile (name is used for the file). Profiles are listed at **Trainer Profiles** → **All Profiles**.

### 18.2 Company Profiles

**Company Profiles** → **Create Profile** — upload a company/client PDF profile. Used for corporate proposals and documentation.

---

## 19. Common Actions Quick Reference

| Action | Where |
|--------|-------|
| Create new invoice | Invoices → Create Invoice |
| Record a payment | Invoice detail → Add Payment |
| Mark invoice as paid | Invoice list → Mark Paid action |
| Create registration | Registrations → New Registration |
| Update student status | Registration detail → Status button |
| Print certificate | Certificates → Open certificate → Print |
| Print tax invoice | Invoice detail → Print Invoice |
| Export revenue report | Reports → Revenue → Export CSV |
| Generate company portal link | Admin Portal → Generate New Link |
| Generate student form link | Registrations → Student Form Links → Generate |
| Jump to CRM | Sidebar → CRM |

---

## 20. Frequently Asked Questions

**Q: The price field on the invoice is blank — how do I fix it?**
A: The price auto-populates when you select a course, class type, and level. If it is blank, the course may not have a price set for that combination. Ask your admin to update the course pricing.

**Q: I get a "Discount exceeds maximum" error.**
A: Discounts are capped at 20% for single-course invoices and 30% for multi-course invoices. Enter a value within the allowed range.

**Q: The registration number is OT/26/047 — what does that mean?**
A: OT = Orbit Training, 26 = year 2026, 047 = the 47th registration of that year. The counter resets each January.

**Q: How do I add VAT to an invoice?**
A: VAT is calculated automatically (5%). Simply enter the pre-VAT unit price — do not add VAT yourself. The invoice total shown to the client already includes VAT.

**Q: Can I delete an invoice?**
A: Only Admin role users can delete invoices. Contact your admin if you need to remove an invoice.

**Q: I clicked "CRM" but it says access denied.**
A: Your account must be synced to the CRM. Ask your admin to run the CRM sync or check your role assignment.

**Q: How do I find an old registration?**
A: Use the search bar at the top of the student dashboard, or use **Search** (`/search/`) for a global search across registrations, invoices, and certificates.

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
