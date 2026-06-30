# Orbit ERP — Advanced Features & Gap Analysis Roadmap
**Institute Management System | Date: 2026-06-25 | Version 2.0**

> **Migration Safety Note:** Every feature in this document is designed to be additive — new tables, new columns with defaults, new views. Nothing modifies or removes existing columns, tables, or data that the 3-year running system depends on. All DB changes are marked clearly.

---

## Table of Contents
1. [Critical Code Bugs](#1-critical-code-bugs-fix-immediately)
2. [Student Lifecycle](#2-student-lifecycle-management)
3. [Financial & Accounting](#3-financial--accounting)
4. [Academic Operations](#4-academic-operations)
5. [HR & Trainer Management](#5-hr--trainer-management)
6. [Reporting & Business Intelligence](#6-reporting--business-intelligence)
7. [Notifications & Communication](#7-notifications--communication)
8. [Payments & Integrations](#8-payments--integrations)
9. [Security & Compliance](#9-security--compliance)
10. [System Administration](#10-system-administration)
11. [UI / UX Enhancements](#11-ui--ux-enhancements)
12. [Data Quality Issues](#12-data-quality--integrity)
13. [Priority Matrix](#13-priority-matrix)
15. [Implementation Phases](#15-implementation-phases)

---

## 1. Critical Code Bugs (Fix Immediately)

These are bugs in the **current code** that cause incorrect behavior today.

### B1 — `__str__` Method Typos *(No DB change — Python fix only)*
| Model | Bug | Impact |
|---|---|---|
| `Client` | `_str_()` instead of `__str__()` | Django admin shows `<Client object>` |
| `Course` | `_str_()` instead of `__str__()` | Dropdowns/admin broken |
| `Invoice` | `_str_()` instead of `__str__()` | Admin lists unreadable |
| `InvoicePurchase` | `_str_()` instead of `__str__()` | Admin lists unreadable |
| `Quotation` | Returns `quotation_numbe` (missing 'r') | Truncated display |
| `Proposal` | Has two `__str__()` methods; second references non-existent field | Runtime error risk |

**Fix:** Rename each method and correct the return values.

### B2 — Duplicate Total Calculation Logic *(No DB change)*
`Invoice.calculate_total_amount()` and `Invoice.get_total_amount()` implement different logic. The `save()` method calls `calculate_total_amount()` but views sometimes call `get_total_amount()`, giving inconsistent totals.

**Fix:** Remove `get_total_amount()`, use `calculate_total_amount()` everywhere.

### B3 — Certificate Data Integrity *(No DB change — logic fix)*
`Certificate.register_number` and `Certificate.course_name` are plain strings, not ForeignKeys. If a Registration or Course is edited, certificates become orphaned/stale.

**Fix:** Add a lookup helper that cross-references the string `register_number` against `Registration.registration_number`. Flag mismatches in admin. (Full FK migration optional later.)

### B4 — Admin Hardcode in Legacy View *(No DB change — code fix)*
```python
# views.py line ~1800
if request.user.username == 'admin':
```
This hardcoded check bypasses the role system. Should be `is_admin_user(request.user)`.

---

## 2. Student Lifecycle Management

### S1 — Student Status Tracking *(New column, additive)*
**Gap:** No field tracks whether a student is Active, Completed, Dropped, Suspended.

**Add to `Registration` model:**
```python
STATUS_CHOICES = [
    ('active','Active'), ('completed','Completed'),
    ('dropped','Dropped Out'), ('suspended','Suspended'), ('pending','Pending')
]
student_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
```

**Features to build:**
- Status change dropdown on registration detail page
- Filter by status in student dashboard
- Auto-set to 'completed' when certificate is issued
- 'Dropped' reason field (optional, text)

---

### S2 — Course Start / End Date per Registration *(New columns, additive)*
**Gap:** No actual training dates tracked. Quotation has `schedule` (text), but no structured dates on the registration itself.

**Add to `RegistrationCourse` model:**
```python
start_date = models.DateField(null=True, blank=True)
end_date   = models.DateField(null=True, blank=True)
trainer    = models.ForeignKey('TrainerProfile', null=True, blank=True, on_delete=models.SET_NULL)
```

**Features:**
- Date picker on registration course form
- Calendar view of upcoming courses
- "Upcoming This Week" widget on dashboards

---

### S3 — Attendance Tracking *(New model, additive)*
**Note:** User said skip for now — documented here for future reference.

```python
class AttendanceRecord(models.Model):
    registration_course = models.ForeignKey(RegistrationCourse, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(choices=[('present','Present'),('absent','Absent'),('late','Late')])
    notes = models.TextField(blank=True)
```

---

### S4 — Student Self-Service Portal *(New views, no DB change)*
**Gap:** Students have no way to log in and view their own data.

**Required additions (no DB change needed initially):**
- Dedicated login URL for students
- Student dashboard: show their registration(s), courses, certificate status, payment status
- Certificate download (if uploaded)
- Read-only — students cannot edit data

**Implementation notes:**
- Use existing `Registration.email` as login identifier
- Add a `StudentUser` flag to `UserProfile` (new role: 'student')
- Or use a separate PIN/token-based access (no account required)

---

### S5 — Progress Tracking & Completion *(New columns, additive)*
**Gap:** No tracking of whether each course within a registration has been completed.

**Add to `RegistrationCourse`:**
```python
is_completed = models.BooleanField(default=False)
completion_date = models.DateField(null=True, blank=True)
completion_notes = models.TextField(blank=True)
```

**Features:**
- Checkbox on registration detail to mark each course complete
- Auto-generate certificate prompt when all courses completed
- Completion rate KPI on dashboards

---

### S6 — Student Document Management *(New model, additive)*
**Gap:** Only one form upload and one certificate upload supported (OneToOneField). Students may have multiple documents (passport, emirates ID, visa, medical certificate).

**New model:**
```python
class StudentDocument(models.Model):
    DOC_TYPES = [('passport','Passport'),('emirates_id','Emirates ID'),
                 ('visa','Visa'),('photo','Photo'),('academic_cert','Academic Certificate'),('other','Other')]
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES)
    file = models.FileField(upload_to='student_docs/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=200, blank=True)
```

---

### S7 — Student Feedback & Course Ratings *(New model, additive)*
**Gap:** No feedback collection after course completion.

**New model:**
```python
class CourseFeedback(models.Model):
    registration_course = models.OneToOneField(RegistrationCourse, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i,i) for i in range(1,6)])
    trainer_rating = models.IntegerField(choices=[(i,i) for i in range(1,6)], null=True)
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
```

**Features:**
- Email/WhatsApp link sent after course completion
- Average rating shown on course list
- Trainer performance dashboard includes average ratings

---

## 3. Financial & Accounting

### F1 — Receivables Aging Report *(No DB change — new view)*
**Gap:** Admin sees outstanding amounts but no aging analysis (0-30 days, 31-60, 61-90, 90+ days overdue).

**New view:** `receivables_aging()` — groups overdue invoices by age bracket.

**Template additions:**
- Color-coded aging table (green → yellow → orange → red)
- Drill-down by consultant
- Export to CSV

---

### F2 — Expense / Cost Tracking *(New model, additive)*
**Gap:** Purchase invoices track client-billed items, but internal business expenses (rent, utilities, marketing) are not tracked.

**New model:**
```python
class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('rent','Rent'),('utilities','Utilities'),('marketing','Marketing'),
        ('trainer_fee','Trainer Fee'),('printing','Printing'),('travel','Travel'),('other','Other')
    ]
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    receipt = models.FileField(upload_to='expenses/%Y/%m/', null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Features:**
- Expense entry form
- Monthly expense vs. revenue P&L summary
- Category-wise breakdown chart

---

### F3 — Payment Recording & Partial Payments *(New model, additive)*
**Gap:** `Invoice.amount_paid` is a single number. Multiple payments (term payments) have no history.

**New model:**
```python
class PaymentRecord(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    method = models.CharField(max_length=20, choices=Invoice.CARD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)  # cheque#, transfer ref
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.CharField(max_length=200, blank=True)
```

**Features:**
- "Record Payment" button on invoice
- Auto-updates `invoice.amount_paid` as sum of records
- Payment history timeline on registration detail

---

### F4 — VAT Report / Tax Summary *(No DB change — new view)*
**Gap:** System collects 5% VAT on all invoices but has no tax summary report.

**New view:** `vat_report()` — monthly VAT collected, VAT due, net VAT.
- Filter by date range
- Output in UAE FTA-compatible format
- Export to CSV

---

### F5 — Profit Margin per Course *(No DB change — computation)*
**Gap:** Revenue per course is visible, but no cost subtraction.

**New analytics view:**
- Revenue by course (from invoices)
- Trainer cost (if Expense model added)
- Gross margin %
- Most profitable courses ranking

---

### F6 — Coupon Enhancement *(New columns, additive)*
**Gap:** Coupon model lacks expiry date, usage limits, and min purchase amount.

**Add to `Coupon`:**
```python
expiry_date        = models.DateField(null=True, blank=True)
max_uses           = models.IntegerField(null=True, blank=True)
used_count         = models.IntegerField(default=0)
min_order_amount   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
applicable_courses = models.ManyToManyField(Course, blank=True)
```

**Features:**
- Auto-deactivate expired coupons (management command / cron)
- Usage counter incremented on each invoice
- Course-specific coupons in registration form

---

### F7 — Invoice Approval Workflow *(New column, additive)*
**Gap:** Any user can create and print an invoice without approval.

**Add to `Invoice`:**
```python
APPROVAL_CHOICES = [('draft','Draft'),('pending','Pending Approval'),('approved','Approved'),('rejected','Rejected')]
approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='approved')
approved_by     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_invoices')
approved_at     = models.DateTimeField(null=True, blank=True)
```

---

## 5. Academic Operations

### A1 — Course Scheduling & Batch Management *(New model, additive)*
**Gap:** No concept of a class/batch — only individual registrations exist.

**New model:**
```python
class CourseSchedule(models.Model):
    course      = models.ForeignKey(Course, on_delete=models.CASCADE)
    batch_name  = models.CharField(max_length=100)  # e.g., "Batch A - Jan 2026"
    trainer     = models.ForeignKey(TrainerProfile, null=True, on_delete=models.SET_NULL)
    start_date  = models.DateField()
    end_date    = models.DateField()
    venue       = models.CharField(max_length=200)
    max_capacity = models.IntegerField(default=20)
    class_type  = models.CharField(max_length=20, choices=Registration.CLASS_TYPE_CHOICES)
    status      = models.CharField(max_length=20, choices=[('planned','Planned'),('ongoing','Ongoing'),('completed','Completed'),('cancelled','Cancelled')], default='planned')
    notes       = models.TextField(blank=True)
```

**Features:**
- Schedule calendar view (month/week view using FullCalendar.js)
- Assign registered students to a batch
- Batch capacity tracking (X of Y students enrolled)
- Batch status updates

---

### A2 — Academic Calendar / Holiday Management *(New model, additive)*

```python
class AcademicEvent(models.Model):
    EVENT_TYPES = [('class','Class'),('exam','Exam'),('holiday','Holiday'),('event','Event')]
    title      = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    date       = models.DateField()
    end_date   = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_public  = models.BooleanField(default=True)
```

**Features:**
- Calendar view on all dashboards
- Holiday list used to calculate working days for payment terms
- Export to iCal format

---

### A3 — Assessment & Grading System *(New model, additive)*

```python
class Assessment(models.Model):
    registration_course = models.ForeignKey(RegistrationCourse, on_delete=models.CASCADE)
    title         = models.CharField(max_length=200)
    max_score     = models.DecimalField(max_digits=6, decimal_places=2)
    obtained_score = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    date          = models.DateField(null=True)
    pass_mark     = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    notes         = models.TextField(blank=True)

    @property
    def is_passed(self):
        return self.obtained_score >= self.pass_mark if self.obtained_score else None

    @property
    def grade_letter(self):
        if not self.obtained_score: return '—'
        pct = (self.obtained_score / self.max_score) * 100
        if pct >= 90: return 'A+'
        elif pct >= 80: return 'A'
        elif pct >= 70: return 'B+'
        elif pct >= 60: return 'B'
        elif pct >= 50: return 'C'
        return 'F'
```

**Features:**
- Add assessment scores from registration detail page
- Auto-fill grade on certificate based on assessment score
- Pass/fail analytics per course

---

### A4 — Certificate Expiry Tracking *(New column, additive)*
**Gap:** Some certifications (safety, compliance) expire — not tracked.

**Add to `Certificate`:**
```python
expiry_date          = models.DateField(null=True, blank=True)
renewal_reminder_sent = models.BooleanField(default=False)
```

**Features:**
- "Expiring Soon" widget on admin dashboard (certificates expiring in 30/60/90 days)
- Auto-send reminder email (requires email setup)
- Expiry status badge on certificate table

---

### A5 — Course Content Version Control *(New column, additive)*

**Add to `CourseContent`:**
```python
version      = models.CharField(max_length=20, default='1.0')
is_current   = models.BooleanField(default=True)
uploaded_by  = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
description  = models.CharField(max_length=500, blank=True)
```

**Features:**
- Multiple versions of a document
- Previous versions archived, not deleted
- Version history displayed on course detail

---

## 6. HR & Trainer Management

### H1 — Enhanced Trainer Profile *(New columns, additive)*
**Gap:** TrainerProfile only stores name + PDF. Cannot search by specialization or book a trainer.

**Add to `TrainerProfile`:**
```python
email            = models.EmailField(blank=True)
phone            = models.CharField(max_length=20, blank=True)
specializations  = models.TextField(blank=True)  # comma-separated or JSON
experience_years = models.IntegerField(default=0)
hourly_rate      = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
availability     = models.CharField(max_length=20, choices=[('available','Available'),('busy','Busy'),('on_leave','On Leave')], default='available')
bio              = models.TextField(blank=True)
```

**Features:**
- Trainer search by specialization
- Trainer availability filter when scheduling a course
- Trainer workload report (hours assigned this month)

---

### H2 — Staff / Employee Directory *(New model, additive)*
**Gap:** Only trainer profiles exist. Admin, sales, accounts staff have no records beyond their User account.

**New model:**
```python
class StaffProfile(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    department    = models.CharField(max_length=100)
    designation   = models.CharField(max_length=100)
    join_date     = models.DateField()
    phone         = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    address       = models.TextField(blank=True)
    is_active_employee = models.BooleanField(default=True)
```

---

### H3 — Leave Management *(New model, additive)*

```python
class LeaveRequest(models.Model):
    LEAVE_TYPES = [('annual','Annual'),('sick','Sick'),('emergency','Emergency'),('unpaid','Unpaid')]
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    leave_type   = models.CharField(max_length=20, choices=LEAVE_TYPES)
    from_date    = models.DateField()
    to_date      = models.DateField()
    reason       = models.TextField()
    status       = models.CharField(max_length=20, choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')], default='pending')
    approved_by  = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='leave_approvals')
```

---

## 7. Reporting & Business Intelligence

### R1 — Executive KPI Dashboard *(No DB change — new views)*
**Gap:** Admin dashboard has basic KPIs but no trend comparison or executive summary.

**New features:**
- MTD vs. LMTD (last month to date) comparison
- YTD (year-to-date) revenue
- Rolling 12-month revenue trend
- Top 5 courses by revenue
- Top 5 consultants by revenue
- Lead conversion rate (leads → registrations)
- Certificate issuance rate

---

### R2 — Student Enrollment Report *(No DB change — new view)*
**Columns:** Registration #, Student Name, Course(s), Consultant, Date, Class Type, Status, Payment Status, Invoice #

**Filters:** Date range, consultant, course, class type, payment status, student status
**Export:** CSV + Excel

---

### R3 — Course Performance Report *(No DB change — new view)*
**Per course:** Number of students, revenue generated, average invoice amount, completion rate, certificate count, average rating (if S7 added)

**Includes:** Period comparison (this month vs last month)
**Export:** CSV

---

### R4 — Lead Pipeline Report *(No DB change — new view)*
**Shows:** Leads by status, leads by source, avg days from lead creation to conversion, conversion rates, follow-up compliance rate (% of leads with follow-ups on time)

---

### R5 — Consultant Performance Report *(No DB change — new view)*
**Per consultant:** Leads owned, leads converted, registrations, invoices generated, revenue, target achievement %

**Includes:** Period filter, rank/leaderboard export

---

### R6 — Certificate Report *(No DB change — new view)*
**Per period:** Certificates issued by course, by type (KHDA/Internal), by consultant, expiring soon

---

### R7 — Overdue Invoice Aging Report *(No DB change — new view)*
**Groups:** 0-15 days, 16-30 days, 31-60 days, 61-90 days, 90+ days overdue

**Includes:** Client contact info, invoice # and amount, consultant name, action buttons (send reminder, mark paid)

---

### R8 — Scheduled Reports *(New model, additive)*

```python
class ScheduledReport(models.Model):
    name       = models.CharField(max_length=100)
    report_type = models.CharField(max_length=50)  # revenue, leads, certificates
    frequency  = models.CharField(max_length=20, choices=[('daily','Daily'),('weekly','Weekly'),('monthly','Monthly')])
    recipients = models.TextField()  # comma-separated emails
    last_sent  = models.DateTimeField(null=True)
    is_active  = models.BooleanField(default=True)
```

---

## 8. Notifications & Communication

### N1 — In-App Notification Center *(New model, additive)*

```python
class Notification(models.Model):
    NOTIF_TYPES = [
        ('invoice_due','Invoice Due'), ('lead_followup','Lead Follow-up Due'),
        ('certificate_expiry','Certificate Expiring'), ('target_alert','Target Alert'),
        ('registration_new','New Registration'), ('payment_received','Payment Received'),
    ]
    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type        = models.CharField(max_length=30, choices=NOTIF_TYPES)
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    link        = models.CharField(max_length=200, blank=True)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
```

**Features:**
- Bell icon in navbar with unread count badge
- Dropdown shows last 10 notifications
- Mark as read on click
- Triggered by: invoice due date, overdue follow-ups, target near deadline, new registrations (for admin)

---

### N2 — Email Notification Engine *(New model, additive + SMTP config)*

```python
class EmailLog(models.Model):
    to_email   = models.EmailField()
    subject    = models.CharField(max_length=200)
    body       = models.TextField()
    sent_at    = models.DateTimeField(auto_now_add=True)
    status     = models.CharField(max_length=20, choices=[('sent','Sent'),('failed','Failed')])
    error      = models.TextField(blank=True)
    triggered_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    related_type = models.CharField(max_length=50, blank=True)  # 'invoice', 'lead', 'certificate'
    related_id   = models.IntegerField(null=True)
```

**Automated emails to implement:**
| Trigger | Recipient | Template |
|---|---|---|
| Invoice created | Student | "Your invoice is ready" |
| Invoice overdue | Student + Consultant | "Payment reminder" |
| Certificate issued | Student | "Your certificate is ready" |
| Lead follow-up due | Consultant | "You have a follow-up today" |
| Registration created | Admin + Consultant | "New student registered" |
| Target 80% achieved | Executive | "You are close to your target" |

---

### N3 — WhatsApp Integration via API *(New model, additive)*
**Gap:** WhatsApp is used manually — no automated messages or logs.

**New model:**
```python
class WhatsAppLog(models.Model):
    phone      = models.CharField(max_length=20)
    message    = models.TextField()
    sent_at    = models.DateTimeField(auto_now_add=True)
    status     = models.CharField(max_length=20)
    sent_by    = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    related_lead = models.ForeignKey(Lead, null=True, on_delete=models.SET_NULL)
```

**Integration options:** WhatsApp Business API (Meta), Twilio WhatsApp, WATI.io

---

## 9. Payments & Integrations

### P1 — Payment Gateway Integration
**Gap:** Tabby and Tamara appear as payment methods but are not actually integrated.

**Required:**
- Tabby API integration for BNPL payment links
- Tamara API integration
- Stripe integration (international cards)
- Payment link generation (already partially exists via `payment_link` view)
- Webhook to auto-update invoice status when payment confirmed

---

### P2 — Online Payment Reconciliation *(New model, additive)*

```python
class PaymentGatewayTransaction(models.Model):
    invoice      = models.ForeignKey(Invoice, null=True, on_delete=models.SET_NULL)
    gateway      = models.CharField(max_length=30)  # tabby, tamara, stripe
    transaction_id = models.CharField(max_length=100, unique=True)
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    currency     = models.CharField(max_length=3, default='AED')
    status       = models.CharField(max_length=20)
    gateway_response = models.JSONField(blank=True, default=dict)
    created_at   = models.DateTimeField(auto_now_add=True)
```

---

### P3 — Excel Export for All Reports *(No DB change — library addition)*
**Gap:** Only CSV export exists.

**Add `openpyxl` to requirements:**
- Formatted Excel with headers, totals rows, color-coded status cells
- Applies to: Revenue Report, Student List, Lead Report, Certificate Report

---

### P4 — Bulk Import via Excel *(No DB change — new view)*
**Features:**
- Upload Excel template → parse → validate → preview → import
- Bulk student import for corporate registrations
- Bulk course import
- Error report for invalid rows

---

### P5 — REST API for Mobile / Integration *(New URLs)*
**Gap:** No API — all data is only accessible through the web UI.

**Using Django REST Framework:**
- Registration API (create, read)
- Invoice status API
- Certificate verification API (public — verify by certificate number)
- Lead API (for website contact form integration)
- Authentication via token

---

## 10. Security & Compliance

### SC1 — Audit Log *(New model, additive)*
**Gap:** No history of who changed what. Critical for a financial system.

```python
class AuditLog(models.Model):
    user        = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action      = models.CharField(max_length=20, choices=[('create','Create'),('update','Update'),('delete','Delete'),('login','Login'),('export','Export')])
    model_name  = models.CharField(max_length=100)
    object_id   = models.IntegerField(null=True)
    object_repr = models.CharField(max_length=500)
    changes     = models.JSONField(default=dict)  # {field: [old, new]}
    ip_address  = models.GenericIPAddressField(null=True)
    timestamp   = models.DateTimeField(auto_now_add=True)
```

**Trigger on:** Invoice CRUD, Registration CRUD, Certificate issuance, User role changes, Payment recording
**View:** Admin-only audit trail page with filters

---

### SC2 — Role-Based Field Access *(No DB change — template/view logic)*
**Gap:** All roles see all fields. Accounts should not see lead notes; sales executives should not see profit margins.

**Implementation:**
- Context processor that injects `user_role` into all templates
- Template conditionals for sensitive fields: `{% if user_role == 'admin' %}profit_margin{% endif %}`
- View decorators check role before rendering sensitive data

---

### SC3 — Two-Factor Authentication *(No DB change — library addition)*
**Library:** `django-otp` or `django-allauth`

**Options:**
- TOTP (Google Authenticator) — for admin accounts
- Email OTP — for all accounts
- Enforce for admin role only (configurable)

---

### SC4 — GDPR / Data Privacy *(New view, additive)*
**Gap:** No way to export or delete a student's personal data.

**New views:**
- `student_data_export(registration_id)` — ZIP download of all data related to that student
- `student_data_delete(registration_id)` — Anonymize personal fields (replace with "DELETED")
- Consent flag on registration form: `data_consent = BooleanField(default=False)`

---

### SC5 — Sensitive Data Masking *(No DB change — template logic)*
**Gap:** Passport numbers, Emirates IDs, and phone numbers show in full in all views.

**Implementation:**
- Template filter `mask_sensitive` → shows `**6789` for last 4 digits
- Toggle "Reveal" button (logs access to AuditLog)
- Applied to: passport_no, uid_no, emirates_id_no, phone_no

---

### SC6 — File Upload Security *(No DB change — validation)*
**Gap:** No validation on file types for uploads.

**Add to all FileField forms:**
- Allowed extensions whitelist (.pdf, .jpg, .png, .docx)
- Max file size (5MB)
- Virus scan (ClamAV if available)
- Rename files to UUID on upload (prevent path traversal)

---

## 11. System Administration

### SA1 — System Settings Panel *(New model, additive)*

```python
class SystemSetting(models.Model):
    key   = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    type  = models.CharField(max_length=20, choices=[('text','Text'),('number','Number'),('boolean','Boolean'),('email','Email')])
    description = models.CharField(max_length=500)
    updated_at  = models.DateTimeField(auto_now=True)
```

**Settings to manage through UI (not hardcode):**
- Company name, address, TRN, logo
- VAT rate (currently hardcoded at 5%)
- Invoice prefix format
- Default payment terms (days)
- SMTP email settings
- WhatsApp API key
- Certificate validity period

---

### SA2 — Django Management Commands

**Useful commands to build:**
```bash
python manage.py send_invoice_reminders  # invoices due in next 3 days
python manage.py send_followup_reminders # leads with follow-up today
python manage.py expire_coupons          # auto-deactivate expired coupons
python manage.py generate_monthly_report # email monthly summary to admin
python manage.py backup_database         # export DB to file
```

**Schedule with:** Windows Task Scheduler (XAMPP) or Celery Beat

---

### SA3 — Activity Feed / Timeline *(No DB change — computed)*
**Gap:** No way to see what happened in the system today.

**New view:** `activity_feed()` — shows last 100 actions across:
- New registrations
- Invoices created
- Payments received
- Leads added
- Certificates issued
- User logins

---

### SA4 — Data Backup & Export *(No DB change — new management command)*
**Gap:** No backup mechanism.

**New management command:**
- Dumps all tables to JSON
- Compresses to ZIP with timestamp
- Uploads to configurable path
- Configurable retention (keep last N backups)

---

### SA5 — Multi-Branch / Location Support *(New model, additive)*
**Gap:** System assumes single location. As Orbit grows, they may open more centers.

```python
class Branch(models.Model):
    name     = models.CharField(max_length=100)
    address  = models.TextField()
    phone    = models.CharField(max_length=20)
    email    = models.EmailField()
    is_active = models.BooleanField(default=True)
```

**Add `branch = ForeignKey(Branch)` to:** Registration, Invoice, Lead, Course (optional)

---

## 12. UI / UX Enhancements

### U1 — Mobile-Responsive Navigation
**Gap:** Current sidebar assumes desktop. On mobile, tables overflow.

**Improvements:**
- Collapsible sidebar with hamburger
- Touch-friendly action buttons (minimum 44px tap target)
- Responsive tables (horizontal scroll on small screens)
- Swipe gestures for invoice/registration list

---

### U2 — Global Quick Search *(No DB change — new AJAX view)*
**Gap:** No system-wide search.

**New search bar in navbar:**
- Search across: Registrations, Invoices, Leads, Courses, Certificates
- Returns top 5 results per category
- Click → navigate to detail page
- Keyboard shortcut: `Ctrl + K`

---

### U3 — Dark Mode *(No DB change — CSS variable toggle)*
**Gap:** Single light theme.

**Implementation:**
- Toggle in user preferences (saved to LocalStorage or UserProfile)
- CSS variables already partially in place in `base_generic.html`
- Dark palette: `--bg: #0f172a`, `--sidebar: #1e293b`, `--card: #1e293b`

---

### U4 — Keyboard Shortcuts *(No DB change — JS)*
| Shortcut | Action |
|---|---|
| `N R` | New Registration |
| `N I` | New Invoice |
| `N L` | New Lead |
| `Ctrl + K` | Global Search |
| `Esc` | Close Modal |
| `?` | Show shortcuts help |

---

### U5 — Print Improvements *(No DB change)*
**Gap:** Print functions work but have no preview.

**Improvements:**
- Print preview modal before opening print window
- Batch print (select multiple, print all certificates in one PDF)
- Invoice print with company letterhead customization
- Email PDF directly from print modal

---

### U6 — Breadcrumbs on All Pages *(No DB change)*
**Gap:** Many pages have no breadcrumbs.

**Add consistent breadcrumb block to all templates:**
```
Home > Registrations > REG-26-001 > Invoice Detail
Home > Leads > John Doe
Home > Reports > Revenue Report
```

---

### U7 — Onboarding / Empty States *(No DB change)*
**Gap:** Empty tables show no guidance.

**Improve empty states:**
- Illustration + helpful message
- "Get started" button pointing to creation form
- Example: "No leads yet. Import from a CSV or add your first lead →"

---

## 13. Data Quality & Integrity

### DQ1 — Duplicate Student Detection *(No DB change — new logic)*
**Gap:** The same student can be registered multiple times with slightly different names.

**New checks:**
- Fuzzy name matching on registration form (show warning if similar name + phone found)
- Duplicate email detection (email is not unique in Registration model — this is intentional but should warn)
- "Possible Duplicate" badge on student dashboard

---

### DQ2 — Certificate Reference Integrity Fix *(No DB change — migration optional later)*
**Current issue:** `Certificate.register_number` is a string, not a FK.

**Short-term fix:** Add a lookup on certificate list that cross-checks against Registration records and flags mismatches.

**Long-term fix (migration, later):**
```python
# Future migration — SAFE if done correctly
registration = models.ForeignKey(Registration, null=True, blank=True, on_delete=models.SET_NULL)
```

---

### DQ3 — Mandatory Field Enforcement
**Gap:** Several important fields are blank=True but should be required in business context.

**Fields to validate at form level (no DB change):**
- `Registration.consultant_name` — should always be assigned
- `Invoice.due_date` — must be after `invoice.date`
- `Lead.follow_up_date` — should be set when status is "Interested Highly"

---

### DQ4 — Phone Number Standardization *(No DB change — form validation)*
**Gap:** Phone numbers stored in inconsistent formats (+971 50 xxx, 050xxxxxxx, etc.)

**Add form validator:**
```python
import re
def validate_uae_phone(value):
    cleaned = re.sub(r'\s+|-', '', value)
    if not re.match(r'^\+?(?:971)?0?5[024568]\d{7}$', cleaned):
        raise ValidationError('Enter a valid UAE mobile number')
```

---

## 14. Priority Matrix

| Priority | Feature | Effort | Impact | DB Change? |
|---|---|---|---|---|
| **P0 - Now** | B1: Fix `__str__` bugs | Low | High | No |
| **P0 - Now** | B2: Fix duplicate total calc | Low | High | No |
| **P0 - Now** | B4: Fix admin hardcode | Low | Medium | No |
| **P0 - Now** | SC6: File upload validation | Low | High | No |
| **P1 - Sprint 1** | C3: Quotation status workflow | Low | High | Yes (additive) |
| **P1 - Sprint 1** | F3: Payment recording history | Medium | High | Yes (new table) |
| **P1 - Sprint 1** | N1: In-app notifications | Medium | High | Yes (new table) |
| **P1 - Sprint 1** | R1: Executive KPI dashboard | Medium | High | No |
| **P1 - Sprint 1** | R7: Aging report | Low | High | No |
| **P1 - Sprint 1** | SA1: System settings panel | Medium | Medium | Yes (new table) |
| **P1 - Sprint 1** | C2: Lead conversion tracking | Low | High | Yes (additive) |
| **P2 - Sprint 2** | S1: Student status field | Low | High | Yes (additive) |
| **P2 - Sprint 2** | S2: Course dates per registration | Low | High | Yes (additive) |
| **P2 - Sprint 2** | C1: Lead scoring | Medium | High | Yes (additive) |
| **P2 - Sprint 2** | F2: Expense tracking | Medium | Medium | Yes (new table) |
| **P2 - Sprint 2** | F4: VAT report | Low | High | No |
| **P2 - Sprint 2** | N2: Email notification engine | High | High | Yes (new table) |
| **P2 - Sprint 2** | A1: Course scheduling | High | High | Yes (new table) |
| **P2 - Sprint 2** | U2: Global quick search | Medium | High | No |
| **P2 - Sprint 2** | SC1: Audit log | Medium | High | Yes (new table) |
| **P3 - Sprint 3** | H1: Enhanced trainer profile | Low | Medium | Yes (additive) |
| **P3 - Sprint 3** | S6: Student document management | Medium | Medium | Yes (new table) |
| **P3 - Sprint 3** | S7: Student feedback/ratings | Medium | Medium | Yes (new table) |
| **P3 - Sprint 3** | F6: Coupon enhancements | Low | Medium | Yes (additive) |
| **P3 - Sprint 3** | R2-R6: Additional reports | Medium | High | No |
| **P3 - Sprint 3** | P3: Excel export | Low | Medium | No |
| **P4 - Future** | S4: Student self-service portal | High | High | Yes |
| **P4 - Future** | A3: Assessment & grading | High | High | Yes (new table) |
| **P4 - Future** | P1: Payment gateway integration | High | High | No |
| **P4 - Future** | SC3: Two-factor authentication | Medium | High | No |
| **P4 - Future** | SA5: Multi-branch support | High | Medium | Yes (new table) |
| **P4 - Future** | P5: REST API | High | Medium | No |
| **P4 - Future** | N3: WhatsApp integration | High | High | Yes (new table) |

---

## 15. Implementation Phases

### Phase 0 — Bug Fixes (1–2 days, zero risk)
- Fix all `_str_()` → `__str__()` bugs
- Fix duplicate Invoice calculation
- Fix admin hardcode
- Add file upload validation
- Fix Certificate reference lookup

### Phase 1 — Core Business Upgrades (2–3 weeks)
- Quotation status workflow
- Lead conversion tracking
- Payment recording history
- Student status field
- In-app notifications
- Executive KPI dashboard enhancements
- VAT report
- Receivables aging report
- Global quick search
- System settings panel

### Phase 2 — Advanced Features (4–6 weeks)
- Lead scoring
- Course scheduling & batch management
- Email notification engine
- Expense tracking
- Enhanced trainer profiles
- Student document management
- Student feedback system
- All missing reports (R2–R6)
- Audit log
- Excel export

### Phase 3 — Integrations & Portal (2–3 months)
- Student self-service portal
- WhatsApp Business API
- Payment gateway (Tabby, Tamara, Stripe)
- Assessment & grading system
- Scheduled reports
- GDPR compliance tools
- REST API for mobile/integrations
- Multi-branch support

---

## Appendix — Quick Wins (< 1 day each, no DB change)

These can be done immediately by a developer without risk:

| # | Task | Where |
|---|---|---|
| QW1 | Add "total registered students" KPI to admin dashboard | views.py + admin_dashboard.html |
| QW2 | Add consultant filter to student dashboard | views.py student_dashboard |
| QW3 | Add "days since created" to lead table | lead_dashboard.html |
| QW4 | Show overdue invoices count badge in accounts sidebar | base_generic.html |
| QW5 | Add date created to all existing tables | Multiple templates |
| QW6 | Export certificate list to CSV | New view |
| QW7 | Export lead list to CSV | New view |
| QW8 | Show registration count on course list | views.py |
| QW9 | Add "Mark as Paid" quick button on invoice table | dashboard.html JS |
| QW10 | Print all selected registrations (batch print) | student_dashboard.html JS |
| QW11 | Add character counter to lead notes field | lead_dashboard.html JS |
| QW12 | Add "Copy invoice number" button | dashboard.html |
| QW13 | Show payment method breakdown pie chart on accounts dashboard | accounts_dashboard.html |
| QW14 | Add WhatsApp share button to invoice print modal | dashboard.html |
| QW15 | Color-code due date column (red = overdue, orange = due soon) | dashboard.html |

---

*Generated by Claude Code on 2026-06-25 | Based on full codebase audit of Orbit ERP v1.0*
