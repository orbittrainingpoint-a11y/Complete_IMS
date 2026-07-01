from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.utils.crypto import get_random_string
from django.core.exceptions import ValidationError
import os
from django.conf import settings

class Client(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    emirates = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    trn_number = models.CharField(max_length=50, blank=True, default='', verbose_name='TRN Number')

    def __str__(self):
        return self.name

class Course(models.Model):
    name = models.CharField(max_length=255)
    batch_rate = models.DecimalField(max_digits=10, decimal_places=2)
    online_rate = models.DecimalField(max_digits=10, decimal_places=2)
    private_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    code = models.CharField(max_length=10, unique=True)


    def __str__(self):
        return self.name

def generate_invoice_number(date):
    year = date.strftime('%y')  # Last two digits of the year
    month = date.strftime('%m')  # Two-digit month

    # Get the number of existing invoices for this year and month
    count = Invoice.objects.filter(date_year=date.year, date_month=date.month).count() + 1
    return f"{year}/{month}/{count:03d}"

class Registration(models.Model):
    REGISTRATION_TYPE_CHOICES = [
        ('OT', 'Individual'),
        ('OC', 'Corporate'),
    ]

    CLASS_TYPE_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('batch', 'Batch'),
        ('private', 'private'),
    ]

    class_type = models.CharField(max_length=10, choices=CLASS_TYPE_CHOICES, default='offline')
    registration_number = models.CharField(max_length=20, unique=True, editable=False)
    registration_type = models.CharField(max_length=2, choices=REGISTRATION_TYPE_CHOICES, default='OT')
    date = models.DateField(default=timezone.now)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)  # Made optional
    passport_no = models.CharField(max_length=100, blank=True)
    uid_no = models.CharField(max_length=100, blank=True)
    emirates_id_no = models.CharField(max_length=100, blank=True)
    nationality = models.CharField(max_length=100, blank=True)  # Made optional
    education = models.CharField(max_length=100, blank=True)  # Made optional
    phone_no = models.CharField(max_length=20)
    alternative_no = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    emirates = models.CharField(max_length=100, blank=True)  # Add this line if not present
    country = models.CharField(max_length=100)
    address = models.TextField(blank=True)  # Made optional
    company_or_university_name = models.CharField(max_length=100, blank=True)  # Made optional
    consultant_name = models.CharField(max_length=100)
    courses = models.ManyToManyField(Course, through='RegistrationCourse')

    STUDENT_STATUS_CHOICES = [
        ('active', 'Active'), ('completed', 'Completed'),
        ('dropped', 'Dropped Out'), ('suspended', 'Suspended'), ('pending', 'Pending'),
    ]
    student_status = models.CharField(max_length=20, choices=STUDENT_STATUS_CHOICES, default='active')

    def save(self, *args, **kwargs):
        if not self.registration_number:
            year = timezone.now().strftime('%y')
            prefix = 'OC' if self.registration_type == 'OC' else 'OT'
            last_registration = Registration.objects.filter(
                registration_number__startswith=f"{prefix}/{year}/"
            ).order_by('-registration_number').first()

            if last_registration:
                last_number = int(last_registration.registration_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.registration_number = f"{prefix}/{year}/{new_number:03d}"
        is_new = self.pk is None
        super().save(*args, **kwargs)


    def get_course_status(self, course):
        certificate = Certificate.objects.filter(
            register_number=self.registration_number,
            course_name=course.name
        ).exists()
        return "Finished" if certificate else "In Progress"

    def __str__(self):
        return f"{self.registration_number} - {self.first_name} {self.last_name}"
    
class CorporateRegistration(models.Model):
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='corporate_details')
    company_name = models.CharField(max_length=255)
    company_address = models.TextField()
    company_location = models.CharField(max_length=255)
    company_phone = models.CharField(max_length=20)
    company_email = models.EmailField()

    def __str__(self):
        return f"Corporate Registration for {self.registration.registration_number}"
    
