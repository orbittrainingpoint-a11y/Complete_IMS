from django import forms
from django.contrib.auth.models import User
from .models import Invoice, InvoiceItem, Client, Course, InvoicePurchase, Quotation, QuotationItem, Registration, RegistrationCourse, CorporateRegistration, CourseContent, Certificate, Proposal, TrainerProfile, CompanyProfile, Coupon, CorporateCompany
from django.forms.models import inlineformset_factory
from django.forms.widgets import Select
from django.forms.models import ModelChoiceField
from django.forms import modelformset_factory
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from django.conf import settings

class InvoiceForm(forms.ModelForm):
    # Allow up to 5 decimal places; DB stores 2 (rounded in clean)
    amount_paid = forms.DecimalField(
        max_digits=12, decimal_places=5, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'min': '0'})
    )

    registration_number = forms.CharField(
        max_length=20,
        required=False,
        label='Registration Number',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_registration_number'})
    )

    company_name = forms.CharField(
        max_length=255, 
        required=False, 
        label='Company Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_company_name'})
    )
    client_name = forms.CharField(
        max_length=255,
        required=True,
        label='Client Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_client_name'})
    )
    client_emirates = forms.CharField(
        max_length=100,
        required=False,
        label='Client Emirates',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_client_emirates'})
    )
    client_country = forms.CharField(
        max_length=100,
        required=False,
        label='Client Country',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_client_country'})
    )

    class Meta:
        model = Invoice
        fields = ['registration_number', 'class_type', 'level', 'date', 'due_date', 'discount', 'amount_paid', 'number_of_person', 'status', 'payment', 'po_number']
        widgets = {
            'class_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_class_type', 'readonly': 'readonly'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_discount'}),
            # amount_paid is declared as an explicit field above with 4 decimal places

            'number_of_person': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment': forms.Select(attrs={'class': 'form-control'}),
            'po_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Pre-populate custom client fields when editing an existing invoice (GET only).
        # This ensures they render with a value so validation passes on submit.
        if self.instance and self.instance.pk and not self.data:
            client = getattr(self.instance, 'client', None)
            if client:
                self.initial.setdefault('client_name', client.name or '')
                self.initial.setdefault('client_emirates', client.emirates or '')
                self.initial.setdefault('client_country', client.country or '')
            reg = getattr(self.instance, 'registration', None)
            if reg:
                self.initial.setdefault('registration_number', reg.registration_number or '')

    def clean_amount_paid(self):
        val = self.cleaned_data.get('amount_paid')
        if val is not None:
            from decimal import Decimal, ROUND_HALF_UP
            val = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return val

    def save(self, commit=True):
        registration_number = self.cleaned_data.get('registration_number')
        if registration_number:
            registration = Registration.objects.get(registration_number=registration_number)
            if registration.registration_type == 'OC':
                corporate_registration = CorporateRegistration.objects.get(registration=registration)
                client, created = Client.objects.get_or_create(
                name=corporate_registration.company_name,
                emirates=registration.country,
                country=registration.country,
                user=self.user
            )
            else:
                client, created = Client.objects.get_or_create(
                name=registration.first_name + " " + registration.last_name,
                emirates=registration.country,  # Assuming country field is used for emirates
                country=registration.country,
                user=self.user
            )
        else:
            client_name = self.cleaned_data['client_name']
            client_emirates = self.cleaned_data['client_emirates']
            client_country = self.cleaned_data['client_country']
            client, created = Client.objects.get_or_create(
                name=client_name,
                emirates=client_emirates,
                country=client_country,
                user=self.user
            )
    
        instance = super().save(commit=False)
        instance.client = client
        instance.user = self.user
    
        if commit:
            instance.save()
        
            if registration_number:
                registration_courses = RegistrationCourse.objects.filter(registration__registration_number=registration_number)
                for reg_course in registration_courses:
                    unit_price = reg_course.course.get_rate(instance.class_type, getattr(instance, 'level', 'intermediate'))

                    InvoiceItem.objects.create(
                        invoice=instance,
                        course=reg_course.course,
                        quantity=1,  # Assuming 1 quantity per course
                        unit_price=unit_price,
                        vat_rate=0.05  # Assuming 5% VAT
                    )
    
        return instance

class PurchaseInvoiceForm(forms.ModelForm):
    client_name = forms.CharField(
        max_length=255, required=True, label='Client Name',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    client_emirates = forms.CharField(
        max_length=100, required=False, label='Client Emirates',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    client_country = forms.CharField(
        max_length=100, required=False, label='Client Country',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    client_trn = forms.CharField(
        max_length=50, required=False, label='Client TRN (for company)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 104XXXXXXXXX (if company)'}),
    )
    registration_number = forms.CharField(
        max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = InvoicePurchase
        fields = ['date', 'due_date', 'advance_amount', 'discount', 'number_of_person', 'payment', 'po_number']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'advance_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'min': '0'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_discount', 'step': 'any', 'min': '0'}),
            'number_of_person': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment': forms.Select(attrs={'class': 'form-control'}),
            'po_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        
        if commit:
            instance.save()
        return instance

class InvoiceItemForm(forms.ModelForm):
    unit_price = forms.DecimalField(
        max_digits=10, decimal_places=5, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'min': '0'})
    )

    class Meta:
        model = InvoiceItem
        fields = ['course', 'description', 'quantity', 'unit_price']

    def clean_unit_price(self):
        val = self.cleaned_data.get('unit_price')
        if val is not None:
            from decimal import Decimal, ROUND_HALF_UP
            val = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return val


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'email', 'phone', 'address', 'emirates', 'country', 'trn_number']


