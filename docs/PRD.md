# Product Requirements Document (PRD)
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Product:** Orbit ERP Institute Management System
**Organization:** Orbit Training Point
**Status:** Production (Live System — orbittraining.online)

---

## 1. Executive Summary

Orbit ERP is a web-based Enterprise Resource Planning system built for Orbit Training Point, a professional training institute operating in the UAE. The system manages the full lifecycle of training operations — from lead capture and student registration to course delivery, invoicing, certificate issuance, and business reporting.

Two applications work together as a unified platform:
- **Django ERP** (`orbit-system/`) — core back-office operations, invoicing, registration, certificates, reporting
- **Flask CRM** (`leads-management/`) — lead pipeline management, follow-ups, meetings, and sales analytics

Both apps share user accounts via a HMAC-signed SSO bridge, enabling one-click navigation between them.

---

## 2. Product Vision

**Vision Statement:** Provide a single, unified platform that enables training institute staff to manage every aspect of student and business operations — from first contact to certification — without switching between disconnected systems.

**Business Goals:**
- Reduce administrative overhead through automation of numbering, invoicing, and document generation
- Eliminate manual invoice numbering and registration tracking errors
- Enable real-time visibility into revenue, registrations, lead pipeline, and expenses
- Produce professional client-facing documents (tax invoices, quotations, certificates, proposals) on demand
- Track 100% of student journeys from lead to certified graduate

---

## 3. Stakeholders & Users

| Role | Description | Primary Modules |
|------|-------------|-----------------|
| **Admin** | Full system access, user management, targets, audit log | Dashboard, All Modules |
| **Sales Manager** | Lead management, quotations, proposals, team oversight | Leads (CRM), Quotations, Reports |
| **Accounts** | Invoice tracking, payment management, financial reports | Invoices, Reports, Expenses |
| **Sales Executive** | Lead management, registrations, quotations | Leads (CRM), Registrations, Quotations |
| **Training Coordinator** | Course management, certificates, scheduling | Courses, Certificates, Schedule |

Users are assigned a role (`admin`, `sales_manager`, `accounts`, `sales_executive`) via the UserProfile model. Access to sensitive views is controlled by role.

---

## 4. Core Functional Requirements

### 4.1 Invoice Management

**Priority:** Critical | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| INV-01 | Create tax invoices linked to student registrations or standalone clients |
| INV-02 | Auto-generate invoice numbers in YY/MM/### sequential format |
| INV-03 | Support payment methods: Card, Cash, Account Transfer, Payment Link, Cheque |
| INV-04 | Track payment status: Full Payment, Term Payment, Tabby, Tamara |
| INV-05 | Apply discount at invoice level; enforce cap (20% single course, 30% multi-course) |
| INV-06 | Calculate 5% VAT automatically on all line items (added on top of base price) |
| INV-07 | Support multiple invoice line items (courses) per invoice |
| INV-08 | Track due dates; flag overdue invoices in the dashboard |
| INV-09 | Support PO number tracking for corporate clients |
| INV-10 | Create and manage purchase invoices separately from sales invoices |
| INV-11 | Filter and search invoices by number, registration, name, due date, status |
| INV-12 | Print tax invoice as A4 landscape; Terms column left, Totals+Signatures right |
| INV-13 | Record individual payment installments (InvoicePayment model) |
| INV-14 | Show Previous Payment Reference section only when a prior invoice exists |
| INV-15 | Quick-pay action (Mark as Paid) from invoice list |
| INV-16 | Bulk invoice actions (bulk status update) |
| INV-17 | Level-based pricing: Intermediate, Professional, Advanced for Online/Offline and Private |

### 4.2 Student Registration

**Priority:** Critical | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| REG-01 | Register individual students with full personal details |
| REG-02 | Register corporate clients (company-linked groups) |
| REG-03 | Auto-generate registration numbers: OT/YY/### (individual) or OC/YY/### (corporate) |
| REG-04 | Support multiple class types: Online, Offline, Batch, Private |
| REG-05 | Enroll students in multiple courses per registration |
| REG-06 | Apply per-course discounts at registration time |
| REG-07 | Capture: passport, Emirates ID, UID, nationality, education details |
| REG-08 | Generate printable registration forms |
| REG-09 | Link registration to invoice for payment tracking |
| REG-10 | Student status tracking: Active, Completed, Dropped, Suspended, Pending |
| REG-11 | Level selection (Intermediate / Professional / Advanced) drives pricing |
| REG-12 | Pre-fill registration from CRM lead via SSO link |
| REG-13 | Token-based self-registration links for students (StudentFormLink) |
| REG-14 | Company portal registration (CompanyPortalRequest) for corporate self-service |