class Invoice(models.Model):
    FULL_PAYMENT = 'Full Payment'
    TERM_PAYMENT = 'Term Payment'
    TABBY = 'Tabby'
    TAMARA = 'Tamara'
    
    STATUS_CHOICES = [
        (FULL_PAYMENT, 'Full Payment'),
        (TERM_PAYMENT, 'Term Payment'),
        (TABBY, 'Tabby'),
        (TAMARA, 'Tamara'),
    ]


    CARD = 'Card'
    CASH = 'Cash'
    ACCOUNTTRANSFER = 'Account Transfer'
    PAYMENTLINK = 'Payment Link'
    CHEQUE = 'Cheque'

    CARD_CHOICES = [
        (CARD, 'Card'),
        (CASH, 'Cash'),
        (ACCOUNTTRANSFER, 'Account Transfer'),
        (PAYMENTLINK, 'Payment Link'),
        (CHEQUE, 'Cheque'),
    ]
    
    registration = models.ForeignKey(Registration, on_delete=models.SET_NULL, null=True, blank=True)  # Changed to ForeignKey
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)  # Keep one course field
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    class_type = models.CharField(max_length=10, choices=Registration.CLASS_TYPE_CHOICES, blank=True)
    date = models.DateField(default=datetime.date.today)  # Default to today's date
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    number_of_person = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    payment = models.CharField(max_length=20, choices=CARD_CHOICES)
    po_number = models.CharField(max_length=100, blank=True, default='')

    def calculate_total_amount(self):
        total = Decimal('0.00')
        if self.pk:  # Only calculate if the invoice has been saved
            for item in self.items.all():
                if self.class_type == 'online':
                    course_total = item.course.online_rate * item.quantity * self.number_of_person
                elif self.class_type == 'offline':
                    course_total = item.course.rate * item.quantity * self.number_of_person
                elif self.class_type == 'private':
                    course_total = item.course.private_rate * item.quantity * self.number_of_person
                elif self.class_type == 'batch':
                    course_total = item.course.batch_rate * item.quantity * self.number_of_person
                discounted_total = course_total * (1 - Decimal(self.discount) / 100)
                vat_amount = discounted_total * Decimal('0.05')
                total += discounted_total + vat_amount
        return total.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate invoice number based on current timestamp
            now = timezone.now()
            year = now.strftime('%y')
            month = now.strftime('%m')

            # Get the number of existing invoices for this year and month
            last_invoice = Invoice.objects.filter(
                invoice_number__startswith=f"{year}/{month}/"
            ).order_by('-invoice_number').first()

            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.invoice_number = f"{year}/{month}/{new_number:03d}"

        if not self.pk:
            self.total_amount = Decimal('0.00')  # Set initial total to 0
        else:
            self.total_amount = self.calculate_total_amount()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.invoice_number

    
class InvoicePurchase(models.Model):
    FULL_PAYMENT = 'Full Payment'
    TERM_PAYMENT = 'Term Payment'
    TABBY = 'Tabby'
    TAMARA = 'Tamara'
   
    STATUS_CHOICES = [
        (FULL_PAYMENT, 'Full Payment'),
        (TERM_PAYMENT, 'Term Payment'),
        (TABBY, 'Tabby'),
        (TAMARA, 'Tamara'),
    ]

    CARD = 'Card'
    CASH = 'Cash'
    ACCOUNTTRANSFER = 'Account Transfer'
    PAYMENTLINK = 'Payment Link'
    CHEQUE = 'Cheque'

    CARD_CHOICES = [
        (CARD, 'Card'),
        (CASH, 'Cash'),
        (ACCOUNTTRANSFER, 'Account Transfer'),
        (PAYMENTLINK, 'Payment Link'),
        (CHEQUE, 'Cheque'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)  # Added course field
    invoice_number = models.CharField(max_length=50, unique=True, blank=True, db_index=True)
    date = models.DateField(default=datetime.date.today)  # Default to today's date
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    number_of_person = models.IntegerField()
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    payment = models.CharField(max_length=20, choices=CARD_CHOICES)
    po_number = models.CharField(max_length=100, blank=True, default='')
    def calculate_total_amount(self):
        subtotal = Decimal('0.00')
        for item in self.purchaseitems.all():
            item_total = item.unit_price * max(item.quantity, 1) * self.number_of_person
            after_disc = item_total * (1 - Decimal(self.discount) / 100)
            subtotal += after_disc
        vat = subtotal * Decimal('0.05')
        return (subtotal + vat).quantize(Decimal('.01'))
    def save(self, *args, **kwargs):
        if not self.invoice_number:
        # Generate invoice number based on current timestamp
            now = timezone.now()
            year = now.strftime('%y')
            month = now.strftime('%m')

            # Get the number of existing invoices for this year and month
            last_invoice = InvoicePurchase.objects.filter(
                invoice_number__startswith=f"{year}/{month}/"
            ).order_by('-invoice_number').first()

            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.invoice_number = f"{year}/{month}/{new_number:03d}"
    
    # Set total_amount based on the course rate
        if self.course:
            self.total_amount = (self.course.rate * self.number_of_person) * (1 - Decimal(self.discount) / 100)
        else:
            self.total_amount = 0  # or handle it as needed
    
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number

class InvoicePurchaseItem(models.Model):
    invoice = models.ForeignKey(InvoicePurchase, related_name='purchaseitems', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True)  # Add this field
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=0.05)  # 5% VAT

    def get_subtotal(self):
        return self.quantity * self.unit_price

    def get_vat_amount(self):
        return self.get_subtotal() * self.vat_rate

    def get_total(self):
        return self.get_subtotal() + self.get_vat_amount()

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True)  # Add this field
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=0.05)  # 5% VAT
   
    def get_subtotal(self):
        return self.quantity * self.unit_price

    def get_vat_amount(self):
        return self.get_subtotal() * self.vat_rate

    def get_total(self):
        return self.get_subtotal() + self.get_vat_amount()
        
