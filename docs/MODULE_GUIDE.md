# Module Guide
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25

---

## Module Overview

| # | Module | URL Prefix | Key Models | Forms | Views | Templates |
|---|--------|-----------|-----------|-------|-------|-----------|
| 1 | Authentication | `/accounts/` | auth_user | SignUpForm | signup, logout | login, signup |
| 2 | Dashboard | `/`, `/dashboard/` | All | — | dashboard, orbit_dashboard | dashboard/ |
| 3 | Invoices | `/create_invoice/` | Invoice, InvoiceItem | InvoiceForm, InvoiceItemForm | 7 | invoices/ |
| 4 | Purchase Invoices | `/create_purchase_invoice/` | InvoicePurchase | PurchaseInvoiceForm | 3 | invoices/ |
| 5 | Registrations | `/register/` | Registration, RegistrationCourse | RegistrationForm | 9 | studentregistration/ |
| 6 | Corporate | `/corporate-registration/` | CorporateRegistration | CorporateRegistrationForm | 5 | studentregistration/ |
| 7 | Courses | `/courses/` | Course, CourseContent | CourseForm | 7 | courses/ |
| 8 | Certificates | `/certificates/` | Certificate, CertificateUpload | CertificateForm | 7 | certificates/ |
| 9 | Quotations | `/quotation/` | Quotation, QuotationItem | QuotationForm | 6 | quotation/ |
| 10 | Proposals | `/proposals/` | Proposal | ProposalForm | 6 | proposal/ |
| 11 | CRM/Leads | `/lead/` | Lead, FollowUp, Comment, Meeting | LeadForm, FollowUpForm | 15 | leads/ |
| 12 | Trainer Profile | `/trainer-profile/` | TrainerProfile | TrainerProfileForm | 4 | trainerprofile/ |
| 13 | Company Profile | `/company-profile/` | CompanyProfile | CompanyProfileForm | 4 | companyprofile/ |
| 14 | Coupons | `/coupons/` | Coupon | CouponForm | 5 | coupons/ |

---

## Module 1: Authentication

### Purpose
User login/logout and admin-only user account creation.

### Key Files
- Views: `views.py` — `signup()`, `logout_view()`
- Forms: `forms.py` — `SignUpForm`
- Templates: `templates/registration/login.html`, `signup.html`
- URLs: Uses Django built-in `django.contrib.auth.urls` + custom `signup/`

### Business Logic
- Only `is_staff` or `is_superuser` users can create new accounts
- Login redirect goes to `/` (main dashboard)
- Django's built-in auth handles password hashing and session management

---

## Module 2: Dashboard

### Purpose
Central overview of business metrics and navigation hub.

### Key Files
- Views: `views.py` — `orbit_dashboard()`, `dashboard()`
- Templates: `templates/dashboard/orbit_dashboard.html`, `templates/invoices/dashboard.html`

### Data Points Displayed
**orbit_dashboard:**
- Total registrations (all time + current month)
- Individual vs corporate breakdown
- Recent invoice list
- Lead pipeline summary

**dashboard (invoice-focused):**
- Tabbed: Sales Invoices | Purchase Invoices
- Filter controls
- KPI cards: Total, Pending, Paid

---

## Module 3: Invoices

### Purpose
Core financial transaction management — create, edit, track sales invoices.

### Key Files
- Models: `Invoice`, `InvoiceItem`
- Views: `create_invoice()`, `edit_invoice()`, `delete_invoice()`, `add_invoice_items()`
- Forms: `InvoiceForm`, `InvoiceItemForm`
- Templates: `templates/invoices/`

### Key Logic

**Auto-numbering:**
```python
# YY/MM/### format, sequential per month
prefix = f"{now.strftime('%y/%m')}"
last = Invoice.objects.filter(invoice_number__startswith=prefix)
           .order_by('-invoice_number').first()
```

**VAT Calculation:**
```python
# Applied per line item, stored as vat_rate field (default 5%)
def get_vat_amount(self):
    return self.get_subtotal() * (self.vat_rate / 100)
```