### 4.3 Course Management

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| CRS-01 | Create and manage training courses with unique short codes (2-10 chars) |
| CRS-02 | Set pricing for Online/Offline × 3 levels and Private × 3 levels (6 price fields) |
| CRS-03 | Legacy flat-rate fields retained for backward compatibility |
| CRS-04 | Course list shows dash (—) for unset level prices (not zero) |
| CRS-05 | Upload course content/materials |
| CRS-06 | View all enrolled students per course |

### 4.4 Certificate Management

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| CERT-01 | Issue certificates linked to student registrations |
| CERT-02 | Auto-generate certificate numbers using course code prefix |
| CERT-03 | Support regular and KHDA certificates |
| CERT-04 | Record course dates and grade |
| CERT-05 | Print professional certificate layouts |
| CERT-06 | Upload pre-issued certificates (PDF) against registrations |
| CERT-07 | Upload registration forms as supporting documents |

### 4.5 Quotation Management

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| QUO-01 | Create professional training quotations for clients |
| QUO-02 | Auto-generate quotation numbers in YY/MM/### format |
| QUO-03 | Specify training venue: Orbit Training (In-House), Company Premises (External), Online |
| QUO-04 | Add multiple courses with duration and number of persons per quotation |
| QUO-05 | Include consultant contact details in quotation |
| QUO-06 | Apply discount to full quotation |
| QUO-07 | Support admin price overrides per quotation item (QuotationItemOverride) |
| QUO-08 | Link coupon to quotation |

### 4.6 Proposal Management

**Priority:** Medium | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| PROP-01 | Create training proposals with PROP-YYYY-#### numbering |
| PROP-02 | Link proposals to specific courses and trainers |
| PROP-03 | Upload custom company logo (PNG) |
| PROP-04 | Auto-generate white/inverted version of logo for dark backgrounds |
| PROP-05 | Print professional proposal layout with branding |

### 4.7 CRM / Lead Management (Flask App)

**Priority:** High | **Status:** Implemented (separate Flask application)

| ID | Requirement |
|----|-------------|
| CRM-01 | Capture leads with contact info and interested course |
| CRM-02 | Track lead sources: Website, Referral, Event, Other |
| CRM-03 | Manage lead status pipeline |
| CRM-04 | Schedule and track follow-up tasks with priority levels |
| CRM-05 | Add internal comments/notes on leads |
| CRM-06 | Flag/unflag comments for attention |
| CRM-07 | Schedule meetings linked to leads |
| CRM-08 | Track quoted amounts per lead |
| CRM-09 | One-click "Register in ERP" button that pre-fills the Django registration form via SSO |
| CRM-10 | SSO bridge: staff log in once; both apps share the session via HMAC token |

### 4.8 Trainer & Company Profiles

**Priority:** Medium | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| PRF-01 | Create trainer profiles with PDF CVs |
| PRF-02 | Assign trainers to proposals |
| PRF-03 | Create company profiles with PDF documents |

### 4.9 Coupon Management

**Priority:** Low | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| CPN-01 | Create discount coupon codes |
| CPN-02 | Set percentage discount per coupon |
| CPN-03 | Activate/deactivate coupons |
| CPN-04 | Set expiry date and max usage count per coupon |
| CPN-05 | Validate coupon codes via AJAX at checkout |

### 4.10 Reporting & Business Intelligence

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| RPT-01 | Main dashboard showing total registrations and invoices |
| RPT-02 | Revenue report with date filter and CSV export |
| RPT-03 | Receivables aging report (0-15, 16-30, 31-60, 61-90, 90+ days) |
| RPT-04 | VAT report (tax collected by period) |
| RPT-05 | Enrollment report (registrations by period/consultant/course) |
| RPT-06 | Certificate report (issued by period/type/course) |
| RPT-07 | Expense report (by category, vendor, date range) |
| RPT-08 | Fee reminder dashboard (overdue and upcoming invoices) |

### 4.11 Notifications

**Priority:** Medium | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| NOTIF-01 | In-app notification center (bell icon, unread count) |
| NOTIF-02 | Notification types: Invoice Due, Overdue Invoice, Certificate Ready, New Registration, Target Alert, System |
| NOTIF-03 | Mark individual or all notifications as read |

