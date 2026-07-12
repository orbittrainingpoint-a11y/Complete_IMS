# User Manual
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
**Audience:** All Staff (Consultants, Operations, Finance, Admin)

---

## 1. Getting Started

### 1.1 Login

1. Go to `https://orbittraining.online/` (or `http://localhost:8000/` on local)
2. Enter your **Username** and **Password**
3. Click **Sign In**

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
| Certificates | Issue and manage certificates; view certificate requests |
| Cert. Requests | Review client-submitted certificate completion forms |
| Refunds | View and manage refund records |
| Courses | Manage course catalogue |
| Trainer Profiles | Trainer CVs and profiles |
| Company Profiles | Company/corporate client profiles |
| Schedule | Training schedule |
| Expenses | Track operational expenses |
| Reports | Revenue, aging, VAT, enrollment reports |
| Notifications | In-app notification inbox |
| Audit Log | Login/action history (Admin only) |
| User Management | Manage staff accounts and roles (Admin only) |
| Settings | Institute configuration — logo, banking, branding (Admin only) |
| CRM | Jump to the leads management CRM |
| Coupons | Manage discount coupons |

### 1.3 User Roles

| Role | Access Level |
|------|-------------|
| **Admin** | Full access — all modules, users, audit log, settings |
| **Sales Manager** | Registrations, invoices, quotations, reports, schedules; all team's data |
| **Accounts** | Invoices, expenses, reports, payments, refunds |
| **Sales Executive** | Registrations (1-hr edit window), quotations, own client data |

### 1.4 Notifications Bell

The bell icon in the top-right shows your unread notification count. Click to see notifications. Mark individual ones as read, or use "Mark all read."

---

## 2. Student Registration

### 2.1 Register a New Student

1. Go to **Registrations** → click **+ New Registration**
2. Choose registration type: **Individual (OT)** or **Corporate (OC)**
3. Select Class Type (Online / Offline / Batch / Private) and Level (Intermediate / Professional / Advanced)
4. Fill in student details: name, contact, nationality, ID documents
5. Select one or more courses — prices auto-fill based on class type and level
6. Add a discount per course if applicable
7. Enter consultant name
8. Click **Save Registration**

A registration number (e.g. `OT/26/042`) is auto-assigned.

### 2.2 Edit a Registration

- **Admin / Manager / Accounts:** Can edit at any time
- **Sales Executive:** Can only edit within **1 hour** of creating the registration. After that, the system blocks editing with a message: *"Registrations can only be edited within 1 hour of creation. Please contact your manager."*

### 2.3 View Registration Detail

Click any registration number in the Student Dashboard to open the detail page. This shows:
- Status bar: enrolment doc status, certificate status, refund status
- Invoices and certificates linked to this registration
- Certificate request history (date sent, client submission, feedback, rating)
- Action buttons: Send Certificate Request, Upload Enrolment Doc, Refund, etc.

### 2.4 Enrolment Document

- Click **Upload Enrolment Doc** on the registration detail page
- Status shows "Enrolment Doc Pending" until uploaded, then "Enrolment Doc Uploaded"

---

## 3. Invoices

### 3.1 Create a Sales Invoice

1. Go to **Invoices** → click **+ Tax Invoice**
2. Select client and optionally link to a registration
3. Choose class type, level, payment method, and status
4. Set invoice date, due date, and number of persons
5. Add invoice line items (courses)
6. Apply discount if needed (cap: 20% for one course, 30% for multiple)
7. Click **Create Invoice**

VAT (5%) is added automatically on top of the discounted price.

### 3.2 Print a Tax Invoice

From the invoice list, click the print icon. The invoice prints in A4 landscape with Terms on the left and totals/signatures on the right.

### 3.3 Record a Payment Installment

On the invoice detail, click **Add Payment**. Enter amount, method, reference, and date. Multiple installments can be recorded.

### 3.4 Purchase Invoice (Corporate)

1. Go to **Invoices** → click **+ Purchase Invoice**
2. Click **Corporate Company** tab and search for the company
3. Candidates and their courses load automatically
4. The "Total Candidates" box shows the candidate count — the Number of Persons field is hidden because it is already factored into the quantities

---

## 4. Certificates

### 4.1 Issue a Certificate

1. Go to **Certificates** → click **+ New Certificate**
2. Enter registration number (auto-fills student name)
3. Enter course name, dates, and grade
4. Click **Create** — certificate number is auto-generated
5. Print from the certificate list

### 4.2 Delete a Certificate (Admin Only)

1. On the certificates dashboard, click the **trash icon** next to the certificate
2. A confirmation modal appears — click **Delete** to confirm

### 4.3 Send a Certificate Request to a Client

Used to get the client to confirm course completion before generating their certificate.

1. Open the student's **Registration Detail** page
2. Click the green **Send Certificate Request** button
3. The system emails the client a unique link to a form
4. The client will:
   - Confirm they completed the course
   - Enter the completion date
   - Rate the class (Excellent / Good / Average / Poor)
   - Write about their class experience (required)
5. Once submitted, the status on the registration shows **"Submitted by Client"**

### 4.4 Review and Generate a Certificate

1. Go to **Cert. Requests** in the sidebar (or the Certificates menu)
2. Click **Pending Review** tab to see submitted requests
3. Review the client's completion date, class rating, and written feedback
4. Enter From Date, End Date, and Grade
5. Click **Generate Certificate**

The certificate is created automatically and linked back to the registration.