**Total Calculation:**
```python
def calculate_total_amount(self):
    total = sum(item.get_total() for item in self.invoiceitem_set.all())
    if self.discount:
        total *= (1 - self.discount / 100)
    self.total_amount = total
```

### Template Features
- Separate print template for PDF generation
- AJAX-powered client/registration lookup
- Dynamic item form (add/remove rows)
- Tabbed dashboard (sales + purchase)

---

## Module 4: Student Registration

### Purpose
Enroll individual students and track their course selections, pricing, and discounts.

### Key Files
- Models: `Registration`, `RegistrationCourse`, `CorporateRegistration`
- Views: `registration_form()`, `edit_registration()`, `print_registration()`
- Forms: `RegistrationForm`, `RegistrationCourseForm`
- Templates: `templates/studentregistration/`

### Key Logic

**Auto-numbering:**
```python
# OT/YY/MM/### for individual, OC/YY/MM/### for corporate
prefix = f"OT/{now.strftime('%y/%m')}"
```

**Course pricing:**
```python
# Price auto-selected by class type
price_map = {
    'online': course.online_rate,
    'offline': course.rate,
    'batch': course.batch_rate,
    'private': course.private_rate,
}
```

**ManyToMany through table:**
- `RegistrationCourse` stores per-course price and discount
- Unique constraint prevents duplicate course enrollment
- Frontend uses JavaScript to dynamically add course rows

---

## Module 5: Courses

### Purpose
Manage the training course catalog including pricing tiers and materials.

### Key Files
- Models: `Course`, `CourseContent`
- Views: `course_list()`, `course_create()`, `course_update()`, `course_delete()`, `content_create()`
- Forms: `CourseForm`, `CourseContentForm`
- Templates: `templates/courses/`

### Key Logic

**Course code validation:**
```python
class CourseForm(forms.ModelForm):
    def clean_code(self):
        code = self.cleaned_data['code']
        if len(code) < 2 or len(code) > 10:
            raise ValidationError("Code must be 2-10 characters")
        if Course.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Course code already exists")
        return code.upper()
```

**Course detail shows:**
- All enrolled students (via RegistrationCourse)
- All uploaded course materials
- Usage in quotations and invoices

---

## Module 6: Certificates

### Purpose
Issue, track, and print training completion certificates.

### Key Files
- Models: `Certificate`, `CertificateUpload`, `FormUpload`
- Views: `certificate_dashboard()`, `create_certificate()`, `print_certificate()`, `khda_certificate_form()`
- Forms: `CertificateForm`, `KHDACertificateForm`
- Templates: `templates/certificates/`

### Key Logic

**Certificate number generation:**
```python
# Uses course code prefix
# Format: {COURSE_CODE}/YY/###
course = Course.objects.get(name=course_name)
prefix = f"{course.code}/{now.strftime('%y')}"
```

**KHDA vs Regular:**
- Regular: Generated via form, printable template
- KHDA: Upload pre-issued certificate PDF from KHDA authority
- Both linked to registration number

---

## Module 7: Quotations

### Purpose
Generate professional price quotations for training enquiries.

### Key Files
- Models: `Quotation`, `QuotationItem`
- Views: `create_quotation()`, `quotation_dashboard()`, `quotation_detail()`, `edit_quotation()`
- Forms: `QuotationForm`, `QuotationItemForm`
- Templates: `templates/quotation/`

### Key Logic

**Multi-course quotation:**
- Uses Django inline formset for multiple course rows
- Each row: course, duration, number of persons
- Price calculated from course rates × persons
- Discount applied at quotation level

**Print format includes:**
- Professional header with consultant details
- Tabular course listing with rates
- Terms and conditions footer

---

## Module 8: Proposals

### Purpose
Create branded training proposals for corporate clients.

### Key Files
- Models: `Proposal`
- Views: `create_proposal()`, `edit_proposal()`, `print_proposal()`, `remove_logo()`
- Forms: `ProposalForm`
- Templates: `templates/proposal/`

### Key Logic

**Logo processing:**
```python
# Validates: PNG format, exactly 800×300px
from PIL import Image
img = Image.open(logo_file)
if img.format != 'PNG' or img.size != (800, 300):
    raise ValidationError("Logo must be PNG, 800×300px")

# Generates white version
white_logo = create_white_version(img)
white_logo.save(white_logo_path)
```