class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data
    
class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['client_name', 'schedule', 'training_venue', 'discount', 'consultant_position', 'consultant_name', 'consultant_number', 'consultant_email']
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control'}),
            'schedule': forms.TextInput(attrs={'class': 'form-control'}),
            'training_venue': forms.Select(attrs={'class': 'form-control'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control'}),
            'consultant_position': forms.TextInput(attrs={'class': 'form-control'}),
            'consultant_name': forms.TextInput(attrs={'class': 'form-control'}),
            'consultant_number': forms.TextInput(attrs={'class': 'form-control'}),
            'consultant_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        widgets['client'] = forms.Select(attrs={'class': 'form-control'})

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['course', 'duration', 'number_of_persons']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'number_of_persons': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.all()
        self.fields['course'].label_from_instance = lambda obj: obj.name

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = '__all__'
        exclude = ['courses' , 'discount']  # Exclude the courses field as we're handling it separately
        course = forms.ModelChoiceField(
    queryset=Course.objects.all(), 
    required=True,
    widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_course'}),
)
          # Pre-fill the consultant_name field with the user's username
        
        _p = ' '  # placeholder space — enables Bootstrap form-floating
        widgets = {
            'registration_type': forms.Select(attrs={'class': 'form-select'}),
            'class_type': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'student_status': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder': _p}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder': _p}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'passport_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'uid_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'emirates_id_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'nationality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'education': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'phone_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'alternative_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'emirates': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _p}),
            'company_or_university_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'consultant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'discount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'course' in self.fields:
            del self.fields['course']
        # Pre-fill the consultant_name field with the user's username
        if user:
            self.fields['consultant_name'].initial = user.username

class CourseSelectWidget(Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            option['attrs']['data-rate'] = value.instance.rate
        return option
    
class RegistrationCourseForm(forms.ModelForm):
    course = ModelChoiceField(
        queryset=Course.objects.all(),
        widget=CourseSelectWidget(attrs={'class': 'form-control'})
    )
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    discount = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=0)
    class Meta:
        model = RegistrationCourse
        fields = ['course', 'discount']
        widgets = {
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].label_from_instance = lambda obj: f"{obj.name}"
        self.fields['discount'].required = False

    def clean_discount(self):
        val = self.cleaned_data.get('discount')
        return val if val is not None else 0
       

class CorporateRegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = [
            'first_name', 'last_name', 'email', 'phone_no', 'alternative_no',
            'date_of_birth', 'passport_no', 'uid_no', 'emirates_id_no',
            'nationality', 'education', 'emirates', 'country', 'address',
            'company_or_university_name', 'class_type', 'level', 'date',
            'consultant_name', 'student_status',
        ]
        _p = ' '
        widgets = {
            'class_type':   forms.Select(attrs={'class': 'form-select'}),
            'level':        forms.Select(attrs={'class': 'form-select'}),
            'student_status': forms.Select(attrs={'class': 'form-select'}),
            'date':         forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder': _p}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'placeholder': _p}),
            'first_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'last_name':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'passport_no':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'uid_no':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'emirates_id_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'nationality':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'education':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'phone_no':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'alternative_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'email':        forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'emirates':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'country':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'address':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _p}),
            'company_or_university_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'consultant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['consultant_name'].initial = user.username

class CorporateDetailsForm(forms.ModelForm):
    class Meta:
        model = CorporateRegistration
        fields = ['company_name', 'company_address', 'company_location', 'company_phone', 'company_email']
        _p = ' '
        widgets = {
            'company_name':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_address':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _p}),
            'company_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_phone':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_email':    forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _p}),
        }

RegistrationCourseFormSet = inlineformset_factory(
    Registration, 
    RegistrationCourse, 
    fields=('course', 'discount'), 
    extra=1, 
    can_delete=True,
    widgets={
        'course': forms.Select(attrs={'class': 'form-control'}),
        'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    }
)
# Modify the form in the formset to make fields required
RegistrationCourseFormSet.form.base_fields['course'].required = True
RegistrationCourseFormSet.form.base_fields['discount'].required = True

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'name', 'code',
            'oo_intermediate', 'oo_professional', 'oo_advanced',
            'priv_intermediate', 'priv_professional', 'priv_advanced',
            # legacy fields hidden so existing data is preserved on save
            'batch_rate', 'online_rate', 'private_rate', 'rate',
        ]
        labels = {
            'code': 'Course Code (2-3 letters, unique)',
            'oo_intermediate':   'Intermediate',
            'oo_professional':   'Professional',
            'oo_advanced':       'Advanced',
            'priv_intermediate': 'Intermediate',
            'priv_professional': 'Professional',
            'priv_advanced':     'Advanced',
        }
        widgets = {
            'code':         forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10', 'placeholder': 'e.g., REV, ACD, PY'}),
            'batch_rate':   forms.HiddenInput(),
            'online_rate':  forms.HiddenInput(),
            'private_rate': forms.HiddenInput(),
            'rate':         forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For new courses set legacy fields to 0 so DB NOT NULL constraint is satisfied
        if not self.instance.pk:
            for f in ('batch_rate', 'online_rate', 'private_rate', 'rate'):
                self.fields[f].initial = 0
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise forms.ValidationError('Course code is required.')
        if len(code) < 2:
            raise forms.ValidationError('Course code must be at least 2 characters.')
        # Check if code already exists (excluding current instance if editing)
        if self.instance.pk:
            if Course.objects.exclude(pk=self.instance.pk).filter(code=code).exists():
                raise forms.ValidationError(f'Course code "{code}" already exists. Please use a unique code.')
        else:
            if Course.objects.filter(code=code).exists():
                raise forms.ValidationError(f'Course code "{code}" already exists. Please use a unique code.')
        return code

class CourseContentForm(forms.ModelForm):
    class Meta:
        model = CourseContent
        fields = ['title', 'file']


class CertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ['register_number', 'student_name', 'course_name', 'from_date', 'end_date', 'grade']
        widgets = {
            'from_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class KHDACertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ['register_number', 'student_name', 'course_name', 'uploaded_certificate']
    
class ProposalForm(forms.ModelForm):
    remove_logo = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = Proposal
        fields = ['client_name', 'course', 'presenter_title', 'date', 'location', 'trainer', 'logo']
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'presenter_title': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'trainer': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'logo': 'Logo (maximum size 800x300)',
        }

    trainer = forms.ModelChoiceField(queryset=TrainerProfile.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].label_from_instance = lambda obj: obj.name

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Ensure the file is a PNG image
            if not logo.name.lower().endswith('.png'):
                raise forms.ValidationError('Only PNG files are allowed.')
            
            # Open the image and check its dimensions
            img = Image.open(logo)
            width, height = img.size

            # Check if the image resolution matches 800x300
            if width != 800 or height != 300:
                raise forms.ValidationError('The logo must be 800x300 pixels in resolution.')
            
        return logo

    def save(self, commit=True):
        proposal = super().save(commit=False)
        
        if self.cleaned_data.get('remove_logo'):
            # Delete the existing logo files
            if proposal.logo:
                if os.path.isfile(proposal.logo.path):
                    os.remove(proposal.logo.path)
                proposal.logo = None
            if proposal.logo_white_url:
                white_logo_path = os.path.join(settings.MEDIA_ROOT, proposal.logo_white_url)
                if os.path.isfile(white_logo_path):
                    os.remove(white_logo_path)
                proposal.logo_white_url = ''
        elif self.cleaned_data.get('logo'):
            logo = self.cleaned_data['logo']
            
            # Save the original logo
            proposal.logo.save(logo.name, logo, save=False)
            
            # Open the image
            img = Image.open(logo)
            
            # Ensure the image is in RGBA mode
            img = img.convert('RGBA')
            
            # Create a white version of the image
            datas = img.getdata()
            newData = []
            for item in datas:
                # Change all non-transparent pixels to white
                if item[3] > 0:  # If pixel is not fully transparent
                    newData.append((255, 255, 255, item[3]))  # White with original alpha
                else:
                    newData.append(item)  # Keep fully transparent pixels as is
            
            img.putdata(newData)
            
            # Save the white image
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            
            # Create a new file name for the white version
            white_file_name = f"white_{os.path.basename(logo.name)}"
            
            # Save the white image to the proposal_logos_white/ directory
            white_logo_path = os.path.join('proposal_logos_white', white_file_name)
            white_logo_full_path = os.path.join(settings.MEDIA_ROOT, white_logo_path)
            os.makedirs(os.path.dirname(white_logo_full_path), exist_ok=True)
            
            with open(white_logo_full_path, 'wb') as f:
                f.write(buffer.getvalue())
            
            # Set the logo_white_url field
            proposal.logo_white_url = white_logo_path

        if commit:
            proposal.save()
        return proposal
    
class TrainerProfileForm(forms.ModelForm):
    class Meta:
        model = TrainerProfile
        fields = ['name', 'profile_pdf']

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'company_pdf']
class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'discount_percentage', 'expiry_date', 'max_uses', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SUMMER20'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'max_uses': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Leave blank for unlimited'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CorporateCompanyForm(forms.ModelForm):
    class Meta:
        _p = ' '
        model = CorporateCompany
        fields = [
            'company_name', 'company_email', 'company_phone',
            'company_location', 'company_address',
            'contact_name', 'contact_email', 'contact_phone', 'contact_designation',
            'consultant',
            'tax_certificate', 'trade_license', 'notes',
        ]
        widgets = {
            'company_name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_email':       forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_phone':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_location':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'company_address':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _p}),
            'contact_name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'contact_email':       forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'contact_phone':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'contact_designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _p}),
            'consultant':          forms.Select(attrs={'class': 'form-select'}),
            'notes':               forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _p}),
            'tax_certificate':     forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.webp'}),
            'trade_license':       forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['consultant'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['consultant'].required = False
        self.fields['consultant'].empty_label = '— Select Consultant —'
        if user and not self.instance.pk:
            self.fields['consultant'].initial = user