class Quotation(models.Model):
    VENUE_CHOICES = [
        ('Orbit Training (In-House)', 'Orbit Training (In-House)'),
        ('Company Premises (External)', 'Company Premises (External)'),
        ('online', 'Online'),
    ]

    quotation_number = models.CharField(max_length=20, unique=True, editable=False)
    client_name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    schedule = models.CharField(max_length=255)
    training_venue = models.CharField(max_length=50, choices=VENUE_CHOICES)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    consultant_position = models.CharField(max_length=255)
    consultant_name = models.CharField(max_length=20)
    consultant_number = models.CharField(max_length=20)
    consultant_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            now = timezone.now()
            year = now.strftime('%y')
            month = now.strftime('%m')
            
            # Get the latest quotation number for this year and month
            latest_quotation = Quotation.objects.filter(
                quotation_number__startswith=f"{year}/{month}/"
            ).order_by('-quotation_number').first()

            if latest_quotation:
                # Extract the last number and increment it
                last_number = int(latest_quotation.quotation_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.quotation_number = f"{year}/{month}/{new_number:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.quotation_number


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    duration = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    number_of_persons = models.PositiveIntegerField()


class QuotationItemOverride(models.Model):
    """Custom price per pax set by admin/sales_manager — overrides course rate on the PDF."""
    item = models.OneToOneField(QuotationItem, on_delete=models.CASCADE, related_name='price_override')
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)


class RegistrationCourse(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='registration_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('registration', 'course')


class CourseContent(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='course_contents/')
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.name} - {self.title}"
    
class Certificate(models.Model):
    register_number = models.CharField(max_length=20)
    student_name = models.CharField(max_length=100)
    course_name = models.CharField(max_length=100)
    from_date = models.DateField(null=True, blank=True)  # Made optional
    end_date = models.DateField(null=True, blank=True)   # Made optional
    grade = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)
    certificate_number = models.CharField(max_length=50, unique=True, blank=True)
    certificate_type = models.CharField(max_length=20, choices=[('regular', 'Regular'), ('khda', 'KHDA')], default='regular')
    uploaded_certificate = models.FileField(upload_to='khda_certificates/', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            course = Course.objects.filter(name=self.course_name).first()
            if course and course.code:
                course_code = course.code
            else:
                # If no course code, use first 2-3 letters of course name
                course_code = ''.join(filter(str.isalpha, self.course_name[:3])).upper()
            
            # Check if certificate already exists for this student and course
            existing = Certificate.objects.filter(
                register_number=self.register_number,
                course_name=self.course_name
            ).exists()
            
            if existing:
                # If duplicate, add a counter
                counter = 1
                while Certificate.objects.filter(
                    certificate_number=f"{course_code}{self.register_number}-{counter}"
                ).exists():
                    counter += 1
                self.certificate_number = f"{course_code}{self.register_number}-{counter}"
            else:
                self.certificate_number = f"{course_code}{self.register_number}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_name} - {self.course_name} - {self.certificate_number}"

class CertificateUpload(models.Model):
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='certificate_upload')
    certificate_file = models.FileField(upload_to='certificates/')
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate for {self.registration.registration_number}"

class FormUpload(models.Model):
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='form_upload')
    form_file = models.FileField(upload_to='registration_forms/')
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Form for {self.registration.registration_number}"
    
def validate_png(value):
    if not value.name.lower().endswith('.png'):
        raise ValidationError('Only PNG files are allowed.')
class TrainerProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    profile_pdf = models.FileField(upload_to='trainer_profiles/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class CompanyProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    company_pdf = models.FileField(upload_to='company_profiles/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    # Override the delete method to also delete the associated file
    def delete(self, *args, **kwargs):
        # Delete the file from the storage
        if self.company_pdf:
            file_path = os.path.join(settings.MEDIA_ROOT, self.company_pdf.path)
            if os.path.isfile(file_path):
                os.remove(file_path)
        # Call the original delete method
        super().delete(*args, **kwargs)
        return self.name
    
class Proposal(models.Model):
    proposal_number = models.CharField(max_length=20, unique=True, editable=False)
    client_name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    presenter_title = models.CharField(max_length=255)
    date = models.DateField(default=timezone.now)
    location = models.CharField(max_length=255)
    trainer = models.ForeignKey(TrainerProfile, on_delete=models.SET_NULL, null=True)
    logo = models.ImageField(
        upload_to='proposal_logos/',
        validators=[validate_png],
        null=True,
        blank=True
    )
    logo_white_url = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.proposal_number:
            year = timezone.now().strftime('%Y')
            last_proposal = Proposal.objects.filter(proposal_number__startswith=f'PROP-{year}-').order_by('proposal_number').last()
            if last_proposal:
                last_number = int(last_proposal.proposal_number.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            self.proposal_number = f'PROP-{year}-{new_number:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.proposal_number} - {self.client_name}"
    
class Lead(models.Model):
    STATUS_CHOICES = [
        ('Interested Highly', 'Interested Highly'),
        ('Qualified', 'Qualified'),
        ('Register Soon', 'Register Soon'),
        ('Other', 'Other'),
    ]
    FOLLOW_UP_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="Format: +XX-XXXXXXXXX")
    interested_course = models.ForeignKey(Course, on_delete=models.SET_NULL, blank=True, null=True)
    source = models.CharField(max_length=50, choices=[('Website', 'Website'), ('Referral', 'Referral'), ('Event', 'Event'), ('Other', 'Other')])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Interested Highly')
    notes = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    follow_up_status = models.CharField(max_length=20, choices=FOLLOW_UP_STATUS_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    quote_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)
    def __str__(self):
        return self.full_name

class FollowUp(models.Model):
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Rescheduled', 'Rescheduled'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='follow_ups')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contact_date = models.DateField()
    contact_time = models.TimeField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Follow-up for {self.lead.full_name} on {self.contact_date}"

class Comment(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_flagged = models.BooleanField(default=False)
    def __str__(self):
        return f"Comment by {self.user.username} on {self.lead.full_name}"
    
class Meeting(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='meetings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meetings')
    contact_date = models.DateField()
    contact_time = models.TimeField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Meeting'
        verbose_name_plural = 'Meetings'

    def __str__(self):
        return f"{self.lead.full_name} - {self.contact_date} {self.contact_time}"

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    expiry_date = models.DateField(null=True, blank=True)
    max_uses = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}%"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sales_manager', 'Sales Manager'),
        ('accounts', 'Accounts'),
        ('sales_executive', 'Sales Executive'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales_executive')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_sales_manager(self):
        return self.role == 'sales_manager'

    @property
    def is_accounts(self):
        return self.role == 'accounts'

    @property
    def is_sales_executive(self):
        return self.role == 'sales_executive'


class SalesTarget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales_targets')
    month = models.DateField()
    target_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_registrations = models.IntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='targets_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'month')

    def __str__(self):
        return f"{self.user.username} - {self.month.strftime('%b %Y')} - AED {self.target_amount}"


# Auto-create UserProfile when a User is saved (covers new users and login)
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance, defaults={'role': 'sales_executive'})


class Notification(models.Model):
    NOTIF_TYPES = [
        ('invoice_due', 'Invoice Due'),
        ('overdue_invoice', 'Overdue Invoice'),
        ('certificate_ready', 'Certificate Ready'),
        ('registration_new', 'New Registration'),
        ('target_alert', 'Target Alert'),
        ('system', 'System'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"


import secrets as _secrets

class CompanyPortalRequest(models.Model):
    """Public-facing company self-registration after a deal is closed."""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    token = models.CharField(max_length=64, unique=True, editable=False)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='company_portal_links')
    # Company details
    company_name = models.CharField(max_length=255)
    trade_license_number = models.CharField(max_length=100, blank=True)
    trade_license_doc = models.FileField(upload_to='portal/trade_license/', blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True)
    vat_certificate = models.FileField(upload_to='portal/vat/', blank=True, null=True)
    contact_person = models.CharField(max_length=150)
    designation = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    emirate = models.CharField(max_length=100, blank=True)
    # Meta
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = _secrets.token_urlsafe(40)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_name} ({self.status})"


class CompanyPortalAttendee(models.Model):
    """Training attendees added by a company after their portal registration."""
    portal_request = models.ForeignKey(CompanyPortalRequest, on_delete=models.CASCADE, related_name='attendees')
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    emirates_id = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    course_name = models.CharField(max_length=200, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} — {self.portal_request.company_name}"


class StudentFormLink(models.Model):
    """Token-based shareable link for student self-registration (no pricing shown)."""
    token = models.CharField(max_length=64, unique=True, editable=False)
    consultant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='student_form_links')
    consultant_name_locked = models.CharField(max_length=150)
    pre_selected_courses = models.ManyToManyField('Course', blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    use_count = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=300, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = _secrets.token_urlsafe(40)
        super().save(*args, **kwargs)

    def is_valid(self):
        import datetime
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
# INVOICE PAYMENT INSTALLMENTS
# ═══════════════════════════════════════════════════════════════════════════

class InvoicePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'), ('card', 'Card'), ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'), ('payment_link', 'Payment Link'), ('other', 'Other'),
    ]
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateField()
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"

    class Meta:
        ordering = ['paid_at']