### 4.12 Training Schedule

**Priority:** Medium | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| SCH-01 | Create training schedules with start/end date, time, venue, capacity |
| SCH-02 | Assign instructor, class type, and status (Upcoming/Ongoing/Completed/Cancelled) |
| SCH-03 | Link schedules to courses |

### 4.13 Expense Tracking

**Priority:** Medium | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| EXP-01 | Record business expenses by category: Venue, Materials, Instructor Fee, Marketing, etc. |
| EXP-02 | Track VAT on expenses separately |
| EXP-03 | Link expenses to courses |
| EXP-04 | Expense report with category and date filters |

### 4.14 Audit Log

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| AUD-01 | Log all user logins and logouts with IP address and timestamp |
| AUD-02 | Audit log view (admin-only) with filters |
| AUD-03 | Record action, model, object, changes, and IP for every audit event |

### 4.15 User Management

**Priority:** High | **Status:** Implemented

| ID | Requirement |
|----|-------------|
| USR-01 | Role-based access: admin, sales_manager, accounts, sales_executive |
| USR-02 | Admin can create, edit, delete users and change passwords |
| USR-03 | Sales roles automatically synced to Flask CRM |
| USR-04 | Monthly sales targets per user (amount + registration count) |
| USR-05 | CRM-SSO sync: all existing CRM users batch-synced to ERP |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Authentication** | All pages require login; role-based access for admin operations |
| **Availability** | 99% uptime during business hours (UAE timezone, UTC+4) |
| **Performance** | Page load < 3 seconds for standard list views |
| **File Storage** | PDF, PNG upload; stored in organized media directory |
| **PDF Generation** | Professional print-quality output via browser print |
| **Responsive Design** | Bootstrap 5 layout; functional on modern mobile browsers |
| **Browser Support** | Chrome, Firefox, Edge (modern versions) |
| **Currency** | AED (UAE Dirham) throughout |
| **VAT** | 5% UAE VAT added on top of price (never back-calculated) |
| **Discount Caps** | 20% max for single-course invoices; 30% max for multi-course invoices |
| **Domain** | https://orbittraining.online (Apache proxy → Gunicorn) |

---

## 6. System Integration

### 6.1 CRM-ERP SSO Bridge

```
ERP User clicks "Open CRM"
  → /crm-jump/ generates HMAC token (90-second TTL)
  → Redirect to CRM /auto-login?t=<token>
  → CRM verifies token → logs user into CRM

CRM User clicks "Register in ERP"
  → CRM generates HMAC token
  → Redirect to ERP /crm-auth/?t=<token>&crm_id=<id>&fn=<first>&ln=<last>...
  → ERP verifies token → logs user in → pre-fills /register/ form
```

### 6.2 CRM Internal API

ERP registration form calls CRM to fetch lead data for auto-fill:

```
GET /api/internal/lead/<id>
Authorization: Bearer <CRM_SSO_SECRET>
Returns: { id, full_name, status, phone, email, interested_course }
```

---

## 7. User Flows

### 7.1 Student Enrollment Flow
```
CRM Lead → Follow-up → Qualified → Click "Register in ERP" (SSO) →
Registration Form (pre-filled) → Course Selection + Level Pricing →
Invoice Generated → Tax Invoice Printed → Payment Recorded →
Certificate Issued → Record Complete
```

### 7.2 Corporate Client Flow
```
Quotation Request → Proposal Sent → PO Received →
Corporate Registration → Invoice → Training Delivered →
KHDA Certificates → Account Settled
```

### 7.3 Invoice Payment Flow
```
Invoice Created → Sent to Client → Payment Installments Recorded →
(InvoicePayment records) → Status Updated → Certificate Released
```

---

## 8. Out of Scope (Current Version)

- Student self-service portal (logged in)
- Automated email notifications
- SMS reminders
- Live payment gateway integration (Tabby/Tamara API)
- Student assessment/exam module
- HR and payroll management
- Inventory management
- Multi-branch support
- Public-facing course catalog website

---

## 9. Future Roadmap

| Priority | Feature |
|----------|---------|
| High | Automated invoice email delivery |
| High | Payment gateway integration (Tabby, Tamara, Stripe) |
| Medium | Student self-service portal |
| Medium | Assessment/grading module |
| Medium | WhatsApp notification integration |
| Low | Mobile app |
| Low | Multi-language support (Arabic) |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*
