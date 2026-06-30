# Product Requirements Document (PRD)
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Product:** Orbit ERP Institute Management System  
**Organization:** Orbit Training Point  
**Status:** Production (Live System)

---

## 1. Executive Summary

Orbit ERP is a comprehensive web-based Enterprise Resource Planning system built specifically for Orbit Training Point, a professional training institute operating in the UAE. The system manages the full lifecycle of training operations — from lead capture and student registration to course delivery, invoicing, certificate issuance, and business reporting.

The platform consolidates operations that were previously spread across spreadsheets and manual processes into a single, integrated web application accessible by all staff members.

---

## 2. Product Vision

**Vision Statement:** Provide a single, unified platform that enables training institute staff to manage every aspect of student and business operations — from first contact to certification — without switching between systems.

**Business Goals:**
- Reduce administrative overhead by 60% through automation
- Eliminate manual invoice numbering and registration tracking errors
- Enable real-time visibility into revenue, registrations, and lead pipeline
- Produce professional client-facing documents (proposals, quotations, certificates) on demand
- Track 100% of student journeys from lead to certified graduate

---

## 3. Stakeholders & Users

| Role | Description | Primary Modules |
|------|-------------|-----------------|
| **Admin / Director** | Full system access, user management, business reporting | Dashboard, All Modules |
| **Sales Consultant** | Lead management, quotations, proposals | Leads, Quotations, Proposals |
| **Operations Staff** | Student registration, invoice management | Registration, Invoices |
| **Training Coordinator** | Course management, certificates, scheduling | Courses, Certificates |
| **Finance Staff** | Invoice tracking, payment management | Invoices, Reports |

---

## 4. Core Functional Requirements

### 4.1 Invoice Management

**Priority:** Critical  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| INV-01 | Create sales invoices linked to student registrations or standalone clients |
| INV-02 | Auto-generate invoice numbers in YY/MM/### sequential format |
| INV-03 | Support multiple payment methods: Card, Cash, Account Transfer, Payment Link, Cheque |
| INV-04 | Track payment status: Full Payment, Term Payment, Tabby, Tamara |
| INV-05 | Apply discounts at invoice and item level |
| INV-06 | Calculate 5% VAT automatically on all line items |
| INV-07 | Support multiple invoice line items (courses) per invoice |
| INV-08 | Track due dates and flag overdue invoices |
| INV-09 | Support PO number tracking for corporate clients |
| INV-10 | Create and manage purchase invoices separately from sales invoices |
| INV-11 | Filter and search invoices by number, registration, name, due date, status |
| INV-12 | Print/export invoice as PDF |

### 4.2 Student Registration

**Priority:** Critical  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| REG-01 | Register individual students with full personal details |
| REG-02 | Register corporate clients (company-linked groups) |
| REG-03 | Auto-generate registration numbers: OT/YY/MM/### (individual) or OC/YY/MM/### (corporate) |
| REG-04 | Support multiple class types: Online, Offline, Batch, Private |
| REG-05 | Enroll students in multiple courses per registration |
| REG-06 | Apply per-course discounts at registration time |
| REG-07 | Capture: passport, Emirates ID, UID, nationality, education details |
| REG-08 | Generate printable registration forms |
| REG-09 | Link registration to invoice for payment tracking |
| REG-10 | Separate corporate dashboard from individual student dashboard |

### 4.3 Course Management

**Priority:** High  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| CRS-01 | Create and manage training courses with unique short codes (2-3 chars) |
| CRS-02 | Set pricing for 4 delivery modes: batch, online, private, standard |
| CRS-03 | Upload course content/materials (files) |
| CRS-04 | View all enrolled students per course |
| CRS-05 | Delete courses with confirmation |

### 4.4 Certificate Management

**Priority:** High  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| CERT-01 | Issue certificates linked to student registrations |
| CERT-02 | Auto-generate certificate numbers using course code prefix |
| CERT-03 | Support regular and KHDA (Knowledge and Human Development Authority) certificates |
| CERT-04 | Record course dates (from/end) and grade |
| CERT-05 | Print professional certificate layouts |
| CERT-06 | Upload pre-issued certificates (PDF) against registrations |
| CERT-07 | Upload registration forms as supporting documents |

### 4.5 Quotation Management

**Priority:** High  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| QUO-01 | Create professional training quotations for clients |
| QUO-02 | Auto-generate quotation numbers in YY/MM/### format |
| QUO-03 | Specify training venue: In-House, External, Online |
| QUO-04 | Add multiple courses with duration and number of persons per quotation |
| QUO-05 | Include consultant contact details in quotation |
| QUO-06 | Apply discount to full quotation |
| QUO-07 | Print/export quotation as professional PDF |
| QUO-08 | Edit and delete quotations |