# ═══════════════════════════════════════════════════════════════════════════
# TRAINING SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════

class TrainingSchedule(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'), ('ongoing', 'Ongoing'),
        ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ]
    CLASS_TYPE_CHOICES = [
        ('online', 'Online'), ('offline', 'Offline'),
        ('batch', 'Batch'), ('private', 'Private'),
    ]
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='schedules')
    title = models.CharField(max_length=200)
    class_type = models.CharField(max_length=20, choices=CLASS_TYPE_CHOICES, default='offline')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    max_capacity = models.PositiveIntegerField(default=0)
    instructor = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='schedules_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.start_date})"

    class Meta:
        ordering = ['start_date']


# ═══════════════════════════════════════════════════════════════════════════
# EXPENSE TRACKING
# ═══════════════════════════════════════════════════════════════════════════

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('venue', 'Venue / Facility'), ('materials', 'Training Materials'),
        ('instructor', 'Instructor Fee'), ('marketing', 'Marketing'),
        ('utilities', 'Utilities'), ('software', 'Software & Tools'),
        ('travel', 'Travel & Transport'), ('salary', 'Salary / Staff'),
        ('other', 'Other'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'), ('card', 'Card'), ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'), ('other', 'Other'),
    ]
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vendor = models.CharField(max_length=200, blank=True)
    expense_date = models.DateField()
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True)
    receipt_ref = models.CharField(max_length=100, blank=True)
    course = models.ForeignKey('Course', null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_with_vat(self):
        return self.amount + self.vat_amount

    def __str__(self):
        return f"{self.category}: {self.description} — AED {self.amount}"

    class Meta:
        ordering = ['-expense_date']


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Created'), ('update', 'Updated'), ('delete', 'Deleted'),
        ('payment', 'Payment Recorded'), ('status_change', 'Status Changed'),
        ('export', 'Exported'), ('login', 'Login'), ('view', 'Viewed'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=300)
    changes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Link by {self.consultant_name_locked} ({self.token[:12]}…)"


# ═══════════════════════════════════════════════════════════════════════════
# FEE REMINDER LOG
# ═══════════════════════════════════════════════════════════════════════════

class FeeReminderLog(models.Model):
    """Tracks every fee reminder sent for overdue/upcoming invoices."""
    CHANNEL_CHOICES = [
        ('system', 'System Notification'),
        ('email',  'Email'),
        ('manual', 'Manual Note'),
    ]
    invoice       = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='reminder_logs', null=True, blank=True)
    client_name   = models.CharField(max_length=200)
    invoice_number = models.CharField(max_length=50)
    amount_due    = models.DecimalField(max_digits=10, decimal_places=2)
    due_date      = models.DateField()
    days_overdue  = models.IntegerField(default=0)      # negative = days until due
    channel       = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='system')
    sent_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reminders_sent')
    note          = models.TextField(blank=True)
    sent_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Reminder for {self.invoice_number} — {self.sent_at.strftime('%d %b %Y')}"