### 4.5 Reject a Certificate Request

On the Cert. Requests page, click **Reject** next to a submitted request. This sets the status to "Rejected" and allows a new request to be sent if needed.

---

## 5. Refunds

### 5.1 Initiate a Refund

1. Open the student's **Registration Detail** page
2. Click the **Refund** button (red outline, bottom of page)
3. Fill in: reason for refund, upload supporting document (optional), refund amount
4. Click **Submit Refund**

### 5.2 Confirm a Refund

1. Go to **Refunds** in the sidebar → click **Pending Confirmation** tab
2. Review the refund details
3. Click **Confirm Refund** in the confirmation modal
4. The system:
   - Marks the registration as **REFUNDED**
   - Sends a refund notification email to the client
   - Removes this registration from all revenue calculations

### 5.3 Effect on the System

- The registration shows a red **REFUNDED** banner on its detail page
- In the student dashboard, refunded rows appear faded with a REFUNDED badge
- Revenue reports, dashboards, and sales target calculations exclude refunded registrations

---

## 6. Quotations

### 6.1 Create a Quotation

1. Go to **Quotations** → **+ New Quotation**
2. Enter client name, training venue, schedule, consultant details
3. Add courses with duration and number of persons
4. Apply discount if needed
5. Print from the quotation list

> **Note:** Quotations cannot be directly converted to purchase invoices. Create the purchase invoice separately from the Invoices section.

---

## 7. Proposals

### 7.1 Create a Proposal

1. Go to **Proposals** → **+ New Proposal**
2. Enter client name, select course and trainer
3. Fill in date, location, presenter title
4. Upload client logo (PNG, max 800×300px) if available
5. Click **Save Proposal**
6. Print from the proposal list

---

## 8. Institute Settings (Admin Only)

### 8.1 Configure Company Details

1. Go to **Settings** in the sidebar
2. Fill in the **Company Info** tab: name, trade license, VAT number, address, phone, email, website
3. Click **Save**

### 8.2 Upload Branding Assets

On the **Branding & Stamps** tab, upload:
- **Company Logo** — used on invoices and emails
- **Stamp** — official stamp for certificates and documents
- **Authorization Logo** — accreditation or authorization badge
- **Signature** — authorized signatory signature image

All images are optional. Existing images remain until replaced.

### 8.3 Banking Details

On the **Banking** tab, enter bank name, account name, account number, IBAN, and SWIFT code. These appear on invoice footers.

---

## 9. Reports

### Available Reports

| Report | Where to Find | What it Shows |
|--------|--------------|---------------|
| Revenue Report | Reports → Revenue | Revenue by period/consultant; excludes refunded registrations |
| Aging Report | Reports → Aging | Overdue invoices grouped by age (0-15, 16-30, 31-60, 61-90, 90+ days) |
| VAT Report | Reports → VAT | Tax collected vs. input VAT on expenses |
| Enrollment Report | Reports → Enrollment | Registrations by period/consultant/course |
| Certificate Report | Reports → Certificates | Issued certificates by period and type |
| Expense Report | Expenses → Report | Spending by category/vendor/date |

> All revenue figures exclude registrations that have been refunded.

---

## 10. User Management (Admin Only)

### 10.1 Add a New User

1. Go to **User Management** → **+ Add New User**
2. Enter username and email
3. Set a password (and confirm it — the form shows a ✓ / ✗ indicator)
4. Select a role by clicking one of the four role cards:
   - **Sales Executive** — creates registrations and quotations; can only edit within 1 hour
   - **Sales Manager** — full sales visibility; can see all executives' data
   - **Accounts** — invoice, payment, and financial access
   - **Admin** — full system access

Sales Manager and Sales Executive accounts are **automatically created in the CRM** — no separate CRM signup needed.

### 10.2 Edit or Deactivate a User

From the User Management list, click the **edit (pen) icon** next to any user. You can change their name, email, phone, role, and active status. Deactivating a user blocks their login.

### 10.3 Change a User's Password

From the User Management list, click the **key icon** next to the user, enter a new password, and click **Save Password**.

---

## 11. CRM — Lead Management

### 11.1 Open the CRM

Click **CRM** in the sidebar. You will be automatically logged into the CRM without entering a second password (SSO).

### 11.2 Register a Lead in the ERP

From any lead's detail page in the CRM, click **Register in ERP**. This opens the ERP registration form with the lead's details pre-filled. Complete the form and save.

### 11.3 Delete a Lead

From the leads list or lead detail page, click **Delete**. The system safely removes all linked interactions, quotes, and cleans up related records before deleting.

---

## 12. Troubleshooting

| Problem | Solution |
|---------|---------|
| Can't edit a registration (Sales Executive) | Registrations can only be edited within 1 hour of creation. Ask your manager to edit it. |
| Certificate request form shows "Course Not Completed" | The client indicated they haven't completed the course. Wait until they have and send a new request. |
| Revenue numbers seem low | Check if there are refunded registrations — they are excluded from all revenue totals. |
| CRM login doesn't work | Try logging out of both the ERP and CRM, then log into the ERP first, then click CRM. |
| "Number of Persons" not showing on corporate PI | It's hidden in corporate mode by design — candidate counts are already included in the line item quantities. |

---

*Document updated: 2026-07-13*
*Version 3.0 — adds Refund workflow, Certificate Request flow, Institute Settings, edit lock behaviour, corporate PI clarification*