**Proposal numbering:** `PROP-YYYY-####`

---

## Module 9: CRM / Lead Management

### Purpose
Track potential students from first contact through registration.

### Key Files
- Models: `Lead`, `FollowUp`, `Comment`, `Meeting`, `Pipeline`, `PipelineStage`
- Views: 15 view functions including multiple AJAX endpoints
- Forms: `LeadForm`, `FollowUpForm`, `CommentForm`, `MeetingForm`, `QuoteForm`
- Templates: `templates/leads/`

### Key Logic

**Lead lifecycle:**
```
New Lead (status: Interested Highly)
     ↓
Initial Contact (FollowUp created)
     ↓
Qualification (status: Qualified)
     ↓
Quote Sent (quote_amount updated)
     ↓
Registration Soon (status: Register Soon)
     ↓
Registration Created (converted)
```

**Pipeline stages:**
- Configurable pipeline stages (stored in DB)
- `is_won_stage` — marks successful conversion
- `is_lost_stage` — marks lost lead

**AJAX interactions:**
- Load lead details without page refresh
- Add comments inline
- Update quote amounts
- Get dashboard statistics

**Phone number with country code:**
```python
PHONE_CODES = [
    ('+971', 'UAE (+971)'),
    ('+966', 'Saudi Arabia (+966)'),
    # ... 200+ countries
]
```

---

## Module 10: Trainer & Company Profiles

### Purpose
Maintain PDF profiles for trainers and companies to attach to proposals.

### Key Files
- Models: `TrainerProfile`, `CompanyProfile`
- Views: CRUD functions for both
- Forms: `TrainerProfileForm`, `CompanyProfileForm`
- Templates: `templates/trainerprofile/`, `templates/companyprofile/`

### Key Logic

**Company profile deletion:**
```python
def delete_company_profile(request, pk):
    profile = get_object_or_404(CompanyProfile, pk=pk)
    if profile.company_pdf:
        os.remove(profile.company_pdf.path)  # Delete file from disk
    profile.delete()
```

---

## Module 11: Coupons

### Purpose
Create and manage discount coupon codes for course enrollments.

### Key Files
- Model: `Coupon`
- Views: `coupon_list()`, `create_coupon()`, `edit_coupon()`, `delete_coupon()`, `validate_coupon()`
- Form: `CouponForm`
- Templates: `templates/coupons/`

### Key Logic

**AJAX validation:**
```python
def validate_coupon(request):
    code = request.POST.get('code')
    try:
        coupon = Coupon.objects.get(code=code, is_active=True)
        return JsonResponse({
            'valid': True,
            'discount_percentage': str(coupon.discount_percentage)
        })
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False})
```

---

## Custom Template Filters Reference

All custom filters are in `invoices/templatetags/custom_filters.py`:

### Filters (used with `|`)

| Filter | Usage | Description |
|--------|-------|-------------|
| `multiply` | `{{ qty\|multiply:price }}` | qty × price |
| `subtract` | `{{ total\|subtract:discount }}` | total − discount |
| `add` | `{{ a\|add:b }}` | a + b |
| `divide` | `{{ total\|divide:count }}` | total ÷ count |
| `calculate_course_price` | `{{ price\|calculate_course_price:discount }}` | Apply discount + VAT |
| `get_item` | `{{ list\|get_item:0 }}` | List index access |
| `subtract_percentage` | `{{ amount\|subtract_percentage:10 }}` | amount × 0.90 |
| `add_required_attribute` | `{{ field\|add_required_attribute }}` | Add required to form field |
| `json_script` | `{{ items\|json_script }}` | Serialize invoice items to JSON |
| `quotation_json_script` | `{{ items\|quotation_json_script }}` | Serialize quotation items |

### Simple Tags (used with `{% %}`)

| Tag | Description |
|-----|-------------|
| `{% calculate_total_price registration %}` | Sum all RegistrationCourse prices |
| `{% calculate_running_due invoice ... %}` | Running balance tracker |
| `{% calculate_total_vat registration %}` | Total VAT on registration courses |

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