### 4.6 Proposal Management

**Priority:** Medium  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| PROP-01 | Create training proposals with PROP-YYYY-#### numbering |
| PROP-02 | Link proposals to specific courses and trainers |
| PROP-03 | Upload custom company logo (PNG, 800×300px) |
| PROP-04 | Auto-generate white/inverted version of logo for dark backgrounds |
| PROP-05 | Print professional proposal layout with branding |
| PROP-06 | Manage multiple proposals per client |

### 4.7 Lead Management (CRM)

**Priority:** High  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| CRM-01 | Capture leads with contact info and interested course |
| CRM-02 | Track lead sources: Website, Referral, Event, Other |
| CRM-03 | Manage lead status: Interested Highly, Qualified, Register Soon, Other |
| CRM-04 | Schedule and track follow-up tasks with priority levels |
| CRM-05 | Add internal comments/notes on leads |
| CRM-06 | Flag/unflag comments for attention |
| CRM-07 | Schedule meetings linked to leads |
| CRM-08 | Track quoted amounts per lead |
| CRM-09 | Sales pipeline stage management |
| CRM-10 | Dashboard statistics and lead KPIs |

### 4.8 Trainer & Company Profiles

**Priority:** Medium  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| PRF-01 | Create trainer profiles with PDF CVs |
| PRF-02 | Assign trainers to proposals |
| PRF-03 | Create company profiles with PDF documents |
| PRF-04 | Manage and delete profiles |

### 4.9 Coupon Management

**Priority:** Low  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| CPN-01 | Create discount coupon codes |
| CPN-02 | Set percentage discount per coupon |
| CPN-03 | Activate/deactivate coupons |
| CPN-04 | Validate coupon codes via AJAX at checkout |

### 4.10 Dashboard & Reporting

**Priority:** High  
**Status:** Implemented

| ID | Requirement |
|----|-------------|
| RPT-01 | Main dashboard showing total registrations and invoices |
| RPT-02 | Monthly sales and registration statistics |
| RPT-03 | Corporate vs individual registration breakdown |
| RPT-04 | Invoices due today view |
| RPT-05 | Lead pipeline statistics |
| RPT-06 | Filter dashboard data by date range |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Authentication** | All pages require login; admin-only actions for user management |
| **Availability** | 99% uptime during business hours (UAE timezone) |
| **Performance** | Page load < 3 seconds for standard list views |
| **File Storage** | Support PDF, PNG upload; store in organized media directory |
| **PDF Generation** | Professional print-quality PDF output for invoices, certificates, proposals |
| **Responsive Design** | Mobile-friendly layout for field staff access |
| **Browser Support** | Chrome, Firefox, Edge (modern versions) |
| **Currency** | AED (UAE Dirham) throughout |
| **VAT** | 5% UAE VAT applied to all taxable transactions |
| **Localization** | English interface; UAE-specific fields (Emirates, Emirates ID) |

---

## 6. User Flows

### 6.1 Student Enrollment Flow
```
Lead Captured → Follow-up → Qualified → Registration Form →
Course Selection + Pricing → Invoice Generated → Payment Collected →
Certificate Issued → Record Complete
```

### 6.2 Corporate Client Flow
```
Quotation Request → Proposal Sent → Negotiation → PO Received →
Corporate Registration → Batch Invoice → Training Delivered →
KHDA Certificates → Account Settled
```

### 6.3 Invoice Payment Flow
```
Invoice Created → Sent to Client → Partial/Full Payment Recorded →
Status Updated (Term Payment / Full Payment) → Certificate Released
```

---

## 7. Out of Scope (Current Version)

- Online student self-service portal
- Automated email notifications
- SMS reminders
- Payment gateway integration (Tabby/Tamara API)
- Student assessment/exam module
- HR and payroll management
- Inventory management
- Multi-branch support
- Public-facing course catalog website

---

## 8. Future Roadmap

| Priority | Feature |
|----------|---------|
| High | Automated invoice email delivery |
| High | Student self-registration portal |
| Medium | Payment gateway integration (Tabby, Tamara, Stripe) |
| Medium | Attendance tracking module |
| Medium | Student assessment/grading module |
| Low | Mobile app (iOS/Android) |
| Low | WhatsApp notification integration |
| Low | Multi-language support (Arabic) |

---

## 9. Success Metrics

| Metric | Target |
|--------|--------|
| Invoice processing time | < 5 minutes per invoice |
| Registration completion | < 10 minutes per student |
| Certificate issuance | Same-day after course completion |
| Lead response tracking | 100% of leads have follow-up records |
| Document generation | PDF in < 30 seconds |

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
