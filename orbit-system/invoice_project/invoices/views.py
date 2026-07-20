from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.contrib.auth.decorators import login_required
from django.forms import formset_factory
from .models import Client, Invoice, InvoiceItem, InvoicePurchase, Course, Quotation, QuotationItem ,InvoicePurchaseItem, Course, Registration, RegistrationCourse, CorporateRegistration, CourseContent, Certificate, CertificateUpload, FormUpload, Proposal, TrainerProfile, CompanyProfile, Coupon, Notification, FeeReminderLog, CorporateCompany, CorporateCandidateLink
from .forms import InvoiceForm, InvoiceItemForm, ClientForm, SignUpForm, PurchaseInvoiceForm, QuotationForm, QuotationItemForm, RegistrationForm, RegistrationCourseForm, CorporateRegistrationForm, CorporateDetailsForm, RegistrationCourseFormSet, CourseForm, CourseContentForm, CertificateForm, KHDACertificateForm, ProposalForm, TrainerProfileForm, CompanyProfileForm, CouponForm, CorporateCompanyForm
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core import serializers
import json
from django.forms import inlineformset_factory
from django.contrib import messages
from django.db import transaction
from django.db.models import Q , Sum
from datetime import datetime
from django.db.models import Sum, Count
from django.utils import timezone
from django.db.models import F, ExpressionWrapper, DecimalField, Window, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST
from django.urls import reverse
import logging
from django.template.loader import render_to_string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO
from xhtml2pdf import pisa
import tempfile
from django.http import HttpResponse
from django.template.loader import get_template
import pdfkit
try:
    from weasyprint import HTML as WeasyHTML
except Exception:
    WeasyHTML = None
try:
    from PyPDF2 import PdfMerger, PdfReader
except Exception:
    PdfMerger = PdfReader = None
import io
from django.conf import settings
import os
from PIL import Image
from django.core.files.storage import default_storage
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.serializers.json import DjangoJSONEncoder
import datetime

logger = logging.getLogger(__name__)

from .models import UserProfile, SalesTarget, QuotationItemOverride, QuotationLevel, InstituteSetting, CertificationRequest, Refund
from django.contrib.auth.models import User
import calendar

def is_admin_user(user):
    try:
        return user.profile.role in ('admin',) or user.is_superuser
    except Exception:
        return user.is_superuser or hasattr(user, 'profile') and user.profile.role == 'admin'


# ══════════════════════════════════════════════════════════════════
#  CRM BRIDGE — SSO tokens + user sync
# ══════════════════════════════════════════════════════════════════
import hmac as _hmac, hashlib as _hashlib, time as _time, base64 as _b64, json as _json

_CRM_SECRET = getattr(settings, 'CRM_SSO_SECRET', 'orbit-erp-crm-sso-bridge-2024-x9q3mz')
_CRM_URL    = getattr(settings, 'CRM_URL', 'http://localhost:5000')
_ERP_URL    = getattr(settings, 'ERP_URL', 'http://localhost:8000')

def _make_sso_token(username):
    payload = _b64.urlsafe_b64encode(_json.dumps({'u': username, 't': int(_time.time())}).encode()).decode()
    sig = _hmac.new(_CRM_SECRET.encode(), payload.encode(), _hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"

def _verify_sso_token(token, max_age=90):
    try:
        payload_b64, sig = token.rsplit('.', 1)
        expected = _hmac.new(_CRM_SECRET.encode(), payload_b64.encode(), _hashlib.sha256).hexdigest()[:32]
        if not _hmac.compare_digest(sig, expected):
            return None
        data = _json.loads(_b64.urlsafe_b64decode(payload_b64 + '==').decode())
        if int(_time.time()) - data['t'] > max_age:
            return None
        return data['u']
    except Exception:
        return None

def _make_werkzeug_hash(password, iterations=260000):
    """Generate a werkzeug pbkdf2:sha256 password hash (no werkzeug dep needed)."""
    import hashlib, os, base64
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f"pbkdf2:sha256:{iterations}${salt}${base64.b64encode(dk).decode('ascii')}"

def sync_user_to_crm(user, password=None, role=None):
    """Insert or update user in Flask CRM (leads DB). Only for sales roles."""
    role_map = {'sales_manager': 'sales_manager', 'sales_executive': 'consultant'}
    crm_role = role_map.get(role)
    if not crm_role:
        return
    # sales_manager sees all leads but cannot manage users/settings
    can_view_all = 1 if crm_role in ('admin', 'sales_manager') else 0
    can_manage   = 1 if crm_role == 'admin' else 0
    try:
        import pymysql
        cfg = getattr(settings, 'CRM_DB', {})
        conn = pymysql.connect(**cfg)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM user WHERE username=%s", (user.username,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE user SET role=%s, active=1, can_view_all_leads=%s, can_manage_users=%s WHERE username=%s",
                    (crm_role, can_view_all, can_manage, user.username)
                )
            else:
                pwd_hash = _make_werkzeug_hash(password) if password else _make_werkzeug_hash(user.username)
                email = user.email or f"{user.username}@orbit.ae"
                cur.execute(
                    """INSERT INTO user
                       (username, email, password_hash, role, active, created_at,
                        can_view_all_leads, can_manage_users, can_view_reports, can_manage_courses, can_manage_settings)
                       VALUES (%s,%s,%s,%s,1,NOW(),%s,%s,0,0,0)""",
                    (user.username, email, pwd_hash, crm_role, can_view_all, can_manage)
                )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"CRM user sync skipped for {user.username}: {e}")


@login_required
def api_crm_lead_lookup(request, lead_id):
    """Fetch CRM lead name/status for the registration form live lookup."""
    import urllib.request, urllib.error
    url = f"{_CRM_URL}/api/internal/lead/{lead_id}"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {_CRM_SECRET}'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json as _json2
            data = _json2.loads(resp.read())
            return JsonResponse(data)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return JsonResponse({'error': 'Lead not found'}, status=404)
        return JsonResponse({'error': f'CRM error {e.code}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)


@login_required
def crm_jump(request):
    """Generate SSO token and redirect logged-in ERP user to CRM dashboard."""
    token = _make_sso_token(request.user.username)
    return redirect(f"{_CRM_URL}/auto-login?t={token}")


def crm_auth(request):
    """Receive SSO token from CRM and log the user into ERP."""
    token = request.GET.get('t', '')
    username = _verify_sso_token(token)
    if not username:
        messages.error(request, 'Invalid or expired CRM session link. Please log in.')
        return redirect('login')
    try:
        erp_user = User.objects.get(username=username, is_active=True)
        erp_user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, erp_user)
        # If coming from a "Register in ERP" button on a CRM lead, go straight to the form.
        # The CRM encodes params as separate URL args (fn, ln, ph, em, ci, crm_id) because the
        # next= value isn't URL-encoded by the Flask side — rebuild the full register URL here.
        crm_id = request.GET.get('crm_id', '').strip()
        if crm_id and crm_id.isdigit():
            from urllib.parse import urlencode
            reg_params = {'crm_id': crm_id}
            for key in ('fn', 'ln', 'ph', 'em', 'ci'):
                val = request.GET.get(key, '').strip()
                if val:
                    reg_params[key] = val
            return redirect(f'/register/?{urlencode(reg_params)}')
        next_url = request.GET.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('orbit_dashboard')
    except User.DoesNotExist:
        messages.error(request, f'User "{username}" not found in ERP.')
        return redirect('login')

def get_user_role(user):
    try:
        return user.profile.role
    except Exception:
        return 'sales_executive'


def _save_reg_crm_link(registration_id, crm_lead_id, linked_by=''):
    """Save or update registration → CRM lead link, then auto-convert the CRM lead."""
    import pymysql
    try:
        conn = pymysql.connect(
            host='localhost', user='root', password='',
            database='orbit_invoice', charset='utf8mb4'
        )
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO invoices_registrationcrmlink
                       (registration_id, crm_lead_id, linked_by, linked_at)
                   VALUES (%s, %s, %s, NOW())
                   ON DUPLICATE KEY UPDATE crm_lead_id=%s, linked_by=%s, linked_at=NOW()""",
                (registration_id, crm_lead_id, linked_by, crm_lead_id, linked_by)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"CRM link save failed for reg {registration_id}: {e}")

    # Auto-convert the CRM lead to "Converted" status in the leads DB
    try:
        import pymysql as _pym
        crm_conn = _pym.connect(
            host='localhost', user='root', password='',
            database='leads', charset='utf8mb4'
        )
        with crm_conn.cursor() as cur:
            cur.execute(
                """UPDATE lead
                   SET status='Converted', last_contact_date=CURDATE()
                   WHERE id=%s AND status NOT IN ('Converted', 'Lost')""",
                (crm_lead_id,)
            )
        crm_conn.commit()
        crm_conn.close()
    except Exception as e:
        logger.warning(f"CRM lead auto-convert failed for lead {crm_lead_id}: {e}")


def sync_registration_to_crm(registration, consultant_username=None):
    """Sync an IMS Registration to the CRM leads.ims_student table."""
    import pymysql, json as _j
    try:
        courses = list(
            registration.registration_courses
            .select_related('course')
            .values_list('course__name', 'price')
        )
        course_names = [c[0] for c in courses]
        total_fee = sum(float(c[1]) for c in courses if c[1])

        # Look up CRM lead link from orbit_invoice
        crm_lead_id = None
        try:
            ims_conn = pymysql.connect(
                host='localhost', user='root', password='',
                database='orbit_invoice', charset='utf8mb4'
            )
            with ims_conn.cursor() as cur:
                cur.execute(
                    "SELECT crm_lead_id FROM invoices_registrationcrmlink WHERE registration_id=%s",
                    (registration.pk,)
                )
                row = cur.fetchone()
                if row:
                    crm_lead_id = row[0]
            ims_conn.close()
        except Exception:
            pass

        cfg = getattr(settings, 'CRM_DB', {})
        conn = pymysql.connect(**cfg)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ims_student WHERE ims_registration_id=%s", (registration.pk,))
            existing = cur.fetchone()
            data = (
                registration.first_name,
                registration.last_name or '',
                registration.phone_no,
                registration.email,
                registration.country or '',
                registration.student_status or 'active',
                registration.date,
                registration.registration_type or 'OT',
                getattr(registration, 'class_type', ''),
                _j.dumps(course_names),
                round(total_fee, 2),
                registration.consultant_name or '',
                consultant_username or '',
                registration.registration_number or '',
                crm_lead_id,
            )
            if existing:
                cur.execute("""
                    UPDATE ims_student SET
                        first_name=%s, last_name=%s, phone=%s, email=%s, country=%s,
                        student_status=%s, registration_date=%s, registration_type=%s,
                        class_type=%s, courses_json=%s, total_fee=%s,
                        consultant_name=%s, consultant_username=%s,
                        registration_number=%s, lead_crm_id=%s, updated_at=NOW()
                    WHERE ims_registration_id=%s
                """, data + (registration.pk,))
            else:
                cur.execute("""
                    INSERT INTO ims_student
                        (first_name, last_name, phone, email, country, student_status,
                         registration_date, registration_type, class_type, courses_json,
                         total_fee, consultant_name, consultant_username,
                         registration_number, lead_crm_id, ims_registration_id, synced_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                """, data + (registration.pk,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"CRM student sync failed for reg {getattr(registration, 'pk', '?')}: {e}")

def _get_greeting():
    h = datetime.datetime.now().hour
    if h < 12:
        return 'morning'
    elif h < 17:
        return 'afternoon'
    return 'evening'


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')  # Redirect to the login page after logout


@user_passes_test(is_admin_user)
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            raw_password = form.cleaned_data['password']
            user.set_password(raw_password)
            user.save()
            # Assign role from form if provided, default to sales_executive
            role = request.POST.get('role', 'sales_executive')
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            # Sync to CRM for sales roles (with actual password so SSO works immediately)
            if role in ('sales_manager', 'sales_executive'):
                sync_user_to_crm(user, password=raw_password, role=role)
            # If admin created this user, stay on manage_users; otherwise redirect to dashboard
            if request.user.is_authenticated:
                messages.success(request, f"User '{user.username}' created with role '{role}'.")
                return redirect('manage_users')
            else:
                authenticated = authenticate(username=user.username, password=raw_password)
                login(request, authenticated)
                return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form, 'roles': UserProfile.ROLE_CHOICES if hasattr(UserProfile, 'ROLE_CHOICES') else []})




@login_required
def dashboard(request):
    inv_qs = Invoice.objects.select_related(
        'client', 'registration', 'user'
    ).prefetch_related('items__course').order_by('-id')

    pur_qs = InvoicePurchase.objects.select_related(
        'client', 'user'
    ).prefetch_related('purchaseitems__course').order_by('-id')

    invoice_number    = request.GET.get('invoice_number', '')
    registration_number = request.GET.get('registration_number', '')
    name              = request.GET.get('name', '')
    due_date          = request.GET.get('due_date', '')
    payment_status    = request.GET.get('payment_status', '')
    inv_page          = request.GET.get('inv_page', 1)
    pur_page          = request.GET.get('pur_page', 1)

    if invoice_number:
        inv_qs = inv_qs.filter(invoice_number__icontains=invoice_number)
        pur_qs = pur_qs.filter(invoice_number__icontains=invoice_number)
    if registration_number:
        inv_qs = inv_qs.filter(registration__registration_number__icontains=registration_number)
    if name:
        inv_qs = inv_qs.filter(
            Q(client__name__icontains=name) |
            Q(registration__first_name__icontains=name) |
            Q(registration__last_name__icontains=name)
        )
        pur_qs = pur_qs.filter(client__name__icontains=name)
    if due_date:
        inv_qs = inv_qs.filter(due_date=due_date)
        pur_qs = pur_qs.filter(due_date=due_date)
    if payment_status:
        inv_qs = inv_qs.filter(status=payment_status)
        pur_qs = pur_qs.filter(status=payment_status)

    inv_paginator  = Paginator(inv_qs, 25)
    pur_paginator  = Paginator(pur_qs, 25)
    invoices       = inv_paginator.get_page(inv_page)
    purchase_invoices = pur_paginator.get_page(pur_page)

    for invoice in invoices:
        invoice.items_json = json.dumps([
            {
                'course_name': item.course.name if item.course else '',
                'unit_price': float(item.unit_price),
                'quantity': item.quantity,
                'vat_rate': float(item.vat_rate),
            } for item in invoice.items.all()
        ])
    for pi in purchase_invoices:
        pi.items_json = json.dumps([
            {
                'course_name': item.course.name if item.course else '',
                'unit_price': float(item.unit_price),
                'quantity': item.quantity,
                'vat_rate': float(item.vat_rate),
            } for item in pi.purchaseitems.all()
        ])

    return render(request, 'invoices/dashboard.html', {
        'invoices': invoices,
        'purchase_invoices': purchase_invoices,
        'inv_paginator': inv_paginator,
        'pur_paginator': pur_paginator,
        'invoice_number': invoice_number,
        'registration_number': registration_number,
        'name': name,
        'due_date': due_date,
        'payment_status': payment_status,
        'today': timezone.now().date(),
    })
    

@login_required
def create_invoice(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            
            # Get the registration number from the form
            registration_number = form.cleaned_data.get('registration_number')
            if registration_number:
                try:
                    registration = Registration.objects.get(registration_number=registration_number)
                    invoice.registration = registration
                    invoice.class_type = registration.class_type  # Set the class_type from registration
                    if registration.registration_type == 'OC':
                        corporate_details = CorporateRegistration.objects.get(registration=registration)
                        _client_qs = Client.objects.filter(
                            name=corporate_details.company_name,
                            user=request.user,
                        )
                        if _client_qs.exists():
                            invoice.client = _client_qs.first()
                        else:
                            invoice.client = Client.objects.create(
                                name=corporate_details.company_name,
                                user=request.user,
                                email=corporate_details.company_email or registration.email or '',
                                phone=corporate_details.company_phone or registration.phone_no or '',
                                address=corporate_details.company_address or '',
                                emirates=corporate_details.company_location or '',
                                country=registration.country or '',
                            )
                    else:
                        _client_name = f"{registration.first_name} {registration.last_name}"
                        _client_qs = Client.objects.filter(
                            name=_client_name,
                            user=request.user,
                        )
                        if _client_qs.exists():
                            invoice.client = _client_qs.first()
                        else:
                            invoice.client = Client.objects.create(
                                name=_client_name,
                                user=request.user,
                                email=registration.email or '',
                                phone=registration.phone_no or '',
                                address='',
                                emirates=registration.country or '',
                                country=registration.country or '',
                            )
                except Registration.DoesNotExist:
                    form.add_error('registration_number', 'Invalid registration number')
                    return render(request, 'invoices/create_invoice.html', {'form': form})
            
            # Save the invoice first with an initial total of 0
            invoice.save()
            
            # Handle course items
            for key, value in request.POST.items():
                if key.startswith('course_'):
                    course_id = value
                    quantity_key = f"quantity_{course_id}"
                    quantity = int(request.POST.get(quantity_key, 1))
                    
                    course = Course.objects.get(id=course_id)
                    
                    unit_price = course.get_rate(invoice.class_type, request.POST.get('level', 'intermediate'))
                    
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        course=course,
                        quantity=quantity,
                        unit_price=unit_price,
                        vat_rate=Decimal('0.05')
                    )
            
            # Recalculate total amount after adding items and save again
            invoice.total_amount = invoice.calculate_total_amount()
            invoice.save()

            # Auto-notify admins about new invoice (N1)
            try:
                from .models import Notification
                from django.contrib.auth.models import User as AuthUser
                admin_users = AuthUser.objects.filter(
                    profile__role__in=['admin', 'accounts']
                ).exclude(id=request.user.id)
                for admin in admin_users:
                    Notification.objects.create(
                        recipient=admin,
                        notif_type='system',
                        title=f"New Invoice: {invoice.invoice_number}",
                        message=f"Invoice {invoice.invoice_number} created for {invoice.client.name} — AED {invoice.total_amount:.0f}",
                        link="/dashboard/"
                    )
            except Exception:
                pass

            return redirect('dashboard')
    else:
        form = InvoiceForm(user=request.user)
    # Pre-fill registration number if passed from student/corporate dashboard
    prefill_reg = request.GET.get('reg', '')
    return render(request, 'invoices/create_invoice.html', {'form': form, 'prefill_reg': prefill_reg})


@login_required
def create_purchase_invoice(request):
    if request.method == 'POST':
        form = PurchaseInvoiceForm(request.POST, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            invoice.status = 'Full Payment'

            registration_number = form.cleaned_data.get('registration_number')
            client_name = form.cleaned_data.get('client_name', '').strip()
            client_emirates = form.cleaned_data.get('client_emirates', '')
            client_country = form.cleaned_data.get('client_country', '')
            client_trn = form.cleaned_data.get('client_trn', '')

            if registration_number:
                try:
                    registration = Registration.objects.get(registration_number=registration_number)
                    invoice.registration = registration

                    if registration.registration_type == 'OC':
                        corporate_details = CorporateRegistration.objects.get(registration=registration)
                        client_name = corporate_details.company_name
                    else:
                        client_name = f"{registration.first_name} {registration.last_name}"

                    invoice.client, created = Client.objects.get_or_create(
                        name=client_name,
                        email=registration.email,
                        phone=registration.phone_no,
                        user=request.user,
                        defaults={
                            'emirates': client_emirates or registration.emirates,
                            'country': client_country or registration.country,
                            'trn_number': client_trn,
                        }
                    )
                    if not created and client_trn:
                        invoice.client.trn_number = client_trn
                        invoice.client.save()
                except Registration.DoesNotExist:
                    form.add_error('registration_number', 'Invalid registration number')
                    return render(request, 'invoices/create_purchase_invoice.html', {'form': form})
            else:
                # Corporate mode or manual entry — create/get client from form fields
                invoice.client, created = Client.objects.get_or_create(
                    name=client_name,
                    user=request.user,
                    defaults={
                        'emirates': client_emirates,
                        'country': client_country,
                        'trn_number': client_trn,
                    }
                )
                if not created and client_trn:
                    invoice.client.trn_number = client_trn
                    invoice.client.save()

            invoice.save()
            
            # Handle course items
            for key, value in request.POST.items():
                if key.startswith('course_'):
                    course_id = value
                    quantity = int(request.POST.get(f'quantity_{course_id}', 1))
                    course = Course.objects.get(id=course_id)
                    custom_price = request.POST.get(f'unit_price_{course_id}')
                    unit_price = Decimal(custom_price) if custom_price else (course.rate or Decimal('0'))
                    description = request.POST.get(f'description_{course_id}', '')
                    InvoicePurchaseItem.objects.create(
                        invoice=invoice,
                        course=course,
                        quantity=quantity,
                        unit_price=unit_price,
                        description=description,
                        vat_rate=Decimal('0.05'),
                    )
            
            # Recalculate total amount after adding items and save again
            invoice.total_amount = invoice.calculate_total_amount()
            invoice.save()
            
            
            return redirect('dashboard')
        else:
            print("Form is invalid")
            print(form.errors)
    else:
        form = PurchaseInvoiceForm(user=request.user)
        
    return render(request, 'invoices/create_purchase_invoice.html', {'form': form})

@login_required
def add_invoice_items(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.method == 'POST':
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            invoice_item = form.save(commit=False)
            invoice_item.invoice = invoice
            # Calculate the total amount
            invoice_item.total = invoice_item.quantity * invoice_item.price
            invoice_item.save()
            return redirect('dashboard')  # Redirect after adding items, adjust as needed
    else:
        form = InvoiceItemForm()
    return render(request, 'invoices/add_invoice_items.html', {'form': form, 'invoice': invoice})

@login_required
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)

    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, user=request.user)
        if form.is_valid():
            # form.save(commit=False) sets amount_paid, status, payment, dates, etc.
            # and creates/gets the client from client_name/emirates/country fields.
            invoice = form.save(commit=False)

            # Link registration if provided
            registration_number = form.cleaned_data.get('registration_number', '').strip()
            if registration_number:
                try:
                    registration = Registration.objects.get(registration_number=registration_number)
                    invoice.registration = registration
                    invoice.class_type = registration.class_type
                except Registration.DoesNotExist:
                    form.add_error('registration_number', 'Registration number not found.')
                    return render(request, 'invoices/edit_invoice.html', {'form': form, 'invoice': invoice})

            invoice.save()

            # Rebuild invoice items from posted course_* fields
            invoice.items.all().delete()
            for key, value in request.POST.items():
                if key.startswith('course_') and value:
                    try:
                        course = Course.objects.get(id=int(value))
                        quantity = max(1, int(request.POST.get(f'quantity_{value}', 1)))
                        unit_price = course.get_rate(invoice.class_type, request.POST.get('level', 'intermediate'))
                        InvoiceItem.objects.create(
                            invoice=invoice, course=course,
                            quantity=quantity, unit_price=unit_price,
                            vat_rate=Decimal('0.05')
                        )
                    except (Course.DoesNotExist, ValueError):
                        pass

            invoice.total_amount = invoice.calculate_total_amount()
            invoice.save()
            return redirect('dashboard')
        # form invalid — fall through to re-render with errors
    else:
        form = InvoiceForm(instance=invoice, user=request.user)

    # Sum paid on OTHER invoices for the same registration (excluding this one)
    other_invoices_paid = 0.0
    if invoice.registration_id:
        from django.db.models import Sum as _Sum
        other_paid = Invoice.objects.filter(
            registration_id=invoice.registration_id
        ).exclude(pk=invoice.pk).aggregate(t=_Sum('amount_paid'))['t']
        other_invoices_paid = float(other_paid or 0)

    return render(request, 'invoices/edit_invoice.html', {
        'form': form,
        'invoice': invoice,
        'other_invoices_paid': other_invoices_paid,
    })


@user_passes_test(is_admin_user)
def delete_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        return redirect('dashboard')
    return render(request, 'invoices/delete_invoice.html', {'invoice': invoice})



@login_required
def edit_purchase_invoice(request, invoice_id):
    invoice = get_object_or_404(InvoicePurchase, pk=invoice_id)

    if request.method == 'POST':
        form = PurchaseInvoiceForm(request.POST, instance=invoice, user=request.user)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user

            # Get registration details if provided
            registration_number = form.cleaned_data.get('registration_number')
            if registration_number:
                try:
                    registration = Registration.objects.get(registration_number=registration_number)
                    invoice.registration = registration

                    # Get client details
                    client_name = form.cleaned_data.get('client_name')
                    client_emirates = form.cleaned_data.get('client_emirates')
                    client_country = form.cleaned_data.get('client_country')

                    if registration.registration_type == 'OC':
                        corporate_details = CorporateRegistration.objects.get(registration=registration)
                        client_name = corporate_details.company_name
                    else:
                        client_name = f"{registration.first_name} {registration.last_name}"

                    invoice.client, _ = Client.objects.get_or_create(
                        name=client_name,
                        email=registration.email,
                        phone=registration.phone_no,
                        user=request.user,
                        emirates=client_emirates or registration.emirates,
                        country=client_country or registration.country
                    )
                except Registration.DoesNotExist:
                    messages.error(request, 'Invalid registration number.')
                    return render(request, 'invoices/edit_purchase_invoice.html', {
                        'form': form,
                        'invoice': invoice,
                        'courses': Course.objects.all()
                    })

            invoice.save()

            # Clear existing invoice items
            invoice.purchaseitems.all().delete()

            # Handle all courses from the form
            for key, value in request.POST.items():
                if key.startswith('course_'):
                    course_id = value
                    quantity_key = f"quantity_{course_id}"
                    quantity = request.POST.get(quantity_key, 1)

                    try:
                        course = Course.objects.get(id=course_id)
                        InvoicePurchaseItem.objects.create(
                            invoice=invoice,
                            course=course,
                            quantity=int(quantity),
                            unit_price=course.rate
                        )
                    except Course.DoesNotExist:
                        messages.error(request, f"Course with ID {course_id} not found.")
                        continue

            # Recalculate total amount after adding items
            invoice.total_amount = invoice.calculate_total_amount()
            invoice.save()

            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
            print(form.errors)
    else:
        form = PurchaseInvoiceForm(instance=invoice, user=request.user)
        courses = Course.objects.all()

    return render(request, 'invoices/edit_purchase_invoice.html', {
        'form': form,
        'invoice': invoice,
        'courses': courses
    })


@user_passes_test(is_admin_user)
def delete_purchase_invoice(request, pk):
    invoice = get_object_or_404(InvoicePurchase, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        return redirect('dashboard')
    return render(request, 'invoices/delete_purchase_invoice.html', {'invoice': invoice})


def _resolve_coupon(code):
    """Return (Coupon|None, discount_percentage) for a coupon code string."""
    from django.utils import timezone as tz
    code = (code or '').strip().upper()
    if not code:
        return None, Decimal('0.00')
    try:
        c = Coupon.objects.get(code=code, is_active=True)
        if c.expiry_date and c.expiry_date < tz.now().date():
            return None, Decimal('0.00')
        if c.max_uses and c.used_count >= c.max_uses:
            return None, Decimal('0.00')
        return c, c.discount_percentage
    except Coupon.DoesNotExist:
        return None, Decimal('0.00')


def _course_discount_cap(base_cap, coupon_code):
    """Return (max_allowed_discount, coupon_obj) — extends base_cap by a valid coupon's percentage."""
    coupon_obj, coupon_extra = _resolve_coupon(coupon_code)
    max_allowed = min(base_cap + coupon_extra, Decimal('100.00'))
    return max_allowed, coupon_obj


def _mark_coupon_used(coupon_obj):
    if coupon_obj:
        coupon_obj.used_count += 1
        coupon_obj.save(update_fields=['used_count'])


def _can_custom_quote(user):
    try:
        role = user.profile.role
        return role in ('admin', 'sales_manager') or user.is_superuser
    except Exception:
        return user.is_superuser


@login_required
def create_quotation(request):
    from decimal import Decimal, InvalidOperation
    QuotationItemFormSet = formset_factory(QuotationItemForm, extra=1)
    courses_json = json.dumps(
        list(Course.objects.values(
            'id', 'name',
            'oo_intermediate', 'oo_professional', 'oo_advanced',
            'priv_intermediate', 'priv_professional', 'priv_advanced',
            'rate', 'online_rate', 'private_rate', 'batch_rate',
        )),
        default=float
    )

    if request.method == 'POST':
        quotation_form = QuotationForm(request.POST)
        item_formset = QuotationItemFormSet(request.POST)
        is_custom = request.POST.get('is_custom_quotation') == '1' and _can_custom_quote(request.user)

        if quotation_form.is_valid() and item_formset.is_valid():
            quotation = quotation_form.save(commit=False)
            quotation.user = request.user

            # Discount cap enforcement for sales executives
            role = get_user_role(request.user)
            if role == 'sales_executive':
                item_count = sum(
                    1 for f in item_formset
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                )
                base_cap = Decimal('30.00') if item_count >= 2 else Decimal('20.00')
                coupon_obj, coupon_extra = _resolve_coupon(request.POST.get('coupon_code', ''))
                max_allowed = min(base_cap + coupon_extra, Decimal('100.00'))
                if quotation.discount > max_allowed:
                    quotation.discount = max_allowed
                quotation.coupon = coupon_obj
                if coupon_obj:
                    coupon_obj.used_count += 1
                    coupon_obj.save(update_fields=['used_count'])
            else:
                coupon_obj, _ = _resolve_coupon(request.POST.get('coupon_code', ''))
                quotation.coupon = coupon_obj

            quotation.save()

            # Save pricing level
            _level = request.POST.get('quot_level', 'intermediate')
            if _level not in ('intermediate', 'professional', 'advanced'):
                _level = 'intermediate'
            QuotationLevel.objects.create(quotation=quotation, level=_level)

            for i, form in enumerate(item_formset):
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    item = form.save(commit=False)
                    item.quotation = quotation
                    item.save()
                    if is_custom:
                        raw = request.POST.get(f'custom_price_{i}', '').strip()
                        try:
                            price = Decimal(raw)
                            if price > 0:
                                QuotationItemOverride.objects.create(item=item, custom_price=price)
                        except Exception:
                            pass

            return redirect('quotation_dashboard')
    else:
        quotation_form = QuotationForm()
        item_formset = QuotationItemFormSet()

    return render(request, 'quotation/create_quotation.html', {
        'quotation_form': quotation_form,
        'item_formset': item_formset,
        'courses_json': courses_json,
    })


@login_required
def quotation_detail(request, pk):
    from decimal import Decimal as _Dec
    quotation = get_object_or_404(Quotation, pk=pk)
    venue = quotation.training_venue

    def _fmt(val):
        return f"{float(val):,.2f}"

    # Resolve pricing level
    try:
        level = quotation.level_info.level
    except Exception:
        level = 'intermediate'

    # Map venue to class_type for get_rate()
    if venue == 'online':
        class_type = 'online'
    elif venue == 'Company Premises (External)':
        class_type = 'private'
    else:
        class_type = 'offline'

    LEVEL_LABELS = {'intermediate': 'Intermediate', 'professional': 'Professional', 'advanced': 'Advanced'}
    level_display = LEVEL_LABELS.get(level, 'Intermediate')

    items_data = []
    subtotal = _Dec('0')
    pax_set = set()

    for item in quotation.items.select_related('course'):
        course = item.course
        rate = None
        try:
            rate = item.price_override.custom_price
        except Exception:
            pass
        if rate is None:
            rate = course.get_rate(class_type, level)

        line_total = rate * item.number_of_persons
        subtotal += line_total
        pax_set.add(item.number_of_persons)

        items_data.append({
            'course_name': course.name,
            'duration': item.duration,
            'fee_per_pax_fmt': _fmt(rate),
            'pax': item.number_of_persons,
            'line_total_fmt': _fmt(line_total),
        })

    discount_pct = quotation.discount or _Dec('0')
    discount_amount = subtotal * discount_pct / 100
    final_total = subtotal - discount_amount

    training_mode_labels = {
        'Orbit Training (In-House)': 'In-House Training',
        'Company Premises (External)': 'On-Site Training',
        'online': 'Online Training',
    }
    training_mode_display = training_mode_labels.get(venue, venue)

    if len(pax_set) == 1:
        participants_display = f"{next(iter(pax_set))} Pax"
    elif pax_set:
        participants_display = "Varies per course"
    else:
        participants_display = "—"

    return render(request, 'quotation/quotation_detail.html', {
        'quotation': quotation,
        'items_data': items_data,
        'subtotal_fmt': _fmt(subtotal),
        'discount_amount_fmt': _fmt(discount_amount),
        'final_total_fmt': _fmt(final_total),
        'participants_display': participants_display,
        'training_mode_display': training_mode_display,
        'venue_label': quotation.get_training_venue_display(),
        'level_display': level_display,
    })


@login_required
def quotation_dashboard(request):
    qs = Quotation.objects.prefetch_related('items__course').order_by('-id')
    q_number    = request.GET.get('q_number', '')
    client_name = request.GET.get('client_name', '')
    consultant  = request.GET.get('consultant', '')
    if q_number:
        qs = qs.filter(quotation_number__icontains=q_number)
    if client_name:
        qs = qs.filter(client_name__icontains=client_name)
    if consultant:
        qs = qs.filter(consultant_name__icontains=consultant)

    paginator = Paginator(qs, 25)
    quotations = paginator.get_page(request.GET.get('page', 1))

    for quotation in quotations:
        quotation.items_json = json.dumps([
            {
                'course_name': item.course.name,
                'rate': float(item.course.rate),
                'duration': float(item.duration),
                'number_of_persons': float(item.number_of_persons),
            } for item in quotation.items.all()
        ])
    return render(request, 'quotation/quotation_dashboard.html', {
        'quotations': quotations,
        'paginator': paginator,
        'q_number': q_number,
        'client_name': client_name,
        'consultant': consultant,
    })

@login_required
def edit_quotation(request, pk):
    from decimal import Decimal, InvalidOperation
    quotation = get_object_or_404(Quotation, pk=pk)
    QuotationItemFormSet = formset_factory(QuotationItemForm, extra=0)
    courses_json = json.dumps(
        list(Course.objects.values(
            'id', 'name',
            'oo_intermediate', 'oo_professional', 'oo_advanced',
            'priv_intermediate', 'priv_professional', 'priv_advanced',
            'rate', 'online_rate', 'private_rate', 'batch_rate',
        )),
        default=float
    )
    initial_custom = {}
    has_custom = False

    if request.method == 'POST':
        quotation_form = QuotationForm(request.POST, instance=quotation)
        is_custom = request.POST.get('is_custom_quotation') == '1' and _can_custom_quote(request.user)
        try:
            item_formset = QuotationItemFormSet(request.POST, prefix='items')
            formset_valid = item_formset.is_valid()
        except Exception:
            item_formset = QuotationItemFormSet(prefix='items', initial=[
                {'course': it.course, 'duration': it.duration, 'number_of_persons': it.number_of_persons}
                for it in quotation.items.select_related('course')
            ])
            formset_valid = False

        if quotation_form.is_valid() and formset_valid:
            try:
                with transaction.atomic():
                    quotation = quotation_form.save(commit=False)

                    # Discount cap enforcement for sales executives
                    role = get_user_role(request.user)
                    if role == 'sales_executive':
                        item_count = sum(
                            1 for f in item_formset
                            if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                        )
                        base_cap = Decimal('30.00') if item_count >= 2 else Decimal('20.00')
                        coupon_obj, coupon_extra = _resolve_coupon(request.POST.get('coupon_code', ''))
                        max_allowed = min(base_cap + coupon_extra, Decimal('100.00'))
                        if quotation.discount > max_allowed:
                            quotation.discount = max_allowed
                        # Release previous coupon FK before re-assigning
                        old_coupon = quotation.coupon
                        quotation.coupon = coupon_obj
                        if coupon_obj and coupon_obj != old_coupon:
                            coupon_obj.used_count += 1
                            coupon_obj.save(update_fields=['used_count'])
                    else:
                        coupon_obj, _ = _resolve_coupon(request.POST.get('coupon_code', ''))
                        quotation.coupon = coupon_obj

                    quotation.save()

                    # Save/update pricing level
                    _edit_level = request.POST.get('quot_level', 'intermediate')
                    if _edit_level not in ('intermediate', 'professional', 'advanced'):
                        _edit_level = 'intermediate'
                    QuotationLevel.objects.update_or_create(
                        quotation=quotation, defaults={'level': _edit_level}
                    )

                    from django.db import connection
                    with connection.cursor() as cur:
                        # Delete overrides first — DB FK is RESTRICT so items can't be
                        # deleted while override rows still reference them.
                        cur.execute(
                            "DELETE o FROM invoices_quotationitemoverride o "
                            "INNER JOIN invoices_quotationitem i ON i.id = o.item_id "
                            "WHERE i.quotation_id = %s",
                            [quotation.id]
                        )
                        cur.execute(
                            "DELETE FROM invoices_quotationitem WHERE quotation_id = %s",
                            [quotation.id]
                        )

                    for i, form in enumerate(item_formset):
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            item = form.save(commit=False)
                            item.quotation = quotation
                            item.save()
                            if is_custom:
                                raw = request.POST.get(f'custom_price_{i}', '').strip()
                                try:
                                    price = Decimal(raw)
                                    if price > 0:
                                        QuotationItemOverride.objects.create(item=item, custom_price=price)
                                except Exception:
                                    pass

                return redirect('quotation_dashboard')
            except Exception as exc:
                import traceback as _tb, sys as _sys
                logger.error("edit_quotation POST error pk=%s: %s", pk, _tb.format_exc())
                print(f"ORBIT_ERP edit_quotation ERROR pk={pk}:\n{_tb.format_exc()}", file=_sys.stderr, flush=True)
                messages.error(request, f"Update failed: {type(exc).__name__}: {exc}")
    else:
        existing_items = list(quotation.items.select_related('course'))
        initial_custom = {}
        try:
            current_level = quotation.level_info.level
        except Exception:
            current_level = 'intermediate'
        for i, item in enumerate(existing_items):
            try:
                initial_custom[i] = float(item.price_override.custom_price)
            except Exception:
                pass
        has_custom = bool(initial_custom)

        quotation_form = QuotationForm(instance=quotation)
        item_formset = QuotationItemFormSet(prefix='items', initial=[
            {'course': item.course, 'duration': item.duration, 'number_of_persons': item.number_of_persons}
            for item in existing_items
        ])

    return render(request, 'quotation/edit_quotation.html', {
        'quotation_form': quotation_form,
        'item_formset': item_formset,
        'courses_json': courses_json,
        'initial_custom': json.dumps({str(k): v for k, v in initial_custom.items()}),
        'initial_is_custom': has_custom,
        'quotation': quotation,
        'current_level': locals().get('current_level', 'intermediate'),
    })


@user_passes_test(is_admin_user)
def delete_quotation(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    
    if request.method == 'POST':
        quotation.delete()
        return redirect('quotation_dashboard')
    
    return render(request, 'quotation/delete_quotation.html', {'quotation': quotation})

@login_required
def registration_form(request):
    RegistrationCourseFormSet = formset_factory(RegistrationCourseForm, extra=1)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, user=request.user)
        formset = RegistrationCourseFormSet(request.POST, prefix='form')

        if form.is_valid() and formset.is_valid():
            registration = form.save()
            valid_course_forms = [
                f for f in formset
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False) and f.cleaned_data.get('course')
            ]
            base_cap = Decimal('30') if len(valid_course_forms) >= 2 else Decimal('20')
            for course_form in valid_course_forms:
                course = course_form.cleaned_data['course']
                max_allowed, coupon_obj = _course_discount_cap(base_cap, course_form.cleaned_data.get('coupon_code', ''))
                discount = min(course_form.cleaned_data.get('discount') or Decimal('0'), max_allowed)
                price = course_form.cleaned_data.get('price', 0)
                RegistrationCourse.objects.create(
                    registration=registration,
                    course=course,
                    discount=discount,
                    price=price,
                )
                _mark_coupon_used(coupon_obj)
            # Save CRM lead link if provided
            crm_lead_id = request.POST.get('crm_lead_id', '').strip()
            if crm_lead_id and crm_lead_id.isdigit():
                _save_reg_crm_link(registration.pk, int(crm_lead_id), request.user.username)

            # Sync to CRM student list
            sync_registration_to_crm(registration, consultant_username=request.user.username)

            # Auto-notify admins about new registration (N1)
            try:
                from .models import Notification
                from django.contrib.auth.models import User as AuthUser
                admin_users = AuthUser.objects.filter(
                    profile__role__in=['admin', 'accounts', 'sales_manager']
                ).exclude(id=request.user.id)
                student_name = f"{registration.first_name} {registration.last_name}"
                for admin in admin_users:
                    Notification.objects.create(
                        recipient=admin,
                        notif_type='registration_new',
                        title=f"New Registration: {student_name}",
                        message=f"Student {student_name} ({registration.registration_number}) has been registered.",
                        link="/student-dashboard/"
                    )
            except Exception:
                pass

            # Welcome email sent by cron 1 hour after registration
            return redirect('student_dashboard')
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", formset.errors)
    else:
        # Pre-fill from CRM lead URL params (?fn=&ln=&ph=&em=&ci=&crm_id=)
        crm_initial = {}
        if request.GET.get('fn'):
            crm_initial['first_name'] = request.GET.get('fn', '')
        if request.GET.get('ln'):
            crm_initial['last_name'] = request.GET.get('ln', '')
        if request.GET.get('ph'):
            crm_initial['phone_no'] = request.GET.get('ph', '')
        if request.GET.get('em'):
            crm_initial['email'] = request.GET.get('em', '')
        form = RegistrationForm(user=request.user, initial=crm_initial)
        formset = RegistrationCourseFormSet(prefix='form')

    courses = Course.objects.all()
    crm_course_id = request.GET.get('ci', '')
    crm_id = request.GET.get('crm_id', '')
    return render(request, 'studentregistration/registration_form.html', {
        'form': form,
        'formset': formset,
        'courses': courses,
        'crm_course_id': crm_course_id,
        'crm_id': crm_id,
    })

@login_required
def get_course_details(request):
    course_id = request.GET.get('course_id')
    try:
        course = Course.objects.get(id=course_id)
        return JsonResponse({
            'price': str(course.rate),
            'vat': str(course.rate * 0.05),
        })
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    
@login_required
def student_dashboard(request):
    qs = Registration.objects.filter(
        registration_type='OT'
    ).prefetch_related('registration_courses__course').order_by('-registration_number')

    registration_number = request.GET.get('registration_number', '')
    name       = request.GET.get('name', '')
    consultant = request.GET.get('consultant', '')
    class_type = request.GET.get('class_type', '')

    if registration_number:
        qs = qs.filter(registration_number__icontains=registration_number)
    if name:
        qs = qs.filter(Q(first_name__icontains=name) | Q(last_name__icontains=name))
    if consultant:
        qs = qs.filter(consultant_name__icontains=consultant)
    if class_type:
        qs = qs.filter(class_type=class_type)

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    reg_numbers = [r.registration_number for r in page_obj]
    finished_pairs = set(
        Certificate.objects.filter(register_number__in=reg_numbers)
        .values_list('register_number', 'course_name')
    )

    registration_data = []
    for registration in page_obj:
        courses_with_status = [
            {
                'name': rc.course.name,
                'rate': rc.course.rate,
                'online_rate': rc.course.online_rate,
                'batch_rate': rc.course.batch_rate,
                'private_rate': rc.course.private_rate,
                'status': 'Finished' if (registration.registration_number, rc.course.name) in finished_pairs else 'In Progress',
            }
            for rc in registration.registration_courses.all()
        ]
        registration_data.append({'registration': registration, 'courses': courses_with_status})

    from django.contrib.auth.models import User as _User
    active_users = list(_User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username'))
    consultant_choices = sorted(set(
        list(Registration.objects.exclude(consultant_name='').exclude(consultant_name__isnull=True)
             .values_list('consultant_name', flat=True).distinct())
        + [u.get_full_name() or u.username for u in active_users]
    ))

    context = {
        'registration_data': registration_data,
        'page_obj': page_obj,
        'paginator': paginator,
        'registration_number': registration_number,
        'name': name,
        'consultant': consultant,
        'class_type': class_type,
        'consultant_choices': consultant_choices,
        'active_users': active_users,
    }
    return render(request, 'studentregistration/student_dashboard.html', context)

@login_required
def edit_registration(request, pk):
    registration = get_object_or_404(Registration, pk=pk)

    try:
        role = request.user.profile.role
    except Exception:
        role = 'sales_executive'
    if role == 'sales_executive':
        if registration.created_at is None:
            locked = True
        else:
            locked = (timezone.now() - registration.created_at).total_seconds() > 3600
        if locked:
            messages.error(request, "Registrations can only be edited within 1 hour of creation. Please contact your manager.")
            return redirect('student_dashboard')

    RegistrationCourseFormSet = formset_factory(RegistrationCourseForm, extra=0)

    if request.method == 'POST':
        form = RegistrationForm(request.POST, instance=registration)
        formset = RegistrationCourseFormSet(request.POST, prefix='courses')
        
        if form.is_valid() and formset.is_valid():
            registration = form.save()

            # Delete existing RegistrationCourse objects
            RegistrationCourse.objects.filter(registration=registration).delete()

            valid_course_forms = [f for f in formset if f.cleaned_data and f.cleaned_data.get('course')]
            base_cap = Decimal('30') if len(valid_course_forms) >= 2 else Decimal('20')
            for course_form in valid_course_forms:
                max_allowed, coupon_obj = _course_discount_cap(base_cap, course_form.cleaned_data.get('coupon_code', ''))
                RegistrationCourse.objects.create(
                    registration=registration,
                    course=course_form.cleaned_data['course'],
                    discount=min(course_form.cleaned_data.get('discount') or Decimal('0'), max_allowed),
                    price=course_form.cleaned_data.get('price', 0),
                )
                _mark_coupon_used(coupon_obj)

            # Update CRM lead link if provided
            crm_lead_id = request.POST.get('crm_lead_id', '').strip()
            if crm_lead_id and crm_lead_id.isdigit():
                _save_reg_crm_link(registration.pk, int(crm_lead_id), request.user.username)

            # Sync updated registration to CRM
            sync_registration_to_crm(registration, consultant_username=request.user.username)

            return redirect('student_dashboard')
    else:
        form = RegistrationForm(instance=registration)
        
        # Initialize formset with existing courses
        initial_courses = [
            {'course': rc.course.id, 'discount': rc.discount, 'price': rc.price}
            for rc in registration.registration_courses.all()
        ]
        formset = RegistrationCourseFormSet(initial=initial_courses, prefix='courses')

    courses = Course.objects.all()
    return render(request, 'studentregistration/edit_registration.html', {
        'form': form,
        'formset': formset,
        'registration': registration,
        'courses': courses,
    })

@login_required
@require_POST
def reassign_consultant(request, pk):
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role == 'admin'
    )
    if not is_admin:
        return JsonResponse({'ok': False, 'error': 'Admin only.'}, status=403)
    reg = get_object_or_404(Registration, pk=pk)

    # --- resolve target user or institute mode ---
    user_id_raw = request.POST.get('user_id', '').strip()
    institute_mode = request.POST.get('institute_mode') == '1'
    remove_crm = request.POST.get('remove_crm') == '1'

    if institute_mode:
        new_name = (request.POST.get('consultant_name') or 'Orbit Training').strip()
        # Move invoices to admin user so exec dashboards don't count them
        admin_user = User.objects.filter(
            is_active=True
        ).filter(
            profile__role='admin'
        ).first() or User.objects.filter(is_superuser=True).first()
        target_user = admin_user
    elif user_id_raw:
        try:
            target_user = User.objects.get(pk=int(user_id_raw), is_active=True)
        except (User.DoesNotExist, ValueError):
            return JsonResponse({'ok': False, 'error': 'User not found.'}, status=400)
        new_name = target_user.get_full_name() or target_user.username
    else:
        return JsonResponse({'ok': False, 'error': 'No target selected.'}, status=400)

    # 1. Update consultant_name on the registration
    reg.consultant_name = new_name
    reg.save(update_fields=['consultant_name'])

    # 2. Move all invoices for this registration to the target user
    if target_user:
        Invoice.objects.filter(registration=reg).update(user=target_user)

    # 3. Optionally remove the CRM link (moves revenue to Institute Direct Sales)
    if remove_crm:
        try:
            import pymysql as _pm
            _cn = _pm.connect(host='localhost', user='root', password='',
                              database='orbit_invoice', charset='utf8mb4')
            with _cn.cursor() as _cu:
                _cu.execute("DELETE FROM invoices_registrationcrmlink WHERE registration_id=%s", (reg.pk,))
            _cn.commit()
            _cn.close()
        except Exception as _e:
            logger.warning(f"CRM link removal failed for reg {reg.pk}: {_e}")

    return JsonResponse({'ok': True, 'consultant_name': reg.consultant_name})


@user_passes_test(is_admin_user)
def delete_registration(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        registration.delete()
        if registration.registration_type == 'OC' :
            return redirect('corporate_dashboard')
        else:
            return redirect('student_dashboard')
    return render(request, 'studentregistration/delete_registration.html', {'registration': registration})

@login_required
def print_registration(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    registration_courses = registration.registration_courses.all()
    discount_rate = sum(course.discount for course in registration_courses) / len(registration_courses) if registration_courses else 0
    
    context = {
        'registration': registration,
        'registration_courses': registration_courses,
        'discount_rate': discount_rate,
    }
    
    return render(request, 'studentregistration/registration_print.html', context)


@login_required
def registration_invoice_detail(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id)
    registration_courses = registration.registration_courses.all()
    invoices = Invoice.objects.filter(registration_id=registration.id).order_by('date')
    
    total_course_amount = sum(rc.course.rate * (1 - rc.discount / 100) for rc in registration_courses)
    _invoice_list = list(invoices)
    total_amount_paid = sum(inv.amount_paid for inv in _invoice_list)
    # First invoice's total_amount is the authoritative fee (VAT-inclusive, matches what was invoiced).
    # Installment invoices all carry the same total_amount — summing them would multiply the total.
    total_amount = _invoice_list[0].total_amount if _invoice_list else total_course_amount
    total_due_amount = total_amount - total_amount_paid
    
    unique_courses = set(rc.course for rc in registration_courses)
    
    certificate_uploaded = CertificateUpload.objects.filter(registration=registration).exists()
    form_uploaded = FormUpload.objects.filter(registration=registration).exists()
    cert_requests = CertificationRequest.objects.filter(registration=registration).order_by('-sent_at')
    generated_certificates = Certificate.objects.filter(register_number=registration.registration_number)

    context = {
        'registration': registration,
        'unique_courses': unique_courses,
        'invoices': invoices,
        'total_amount': total_amount,
        'registration_courses': registration_courses,
        'total_amount_paid': total_amount_paid,
        'total_due_amount': total_due_amount,
        'total_course_amount': total_course_amount,
        'certificate_uploaded': certificate_uploaded,
        'form_uploaded': form_uploaded,
        'cert_requests': cert_requests,
        'generated_certificates': generated_certificates,
    }
    return render(request, 'studentregistration/registration_invoice_detail.html', context)

@login_required
def upload_form(request, registration_id):
    if request.method == 'POST':
        registration = get_object_or_404(Registration, id=registration_id)
        form_file = request.FILES.get('form_file')
        
        if form_file:
            FormUpload.objects.update_or_create(
                registration=registration,
                defaults={'form_file': form_file}
            )
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'No file uploaded'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def upload_certificate(request, registration_id):
    if request.method == 'POST':
        registration = get_object_or_404(Registration, id=registration_id)
        certificate_file = request.FILES.get('certificate_file')
        
        if certificate_file:
            CertificateUpload.objects.create(
                registration=registration,
                certificate_file=certificate_file
            )
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'No file uploaded'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def get_registration_details(request):
    registration_number = request.GET.get('registration_number', '')
    try:
        registration = get_object_or_404(Registration, registration_number=registration_number)
        registration_courses = RegistrationCourse.objects.filter(registration=registration)

        courses = []
        discount = 0  # Initialize discount
        for rc in registration_courses:
            c = rc.course
            courses.append({
                'id': c.id,
                'name': c.name,
                'rate': float(c.oo_intermediate),  # default display rate
                'oo_intermediate':   float(c.oo_intermediate),
                'oo_professional':   float(c.oo_professional),
                'oo_advanced':       float(c.oo_advanced),
                'priv_intermediate': float(c.priv_intermediate),
                'priv_professional': float(c.priv_professional),
                'priv_advanced':     float(c.priv_advanced),
                'discount': float(rc.discount),
            })
            if rc.discount > discount:
                discount = rc.discount  # Set the highest discount

        # Sum all previous payments for this registration so the new invoice
        # can show the true remaining balance.
        from django.db.models import Sum as _Sum
        already_paid = float(
            Invoice.objects.filter(registration=registration)
            .aggregate(t=_Sum('amount_paid'))['t'] or 0
        )

        data = {
            'client_name': f"{registration.first_name} {registration.last_name}",
            'candidate_name': f"{registration.first_name} {registration.last_name}",
            'client_emirates': registration.country,
            'client_country': registration.country,
            'courses': courses,
            'registration_type': registration.registration_type,
            'discount': discount,
            'class_type': registration.class_type,
            'level': registration.level or 'intermediate',
            'already_paid': already_paid,
        }

        if registration.registration_type == 'OC':
            try:
                corp = CorporateRegistration.objects.get(registration=registration)
                data['company_name'] = corp.company_name
                data['client_name'] = corp.company_name  # Invoice billed to company, not candidate
                data['client_emirates'] = corp.company_location or registration.country
                data['client_country'] = registration.country
                data['company_email'] = corp.company_email
                data['company_phone'] = corp.company_phone
                data['company_address'] = corp.company_address
            except CorporateRegistration.DoesNotExist:
                pass

        return JsonResponse(data)
    except Registration.DoesNotExist:
        return JsonResponse({'error': 'Registration not found'}, status=404)
    
@login_required
def get_invoice_details(request):
    from .models import InvoicePayment
    registration_number = request.GET.get('registration_number')
    try:
        registration = Registration.objects.get(registration_number=registration_number)
        invoices = list(Invoice.objects.filter(registration=registration).order_by('date'))
        if not invoices:
            return JsonResponse({'error': 'No invoices found for this registration'}, status=404)

        total_amount = invoices[-1].total_amount
        total_amount_paid = sum(invoice.amount_paid for invoice in invoices)

        # Apply 5% VAT to total_amount_paid (amount_paid is stored ex-VAT)
      #  total_amount_paid = total_amount_paid + (total_amount_paid * Decimal('0.05'))

        total_due_amount = total_amount - total_amount_paid

        # --- last payment reference ---
        all_invoice_ids = [inv.id for inv in invoices]
        last_payment_info = None

        lp = (InvoicePayment.objects
              .filter(invoice_id__in=all_invoice_ids)
              .order_by('-paid_at', '-id')
              .select_related('invoice')
              .first())

        if lp:
            last_payment_info = {
                'invoice_number': lp.invoice.invoice_number,
                'reference': lp.reference or '',
                'amount': float(lp.amount),
                'paid_at': lp.paid_at.strftime('%d %b %Y'),
                'payment_method': lp.get_payment_method_display(),
            }
        else:
            # Fall back: last invoice that has a non-zero amount_paid
            paid_invs = [inv for inv in invoices if inv.amount_paid > 0]
            if paid_invs:
                last_paid = max(paid_invs, key=lambda x: x.date)
                last_payment_info = {
                    'invoice_number': last_paid.invoice_number,
                    'reference': '',
                    'amount': float(last_paid.amount_paid),
                    'paid_at': last_paid.date.strftime('%d %b %Y'),
                    'payment_method': last_paid.get_payment_display(),
                }

        data = {
            'registration_number': registration_number,
            'total_amount': float(total_amount),
            'total_amount_paid': float(total_amount_paid),
            'total_due_amount': float(total_due_amount),
            'last_payment': last_payment_info,
            'invoices': [
                {
                    'invoice_number': invoice.invoice_number,
                    'date': invoice.date.strftime('%Y-%m-%d'),
                    'total_amount': float(invoice.total_amount),
                    'amount_paid': float(invoice.amount_paid),
                    'due_amount': float(invoice.total_amount - invoice.amount_paid),
                    'status': invoice.get_status_display(),
                    'payment_method': invoice.get_payment_display(),
                    'items': [
                        {
                            'course_name': item.course.name,
                            'quantity': item.quantity,
                            'unit_price': float(item.unit_price),
                            'subtotal': float(item.get_subtotal())
                        } for item in invoice.items.all()
                    ]
                } for invoice in invoices
            ]
        }
        return JsonResponse(data)
    except Registration.DoesNotExist:
        return JsonResponse({'error': 'Registration not found'}, status=404)


@login_required
def corporate_registration(request):
    RegistrationCourseFormSet = formset_factory(RegistrationCourseForm, extra=1)
    courses = Course.objects.all()
    company_name = request.GET.get('company_name', '').strip()

    if request.method == 'POST':
        registration_form = CorporateRegistrationForm(request.POST, user=request.user)
        corporate_form    = CorporateDetailsForm(request.POST)
        formset           = RegistrationCourseFormSet(request.POST, prefix='form')

        if registration_form.is_valid() and corporate_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    reg = registration_form.save(commit=False)
                    reg.registration_type = 'OC'
                    reg.save()

                    corp = corporate_form.save(commit=False)
                    corp.registration = reg
                    corp.save()

                    valid_forms = [
                        f for f in formset
                        if f.cleaned_data and not f.cleaned_data.get('DELETE', False) and f.cleaned_data.get('course')
                    ]
                    base_cap = Decimal('30') if len(valid_forms) >= 2 else Decimal('20')
                    for cf in valid_forms:
                        course   = cf.cleaned_data['course']
                        max_allowed, coupon_obj = _course_discount_cap(base_cap, cf.cleaned_data.get('coupon_code', ''))
                        discount = min(cf.cleaned_data.get('discount') or Decimal('0'), max_allowed)
                        price    = cf.cleaned_data.get('price', Decimal('0')) or Decimal('0')
                        RegistrationCourse.objects.create(
                            registration=reg, course=course, discount=discount, price=price,
                        )
                        _mark_coupon_used(coupon_obj)

                    try:
                        admin_users = User.objects.filter(
                            profile__role__in=['admin', 'accounts', 'sales_manager']
                        ).exclude(id=request.user.id)
                        student_name = f"{reg.first_name} {reg.last_name}"
                        for admin in admin_users:
                            Notification.objects.create(
                                recipient=admin,
                                notif_type='registration_new',
                                title=f"New Candidate: {corp.company_name}",
                                message=f"{student_name} ({reg.registration_number}) registered under {corp.company_name}.",
                                link=f"/corporate-registration/{reg.pk}/"
                            )
                    except Exception:
                        pass

                    # Welcome email sent by cron 1 hour after registration

                messages.success(request, f"Registration {reg.registration_number} created successfully.")
                return redirect('corporate_company_list')
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        initial_corporate = {}
        if company_name:
            existing = CorporateRegistration.objects.filter(company_name=company_name).first()
            if existing:
                initial_corporate = {
                    'company_name':    existing.company_name,
                    'company_email':   existing.company_email,
                    'company_phone':   existing.company_phone,
                    'company_location': existing.company_location,
                    'company_address': existing.company_address,
                }
            else:
                initial_corporate = {'company_name': company_name}
        registration_form = CorporateRegistrationForm(user=request.user)
        corporate_form    = CorporateDetailsForm(initial=initial_corporate)
        formset           = RegistrationCourseFormSet(prefix='form')

    return render(request, 'studentregistration/corporate_registration.html', {
        'registration_form': registration_form,
        'corporate_form':    corporate_form,
        'formset':           formset,
        'courses':           courses,
        'company_name':      company_name,
    })

@login_required
def corporate_dashboard(request):
    # Redirect to the new company list
    return redirect('corporate_company_list')

@login_required
def corporate_invoice_detail(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id, registration_type='OC')

    invoices = Invoice.objects.filter(registration_id=registration.id).order_by('date')
    total_amount = sum(invoice.total_amount for invoice in invoices)
    total_amount_paid = sum(invoice.amount_paid for invoice in invoices)
  #  total_amount_paid = total_amount_paid + (total_amount_paid * Decimal(0.05))
    total_due_amount = total_amount - total_amount_paid

    context = {
        'registration': registration,
        'invoices': invoices,
        'total_amount': total_amount,
        'total_amount_paid': total_amount_paid,
        'total_due_amount': total_due_amount,
    }
    return render(request, 'studentregistration/corporate_invoice_details.html', context)

@login_required
def print_corporate_registration(request, pk):
    registration = get_object_or_404(Registration, pk=pk, registration_type='OC')
    registration_courses = registration.registration_courses.all()
    corporate_details = registration.corporate_details

    # Calculate totals and individual course details
    total_course_fee = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_vat = Decimal('0.00')
    grand_total = Decimal('0.00')

    course_details = []
    for rc in registration_courses:
        # Use stored price (rc.price) — falls back to course.rate for legacy records
        base_price      = rc.price if rc.price else rc.course.rate
        discount_amount = base_price * (rc.discount / 100)
        discounted_price = base_price - discount_amount
        course_vat   = discounted_price * Decimal('0.05')
        course_total = discounted_price + course_vat

        course_details.append({
            'name': rc.course.name,
            'rate': base_price,
            'discount': rc.discount,
            'discount_amount': discount_amount,
            'vat': course_vat,
            'total': course_total,
        })

        total_course_fee += base_price
        total_discount   += discount_amount
        total_vat        += course_vat
        grand_total      += course_total

    context = {
        'registration': registration,
        'corporate_details': corporate_details,
        'course_details': course_details,
        'total_course_fee': total_course_fee,
        'total_discount': total_discount,
        'total_vat': total_vat,
        'grand_total': grand_total,
    }

    return render(request, 'studentregistration/corporate_registration_print.html', context)

@login_required
def edit_corporate_registration(request, pk):
    registration = get_object_or_404(Registration, pk=pk, registration_type='OC')

    try:
        role = request.user.profile.role
    except Exception:
        role = 'sales_executive'
    if role == 'sales_executive':
        if registration.created_at is None:
            locked = True
        else:
            locked = (timezone.now() - registration.created_at).total_seconds() > 3600
        if locked:
            messages.error(request, "Registrations can only be edited within 1 hour of creation. Please contact your manager.")
            return redirect('student_dashboard')

    try:
        corporate_details = registration.corporate_details
    except CorporateRegistration.DoesNotExist:
        corporate_details = CorporateRegistration(registration=registration)

    if request.method == 'POST':
        registration_form = CorporateRegistrationForm(request.POST, instance=registration, user=request.user)
        corporate_form    = CorporateDetailsForm(request.POST, instance=corporate_details)
        formset           = formset_factory(RegistrationCourseForm, extra=0)(request.POST, prefix='form')

        if registration_form.is_valid() and corporate_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    reg = registration_form.save(commit=False)
                    reg.registration_type = 'OC'
                    reg.save()

                    corp = corporate_form.save(commit=False)
                    corp.registration = reg
                    corp.save()

                    # Re-apply discount cap on edit
                    valid_forms = [
                        f for f in formset
                        if f.cleaned_data and not f.cleaned_data.get('DELETE', False) and f.cleaned_data.get('course')
                    ]
                    base_cap = Decimal('30') if len(valid_forms) >= 2 else Decimal('20')
                    seen = set()
                    for cf in valid_forms:
                        course   = cf.cleaned_data['course']
                        max_allowed, coupon_obj = _course_discount_cap(base_cap, cf.cleaned_data.get('coupon_code', ''))
                        discount = min(cf.cleaned_data.get('discount') or Decimal('0'), max_allowed)
                        price    = cf.cleaned_data.get('price', Decimal('0')) or Decimal('0')
                        RegistrationCourse.objects.update_or_create(
                            registration=reg, course=course,
                            defaults={'discount': discount, 'price': price},
                        )
                        seen.add(course.pk)
                        _mark_coupon_used(coupon_obj)
                    # Remove courses that were deleted
                    for cf in formset:
                        if cf.cleaned_data.get('DELETE') and cf.cleaned_data.get('course'):
                            RegistrationCourse.objects.filter(
                                registration=reg, course=cf.cleaned_data['course']
                            ).delete()

                messages.success(request, "Corporate registration updated successfully.")
                return redirect('corporate_invoice_detail', registration_id=reg.pk)
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        registration_form = CorporateRegistrationForm(instance=registration, user=request.user)
        corporate_form    = CorporateDetailsForm(instance=corporate_details)
        existing = registration.registration_courses.all()
        initial  = [{'course': rc.course, 'discount': rc.discount, 'price': rc.price} for rc in existing]
        EditFormSet = formset_factory(RegistrationCourseForm, extra=0, can_delete=True)
        formset = EditFormSet(prefix='form', initial=initial)

    courses = Course.objects.all()
    context = {
        'registration_form': registration_form,
        'corporate_form':    corporate_form,
        'formset':           formset,
        'registration':      registration,
        'courses':           courses,
    }
    return render(request, 'studentregistration/edit_corporate_registration.html', context)


# ─────────────────────────────────────────────────────────────
#  CORPORATE COMPANY (new company-first flow)
@login_required
def corporate_tax_invoice_search(request):
    """Search Purchase Invoices (Proforma) by PI number or company name,
    then create a Tax Invoice from the selected PI."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        pis = (
            InvoicePurchase.objects
            .filter(Q(invoice_number__icontains=query) | Q(client__name__icontains=query))
            .select_related('client')
            .prefetch_related('purchaseitems__course')
            .order_by('-id')[:40]
        )
        for pi in pis:
            items = list(pi.purchaseitems.all())
            # Recalculate correct total from items (stored total_amount may be 0)
            subtotal = Decimal('0')
            for item in items:
                subtotal += item.unit_price * max(item.quantity, 1) * pi.number_of_person * (1 - Decimal(pi.discount) / 100)
            vat = subtotal * Decimal('0.05')
            total = (subtotal + vat).quantize(Decimal('0.01'))
            results.append({
                'pi': pi,
                'items': items,
                'subtotal': subtotal,
                'vat': vat,
                'total': total,
                'outstanding': total - pi.advance_amount,
            })

    return render(request, 'studentregistration/corporate_tax_invoice_search.html', {
        'query': query,
        'results': results,
    })


@login_required
def create_tax_invoice_from_pi(request, pi_id):
    """Create a Tax Invoice based on an existing Purchase/Proforma Invoice."""
    pi = get_object_or_404(InvoicePurchase, pk=pi_id)
    items = list(pi.purchaseitems.select_related('course').all())

    # Calculate correct totals from items
    subtotal = Decimal('0')
    for item in items:
        subtotal += item.unit_price * max(item.quantity, 1) * pi.number_of_person * (1 - Decimal(pi.discount) / 100)
    vat = subtotal * Decimal('0.05')
    total = (subtotal + vat).quantize(Decimal('0.01'))

    if request.method == 'POST':
        try:
            inv_date = request.POST.get('date') or datetime.date.today()
            due_date = request.POST.get('due_date')
            amount_paid = Decimal(request.POST.get('amount_paid') or '0')
            payment = request.POST.get('payment', 'Account Transfer')
            status = request.POST.get('status', 'Full Payment')
            po_number = request.POST.get('po_number', pi.po_number or '')

            invoice = Invoice(
                client=pi.client,
                user=request.user,
                registration=None,
                class_type='',
                date=inv_date,
                due_date=due_date,
                amount_paid=amount_paid,
                discount=pi.discount,
                number_of_person=pi.number_of_person,
                level='intermediate',
                status=status,
                payment=payment,
                po_number=po_number,
                total_amount=Decimal('0'),
            )
            invoice.save()

            for item in items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    course=item.course,
                    description=item.description or (item.course.name if item.course else ''),
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    vat_rate=item.vat_rate,
                )

            # Bypass Invoice.save() recalculation (which uses course rates, not PI prices)
            Invoice.objects.filter(pk=invoice.pk).update(total_amount=total)

            messages.success(request, f"Tax Invoice {invoice.invoice_number} created successfully.")
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"Error creating invoice: {e}")

    return render(request, 'studentregistration/create_tax_invoice_from_pi.html', {
        'pi': pi,
        'items': items,
        'subtotal': subtotal,
        'vat': vat,
        'total': total,
        'outstanding': total - pi.advance_amount,
        'today': datetime.date.today(),
    })


# ─────────────────────────────────────────────────────────────

@login_required
def api_search_corporate_companies(request):
    """AJAX: search CorporateCompany + legacy CorporateRegistration by name."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    results = []
    seen_names = set()
    for company in CorporateCompany.objects.filter(company_name__icontains=q).order_by('company_name')[:10]:
        results.append({
            'type': 'company', 'id': company.pk,
            'name': company.company_name, 'location': company.company_location,
            'candidate_count': company.candidate_count(),
        })
        seen_names.add(company.company_name.lower())
    legacy_names = (
        CorporateRegistration.objects.filter(company_name__icontains=q)
        .values_list('company_name', flat=True).distinct()[:10]
    )
    for name in legacy_names:
        if name.lower() not in seen_names:
            count = CorporateRegistration.objects.filter(company_name=name).count()
            results.append({
                'type': 'legacy', 'id': None,
                'name': name, 'location': '',
                'candidate_count': count,
            })
            seen_names.add(name.lower())
    return JsonResponse({'results': results[:15]})


@login_required
def api_corporate_pi_data(request):
    """AJAX: return grouped courses + totals for a corporate company to populate a PI."""
    company_id   = request.GET.get('company_id')
    company_name = request.GET.get('company_name', '').strip()
    registrations = []
    company_info  = {}

    if company_id:
        company = get_object_or_404(CorporateCompany, pk=company_id)
        company_info = {
            'name': company.company_name, 'email': company.company_email,
            'phone': company.company_phone, 'location': company.company_location,
        }
        registrations = [
            link.registration for link in
            company.candidates.select_related('registration').prefetch_related(
                'registration__registration_courses__course'
            )
        ]
    elif company_name:
        corp_regs = CorporateRegistration.objects.filter(
            company_name=company_name
        ).select_related('registration').prefetch_related(
            'registration__registration_courses__course'
        )
        if corp_regs.exists():
            first = corp_regs.first()
            company_info = {
                'name': first.company_name, 'email': first.company_email,
                'phone': first.company_phone, 'location': first.company_location,
            }
            registrations = [cr.registration for cr in corp_regs]

    if not company_info:
        return JsonResponse({'error': 'Company not found'}, status=404)

    # Group by (course_id, unit_price) so different-priced courses become separate lines
    course_map = {}
    for reg in registrations:
        candidate_name = f"{reg.first_name} {reg.last_name}"
        for rc in reg.registration_courses.select_related('course').all():
            if not rc.course:
                continue
            price = float(rc.price or 0)
            key = (rc.course.id, price)
            if key not in course_map:
                course_map[key] = {
                    'course_id': rc.course.id,
                    'course_name': rc.course.name,
                    'unit_price': price,
                    'candidates': [],
                }
            course_map[key]['candidates'].append(candidate_name)

    courses = [
        {
            'course_id': d['course_id'],
            'course_name': d['course_name'],
            'unit_price': d['unit_price'],
            'candidate_count': len(d['candidates']),
            'candidates': d['candidates'],
        }
        for d in course_map.values()
    ]

    return JsonResponse({
        'company': company_info,
        'total_candidates': len(registrations),
        'courses': courses,
    })


@login_required
def corporate_company_list(request):
    q = request.GET.get('q', '').strip()
    qs = CorporateCompany.objects.all()
    if q:
        qs = qs.filter(company_name__icontains=q)
    paginator  = Paginator(qs, 20)
    companies  = paginator.get_page(request.GET.get('page', 1))

    # Legacy corporate registrations — group by company_name from CorporateRegistration
    from django.db.models import Count, Max
    legacy_qs = CorporateRegistration.objects.values(
        'company_name', 'company_email', 'company_phone', 'company_location'
    ).annotate(
        candidate_count=Count('registration'),
        last_date=Max('registration__date'),
    ).order_by('-last_date')
    if q:
        legacy_qs = legacy_qs.filter(company_name__icontains=q)

    return render(request, 'studentregistration/corporate_company_list.html', {
        'companies': companies,
        'legacy_companies': list(legacy_qs),
        'q': q,
    })


@login_required
def corporate_legacy_registrations(request):
    """Show legacy corporate registrations (CorporateRegistration model) for a given company name."""
    company_name = request.GET.get('company', '').strip()
    registrations = CorporateRegistration.objects.filter(
        company_name=company_name
    ).select_related('registration').order_by('-registration__date') if company_name else CorporateRegistration.objects.none()
    return render(request, 'studentregistration/corporate_legacy_registrations.html', {
        'company_name': company_name,
        'registrations': registrations,
    })


@login_required
def corporate_company_create(request):
    if request.method == 'POST':
        form = CorporateCompanyForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            company = form.save(commit=False)
            company.created_by = request.user
            company.save()
            messages.success(request, f"Company '{company.company_name}' registered successfully.")
            return redirect('corporate_company_detail', pk=company.pk)
    else:
        form = CorporateCompanyForm(user=request.user)
    return render(request, 'studentregistration/corporate_company_form.html', {'form': form, 'action': 'create'})


@login_required
def corporate_company_detail(request, pk):
    company   = get_object_or_404(CorporateCompany, pk=pk)
    candidates = company.candidates.select_related('registration').prefetch_related(
        'registration__registration_courses__course'
    ).order_by('-added_at')
    return render(request, 'studentregistration/corporate_company_detail.html', {
        'company':    company,
        'candidates': candidates,
    })


@login_required
def corporate_company_edit(request, pk):
    company = get_object_or_404(CorporateCompany, pk=pk)
    if request.method == 'POST':
        form = CorporateCompanyForm(request.POST, request.FILES, instance=company, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Company profile updated.")
            return redirect('corporate_company_detail', pk=company.pk)
    else:
        form = CorporateCompanyForm(instance=company, user=request.user)
    return render(request, 'studentregistration/corporate_company_form.html', {'form': form, 'company': company, 'action': 'edit'})


@login_required
def corporate_company_delete(request, pk):
    company = get_object_or_404(CorporateCompany, pk=pk)
    if request.method == 'POST':
        name = company.company_name
        company.delete()
        messages.success(request, f'Company "{name}" has been deleted.')
        return redirect('corporate_company_list')
    return render(request, 'studentregistration/corporate_company_confirm_delete.html', {'company': company})


@login_required
def corporate_add_candidate(request, pk):
    company = get_object_or_404(CorporateCompany, pk=pk)
    RegistrationCourseFormSet = formset_factory(RegistrationCourseForm, extra=1)
    courses = Course.objects.all()

    if request.method == 'POST':
        reg_form = CorporateRegistrationForm(request.POST, user=request.user)
        formset  = RegistrationCourseFormSet(request.POST, prefix='form')

        if reg_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    reg = reg_form.save(commit=False)
                    reg.registration_type = 'OC'
                    reg.save()

                    valid_forms = [
                        f for f in formset
                        if f.cleaned_data and not f.cleaned_data.get('DELETE', False) and f.cleaned_data.get('course')
                    ]
                    base_cap = Decimal('30') if len(valid_forms) >= 2 else Decimal('20')
                    for cf in valid_forms:
                        course   = cf.cleaned_data['course']
                        max_allowed, coupon_obj = _course_discount_cap(base_cap, cf.cleaned_data.get('coupon_code', ''))
                        discount = min(cf.cleaned_data.get('discount') or Decimal('0'), max_allowed)
                        price    = cf.cleaned_data.get('price', Decimal('0')) or Decimal('0')
                        RegistrationCourse.objects.create(
                            registration=reg, course=course, discount=discount, price=price,
                        )
                        _mark_coupon_used(coupon_obj)

                    CorporateCandidateLink.objects.create(company=company, registration=reg)

                    # Also create legacy CorporateRegistration for backward compat
                    CorporateRegistration.objects.get_or_create(
                        registration=reg,
                        defaults={
                            'company_name':    company.company_name,
                            'company_email':   company.company_email,
                            'company_phone':   company.company_phone,
                            'company_location': company.company_location,
                            'company_address': company.company_address,
                        }
                    )

                    # Notify admins
                    try:
                        admin_users = User.objects.filter(
                            profile__role__in=['admin', 'accounts', 'sales_manager']
                        ).exclude(id=request.user.id)
                        student_name = f"{reg.first_name} {reg.last_name}"
                        for admin in admin_users:
                            Notification.objects.create(
                                recipient=admin,
                                notif_type='registration_new',
                                title=f"New Candidate: {company.company_name}",
                                message=f"{student_name} ({reg.registration_number}) added under {company.company_name}.",
                                link=f"/corporate-companies/{company.pk}/"
                            )
                    except Exception:
                        pass

                    # Welcome email sent by cron 1 hour after registration

                messages.success(request, f"Candidate {reg.first_name} {reg.last_name} added successfully.")
                return redirect('corporate_company_detail', pk=company.pk)
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        reg_form = CorporateRegistrationForm(user=request.user)
        formset  = RegistrationCourseFormSet(prefix='form')

    return render(request, 'studentregistration/corporate_add_candidate.html', {
        'company':   company,
        'reg_form':  reg_form,
        'formset':   formset,
        'courses':   courses,
    })


@login_required
@require_POST
def corporate_company_generate_portal(request, pk):
    """Generate a company portal self-registration link pre-filled from a CorporateCompany record."""
    from .models import CompanyPortalRequest
    company = get_object_or_404(CorporateCompany, pk=pk)
    portal = CompanyPortalRequest.objects.create(
        generated_by=request.user,
        company_name=company.company_name,
        contact_person=company.contact_name or '',
        designation=company.contact_designation or '',
        email=company.contact_email or company.company_email or '',
        phone=company.contact_phone or company.company_phone or '',
        address=company.company_address or '',
        emirate=company.company_location or '',
    )
    portal_url = request.build_absolute_uri(f'/portal/company/{portal.token}/')
    return JsonResponse({'url': portal_url, 'token': portal.token})


@login_required
@require_POST
def corporate_company_get_dashboard_url(request, pk):
    """Generate (or retrieve) a permanent dashboard token for a CorporateCompany."""
    import uuid as _uuid
    company = get_object_or_404(CorporateCompany, pk=pk)
    if not company.dashboard_token:
        company.dashboard_token = _uuid.uuid4()
        company.save(update_fields=['dashboard_token'])
    url = request.build_absolute_uri(f'/company-dashboard/{company.dashboard_token}/')
    return JsonResponse({'url': url})


def company_dashboard_portal(request, token):
    """Public token-based dashboard for a corporate company."""
    company = get_object_or_404(CorporateCompany, dashboard_token=token)

    # Candidates via new company-first flow
    candidate_links = company.candidates.select_related('registration').prefetch_related(
        'registration__registration_courses__course',
        'registration__certificate_upload',
    ).order_by('registration__first_name')

    # Purchase Invoices — match by client name
    purchase_invoices = InvoicePurchase.objects.filter(
        client__name__iexact=company.company_name
    ).order_by('-date')

    # Quotations — match by client_name
    quotations = Quotation.objects.filter(
        client_name__iexact=company.company_name
    ).prefetch_related('items__course').order_by('-created_at')

    # Certificates — from candidate registrations
    cert_registrations = []
    for link in candidate_links:
        reg = link.registration
        cert = None
        try:
            cert = reg.certificate_upload
        except Exception:
            pass
        gen_cert = Certificate.objects.filter(
            register_number=reg.registration_number
        ).first()
        if cert or gen_cert:
            cert_registrations.append({
                'name': f"{reg.first_name} {reg.last_name}",
                'reg_number': reg.registration_number,
                'upload': cert,
                'generated': gen_cert,
            })

    return render(request, 'studentregistration/company_dashboard_portal.html', {
        'company': company,
        'candidate_links': candidate_links,
        'purchase_invoices': purchase_invoices,
        'quotations': quotations,
        'cert_registrations': cert_registrations,
    })


@login_required
def course_list(request):
    from django.db.models import Count as CourseCount, Q
    q = request.GET.get('q', '').strip()
    all_courses = Course.objects.annotate(
        reg_count=CourseCount('registrationcourse')
    ).order_by('name')
    if q:
        all_courses = all_courses.filter(Q(name__icontains=q) | Q(code__icontains=q))
    paginator = Paginator(all_courses, 25)
    courses = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'courses/course_list.html', {'courses': courses, 'query': q})

@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    contents = course.contents.all()
    # Enrolled students: RegistrationCourse rows that reference this course
    enrolled = RegistrationCourse.objects.filter(course=course)\
                    .select_related('registration', 'registration__corporate_details')\
                    .order_by('-registration__registration_number')
    return render(request, 'courses/course_detail.html', {
        'course': course,
        'contents': contents,
        'enrolled': enrolled,
    })

@login_required
def course_create(request):
    if get_user_role(request.user) == 'sales_executive':
        messages.error(request, 'Sales executives cannot create or edit courses.')
        return redirect('course_list')
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'courses/course_form.html', {'form': form})

@login_required
def course_update(request, course_id):
    if get_user_role(request.user) == 'sales_executive':
        messages.error(request, 'Sales executives cannot create or edit courses.')
        return redirect('course_list')
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'courses/course_form.html', {'form': form})

@login_required
def content_create(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseContentForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.save(commit=False)
            content.course = course
            content.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = CourseContentForm()
    return render(request, 'courses/content_form.html', {'form': form, 'course': course})

@user_passes_test(is_admin_user)
def content_delete(request, content_id):
    content = get_object_or_404(CourseContent, id=content_id)
    course_id = content.course.id
    if request.method == 'POST':
        content.delete()
        return redirect('course_detail', course_id=course_id)
    return render(request, 'courses/content_confirm_delete.html', {'content': content})

@user_passes_test(is_admin_user)
def course_delete(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        course.delete()
        messages.success(request, f"Course '{course.name}' has been deleted.")
        return redirect('course_list')
    return render(request, 'courses/course_confirm_delete.html', {'course': course})

@login_required
def orbit_dashboard(request):
    """Role-based dispatcher — sends each user to their own dashboard."""
    role = get_user_role(request.user)
    if role == 'admin' or request.user.is_superuser:
        return _admin_dashboard(request)
    elif role == 'sales_manager':
        return _sales_manager_dashboard(request)
    elif role == 'accounts':
        return _accounts_dashboard(request)
    else:
        return _sales_executive_dashboard(request)


# ─── helpers ────────────────────────────────────────────────────────────────

def _month_range(today=None):
    today = today or timezone.now().date()
    first = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last = today.replace(day=last_day)
    return first, last

def _last_month_range(today=None):
    today = today or timezone.now().date()
    first_this = today.replace(day=1)
    last_last = first_this - datetime.timedelta(days=1)
    first_last = last_last.replace(day=1)
    return first_last, last_last

def _pct_change(current, previous):
    if not previous:
        return 0, 'up' if current else 'neutral'
    change = ((current - previous) / previous) * 100
    return round(abs(change)), 'up' if change >= 0 else 'down'

def _month_label(date):
    return date.strftime('%B %Y')

def _revenue_for_user(user, first, last):
    """All invoices attributed to this user by consultant_name on the registration,
    plus standalone invoices (no registration) created by this user.
    Excludes refunded registrations."""
    full_name = user.get_full_name() or user.username
    # Registration-linked: match by consultant_name (who registered the student)
    reg_revenue = Invoice.objects.filter(
        registration__consultant_name__iexact=full_name,
        date__gte=first, date__lte=last,
    ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')
    # Standalone (corporate tax invoices, no registration): match by invoice creator
    standalone_revenue = Invoice.objects.filter(
        user=user, registration__isnull=True,
        date__gte=first, date__lte=last,
    ).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')
    return reg_revenue + standalone_revenue

def _last_6_months():
    today = timezone.now().date()
    months = []
    for i in range(5, -1, -1):
        d = (today.replace(day=1) - datetime.timedelta(days=i*28)).replace(day=1)
        months.append(d)
    return months

def _exec_target(user, month_first):
    try:
        t = SalesTarget.objects.get(user=user, month=month_first)
        return t.target_amount, t.target_registrations
    except SalesTarget.DoesNotExist:
        return 0, 0


# ─── ADMIN DASHBOARD ────────────────────────────────────────────────────────

def _admin_dashboard(request):
    today = timezone.now().date()
    first, last = _month_range(today)
    prev_first, prev_last = _last_month_range(today)

    month_revenue = Invoice.objects.filter(date__gte=first, date__lte=last)\
                        .exclude(registration__is_refunded=True)\
                        .aggregate(t=Sum('amount_paid'))['t'] or 0
    prev_revenue  = Invoice.objects.filter(date__gte=prev_first, date__lte=prev_last)\
                        .exclude(registration__is_refunded=True)\
                        .aggregate(t=Sum('amount_paid'))['t'] or 0
    rev_pct, rev_dir = _pct_change(month_revenue, prev_revenue)

    month_regs = Registration.objects.filter(date__gte=first, date__lte=last).count()
    prev_regs  = Registration.objects.filter(date__gte=prev_first, date__lte=prev_last).count()
    reg_pct, reg_dir = _pct_change(month_regs, prev_regs)

    outstanding = Invoice.objects.filter(status__in=['Term Payment','Tabby','Tamara'])\
                    .aggregate(t=Sum('total_amount'))['t'] or 0
    paid_inv    = Invoice.objects.filter(date__gte=first, date__lte=last, status='Full Payment')
    paid_count  = paid_inv.count()
    overdue     = Invoice.objects.filter(due_date__lt=today).exclude(status='Full Payment')
    overdue_count = overdue.count()

    total_invoices  = Invoice.objects.filter(date__gte=first, date__lte=last).count()
    total_courses   = Course.objects.count()
    total_certs     = Certificate.objects.count()
    total_students  = Registration.objects.count()

    # 6-month revenue trend
    months = _last_6_months()
    rev_labels = [m.strftime('%b') for m in months]
    rev_data   = []
    for m in months:
        mf = m
        ml = m.replace(day=calendar.monthrange(m.year, m.month)[1])
        v = Invoice.objects.filter(date__gte=mf, date__lte=ml)\
              .exclude(registration__is_refunded=True)\
              .aggregate(t=Sum('amount_paid'))['t'] or 0
        rev_data.append(float(v))

    # class type distribution
    ct = Registration.objects.filter(date__gte=first, date__lte=last)\
           .values('class_type').annotate(c=Count('id'))
    ct_labels = [x['class_type'].title() for x in ct]
    ct_data   = [x['c'] for x in ct]

    # top courses
    from django.db.models import Count as Cnt
    top_courses = Course.objects.annotate(count=Cnt('registrationcourse'))\
                    .order_by('-count')[:5]

    # exec performance — sales executives
    from django.contrib.auth.models import User
    executives = User.objects.filter(profile__role='sales_executive', is_active=True)
    exec_perf  = []
    for i, ex in enumerate(executives):
        rev   = float(_revenue_for_user(ex, first, last))
        regs  = Registration.objects.filter(date__gte=first, date__lte=last, consultant_name__iexact=ex.get_full_name() or ex.username).count()
        tamt, treg = _exec_target(ex, first)
        pct = min(round((rev / float(tamt) * 100) if tamt else 0), 100)
        days_elapsed = (today - first).days + 1
        days_total   = (last - first).days + 1
        run_rate     = rev / days_elapsed if days_elapsed else 0
        projected    = run_rate * days_total
        exec_perf.append({
            'username': ex.username, 'full_name': ex.get_full_name() or ex.username,
            'month_revenue': rev, 'month_registrations': regs,
            'target_pct': pct, 'target_amount': float(tamt),
            'projected': projected,
        })
    exec_perf.sort(key=lambda x: x['month_revenue'], reverse=True)

    # sales managers — always show in the table
    managers = User.objects.filter(profile__role='sales_manager', is_active=True)
    for mgr in managers:
        rev  = float(_revenue_for_user(mgr, first, last))
        regs = Registration.objects.filter(date__gte=first, date__lte=last, consultant_name__iexact=mgr.get_full_name() or mgr.username).count()
        exec_perf.append({
            'username': mgr.username, 'full_name': (mgr.get_full_name() or mgr.username) + ' (Manager)',
            'month_revenue': rev, 'month_registrations': regs,
            'target_pct': 0, 'target_amount': 0, 'projected': 0,
            'is_manager': True,
        })

    # admin / institute direct — invoices with no consultant_name on registration, or registration=None created by admin
    all_exec_names = [ex.get_full_name() or ex.username for ex in executives] + \
                     [mgr.get_full_name() or mgr.username for mgr in managers]
    institute_rev_qs = Invoice.objects.filter(date__gte=first, date__lte=last)\
        .exclude(registration__is_refunded=True)
    # exclude invoices already attributed to any exec or manager by consultant_name
    for name in all_exec_names:
        institute_rev_qs = institute_rev_qs.exclude(registration__consultant_name__iexact=name)
    institute_revenue = float(institute_rev_qs.aggregate(t=Sum('amount_paid'))['t'] or 0)
    institute_count   = institute_rev_qs.count()

    if institute_revenue > 0 or institute_count > 0:
        exec_perf.append({
            'username': '__institute__',
            'full_name': 'Institute / Admin Sales',
            'month_revenue': institute_revenue,
            'month_registrations': institute_count,
            'target_pct': 0, 'target_amount': 0, 'projected': 0,
            'is_institute': True,
        })
    exec_perf.sort(key=lambda x: x['month_revenue'], reverse=True)

    # ── Tabby / Tamara payment gateway breakdown (this month) ──
    from .models import InvoicePayment as _IP
    _D   = Decimal
    _TAB = _D('0.0707'); _TAM = _D('0.0702'); _VAT = _D('0.05')

    tabby_pmts  = _IP.objects.filter(payment_method='tabby',  paid_at__gte=first, paid_at__lte=last)
    tabby_sales = _D(str(tabby_pmts.aggregate(t=Sum('amount'))['t'] or 0))
    tabby_count = tabby_pmts.count()
    tabby_comm  = (tabby_sales * _TAB).quantize(_D('0.01'))
    tabby_vat   = (tabby_comm * _VAT).quantize(_D('0.01'))
    tabby_fee   = _D(str(tabby_count * 6))
    tabby_net   = tabby_sales - tabby_comm - tabby_vat - tabby_fee

    tamara_pmts  = _IP.objects.filter(payment_method='tamara', paid_at__gte=first, paid_at__lte=last)
    tamara_sales = _D(str(tamara_pmts.aggregate(t=Sum('amount'))['t'] or 0))
    tamara_count = tamara_pmts.count()
    tamara_comm  = (tamara_sales * _TAM).quantize(_D('0.01'))
    tamara_vat   = (tamara_comm * _VAT).quantize(_D('0.01'))
    tamara_net   = tamara_sales - tamara_comm - tamara_vat

    ctx = {
        'greeting': _get_greeting(),
        'current_month_label': _month_label(today),
        'month_revenue': float(month_revenue),
        'revenue_trend_pct': rev_pct, 'revenue_trend_dir': rev_dir,
        'month_registrations': month_regs,
        'reg_trend_pct': reg_pct, 'reg_trend_dir': reg_dir,
        'outstanding_amount': float(outstanding),
        'overdue_count': overdue_count,
        'total_invoices': total_invoices, 'paid_invoices': paid_count,
        'total_courses': total_courses, 'total_certificates': total_certs,
        'total_students': total_students,
        'revenue_labels': json.dumps(rev_labels),
        'revenue_data': json.dumps(rev_data),
        'class_type_labels': json.dumps(ct_labels),
        'class_type_data': json.dumps(ct_data),
        'top_courses': top_courses,
        'exec_performance': exec_perf,
        'recent_invoices': Invoice.objects.select_related('client').order_by('-id')[:8],
        'unattributed_count': institute_count,
        'unattributed_revenue': institute_revenue,
        # gateway stats
        'tabby_sales': float(tabby_sales), 'tabby_count': tabby_count,
        'tabby_comm': float(tabby_comm), 'tabby_vat': float(tabby_vat),
        'tabby_fee': float(tabby_fee), 'tabby_net': float(tabby_net),
        'tamara_sales': float(tamara_sales), 'tamara_count': tamara_count,
        'tamara_comm': float(tamara_comm), 'tamara_vat': float(tamara_vat),
        'tamara_net': float(tamara_net),
    }
    return render(request, 'dashboard/admin_dashboard.html', ctx)


# ─── SALES EXECUTIVE DASHBOARD ──────────────────────────────────────────────

def _sales_executive_dashboard(request):
    from django.db.models import Q
    user  = request.user
    today = timezone.now().date()
    first, last = _month_range(today)

    # Revenue is attributed by who REGISTERED the student (consultant_name),
    # not by who happened to create the invoice (Invoice.user).
    full_name = user.get_full_name() or user.username

    # Registration-linked invoices: match by registration's consultant_name
    reg_revenue = Invoice.objects.filter(
        registration__consultant_name__iexact=full_name,
        date__gte=first, date__lte=last,
    ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')

    # Standalone invoices (no registration, e.g. corporate tax): match by Invoice.user
    standalone_revenue = Invoice.objects.filter(
        user=user, registration__isnull=True,
        date__gte=first, date__lte=last,
    ).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')

    my_revenue = float(reg_revenue + standalone_revenue)

    my_target_amt, my_target_reg = _exec_target(user, first)
    my_target_f = float(my_target_amt)

    target_pct  = min(round((my_revenue / my_target_f * 100) if my_target_f else 0), 100)
    # SVG dash for 110px radius circle: circumference = 2*pi*55 ≈ 345.4
    target_dash = round(345.4 * target_pct / 100, 1)

    days_elapsed  = max((today - first).days + 1, 1)
    days_total    = (last - first).days + 1
    days_remaining = days_total - days_elapsed
    run_rate      = my_revenue / days_elapsed
    projected_rev = run_rate * days_total
    remaining     = max(my_target_f - my_revenue, 0)
    needed_daily  = remaining / days_remaining if days_remaining > 0 else 0
    run_rate_pct  = min(round((run_rate / needed_daily * 100) if needed_daily else 100), 100)
    gap           = max(my_target_f - projected_rev, 0)

    my_regs_qs = Registration.objects.filter(
        date__gte=first, date__lte=last,
        consultant_name__iexact=full_name
    ).prefetch_related('registration_courses__course', 'invoice_set')
    my_regs_count = my_regs_qs.count()

    my_quotations = Quotation.objects.filter(user=user).count()

    # All invoices attributable to this consultant this month (for avg deal size)
    all_invs = Invoice.objects.filter(
        Q(registration__consultant_name__iexact=full_name) |
        Q(user=user, registration__isnull=True),
        date__gte=first, date__lte=last,
    ).exclude(registration__is_refunded=True)
    avg_deal = float(all_invs.aggregate(t=Sum('amount_paid'))['t'] or 0) / max(all_invs.count(), 1)

    # weekly revenue (last 7 weeks) — same attribution logic
    weekly_labels = []
    weekly_data   = []
    for i in range(6, -1, -1):
        wstart = today - datetime.timedelta(days=today.weekday() + 7*i)
        wend   = wstart + datetime.timedelta(days=6)
        v = Invoice.objects.filter(
            Q(registration__consultant_name__iexact=full_name) |
            Q(user=user, registration__isnull=True),
            date__gte=wstart, date__lte=wend,
        ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or 0
        weekly_labels.append(wstart.strftime('%b %d'))
        weekly_data.append(float(v))

    ctx = {
        'current_month_label': _month_label(today),
        'my_revenue': my_revenue, 'my_target': my_target_f,
        'target_pct': target_pct, 'target_dash': target_dash,
        'remaining': remaining,
        'my_registrations': my_regs_count, 'target_reg': my_target_reg,
        'run_rate': run_rate, 'days_remaining': days_remaining,
        'projected_revenue': projected_rev,
        'needed_daily': needed_daily, 'run_rate_pct': run_rate_pct,
        'gap_to_target': gap,
        'my_quotations': my_quotations, 'avg_deal': avg_deal,
        'my_registrations_list': my_regs_qs[:10],
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_data': json.dumps(weekly_data),
    }
    return render(request, 'dashboard/sales_executive_dashboard.html', ctx)


# ─── SALES MANAGER DASHBOARD ────────────────────────────────────────────────

def _sales_manager_dashboard(request):
    today = timezone.now().date()
    first, last = _month_range(today)
    prev_first, prev_last = _last_month_range(today)

    from django.contrib.auth.models import User
    from django.db.models import Count

    executives = User.objects.filter(profile__role='sales_executive', is_active=True)

    exec_names = [ex.get_full_name() or ex.username for ex in executives]
    team_revenue = Invoice.objects.filter(
        registration__consultant_name__in=exec_names,
        date__gte=first, date__lte=last
    ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or 0
    prev_team_rev = Invoice.objects.filter(
        registration__consultant_name__in=exec_names,
        date__gte=prev_first, date__lte=prev_last
    ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or 0
    rev_pct, rev_dir = _pct_change(team_revenue, prev_team_rev)

    team_regs     = Registration.objects.filter(date__gte=first, date__lte=last).count()
    prev_team_reg = Registration.objects.filter(date__gte=prev_first, date__lte=prev_last).count()
    reg_pct, _    = _pct_change(team_regs, prev_team_reg)

    colors = [('#2563eb','#7c3aed'),('#10b981','#059669'),('#f59e0b','#d97706'),
              ('#8b5cf6','#7c3aed'),('#ef4444','#dc2626'),('#06b6d4','#0891b2')]

    days_elapsed  = max((today - first).days + 1, 1)
    days_total    = (last - first).days + 1

    exec_perf = []
    for i, ex in enumerate(executives):
        rev   = float(_revenue_for_user(ex, first, last))
        tamt, treg = _exec_target(ex, first)
        pct   = min(round((rev / float(tamt) * 100) if tamt else 0), 100)
        run_r = rev / days_elapsed
        proj  = run_r * days_total
        exec_perf.append({
            'id': ex.id, 'username': ex.username,
            'full_name': ex.get_full_name() or ex.username,
            'month_revenue': rev, 'month_registrations': Registration.objects.filter(
                date__gte=first, date__lte=last,
                consultant_name__iexact=ex.get_full_name() or ex.username).count(),
            'target_pct': pct, 'target_amount': float(tamt),
            'projected': proj,
            'color1': colors[i % len(colors)][0], 'color2': colors[i % len(colors)][1],
            'rank': i + 1,
        })
    exec_perf.sort(key=lambda x: x['month_revenue'], reverse=True)
    for idx, ep in enumerate(exec_perf):
        ep['rank'] = idx + 1

    exec_labels  = json.dumps([e['full_name'] for e in exec_perf])
    exec_rev_data= json.dumps([e['month_revenue'] for e in exec_perf])
    exec_tgt_data= json.dumps([e['target_amount'] for e in exec_perf])

    # 6-month team trend
    months = _last_6_months()
    trend_labels = json.dumps([m.strftime('%b') for m in months])
    trend_data   = []
    for m in months:
        mf = m; ml = m.replace(day=calendar.monthrange(m.year, m.month)[1])
        v = Invoice.objects.filter(
                registration__consultant_name__in=exec_names,
                date__gte=mf, date__lte=ml
            ).exclude(registration__is_refunded=True).aggregate(t=Sum('amount_paid'))['t'] or 0
        trend_data.append(float(v))
    trend_data = json.dumps(trend_data)

    ctx = {
        'current_month_label': _month_label(today),
        'team_revenue': float(team_revenue), 'team_rev_dir': rev_dir, 'team_rev_pct': rev_pct,
        'team_registrations': team_regs, 'reg_trend_pct': reg_pct,
        'exec_performance': exec_perf,
        'exec_labels': exec_labels, 'exec_revenue_data': exec_rev_data,
        'exec_target_data': exec_tgt_data,
        'trend_labels': trend_labels, 'trend_data': trend_data,
    }
    return render(request, 'dashboard/sales_manager_dashboard.html', ctx)


# ─── ACCOUNTS DASHBOARD ─────────────────────────────────────────────────────

def _accounts_dashboard(request):
    today = timezone.now().date()
    first, last = _month_range(today)
    prev_first, prev_last = _last_month_range(today)

    month_rev = Invoice.objects.filter(date__gte=first, date__lte=last)\
                  .aggregate(t=Sum('amount_paid'))['t'] or 0
    prev_rev  = Invoice.objects.filter(date__gte=prev_first, date__lte=prev_last)\
                  .aggregate(t=Sum('amount_paid'))['t'] or 0
    rev_pct, rev_dir = _pct_change(month_rev, prev_rev)

    outstanding = Invoice.objects.exclude(status='Full Payment')\
                    .aggregate(t=Sum('total_amount'))['t'] or 0
    paid_inv    = Invoice.objects.filter(date__gte=first, date__lte=last, status='Full Payment')
    paid_count  = paid_inv.count()
    paid_amt    = paid_inv.aggregate(t=Sum('amount_paid'))['t'] or 0

    overdue_qs  = Invoice.objects.filter(due_date__lt=today).exclude(status='Full Payment')
    overdue_count = overdue_qs.count()

    total_inv_m = Invoice.objects.filter(date__gte=first, date__lte=last).count()
    pending_inv = Invoice.objects.filter(date__gte=first, date__lte=last)\
                    .exclude(status='Full Payment').count()

    # annotate overdue with days overdue
    overdue_list = []
    for inv in overdue_qs.select_related('client')[:10]:
        inv.days_overdue = (today - inv.due_date).days
        overdue_list.append(inv)

    # term payment
    term_qs = Invoice.objects.filter(status='Term Payment').select_related('client')[:10]
    term_inv = []
    for inv in term_qs:
        inv.balance = inv.total_amount - inv.amount_paid
        term_inv.append(inv)

    # 6-month collected vs outstanding
    months = _last_6_months()
    monthly_labels = json.dumps([m.strftime('%b') for m in months])
    collected_data = []
    outstanding_data = []
    for m in months:
        mf = m; ml = m.replace(day=calendar.monthrange(m.year, m.month)[1])
        coll = Invoice.objects.filter(date__gte=mf, date__lte=ml)\
                 .aggregate(t=Sum('amount_paid'))['t'] or 0
        tot  = Invoice.objects.filter(date__gte=mf, date__lte=ml)\
                 .aggregate(t=Sum('total_amount'))['t'] or 0
        collected_data.append(float(coll))
        outstanding_data.append(float(tot) - float(coll))

    # payment methods
    from django.db.models import Count
    pm = Invoice.objects.filter(date__gte=first, date__lte=last)\
           .values('payment').annotate(c=Count('id'))
    pm_labels = [x['payment'] for x in pm] or ['—']
    pm_values = [x['c'] for x in pm] or [0]

    # purchase invoices
    from .models import InvoicePurchase
    purchase_qs = InvoicePurchase.objects.filter(date__gte=first, date__lte=last)
    purchase_count = purchase_qs.count()
    purchase_total = float(purchase_qs.aggregate(t=Sum('total_amount'))['t'] or 0)
    net_revenue    = float(month_rev) - purchase_total

    ctx = {
        'current_month_label': _month_label(today),
        'month_revenue': float(month_rev), 'rev_trend_dir': rev_dir, 'rev_trend_pct': rev_pct,
        'outstanding_amount': float(outstanding), 'overdue_count': overdue_count,
        'paid_invoices': paid_count, 'paid_amount': float(paid_amt),
        'total_invoices': total_inv_m, 'pending_invoices': pending_inv,
        'overdue_invoices': overdue_list, 'term_invoices': term_inv,
        'monthly_labels': monthly_labels,
        'collected_data': json.dumps(collected_data),
        'outstanding_data': json.dumps(outstanding_data),
        'payment_method_data': json.dumps({'labels': pm_labels, 'values': pm_values}),
        'purchase_count': purchase_count, 'purchase_total': purchase_total,
        'net_revenue': net_revenue,
    }
    return render(request, 'dashboard/accounts_dashboard.html', ctx)


# ─── MANAGE USERS ───────────────────────────────────────────────────────────

@login_required
def sync_all_crm_users(request):
    """Re-push every sales_manager / sales_executive to the CRM DB so flags are current."""
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User
    sales_users = User.objects.select_related('profile').filter(
        profile__role__in=('sales_manager', 'sales_executive'), is_active=True
    )
    ok = fail = 0
    for u in sales_users:
        try:
            sync_user_to_crm(u, role=u.profile.role)
            ok += 1
        except Exception:
            fail += 1
    messages.success(request, f"CRM sync done — {ok} user(s) updated, {fail} failed.")
    return redirect('manage_users')


@login_required
def manage_users(request):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User
    users = User.objects.select_related('profile').order_by('username')
    for u in users:
        if not hasattr(u, 'profile') or u.profile is None:
            UserProfile.objects.get_or_create(user=u, defaults={'role': 'sales_executive'})
    users = User.objects.select_related('profile').order_by('username')
    return render(request, 'dashboard/manage_users.html', {'users': users})


@login_required
def update_user_role(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    if request.method == 'POST':
        from django.contrib.auth.models import User
        u = get_object_or_404(User, pk=user_id)
        role = request.POST.get('role', 'sales_executive')
        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.role = role
        profile.save()
        # Sync to CRM for sales roles
        if role in ('sales_manager', 'sales_executive'):
            sync_user_to_crm(u, role=role)
            messages.success(request, f"Role updated for {u.username} and synced to Sales CRM.")
        else:
            messages.success(request, f"Role updated for {u.username}.")
    return redirect('manage_users')


@login_required
def edit_user(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User
    u = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=u)
    if request.method == 'POST':
        u.first_name = request.POST.get('first_name', '').strip()
        u.last_name  = request.POST.get('last_name', '').strip()
        u.email      = request.POST.get('email', '').strip()
        u.is_active  = request.POST.get('is_active') == '1'
        u.save()
        profile.role  = request.POST.get('role', 'sales_executive')
        profile.phone = request.POST.get('phone', '').strip()
        profile.save()
        if profile.role in ('sales_manager', 'sales_executive'):
            sync_user_to_crm(u, role=profile.role)
        messages.success(request, f"User '{u.username}' updated.")
        return redirect('manage_users')
    return render(request, 'dashboard/edit_user.html', {'u': u, 'profile': profile})


@login_required
def delete_user(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User
    if request.method == 'POST':
        u = get_object_or_404(User, pk=user_id)
        if u.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account.")
            return redirect('manage_users')
        username = u.username
        u.delete()
        messages.success(request, f"User '{username}' deleted.")
    return redirect('manage_users')


@login_required
def change_user_password(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User
    if request.method == 'POST':
        u = get_object_or_404(User, pk=user_id)
        new_pw = request.POST.get('new_password', '').strip()
        if len(new_pw) >= 6:
            u.set_password(new_pw)
            u.save()
            messages.success(request, f"Password changed for '{u.username}'.")
        else:
            messages.error(request, "Password must be at least 6 characters.")
    return redirect('manage_users')


# ─── SET TARGETS ────────────────────────────────────────────────────────────

@login_required
def set_targets(request):
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    from django.contrib.auth.models import User

    today = timezone.now().date()
    selected_month_str = request.GET.get('month') or request.POST.get('month') or today.strftime('%Y-%m')

    try:
        sel_year, sel_mon = map(int, selected_month_str.split('-'))
        month_first = datetime.date(sel_year, sel_mon, 1)
    except Exception:
        month_first = today.replace(day=1)
        selected_month_str = month_first.strftime('%Y-%m')

    first, last = _month_range(today)

    executives = User.objects.filter(profile__role='sales_executive', is_active=True)

    if request.method == 'POST':
        for ex in executives:
            tamt = request.POST.get(f'target_amount_{ex.id}', '').strip()
            treg = request.POST.get(f'target_reg_{ex.id}', '').strip()
            if tamt:
                SalesTarget.objects.update_or_create(
                    user=ex, month=month_first,
                    defaults={
                        'target_amount': Decimal(tamt),
                        'target_registrations': int(treg) if treg else 0,
                        'created_by': request.user,
                    }
                )
        messages.success(request, f"Targets saved for {month_first.strftime('%B %Y')}.")
        return redirect('set_targets')

    exec_data = []
    for ex in executives:
        tamt, treg = _exec_target(ex, month_first)
        rev  = float(_revenue_for_user(ex, first, last))
        regs = Registration.objects.filter(
            date__gte=first, date__lte=last,
            consultant_name__iexact=ex.get_full_name() or ex.username).count()
        pct  = min(round((rev / float(tamt) * 100) if tamt else 0), 100)
        exec_data.append({
            **ex.__dict__,
            'id': ex.id, 'username': ex.username,
            'get_full_name': ex.get_full_name,
            'target_amount': tamt, 'target_registrations': treg,
            'month_revenue': rev, 'month_registrations': regs, 'month_pct': pct,
        })

    ctx = {
        'executives': exec_data,
        'selected_month': selected_month_str,
        'current_month_label': _month_label(month_first),
    }
    return render(request, 'dashboard/set_targets.html', ctx)


# ─── KEEP OLD ORB DASHBOARD LINE (legacy) ───────────────────────────────────

@login_required
def orbit_dashboard_legacy(request):
    # Get the current date and the first day of the current month
    today = timezone.now().date()
    #today = date(2026, 1, 31) - testing the date when ever needed
    first_day_of_month = today.replace(day=1)

    # Total Registrations
    total_registrations = Registration.objects.count()

    # Total Registrations this month
    total_registrations_this_month = Registration.objects.filter(date__gte=first_day_of_month).count()

    # Total sale this month (from Invoices)
    total_sale_this_month = Invoice.objects.filter(date__gte=first_day_of_month).aggregate(
        total_sale=Sum('amount_paid'))['total_sale'] or 0

    # Total corporate sale this month
    total_corporate_sale_this_month = Invoice.objects.filter(
        date__gte=first_day_of_month,
        registration__registration_type='OC'
    ).aggregate(total_sale=Sum('amount_paid'))['total_sale'] or 0

    # VAT rate
    VAT_RATE = Decimal('0.05')
    
    # Get today's date
    today = timezone.now().date()
    
    # Subquery to get the total amount paid for each registration, including VAT
    total_paid_subquery = Invoice.objects.filter(
        registration_id=OuterRef('registration_id')
    ).values('registration_id').annotate(
        total_paid=ExpressionWrapper(
            Sum('amount_paid') * (1 + VAT_RATE),  # Adding 5% VAT
            output_field=DecimalField()
        )
    ).values('total_paid')
    
    # Get invoices due today with correct due amount calculation
    due_invoices = Invoice.objects.filter(due_date=today).annotate(
        total_paid=Coalesce(Subquery(total_paid_subquery), 0, output_field=DecimalField()),
        due_amount=F('total_amount') - F('total_paid')
    ).select_related('registration', 'registration__corporate_details').prefetch_related('items__course').order_by('registration_id', 'invoice_number')
    
    # Group invoices by registration to avoid duplicates
    grouped_invoices = {}
    for invoice in due_invoices:
        reg_id = invoice.registration_id
        if reg_id not in grouped_invoices or invoice.due_amount > grouped_invoices[reg_id].due_amount:
            # Get the course names for this invoice
            course_names = ", ".join([item.course.name for item in invoice.items.all() if item.course])
            invoice.course_names = course_names
            grouped_invoices[reg_id] = invoice

    # Consultant sales for current month (admin only)
    consultant_sales = []
    if is_admin_user(request.user):
        consultant_sales_data = Invoice.objects.filter(
            date__gte=first_day_of_month,
            registration__consultant_name__isnull=False
        ).exclude(registration__consultant_name='').values(
            'registration__consultant_name'
        ).annotate(
            total_sales=Sum('amount_paid')
        ).order_by('-total_sales')
        
        for item in consultant_sales_data:
            consultant_sales.append({
                'consultant_name': item['registration__consultant_name'],
                'total_sales': item['total_sales'] * (1 + VAT_RATE)
            })

    context = {
        'total_registrations': total_registrations,
        'total_registrations_this_month': total_registrations_this_month,
        'total_sale_this_month': total_sale_this_month * (1 + VAT_RATE),  # Adding 5% VAT
        'total_corporate_sale_this_month': total_corporate_sale_this_month * (1 + VAT_RATE),  # Adding 5% VAT
        'due_invoices': grouped_invoices.values(),
        'consultant_sales': consultant_sales,
    }

    return render(request, 'dashboard/orbit_dashboard.html', context)


def certificate_dashboard(request):
    all_certs = Certificate.objects.all().order_by('-created_at')
    paginator = Paginator(all_certs, 30)
    certificates = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'certificates/dashboard.html', {'certificates': certificates})

@require_POST
def create_certificate(request):
    try:
        certificate = Certificate.objects.create(
            register_number=request.POST['register_number'],
            student_name=request.POST['student_name'],
            course_name=request.POST['course_name'],
            from_date=request.POST['from_date'],
            end_date=request.POST['end_date'],
            grade=request.POST['grade']
        )
        # Return the URL to redirect to
        # Return a JSON response with success status and redirect URL
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('certificate_dashboard')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def print_certificate(request, pk):
    certificate = get_object_or_404(Certificate, pk=pk)
    if certificate.certificate_type == 'khda' and certificate.uploaded_certificate:
        # Redirect to the uploaded certificate file
        return redirect(certificate.uploaded_certificate.url)
    else:
        # Render the regular certificate template
        return render(request, 'certificates/print_certificate.html', {'certificate': certificate})


def khda_certificate_form(request):
    form = KHDACertificateForm()
    return render(request, 'certificates/khda_certificate_form.html', {'form': form})


@require_POST
def create_khda_certificate(request):
    try:
        form = KHDACertificateForm(request.POST, request.FILES)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.certificate_type = 'khda'
            certificate.save()
            return JsonResponse({
                'success': True,
                'message': 'KHDA Certificate created successfully.',
                'redirect_url': reverse('certificate_dashboard')
            })
        else:
            logger.error(f"Form validation errors: {form.errors}")
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    except Exception as e:
        logger.exception("Unexpected error in create_khda_certificate")
        return JsonResponse({
            'success': False,
            'errors': str(e)
        }, status=500)

@login_required
@require_POST
def delete_certificate(request, pk):
    try:
        role = request.user.profile.role
    except Exception:
        role = ''
    if request.user.username != 'admin' and role != 'admin':
        messages.error(request, "Only admins can delete certificates.")
        return redirect('certificate_dashboard')
    certificate = get_object_or_404(Certificate, pk=pk)
    certificate.delete()
    messages.success(request, "Certificate deleted successfully.")
    return redirect('certificate_dashboard')


@login_required
def proposal_dashboard(request):
    qs = Proposal.objects.select_related('course', 'trainer').order_by('-created_at')
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(client_name__icontains=search) | Q(proposal_number__icontains=search))
    paginator = Paginator(qs, 20)
    proposals = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'proposal/proposal_dashboard.html', {
        'proposals': proposals,
        'paginator': paginator,
        'search': search,
    })

@login_required
def create_proposal(request):
    if request.method == 'POST':
        form = ProposalForm(request.POST, request.FILES)
        if form.is_valid():
            proposal = form.save()
            return redirect('proposal_dashboard')
    else:
        form = ProposalForm()
    return render(request, 'proposal/create_proposal.html', {'form': form})

@login_required

def edit_proposal(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    if request.method == 'POST':
        form = ProposalForm(request.POST, request.FILES, instance=proposal)
        if form.is_valid():
            form.save()
            return redirect('proposal_dashboard')
    else:
        form = ProposalForm(instance=proposal)
    return render(request, 'proposal/edit_proposal.html', {'form': form})

@login_required
@user_passes_test(is_admin_user)
def delete_proposal(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    if request.method == 'POST':
        proposal.delete()
        return redirect('proposal_dashboard')
    return render(request, 'proposal/delete_proposal.html', {'proposal': proposal})

@login_required
def print_proposal(request, pk):
    try:
        proposal = get_object_or_404(Proposal, pk=pk)

        merger = PdfMerger()

        # Pages 1-3: cover, about, course overview (dynamic, theme-matched)
        front_html = render_to_string('proposal/proposal_front.html', {'proposal': proposal})
        front_pdf = WeasyHTML(string=front_html, base_url=request.build_absolute_uri()).write_pdf()
        merger.append(io.BytesIO(front_pdf))

        # Course syllabus PDFs for the selected course
        course_contents = CourseContent.objects.filter(course=proposal.course)
        for content in course_contents:
            if content.file and content.file.name.lower().endswith('.pdf'):
                try:
                    with default_storage.open(content.file.name, 'rb') as file:
                        merger.append(PdfReader(file))
                except Exception as e:
                    print(f"Error appending course content PDF: {str(e)}")

        # Trainer's profile PDF, if this proposal has one assigned
        if proposal.trainer and proposal.trainer.profile_pdf:
            try:
                with default_storage.open(proposal.trainer.profile_pdf.name, 'rb') as file:
                    merger.append(PdfReader(file))
            except Exception as e:
                print(f"Error appending trainer profile PDF: {str(e)}")

        # Company profile PDFs
        company_profiles = CompanyProfile.objects.exclude(company_pdf='')
        for profile in company_profiles:
            if profile.company_pdf and profile.company_pdf.name.lower().endswith('.pdf'):
                try:
                    with default_storage.open(profile.company_pdf.name, 'rb') as file:
                        merger.append(PdfReader(file))
                except Exception as e:
                    print(f"Error appending company profile PDF for {profile.name}: {str(e)}")

        # Pages 4-6: reviews, stats, contact (closes out the document)
        back_html = render_to_string('proposal/proposal_back.html', {'proposal': proposal})
        back_pdf = WeasyHTML(string=back_html, base_url=request.build_absolute_uri()).write_pdf()
        merger.append(io.BytesIO(back_pdf))

        # Write the merged PDF to a buffer
        buffer = io.BytesIO()
        merger.write(buffer)
        buffer.seek(0)

        # Return the PDF as a response
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{proposal.proposal_number}.pdf"'
        return response

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return HttpResponseServerError("Failed to generate PDF")
    
def change_logo_to_white(input_path, output_path):
    # Open the image
    with Image.open(input_path) as img:
        # Convert image to RGBA if it isn't already
        img = img.convert("RGBA")
        
        # Get the alpha channel
        alpha = img.split()[3]
        
        # Create a white image of the same size
        white = Image.new('RGBA', img.size, (255, 255, 255, 0))
        
        # Copy the alpha channel to the white image
        white.putalpha(alpha)
        
        # Save the result
        white.save(output_path)
    
def process_directory(input_dir, output_dir):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Process each file in the input directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"white_{filename}")
            change_logo_to_white(input_path, output_path)
            print(f"Processed: {filename}")


@login_required
def create_trainer_profile(request):
    if request.method == 'POST':
        form = TrainerProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect('trainer_profile_list')  # Redirect to a list of trainer profiles
    else:
        form = TrainerProfileForm()
    return render(request, 'trainerprofile/create_trainer_profile.html', {'form': form})

@login_required
def edit_trainer_profile(request, pk):
    profile = get_object_or_404(TrainerProfile, pk=pk)
    if request.method == 'POST':
        form = TrainerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('trainer_profile_list')
    else:
        form = TrainerProfileForm(instance=profile)
    return render(request, 'trainerprofile/edit_trainer_profile.html', {'form': form})

@login_required
def trainer_profile_list(request):
    search = request.GET.get('q', '')
    qs = TrainerProfile.objects.all().order_by('name')
    if search:
        qs = qs.filter(name__icontains=search)
    paginator = Paginator(qs, 20)
    profiles = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'trainerprofile/trainer_profile_list.html', {'profiles': profiles, 'search': search})

@login_required
@user_passes_test(is_admin_user)
def delete_trainer_profile(request, pk):
    profile = get_object_or_404(TrainerProfile, pk=pk)
    if request.method == 'POST':
        profile.delete()
        messages.success(request, f'Trainer profile "{profile.name}" has been deleted.')
        return redirect('trainer_profile_list')
    return render(request, 'trainerprofile/confirm_delete_trainer_profile.html', {'profile': profile})


def subscription(request):
    profiles = TrainerProfile.objects.all()
    return render(request, 'subscription/plan.html')

@login_required
def create_company_profile(request):
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect('company_profile_list')  # Redirect to a list of trainer profiles
    else:
        form = CompanyProfileForm()
    return render(request, 'companyprofile/create_company_profile.html', {'form': form})

@login_required
def edit_company_profile(request, pk):
    profile = get_object_or_404(CompanyProfile, pk=pk)
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('company_profile_list')
    else:
        form = CompanyProfileForm(instance=profile)
    return render(request, 'companyprofile/edit_company_profile.html', {'form': form})

@login_required
def company_profile_list(request):
    search = request.GET.get('q', '')
    qs = CompanyProfile.objects.all().order_by('name')
    if search:
        qs = qs.filter(name__icontains=search)
    paginator = Paginator(qs, 20)
    profiles = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'companyprofile/company_profile_list.html', {'profiles': profiles, 'search': search})

@login_required
@user_passes_test(is_admin_user)
def delete_company_profile(request, pk):
    profile = get_object_or_404(CompanyProfile, pk=pk)
    if request.method == 'POST':
        profile.delete()
        messages.success(request, f'Company profile "{profile.name}" has been deleted.')
        return redirect('company_profile_list')
    return render(request, 'companyprofile/confirm_delete_company_profile.html', {'profile': profile})

@require_POST
def remove_logo(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    
    if proposal.logo:
        if os.path.isfile(proposal.logo.path):
            os.remove(proposal.logo.path)
        proposal.logo = None
    
    if proposal.logo_white_url:
        white_logo_path = os.path.join(settings.MEDIA_ROOT, proposal.logo_white_url)
        if os.path.isfile(white_logo_path):
            os.remove(white_logo_path)
        proposal.logo_white_url = ''
    
    proposal.save()
    
    return JsonResponse({'status': 'success'})

@login_required
def payment_link(request):
    return render(request, 'payment/payment_link.html')

def _can_manage_coupons(user):
    try:
        return user.profile.role in ('admin', 'sales_manager') or user.is_superuser
    except Exception:
        return user.is_superuser

@login_required
def coupon_list(request):
    if not _can_manage_coupons(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    qs = Coupon.objects.all().order_by('-created_at')
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(description__icontains=search))
    paginator = Paginator(qs, 20)
    coupons   = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'coupons/coupon_list.html', {
        'coupons': coupons,
        'paginator': paginator,
        'search': search,
    })

@login_required
def create_coupon(request):
    if not _can_manage_coupons(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.created_by = request.user
            coupon.save()
            messages.success(request, 'Coupon created successfully!')
            return redirect('coupon_list')
    else:
        form = CouponForm()
    return render(request, 'coupons/create_coupon.html', {'form': form})

@login_required
def edit_coupon(request, pk):
    if not _can_manage_coupons(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon updated successfully!')
            return redirect('coupon_list')
    else:
        form = CouponForm(instance=coupon)
    return render(request, 'coupons/edit_coupon.html', {'form': form, 'coupon': coupon})

@login_required
def delete_coupon(request, pk):
    if not _can_manage_coupons(request.user):
        messages.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, 'Coupon deleted successfully!')
        return redirect('coupon_list')
    return render(request, 'coupons/delete_coupon.html', {'coupon': coupon})

@login_required
def validate_coupon(request):
    from django.utils import timezone as tz
    code = request.GET.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'valid': False, 'error': 'No code provided'})
    try:
        coupon = Coupon.objects.get(code=code, is_active=True)
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Invalid or inactive coupon'})
    if coupon.expiry_date and coupon.expiry_date < tz.now().date():
        return JsonResponse({'valid': False, 'error': 'Coupon has expired'})
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        return JsonResponse({'valid': False, 'error': 'Coupon usage limit reached'})
    return JsonResponse({'valid': True, 'discount': float(coupon.discount_percentage), 'code': coupon.code})


# ── Revenue Report (F18) ────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def revenue_report(request):
    import csv
    from decimal import Decimal

    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    consultant = request.GET.get('consultant', '')
    status_f   = request.GET.get('status', '')

    invoices_qs = Invoice.objects.select_related('registration').order_by('-date')

    if date_from:
        try:
            invoices_qs = invoices_qs.filter(date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            invoices_qs = invoices_qs.filter(date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if consultant:
        invoices_qs = invoices_qs.filter(registration__consultant_name__iexact=consultant)
    if status_f:
        invoices_qs = invoices_qs.filter(status=status_f)

    # Annotate due_amount for display
    invoice_list = []
    total_revenue = Decimal('0')
    total_collected = Decimal('0')
    for inv in invoices_qs:
        paid_with_vat = inv.amount_paid * Decimal('1.05')
        due = max(Decimal('0'), inv.total_amount - paid_with_vat)
        inv.due_amount = due
        invoice_list.append(inv)
        total_revenue   += inv.total_amount
        total_collected += paid_with_vat

    total_outstanding = max(Decimal('0'), total_revenue - total_collected)

    # Monthly trend
    from collections import defaultdict
    monthly = defaultdict(Decimal)
    for inv in invoice_list:
        key = inv.date.strftime('%b %Y')
        monthly[key] += inv.total_amount
    monthly_data = [{'month': k, 'revenue': float(v)} for k, v in sorted(monthly.items(), key=lambda x: x[0])]

    # Status breakdown
    status_map = defaultdict(Decimal)
    for inv in invoice_list:
        status_map[inv.get_status_display()] += inv.total_amount
    status_data = [{'status': k, 'amount': float(v)} for k, v in status_map.items()]

    # Consultant summary
    consult_map = defaultdict(lambda: {'count': 0, 'revenue': Decimal('0')})
    for inv in invoice_list:
        c = getattr(inv.registration, 'consultant_name', 'Unknown') or 'Unknown'
        consult_map[c]['count'] += 1
        consult_map[c]['revenue'] += inv.total_amount
    consultant_summary = [{'consultant': k, **v} for k, v in sorted(consult_map.items())]

    # All consultant names for filter dropdown
    consultants = list(
        Registration.objects.values_list('consultant_name', flat=True)
        .exclude(consultant_name='').exclude(consultant_name__isnull=True).distinct().order_by('consultant_name')
    )

    paginator = Paginator(invoice_list, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    import json as _json
    return render(request, 'reports/revenue_report.html', {
        'invoices': page_obj,
        'total_invoices': len(invoice_list),
        'total_revenue': total_revenue,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'monthly_data': _json.dumps(monthly_data),
        'status_data': _json.dumps(status_data),
        'consultant_summary': consultant_summary,
        'consultants': consultants,
        'date_from': date_from,
        'date_to': date_to,
        'consultant': consultant,
        'status': status_f,
    })


@login_required
@user_passes_test(is_admin_user)
def export_revenue_csv(request):
    import csv
    from decimal import Decimal

    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    consultant = request.GET.get('consultant', '')
    status_f   = request.GET.get('status', '')

    invoices_qs = Invoice.objects.select_related('registration').order_by('-date')
    if date_from:
        try:
            invoices_qs = invoices_qs.filter(date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            invoices_qs = invoices_qs.filter(date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if consultant:
        invoices_qs = invoices_qs.filter(registration__consultant_name__iexact=consultant)
    if status_f:
        invoices_qs = invoices_qs.filter(status=status_f)

    response = HttpResponse(content_type='text/csv')
    fname = f"revenue_report_{datetime.date.today()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{fname}"'

    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Date', 'Due Date', 'Student Name', 'Email', 'Consultant',
                     'Total (AED)', 'Paid (AED)', 'Paid+VAT (AED)', 'Due (AED)', 'Status', 'Payment Method'])
    for inv in invoices_qs:
        paid_vat = inv.amount_paid * Decimal('1.05')
        due = max(Decimal('0'), inv.total_amount - paid_vat)
        reg = inv.registration
        writer.writerow([
            inv.invoice_number,
            inv.date,
            inv.due_date,
            f"{reg.first_name} {reg.last_name}",
            reg.email,
            reg.consultant_name or '',
            float(inv.total_amount),
            float(inv.amount_paid),
            float(paid_vat),
            float(due),
            inv.get_status_display(),
            inv.get_payment_display(),
        ])
    return response


# ── Receivables Aging Report ─────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def receivables_aging(request):
    import datetime, csv as _csv
    today = datetime.date.today()
    unpaid = Invoice.objects.exclude(status='Full Payment').select_related('client', 'user').order_by('due_date')

    buckets = {'current': [], '1_30': [], '31_60': [], '61_90': [], 'over_90': []}
    totals = {'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, 'over_90': 0}

    for inv in unpaid:
        outstanding = float(inv.total_amount) - float(inv.amount_paid)
        if outstanding <= 0:
            continue
        days_over = (today - inv.due_date).days if inv.due_date else 0
        inv.outstanding = outstanding
        inv.days_overdue = max(days_over, 0)
        if days_over <= 0:
            buckets['current'].append(inv); totals['current'] += outstanding
        elif days_over <= 30:
            buckets['1_30'].append(inv); totals['1_30'] += outstanding
        elif days_over <= 60:
            buckets['31_60'].append(inv); totals['31_60'] += outstanding
        elif days_over <= 90:
            buckets['61_90'].append(inv); totals['61_90'] += outstanding
        else:
            buckets['over_90'].append(inv); totals['over_90'] += outstanding

    grand_total = sum(totals.values())

    if request.GET.get('export') == 'csv':
        from django.http import HttpResponse as _HR
        resp = _HR(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="aging_report_{today}.csv"'
        w = _csv.writer(resp)
        w.writerow(['Invoice #', 'Client', 'Due Date', 'Days Overdue', 'Outstanding (AED)', 'Bucket'])
        bucket_labels = {'current': 'Current', '1_30': '1-30 Days', '31_60': '31-60 Days', '61_90': '61-90 Days', 'over_90': '90+ Days'}
        for key, label in bucket_labels.items():
            for inv in buckets[key]:
                w.writerow([inv.invoice_number, inv.client.name if inv.client else '', inv.due_date, inv.days_overdue, f'{inv.outstanding:.2f}', label])
        return resp

    return render(request, 'reports/aging_report.html', {
        'buckets': buckets, 'totals': totals, 'grand_total': grand_total, 'today': today,
    })


# ── VAT Report ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def vat_report(request):
    import datetime
    from django.db.models import Sum
    today = datetime.date.today()
    date_from = request.GET.get('date_from', today.replace(day=1).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())

    try:
        df = datetime.date.fromisoformat(date_from)
        dt = datetime.date.fromisoformat(date_to)
    except ValueError:
        df, dt = today.replace(day=1), today

    invoices = Invoice.objects.filter(date__gte=df, date__lte=dt)
    total_net = float(invoices.aggregate(t=Sum('total_amount'))['t'] or 0)
    total_vat = round(total_net * 0.05, 2)
    total_gross = round(total_net * 1.05, 2)
    total_collected_net = float(invoices.aggregate(t=Sum('amount_paid'))['t'] or 0)
    total_collected_vat = round(total_collected_net * 0.05, 2)

    monthly = {}
    for inv in invoices:
        key = inv.date.strftime('%B %Y')
        if key not in monthly:
            monthly[key] = {'net': 0, 'vat': 0, 'count': 0}
        monthly[key]['net'] += float(inv.total_amount)
        monthly[key]['vat'] += float(inv.total_amount) * 0.05
        monthly[key]['count'] += 1

    if request.GET.get('export') == 'csv':
        import csv as _csv
        from django.http import HttpResponse as _HR
        resp = _HR(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="vat_report_{date_from}_to_{date_to}.csv"'
        w = _csv.writer(resp)
        w.writerow(['Month', 'Invoices', 'Net Amount (AED)', 'VAT 5% (AED)', 'Gross (AED)'])
        for month, vals in monthly.items():
            w.writerow([month, vals['count'], f"{vals['net']:.2f}", f"{vals['vat']:.2f}", f"{vals['net']+vals['vat']:.2f}"])
        w.writerow(['TOTAL', invoices.count(), f'{total_net:.2f}', f'{total_vat:.2f}', f'{total_gross:.2f}'])
        return resp

    return render(request, 'reports/vat_report.html', {
        'date_from': date_from, 'date_to': date_to,
        'total_net': total_net, 'total_vat': total_vat, 'total_gross': total_gross,
        'total_collected_net': total_collected_net, 'total_collected_vat': total_collected_vat,
        'monthly': monthly, 'invoice_count': invoices.count(),
    })


# ── Student Enrollment Report ─────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def enrollment_report(request):
    import datetime
    from django.db.models import Q
    today = datetime.date.today()
    date_from = request.GET.get('date_from', today.replace(day=1).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    consultant = request.GET.get('consultant', '')
    class_type = request.GET.get('class_type', '')

    try:
        df = datetime.date.fromisoformat(date_from)
        dt = datetime.date.fromisoformat(date_to)
    except ValueError:
        df, dt = today.replace(day=1), today

    qs = Registration.objects.filter(date__gte=df, date__lte=dt).prefetch_related('registration_courses__course', 'invoice_set')
    if consultant:
        qs = qs.filter(consultant_name__icontains=consultant)
    if class_type:
        qs = qs.filter(class_type=class_type)

    if request.GET.get('export') == 'csv':
        import csv as _csv
        from django.http import HttpResponse as _HR
        resp = _HR(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="enrollment_report_{date_from}_to_{date_to}.csv"'
        w = _csv.writer(resp)
        w.writerow(['Reg #', 'Name', 'Email', 'Phone', 'Consultant', 'Class Type', 'Date', 'Courses', 'Status'])
        for r in qs.order_by('-date'):
            courses = ', '.join(rc.course.name for rc in r.registration_courses.all())
            w.writerow([r.registration_number, f'{r.first_name} {r.last_name}', r.email, r.phone_no, r.consultant_name, r.class_type, r.date, courses, r.student_status])
        return resp

    paginator = Paginator(qs.order_by('-date'), 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'reports/enrollment_report.html', {
        'registrations': page_obj, 'date_from': date_from, 'date_to': date_to,
        'consultant': consultant, 'class_type': class_type,
        'total_count': qs.count(),
        'class_type_choices': Registration.CLASS_TYPE_CHOICES,
    })


# ── Certificate Report ────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def certificate_report(request):
    import datetime
    today = datetime.date.today()
    date_from = request.GET.get('date_from', today.replace(day=1).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    cert_type = request.GET.get('cert_type', '')

    try:
        df = datetime.date.fromisoformat(date_from)
        dt = datetime.date.fromisoformat(date_to)
    except ValueError:
        df, dt = today.replace(day=1), today

    qs = Certificate.objects.filter(created_at__date__gte=df, created_at__date__lte=dt)
    if cert_type:
        qs = qs.filter(certificate_type=cert_type)

    if request.GET.get('export') == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="certificates_{df}_{dt}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Certificate #', 'Registration #', 'Student', 'Course', 'Type', 'Grade', 'From', 'To', 'Issued'])
        for c in qs:
            writer.writerow([c.certificate_number, c.register_number, c.student_name, c.course_name, c.certificate_type, c.grade, c.from_date, c.end_date, c.created_at.date()])
        return response

    return render(request, 'reports/certificate_report.html', {
        'certificates': qs.order_by('-created_at'), 'date_from': date_from, 'date_to': date_to,
        'cert_type': cert_type, 'total_count': qs.count(),
        'khda_count': qs.filter(certificate_type='KHDA').count(),
        'internal_count': qs.filter(certificate_type='regular').count(),
    })


# ── Global Quick Search ───────────────────────────────────────────────────────

@login_required
def global_search(request):
    from django.db.models import Q
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    results = []

    regs = Registration.objects.filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(registration_number__icontains=q) | Q(email__icontains=q)
    )[:5]
    for r in regs:
        results.append({'type': 'Registration', 'icon': 'fa-user-graduate', 'title': f"{r.first_name} {r.last_name}", 'sub': r.registration_number, 'url': f'/student-dashboard/'})

    invs = Invoice.objects.filter(
        Q(invoice_number__icontains=q) | Q(client__name__icontains=q)
    ).select_related('client')[:5]
    for inv in invs:
        results.append({'type': 'Invoice', 'icon': 'fa-file-invoice', 'title': inv.invoice_number, 'sub': inv.client.name, 'url': f'/dashboard/'})

    courses = Course.objects.filter(Q(name__icontains=q) | Q(code__icontains=q))[:4]
    for c in courses:
        results.append({'type': 'Course', 'icon': 'fa-book-open', 'title': c.name, 'sub': c.code, 'url': f'/courses/'})

    certs = Certificate.objects.filter(Q(student_name__icontains=q) | Q(register_number__icontains=q) | Q(certificate_number__icontains=q))[:4]
    for cert in certs:
        results.append({'type': 'Certificate', 'icon': 'fa-certificate', 'title': cert.student_name, 'sub': cert.certificate_number, 'url': f'/certificates/'})

    return JsonResponse({'results': results})


# ── Notifications API ─────────────────────────────────────────────────────────

@login_required
def get_notifications(request):
    from .models import Notification
    notifs = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:10]
    data = [{'id': n.id, 'title': n.title, 'message': n.message, 'link': n.link, 'type': n.notif_type, 'created_at': n.created_at.strftime('%d %b %H:%M')} for n in notifs]
    return JsonResponse({'notifications': data, 'count': notifs.count()})

@login_required
def mark_notification_read(request, notif_id):
    from .models import Notification
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@login_required
def mark_all_notifications_read(request):
    from .models import Notification
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


# ── Mark Invoice as Paid (QW9) ────────────────────────────────────────────────

@login_required
@require_POST
def mark_invoice_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not (is_admin_user(request.user) or hasattr(request.user, 'profile') and request.user.profile.role == 'accounts'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    invoice.status = 'Full Payment'
    invoice.amount_paid = invoice.total_amount
    invoice.save()
    return JsonResponse({'status': 'ok', 'invoice_number': invoice.invoice_number})


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRATION SEARCH (smart autocomplete for invoice creation)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def search_registrations(request):
    """Return matching registrations for autocomplete — searches by reg number, name, phone."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    from django.db.models import Q as _Q
    results = Registration.objects.filter(
        _Q(registration_number__icontains=q) |
        _Q(first_name__icontains=q) |
        _Q(last_name__icontains=q) |
        _Q(phone_no__icontains=q) |
        _Q(email__icontains=q)
    ).select_related()[:12]
    data = []
    for r in results:
        courses = list(r.registration_courses.select_related('course').values_list('course__name', flat=True))
        data.append({
            'registration_number': r.registration_number,
            'name': f"{r.first_name} {r.last_name}",
            'type': r.get_registration_type_display(),
            'class_type': r.class_type,
            'courses': courses[:3],
        })
    return JsonResponse({'results': data})


# ═══════════════════════════════════════════════════════════════════════════
# COMPANY PORTAL (public-facing)
# ═══════════════════════════════════════════════════════════════════════════

def company_portal(request, token):
    """Public page for company to fill in their details."""
    from .models import CompanyPortalRequest
    portal = get_object_or_404(CompanyPortalRequest, token=token)
    if portal.submitted_at:
        return render(request, 'portal/company_portal_already_submitted.html', {'portal': portal})

    error = None
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        if not company_name:
            error = 'Company name is required.'
        else:
            import datetime as _dt
            portal.company_name = company_name
            portal.trade_license_number = request.POST.get('trade_license_number', '')
            portal.vat_number = request.POST.get('vat_number', '')
            portal.contact_person = request.POST.get('contact_person', '')
            portal.designation = request.POST.get('designation', '')
            portal.email = request.POST.get('email', '')
            portal.phone = request.POST.get('phone', '')
            portal.address = request.POST.get('address', '')
            portal.emirate = request.POST.get('emirate', '')
            if 'trade_license_doc' in request.FILES:
                portal.trade_license_doc = request.FILES['trade_license_doc']
            if 'vat_certificate' in request.FILES:
                portal.vat_certificate = request.FILES['vat_certificate']
            portal.submitted_at = _dt.datetime.now()
            portal.save()
            # Notify admins
            try:
                from .models import Notification
                admin_users = User.objects.filter(profile__role='admin')
                for admin in admin_users:
                    Notification.objects.create(
                        recipient=admin,
                        notif_type='system',
                        title=f"Company Portal: {portal.company_name}",
                        message=f"{portal.company_name} has submitted their company registration via the portal.",
                        link="/admin-portal/"
                    )
            except Exception:
                pass
            return redirect('company_portal_success', token=token)

    return render(request, 'portal/company_portal_form.html', {'portal': portal, 'error': error})


def company_portal_success(request, token):
    from .models import CompanyPortalRequest
    portal = get_object_or_404(CompanyPortalRequest, token=token)
    return render(request, 'portal/company_portal_success.html', {'portal': portal})


def company_portal_add_attendees(request, token):
    """Public page for company to add training attendees."""
    from .models import CompanyPortalRequest, CompanyPortalAttendee
    portal = get_object_or_404(CompanyPortalRequest, token=token)
    if not portal.submitted_at:
        return redirect('company_portal', token=token)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            CompanyPortalAttendee.objects.create(
                portal_request=portal,
                full_name=full_name,
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                designation=request.POST.get('designation', ''),
                emirates_id=request.POST.get('emirates_id', ''),
                nationality=request.POST.get('nationality', ''),
                course_name=request.POST.get('course_name', ''),
            )
        return redirect('company_portal_add_attendees', token=token)

    attendees = portal.attendees.all().order_by('added_at')
    return render(request, 'portal/company_portal_attendees.html', {'portal': portal, 'attendees': attendees})


@login_required
def admin_company_portal(request):
    """Admin view of all company portal requests."""
    from .models import CompanyPortalRequest
    requests_list = CompanyPortalRequest.objects.all().order_by('-created_at')
    return render(request, 'portal/admin_company_portal.html', {'requests': requests_list})


@login_required
def generate_company_portal_link(request):
    """Admin/sales generates a company portal link."""
    from .models import CompanyPortalRequest
    if request.method == 'POST':
        company_name = request.POST.get('company_name', 'New Company')
        portal = CompanyPortalRequest.objects.create(
            generated_by=request.user,
            company_name=company_name,
        )
        return JsonResponse({'token': portal.token, 'url': request.build_absolute_uri(f'/portal/company/{portal.token}/')})
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def approve_company_portal(request, pk):
    """Admin approves a company portal request and converts to CorporateRegistration."""
    from .models import CompanyPortalRequest
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    portal = get_object_or_404(CompanyPortalRequest, pk=pk)
    portal.status = 'approved'
    portal.save()
    return JsonResponse({'status': 'approved'})


# ═══════════════════════════════════════════════════════════════════════════
# STUDENT SELF-REGISTRATION FORM LINK
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def student_form_links(request):
    """List and manage student form links for the logged-in consultant."""
    from .models import StudentFormLink
    links = list(StudentFormLink.objects.filter(consultant=request.user).order_by('-created_at'))
    # Safely attach config to each link so template never touches the reverse descriptor
    # (avoids OperationalError if migration hasn't been applied yet)
    try:
        from .models import StudentFormLinkConfig
        cfg_map = {c.link_id: c for c in StudentFormLinkConfig.objects.filter(link_id__in=[l.pk for l in links])}
    except Exception:
        cfg_map = {}
    for lnk in links:
        lnk.link_config = cfg_map.get(lnk.pk)
        # Strip hidden level metadata from display notes
        if lnk.notes and '||LVL:' in lnk.notes:
            lnk.display_notes = lnk.notes.split('||LVL:')[0].strip()
        else:
            lnk.display_notes = lnk.notes
    courses = list(Course.objects.all().order_by('name'))
    import json as _json
    course_price_data = {
        c.id: {
            'name': c.name,
            'oo_intermediate':   float(c.oo_intermediate),
            'oo_professional':   float(c.oo_professional),
            'oo_advanced':       float(c.oo_advanced),
            'priv_intermediate': float(c.priv_intermediate),
            'priv_professional': float(c.priv_professional),
            'priv_advanced':     float(c.priv_advanced),
        }
        for c in courses
    }
    return render(request, 'portal/student_form_links.html', {
        'links': links,
        'courses': courses,
        'course_price_json': _json.dumps(course_price_data),
    })


@login_required
@require_POST
def generate_student_form_link(request):
    """Generate a new student self-registration link."""
    from .models import StudentFormLink, StudentFormLinkConfig
    import datetime as _dt
    import json as _json

    consultant_name = request.user.get_full_name() or request.user.username
    level = request.POST.get('level', 'intermediate')
    if level not in ('intermediate', 'professional', 'advanced'):
        level = 'intermediate'
    notes_raw = request.POST.get('notes', '').strip()

    # Build per-course prices before creating the link so they can be embedded in notes
    course_ids = request.POST.getlist('courses')
    course_prices = {}
    for cid in course_ids:
        price_val = request.POST.get(f'price_{cid}', '').strip()
        try:
            p = float(price_val)
            if p > 0:
                course_prices[cid] = p
        except (ValueError, TypeError):
            pass

    # Embed level + prices in notes as a fallback for when migration 0061 hasn't been applied
    prices_json = _json.dumps(course_prices, separators=(',', ':'))
    meta_suffix = f"||LVL:{level}||PRC:{prices_json}"
    notes_stored = f"{notes_raw}{meta_suffix}" if notes_raw else meta_suffix

    link = StudentFormLink.objects.create(
        consultant=request.user,
        consultant_name_locked=consultant_name,
        notes=notes_stored,
    )
    if course_ids:
        link.pre_selected_courses.set(Course.objects.filter(id__in=course_ids))

    # Also save to StudentFormLinkConfig (primary; used when migration 0061 is applied)
    try:
        StudentFormLinkConfig.objects.create(
            link=link,
            level=level,
            course_prices_json=_json.dumps(course_prices),
        )
    except Exception:
        pass  # table may not exist until migration 0061 is applied

    full_url = request.build_absolute_uri(f'/portal/student/{link.token}/')
    return JsonResponse({'token': link.token, 'url': full_url})


def student_self_register(request, token):
    """Public student registration form."""
    from .models import StudentFormLink, StudentFormLinkConfig
    link = get_object_or_404(StudentFormLink, token=token)
    if not link.is_valid():
        return render(request, 'portal/student_form_expired.html')

    # Load consultant config (level + per-course prices)
    # Primary: StudentFormLinkConfig table (migration 0061)
    # Fallback: level embedded in notes field as ||LVL:xxx
    config_level = 'intermediate'
    config_prices = {}
    try:
        cfg = link.config
        config_level = cfg.level
        config_prices = cfg.get_course_prices()
    except Exception:
        # Fallback: parse level and prices from notes field (||LVL:xxx||PRC:{json})
        import json as _json
        if link.notes and '||LVL:' in link.notes:
            try:
                meta = link.notes.split('||LVL:')[1]
                lvl_part, *prc_parts = meta.split('||PRC:')
                lvl = lvl_part.strip()
                if lvl in ('intermediate', 'professional', 'advanced'):
                    config_level = lvl
                if prc_parts:
                    config_prices = {int(k): float(v) for k, v in _json.loads(prc_parts[0]).items()}
            except Exception:
                pass

    LEVEL_LABELS = {'intermediate': 'Intermediate', 'professional': 'Professional', 'advanced': 'Advanced'}

    # CRM lead ID embedded in the link by the consultant — never shown to the student
    crm_lead_id = request.GET.get('cli', '').strip()
    if not (crm_lead_id and crm_lead_id.isdigit()):
        crm_lead_id = ''

    pre_courses = list(link.pre_selected_courses.all())
    courses = pre_courses if pre_courses else list(Course.objects.all().order_by('name'))
    courses_locked = bool(pre_courses)
    error = None
    success = False
    reg = None

    if request.method == 'POST':
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        phone_no     = request.POST.get('phone_no', '').strip()
        email        = request.POST.get('email', '').strip()
        emirates_id  = request.POST.get('emirates_id', '').strip()
        uid_no       = request.POST.get('uid_no', '').strip()
        passport_no  = request.POST.get('passport_no', '').strip()
        post_crm_lead_id = request.POST.get('crm_lead_id', '').strip()

        if not (first_name and last_name and phone_no):
            error = 'First name, last name and phone number are required.'
        elif not (emirates_id or uid_no or passport_no):
            error = 'Please provide at least one ID document: Emirates ID, UID No, or Passport No.'
        else:
            reg = Registration(
                first_name=first_name,
                last_name=last_name,
                phone_no=phone_no,
                email=email,
                nationality=request.POST.get('nationality', ''),
                emirates_id_no=emirates_id,
                uid_no=uid_no,
                passport_no=passport_no,
                country=request.POST.get('country', 'UAE'),
                consultant_name=link.consultant_name_locked,
                class_type=request.POST.get('class_type', 'offline'),
                registration_type='OT',
            )
            # DOB if provided
            dob = request.POST.get('date_of_birth', '').strip()
            if dob:
                try:
                    from datetime import date as _date
                    reg.date_of_birth = _date.fromisoformat(dob)
                except Exception:
                    pass
            try:
                reg.save()
            except Exception as e:
                error = f'Submission failed: {e}'
            else:
                # Save courses — use pre-selected if locked, else student selection
                if courses_locked:
                    selected_course_ids = [str(c.id) for c in pre_courses]
                else:
                    selected_course_ids = request.POST.getlist('course_ids')
                _class_type = reg.class_type or 'offline'
                for cid in selected_course_ids:
                    try:
                        c = Course.objects.get(id=int(cid))
                        list_price = c.get_rate(_class_type, config_level)
                        final_price = config_prices.get(int(cid), list_price)
                        # Compute discount % from list vs final price
                        if list_price and list_price > 0 and final_price < list_price:
                            discount_pct = round((1 - float(final_price) / float(list_price)) * 100, 2)
                        else:
                            discount_pct = 0
                        RegistrationCourse.objects.create(
                            registration=reg, course=c,
                            discount=discount_pct, price=final_price,
                        )
                    except Exception:
                        pass
                # Save CRM lead link (hidden from student, set by consultant via link URL)
                if post_crm_lead_id and post_crm_lead_id.isdigit():
                    _save_reg_crm_link(reg.pk, int(post_crm_lead_id),
                                       linked_by=link.consultant.username)
                link.use_count += 1
                link.save()
                # Sync to CRM student list
                sync_registration_to_crm(reg, consultant_username=link.consultant.username)
                # Welcome email sent by cron 1 hour after registration
                # Notify consultant
                try:
                    from .models import Notification
                    Notification.objects.create(
                        recipient=link.consultant,
                        notif_type='registration_new',
                        title=f"New Self-Registration: {first_name} {last_name}",
                        message=f"Student {first_name} {last_name} registered via your form link.",
                        link="/student-dashboard/"
                    )
                except Exception:
                    pass
                success = True

    # For success screen: show enrolled courses with prices
    success_courses = []
    if success and reg is not None:
        try:
            success_courses = list(reg.registration_courses.select_related('course').all())
        except Exception:
            pass

    return render(request, 'portal/student_self_register.html', {
        'link': link,
        'courses': courses,
        'courses_locked': courses_locked,
        'config_level': config_level,
        'level_label': LEVEL_LABELS.get(config_level, 'Intermediate'),
        'error': error,
        'success': success,
        'crm_lead_id': crm_lead_id,
        'success_courses': success_courses,
        'success_reg': reg,
    })


# ═══════════════════════════════════════════════════════════════════════════
# STUDENT STATUS UPDATE (inline AJAX)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def update_student_status(request, pk):
    from .models import AuditLog
    reg = get_object_or_404(Registration, pk=pk)
    new_status = request.POST.get('status', '')
    valid = [s[0] for s in Registration.STUDENT_STATUS_CHOICES]
    if new_status not in valid:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    old_status = reg.student_status
    reg.student_status = new_status
    reg.save()
    ip = request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        user=request.user, action='status_change', model_name='Registration',
        object_id=str(reg.pk), object_repr=str(reg),
        changes=f'{old_status} → {new_status}', ip_address=ip
    )
    # Propagate status change to CRM
    sync_registration_to_crm(reg, consultant_username=request.user.username)
    return JsonResponse({'status': new_status, 'label': reg.get_student_status_display()})


# ═══════════════════════════════════════════════════════════════════════════
# BULK INVOICE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def bulk_invoice_action(request):
    import csv as _csv
    from .models import AuditLog
    action = request.POST.get('action', '')
    ids = request.POST.getlist('invoice_ids')
    if not ids:
        return JsonResponse({'error': 'No invoices selected'}, status=400)

    invoices = Invoice.objects.filter(pk__in=ids)

    if action == 'mark_paid':
        if not (is_admin_user(request.user) or (hasattr(request.user, 'profile') and request.user.profile.role in ['admin', 'accounts'])):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        count = 0
        for inv in invoices:
            if inv.status != 'Full Payment':
                inv.status = 'Full Payment'
                inv.amount_paid = inv.total_amount
                inv.save()
                AuditLog.objects.create(user=request.user, action='status_change', model_name='Invoice', object_id=str(inv.pk), object_repr=inv.invoice_number, changes='Bulk marked as Paid', ip_address=request.META.get('REMOTE_ADDR'))
                count += 1
        return JsonResponse({'status': 'ok', 'count': count})

    if action == 'export_csv':
        from django.http import HttpResponse as _HR
        resp = _HR(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="invoices_export.csv"'
        w = _csv.writer(resp)
        w.writerow(['Invoice #', 'Client', 'Date', 'Due Date', 'Amount', 'Paid', 'Balance', 'Status', 'Reg #'])
        for inv in invoices.select_related('client', 'registration'):
            balance = float(inv.total_amount) - float(inv.amount_paid)
            w.writerow([
                inv.invoice_number,
                inv.client.name if inv.client else '',
                inv.date, inv.due_date,
                inv.total_amount, inv.amount_paid,
                f'{balance:.2f}', inv.status,
                inv.registration.registration_number if inv.registration else ''
            ])
        AuditLog.objects.create(user=request.user, action='export', model_name='Invoice', object_repr=f'{len(ids)} invoices', ip_address=request.META.get('REMOTE_ADDR'))
        return resp

    return JsonResponse({'error': 'Unknown action'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
# INVOICE PAYMENT INSTALLMENTS
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def invoice_payments(request, pk):
    from .models import InvoicePayment
    invoice = get_object_or_404(Invoice, pk=pk)
    payments = invoice.payments.all()
    total_paid = sum(p.amount for p in payments)
    return JsonResponse({
        'invoice_number': invoice.invoice_number,
        'total_amount': float(invoice.total_amount),
        'payments': [
            {'id': p.id, 'amount': float(p.amount), 'method': p.get_payment_method_display(),
             'reference': p.reference, 'paid_at': str(p.paid_at), 'notes': p.notes}
            for p in payments
        ],
        'total_recorded': float(total_paid),
        'balance': float(invoice.total_amount) - float(total_paid),
    })


@login_required
@require_POST
def add_invoice_payment(request, pk):
    from .models import InvoicePayment, AuditLog
    from decimal import Decimal as _Dec
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        amount = _Dec(request.POST.get('amount', '0'))
        if amount <= 0:
            raise ValueError()
    except (ValueError, Exception):
        return JsonResponse({'error': 'Invalid amount'}, status=400)

    method = request.POST.get('payment_method', 'cash')
    paid_at = request.POST.get('paid_at', '') or str(invoice.date)
    reference = request.POST.get('reference', '')
    notes = request.POST.get('notes', '')

    payment = InvoicePayment.objects.create(
        invoice=invoice, amount=amount, payment_method=method,
        reference=reference, paid_at=paid_at,
        recorded_by=request.user, notes=notes
    )
    # Update invoice.amount_paid
    total_paid = sum(p.amount for p in invoice.payments.all())
    invoice.amount_paid = total_paid
    if total_paid >= invoice.total_amount:
        invoice.status = 'Full Payment'
    invoice.save()

    AuditLog.objects.create(
        user=request.user, action='payment', model_name='Invoice',
        object_id=str(invoice.pk), object_repr=invoice.invoice_number,
        changes=f'AED {amount} via {method}', ip_address=request.META.get('REMOTE_ADDR')
    )
    return JsonResponse({
        'status': 'ok', 'payment_id': payment.id,
        'total_paid': float(invoice.amount_paid),
        'invoice_status': invoice.status
    })


# ═══════════════════════════════════════════════════════════════════════════
# TRAINING SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def training_schedule_list(request):
    from .models import TrainingSchedule
    import datetime
    schedules = TrainingSchedule.objects.select_related('course', 'created_by').all()
    status_filter = request.GET.get('status', '')
    if status_filter:
        schedules = schedules.filter(status=status_filter)
    today = datetime.date.today()
    # Auto-update status
    for s in schedules:
        if s.status == 'upcoming' and s.start_date <= today:
            s.status = 'ongoing' if s.end_date >= today else 'completed'
            s.save()
    return render(request, 'schedule/schedule_list.html', {
        'schedules': schedules,
        'status_filter': status_filter,
        'today': today,
        'courses': Course.objects.all().order_by('name'),
    })


@login_required
def training_schedule_create(request):
    from .models import TrainingSchedule
    error = None
    if request.method == 'POST':
        try:
            s = TrainingSchedule(
                course=Course.objects.get(pk=request.POST['course']),
                title=request.POST['title'],
                class_type=request.POST.get('class_type', 'offline'),
                start_date=request.POST['start_date'],
                end_date=request.POST['end_date'],
                start_time=request.POST.get('start_time') or None,
                end_time=request.POST.get('end_time') or None,
                venue=request.POST.get('venue', ''),
                max_capacity=int(request.POST.get('max_capacity') or 0),
                instructor=request.POST.get('instructor', ''),
                notes=request.POST.get('notes', ''),
                status=request.POST.get('status', 'upcoming'),
                created_by=request.user,
            )
            s.save()
            from .models import AuditLog
            AuditLog.objects.create(user=request.user, action='create', model_name='TrainingSchedule', object_id=str(s.pk), object_repr=str(s))
            return redirect('training_schedule_list')
        except Exception as e:
            error = str(e)
    courses = Course.objects.all().order_by('name')
    return render(request, 'schedule/schedule_form.html', {'courses': courses, 'error': error, 'mode': 'create'})


@login_required
def training_schedule_edit(request, pk):
    from .models import TrainingSchedule
    schedule = get_object_or_404(TrainingSchedule, pk=pk)
    error = None
    if request.method == 'POST':
        try:
            schedule.course = Course.objects.get(pk=request.POST['course'])
            schedule.title = request.POST['title']
            schedule.class_type = request.POST.get('class_type', 'offline')
            schedule.start_date = request.POST['start_date']
            schedule.end_date = request.POST['end_date']
            schedule.start_time = request.POST.get('start_time') or None
            schedule.end_time = request.POST.get('end_time') or None
            schedule.venue = request.POST.get('venue', '')
            schedule.max_capacity = int(request.POST.get('max_capacity') or 0)
            schedule.instructor = request.POST.get('instructor', '')
            schedule.notes = request.POST.get('notes', '')
            schedule.status = request.POST.get('status', schedule.status)
            schedule.save()
            return redirect('training_schedule_list')
        except Exception as e:
            error = str(e)
    courses = Course.objects.all().order_by('name')
    return render(request, 'schedule/schedule_form.html', {'courses': courses, 'schedule': schedule, 'error': error, 'mode': 'edit'})


@login_required
@require_POST
def training_schedule_delete(request, pk):
    from .models import TrainingSchedule
    schedule = get_object_or_404(TrainingSchedule, pk=pk)
    schedule.delete()
    return redirect('training_schedule_list')


# ═══════════════════════════════════════════════════════════════════════════
# EXPENSE TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def expense_list(request):
    from .models import Expense
    from django.db.models import Sum
    import datetime
    today = datetime.date.today()
    month_start = today.replace(day=1)

    expenses = Expense.objects.select_related('course', 'recorded_by')
    cat_filter = request.GET.get('category', '')
    month_filter = request.GET.get('month', '')
    if cat_filter:
        expenses = expenses.filter(category=cat_filter)
    if month_filter:
        try:
            y, m = month_filter.split('-')
            expenses = expenses.filter(expense_date__year=y, expense_date__month=m)
        except Exception:
            pass

    total = expenses.aggregate(t=Sum('amount'))['t'] or 0
    total_vat = expenses.aggregate(t=Sum('vat_amount'))['t'] or 0
    month_total = Expense.objects.filter(expense_date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0

    return render(request, 'expenses/expense_list.html', {
        'expenses': expenses.order_by('-expense_date'),
        'total': total, 'total_vat': total_vat, 'month_total': month_total,
        'cat_filter': cat_filter, 'month_filter': month_filter,
        'categories': Expense.CATEGORY_CHOICES,
        'courses': Course.objects.all().order_by('name'),
    })


@login_required
def expense_create(request):
    from .models import Expense, AuditLog
    error = None
    if request.method == 'POST':
        try:
            from decimal import Decimal as _D
            e = Expense(
                category=request.POST['category'],
                description=request.POST['description'],
                amount=_D(request.POST['amount']),
                vat_amount=_D(request.POST.get('vat_amount') or '0'),
                vendor=request.POST.get('vendor', ''),
                expense_date=request.POST['expense_date'],
                payment_method=request.POST.get('payment_method', ''),
                receipt_ref=request.POST.get('receipt_ref', ''),
                notes='',
                recorded_by=request.user,
            )
            course_id = request.POST.get('course')
            if course_id:
                e.course = Course.objects.get(pk=course_id)
            e.save()
            AuditLog.objects.create(user=request.user, action='create', model_name='Expense', object_id=str(e.pk), object_repr=str(e))
            return redirect('expense_list')
        except Exception as ex:
            error = str(ex)
    return render(request, 'expenses/expense_form.html', {
        'courses': Course.objects.all().order_by('name'),
        'categories': Expense.CATEGORY_CHOICES,
        'error': error, 'mode': 'create'
    })


@login_required
def expense_edit(request, pk):
    from .models import Expense, AuditLog
    expense = get_object_or_404(Expense, pk=pk)
    error = None
    if request.method == 'POST':
        try:
            from decimal import Decimal as _D
            expense.category = request.POST['category']
            expense.description = request.POST['description']
            expense.amount = _D(request.POST['amount'])
            expense.vat_amount = _D(request.POST.get('vat_amount') or '0')
            expense.vendor = request.POST.get('vendor', '')
            expense.expense_date = request.POST['expense_date']
            expense.payment_method = request.POST.get('payment_method', '')
            expense.receipt_ref = request.POST.get('receipt_ref', '')
            course_id = request.POST.get('course')
            expense.course = Course.objects.get(pk=course_id) if course_id else None
            expense.save()
            return redirect('expense_list')
        except Exception as ex:
            error = str(ex)
    return render(request, 'expenses/expense_form.html', {
        'courses': Course.objects.all().order_by('name'),
        'categories': Expense.CATEGORY_CHOICES,
        'expense': expense, 'error': error, 'mode': 'edit'
    })


@login_required
@require_POST
def expense_delete(request, pk):
    from .models import Expense
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    return redirect('expense_list')


@login_required
def expense_report(request):
    from .models import Expense
    from django.db.models import Sum
    import datetime, json as _json
    today = datetime.date.today()
    year = int(request.GET.get('year', today.year))

    expenses_qs = Expense.objects.filter(expense_date__year=year)
    # Revenue for comparison (same year)
    revenue_qs = Invoice.objects.filter(date__year=year)
    total_revenue = float(revenue_qs.aggregate(t=Sum('total_amount'))['t'] or 0)
    total_expense = float(expenses_qs.aggregate(t=Sum('amount'))['t'] or 0)
    net_profit = total_revenue - total_expense

    # By category
    by_cat = {}
    for e in expenses_qs:
        by_cat[e.category] = by_cat.get(e.category, 0) + float(e.amount)

    # Monthly expenses
    monthly = [0] * 12
    for e in expenses_qs:
        monthly[e.expense_date.month - 1] += float(e.amount)

    # Monthly revenue
    monthly_rev = [0] * 12
    for inv in revenue_qs:
        monthly_rev[inv.date.month - 1] += float(inv.total_amount)

    return render(request, 'expenses/expense_report.html', {
        'year': year, 'total_revenue': total_revenue,
        'total_expense': total_expense, 'net_profit': net_profit,
        'by_cat': by_cat, 'monthly': _json.dumps(monthly),
        'monthly_rev': _json.dumps(monthly_rev),
        'expense_categories': Expense.CATEGORY_CHOICES,
        'expenses': expenses_qs.order_by('-expense_date')[:50],
    })


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def audit_log_view(request):
    from .models import AuditLog
    if not (is_admin_user(request.user)):
        from django.contrib import messages as _msg
        _msg.error(request, 'Access denied.')
        return redirect('orbit_dashboard')
    logs = AuditLog.objects.select_related('user').all()
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    user_filter = request.GET.get('user', '')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if model_filter:
        logs = logs.filter(model_name__icontains=model_filter)
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    from .models import AuditLog as _AL
    return render(request, 'audit/audit_log.html', {
        'logs': page_obj, 'action_filter': action_filter,
        'model_filter': model_filter, 'user_filter': user_filter,
        'action_choices': _AL.ACTION_CHOICES,
    })


# ═══════════════════════════════════════════════════════════════════════════
# FEE REMINDER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def fee_reminder_dashboard(request):
    from .models import FeeReminderLog
    from decimal import Decimal

    today    = timezone.now().date()
    week_end = today + datetime.timedelta(days=7)

    _base = Invoice.objects.select_related('client', 'user')

    # Separate querysets per section
    overdue_qs   = _base.filter(amount_paid__lt=F('total_amount'), due_date__lt=today).order_by('due_date')
    due_today_qs = _base.filter(amount_paid__lt=F('total_amount'), due_date=today).order_by('id')
    upcoming_qs  = _base.filter(amount_paid__lt=F('total_amount'), due_date__gt=today, due_date__lte=week_end).order_by('due_date')

    # KPI totals (aggregate, not paginated)
    _expr = lambda: ExpressionWrapper(F('total_amount') - F('amount_paid'), output_field=DecimalField())
    overdue_amount  = Invoice.objects.filter(amount_paid__lt=F('total_amount'), due_date__lt=today) \
                          .aggregate(t=Sum(_expr()))['t'] or 0
    upcoming_amount = Invoice.objects.filter(amount_paid__lt=F('total_amount'), due_date__gt=today, due_date__lte=week_end) \
                          .aggregate(t=Sum(_expr()))['t'] or 0
    overdue_count  = overdue_qs.count()
    today_count    = due_today_qs.count()
    upcoming_count = upcoming_qs.count()

    # Handle "Send Reminder" POST
    if request.method == 'POST':
        invoice_id = request.POST.get('invoice_id')
        channel    = request.POST.get('channel', 'system')
        note       = request.POST.get('note', '').strip()
        inv  = get_object_or_404(Invoice, pk=invoice_id)
        days = (today - inv.due_date).days
        FeeReminderLog.objects.create(
            invoice=inv,
            client_name=inv.client.name if inv.client else '—',
            invoice_number=inv.invoice_number,
            amount_due=inv.total_amount - inv.amount_paid,
            due_date=inv.due_date,
            days_overdue=days,
            channel=channel,
            sent_by=request.user,
            note=note,
        )
        if inv.user:
            try:
                Notification.objects.create(
                    recipient=inv.user,
                    notif_type='overdue_invoice' if days > 0 else 'invoice_due',
                    title=f"Fee Reminder: {inv.invoice_number}",
                    message=f"Reminder sent for {'overdue ' if days>0 else 'upcoming '}{inv.invoice_number} "
                            f"(AED {inv.total_amount - inv.amount_paid:,.2f} due {inv.due_date.strftime('%d %b %Y')})",
                    link=f'/invoice/{inv.pk}/',
                )
            except Exception:
                pass
        if channel == 'email' and inv.client and inv.client.email:
            _send_fee_reminder_email(inv, days, note, request)
        messages.success(request, f"Reminder logged for invoice {inv.invoice_number}.")
        return redirect('fee_reminder_dashboard')

    # Paginate each section
    o_pag = Paginator(overdue_qs, 20)
    d_pag = Paginator(due_today_qs, 20)
    u_pag = Paginator(upcoming_qs, 20)
    overdue   = o_pag.get_page(request.GET.get('opage', 1))
    due_today = d_pag.get_page(request.GET.get('dpage', 1))
    upcoming  = u_pag.get_page(request.GET.get('upage', 1))

    # Reminder history (paginated)
    reminder_qs = FeeReminderLog.objects.select_related('sent_by').all()
    r_paginator = Paginator(reminder_qs, 20)
    reminder_page = r_paginator.get_page(request.GET.get('rpage', 1))

    return render(request, 'invoices/fee_reminder_dashboard.html', {
        'overdue': overdue,
        'due_today': due_today,
        'upcoming': upcoming,
        'overdue_count': overdue_count,
        'today_count': today_count,
        'upcoming_count': upcoming_count,
        'overdue_amount': overdue_amount,
        'upcoming_amount': upcoming_amount,
        'today': today,
        'reminders': reminder_page,
        'r_paginator': r_paginator,
    })


def _find_logo_path():
    """Return the filesystem path of Orbit-Logo-1.png, or None."""
    import os
    from django.conf import settings as _s
    for p in [
        os.path.join(_s.BASE_DIR, 'invoices', 'static', 'Orbit-Logo-1.png'),
        os.path.join(_s.BASE_DIR, 'staticfiles', 'Orbit-Logo-1.png'),
        os.path.join(_s.BASE_DIR, 'static', 'images', 'Orbit-Logo-1.png'),
        os.path.join(_s.BASE_DIR, 'invoice_project', 'static', 'Orbit-Logo-1.png'),
    ]:
        if os.path.exists(p):
            return p
    return None


def _logo_data_uri():
    """Return Orbit logo as base64 data URI (kept for any legacy callers)."""
    import base64
    p = _find_logo_path()
    if p:
        try:
            with open(p, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{data}"
        except Exception:
            pass
    return ''


def _attach_logo_inline(msg):
    """Attach the Orbit logo as a CID inline image on an EmailMultiAlternatives msg.

    Using CID attachments instead of data: URIs because Outlook and some
    corporate mail clients strip data: URIs from <img> src attributes.
    """
    from email.mime.image import MIMEImage
    path = _find_logo_path()
    if not path:
        return False
    try:
        with open(path, 'rb') as f:
            img = MIMEImage(f.read())
        img.add_header('Content-ID', '<orbit_logo>')
        img.add_header('Content-Disposition', 'inline', filename='logo.png')
        msg.attach(img)
        msg.mixed_subtype = 'related'
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# REFUND SYSTEM
# ─────────────────────────────────────────────

@login_required
def initiate_refund(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    if registration.is_refunded:
        messages.error(request, "This registration has already been refunded.")
        return redirect('registration_invoice_detail', registration_id=pk)

    # Prevent duplicate pending refund
    existing = Refund.objects.filter(registration=registration).first()
    if existing and existing.status == 'pending':
        messages.warning(request, "A refund request is already pending for this registration.")
        return redirect('confirm_refund', pk=existing.pk)

    invoices = Invoice.objects.filter(registration=registration)
    total_paid = invoices.aggregate(t=Sum('amount_paid'))['t'] or 0

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        amount = request.POST.get('amount', '0').strip()
        doc = request.FILES.get('document')

        if not reason:
            messages.error(request, "Please provide a reason for the refund.")
            return render(request, 'refunds/initiate_refund.html', {
                'registration': registration, 'total_paid': total_paid, 'invoices': invoices,
            })

        try:
            amount_dec = Decimal(amount)
        except Exception:
            amount_dec = Decimal('0')

        refund = Refund.objects.create(
            registration=registration,
            reason=reason,
            amount=amount_dec,
            document=doc,
            initiated_by=request.user,
            status='pending',
        )
        return redirect('confirm_refund', pk=refund.pk)

    return render(request, 'refunds/initiate_refund.html', {
        'registration': registration,
        'total_paid': total_paid,
        'invoices': invoices,
    })


@login_required
def confirm_refund(request, pk):
    refund = get_object_or_404(Refund, pk=pk)
    registration = refund.registration

    if refund.status != 'pending':
        messages.error(request, "This refund has already been processed.")
        return redirect('refund_list')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cancel':
            refund.status = 'cancelled'
            refund.save(update_fields=['status'])
            messages.success(request, "Refund cancelled.")
            return redirect('registration_invoice_detail', registration_id=registration.pk)

        if action == 'confirm':
            refund.admin_notes = request.POST.get('admin_notes', '').strip()
            refund.refund_reference = request.POST.get('refund_reference', '').strip()
            refund.status = 'confirmed'
            refund.confirmed_by = request.user
            refund.confirmed_at = timezone.now()
            refund.save()

            # Mark registration as refunded
            registration.is_refunded = True
            registration.save(update_fields=['is_refunded'])

            # Send confirmation email to student
            _send_refund_email(refund, request)

            messages.success(request, f"Refund confirmed for {registration.first_name} {registration.last_name}. Email sent to {registration.email}.")
            return redirect('refund_list')

    invoices = Invoice.objects.filter(registration=registration)
    return render(request, 'refunds/confirm_refund.html', {
        'refund': refund,
        'registration': registration,
        'invoices': invoices,
    })


def _send_refund_email(refund, request):
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _s
    reg = refund.registration
    subject = f"Refund Confirmation — {reg.registration_number}"
    amount_str = f"AED {float(refund.amount):,.2f}" if refund.amount else "as discussed"
    ref_str = f" (Ref: {refund.refund_reference})" if refund.refund_reference else ""
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;">
      <h2 style="color:#1e40af;">Refund Confirmation</h2>
      <p>Dear <strong>{reg.first_name} {reg.last_name}</strong>,</p>
      <p>We confirm that a refund has been processed for your registration.</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:8px;background:#f8fafc;font-weight:600;width:40%;">Registration No.</td>
            <td style="padding:8px;">{reg.registration_number}</td></tr>
        <tr><td style="padding:8px;font-weight:600;">Refund Amount</td>
            <td style="padding:8px;color:#059669;font-weight:700;">{amount_str}</td></tr>
        <tr><td style="padding:8px;background:#f8fafc;font-weight:600;">Reference{ref_str}</td>
            <td style="padding:8px;">{refund.refund_reference or '—'}</td></tr>
        <tr><td style="padding:8px;font-weight:600;">Reason</td>
            <td style="padding:8px;">{refund.reason}</td></tr>
        <tr><td style="padding:8px;background:#f8fafc;font-weight:600;">Processed On</td>
            <td style="padding:8px;">{refund.confirmed_at.strftime('%d %B %Y') if refund.confirmed_at else '—'}</td></tr>
      </table>
      <p style="color:#64748b;font-size:13px;">If you have any questions please contact us.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin-top:24px;">
      <p style="color:#94a3b8;font-size:12px;">Orbit Training Centre</p>
    </div>
    """
    text_body = (
        f"Dear {reg.first_name} {reg.last_name},\n\n"
        f"Your refund has been processed.\n"
        f"Registration: {reg.registration_number}\n"
        f"Amount: {amount_str}\n"
        f"Reason: {refund.reason}\n\n"
        "Orbit Training Centre"
    )
    try:
        msg = EmailMultiAlternatives(subject, text_body, _s.DEFAULT_FROM_EMAIL, [reg.email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        pass


@login_required
def refund_list(request):
    try:
        role = request.user.profile.role
    except Exception:
        role = ''
    if request.user.username != 'admin' and role not in ('admin', 'accounts'):
        messages.error(request, "Access restricted.")
        return redirect('student_dashboard')

    refunds = Refund.objects.select_related(
        'registration', 'initiated_by', 'confirmed_by'
    ).order_by('-initiated_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        refunds = refunds.filter(status=status_filter)

    return render(request, 'refunds/refund_list.html', {
        'refunds': refunds,
        'status_filter': status_filter,
    })


# ─────────────────────────────────────────────
# INSTITUTE SETTINGS
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_admin_user)
def institute_settings(request):
    setting = InstituteSetting.get()
    if request.method == 'POST':
        # Text fields
        for field in [
            'company_name', 'tagline', 'address', 'po_box', 'city', 'country',
            'phone', 'email', 'website', 'trn_number', 'license_number', 'license_authority',
            'invoice_prefix', 'invoice_footer',
            'bank_name', 'bank_account_name', 'bank_account_no', 'bank_iban', 'bank_swift',
            'social_instagram', 'social_linkedin', 'social_facebook', 'social_twitter',
        ]:
            val = request.POST.get(field, '').strip()
            setattr(setting, field, val)

        # Image fields — only update if a new file was uploaded
        for img_field in ['company_logo', 'stamp', 'authorization_logo', 'signature']:
            file = request.FILES.get(img_field)
            if file:
                # Delete old file to save storage
                old = getattr(setting, img_field)
                if old:
                    try:
                        import os as _os
                        from django.conf import settings as _s
                        old_path = _os.path.join(_s.MEDIA_ROOT, old.name)
                        if _os.path.isfile(old_path):
                            _os.remove(old_path)
                    except Exception:
                        pass
                setattr(setting, img_field, file)
            # Handle "clear" checkbox
            if request.POST.get(f'{img_field}_clear'):
                old = getattr(setting, img_field)
                if old:
                    try:
                        import os as _os
                        from django.conf import settings as _s
                        old_path = _os.path.join(_s.MEDIA_ROOT, old.name)
                        if _os.path.isfile(old_path):
                            _os.remove(old_path)
                    except Exception:
                        pass
                setattr(setting, img_field, None)

        setting.save()
        messages.success(request, 'Settings saved successfully.')
        return redirect('institute_settings')

    img_fields = [
        ('company_logo',       'Company Logo',          'Main logo on invoices, emails, and proposals'),
        ('stamp',              'Company Stamp',          'Official stamp for certificates and official documents'),
        ('authorization_logo', 'Authorization Logo',     'Accreditation / authorization badge (KHDA, ISO, etc.)'),
        ('signature',          'Authorized Signature',   'Signature image of authorized signatory'),
    ]
    # Build image field data with current file info for template
    img_field_data = []
    for name, label, hint in img_fields:
        current = getattr(setting, name)
        img_field_data.append({
            'name': name,
            'label': label,
            'hint': hint,
            'url': current.url if current else None,
            'has_file': bool(current),
        })
    return render(request, 'settings/institute_settings.html', {
        'setting': setting,
        'img_fields': img_field_data,
    })


# ─────────────────────────────────────────────
# CERTIFICATION REQUEST FLOW
# ─────────────────────────────────────────────

@login_required
@require_POST
def send_cert_request(request, pk):
    """Send a token-based certification request form link to the student/client."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _s
    from invoices.models import CertificationRequest

    registration = get_object_or_404(Registration, pk=pk)
    course_name = request.POST.get('course_name', '').strip()
    if not course_name:
        messages.error(request, "Please select a course.")
        return redirect('registration_invoice_detail', registration_id=pk)

    # Create a fresh request token each time
    cert_req = CertificationRequest.objects.create(
        registration=registration,
        course_name=course_name,
        sent_by=request.user,
    )

    form_url = request.build_absolute_uri(reverse('cert_request_form', args=[cert_req.token]))
    recipient = registration.email

    subject = f"Certificate Request — {registration.first_name} {registration.last_name}"
    text_body = (
        f"Dear {registration.first_name} {registration.last_name},\n\n"
        f"Please complete the certification request form for your course: {course_name}\n\n"
        f"Click the link below to fill in the form:\n{form_url}\n\n"
        f"Orbit Training Centre"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;">
      <h2 style="color:#1e40af;">Certificate Request Form</h2>
      <p>Dear <strong>{registration.first_name} {registration.last_name}</strong>,</p>
      <p>Please complete the certification request form for your course:</p>
      <p style="font-size:16px;font-weight:bold;color:#1e40af;">{course_name}</p>
      <p>Click the button below to fill in your course completion details:</p>
      <a href="{form_url}" style="display:inline-block;background:#1e40af;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:bold;margin:16px 0;">
        Complete Certification Form
      </a>
      <p style="color:#64748b;font-size:12px;margin-top:24px;">
        If the button doesn't work, copy and paste this link:<br>{form_url}
      </p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin-top:24px;">
      <p style="color:#64748b;font-size:12px;">Orbit Training Centre</p>
    </div>
    """
    try:
        msg = EmailMultiAlternatives(subject, text_body, _s.DEFAULT_FROM_EMAIL, [recipient])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        messages.success(request, f"Certification request form sent to {recipient}.")
    except Exception as e:
        messages.error(request, f"Email could not be sent: {e}")

    return redirect('registration_invoice_detail', registration_id=pk)


def cert_request_form(request, token):
    """Public form for client to fill in course completion details."""
    from invoices.models import CertificationRequest
    cert_req = get_object_or_404(CertificationRequest, token=token)

    if cert_req.status in ('approved', 'rejected'):
        return render(request, 'certificates/cert_request_done.html', {
            'cert_req': cert_req,
            'already_done': True,
        })

    if request.method == 'POST':
        course_completed = request.POST.get('course_completed')
        completion_date = request.POST.get('completion_date', '').strip()
        class_feedback = request.POST.get('class_feedback', '').strip()
        client_notes = request.POST.get('client_notes', '').strip()

        if course_completed == 'no':
            return render(request, 'certificates/cert_request_form.html', {
                'cert_req': cert_req,
                'error_not_completed': True,
            })

        if not completion_date:
            return render(request, 'certificates/cert_request_form.html', {
                'cert_req': cert_req,
                'error_date': True,
            })

        import datetime as _dt
        try:
            parsed_date = _dt.date.fromisoformat(completion_date)
        except ValueError:
            return render(request, 'certificates/cert_request_form.html', {
                'cert_req': cert_req,
                'error_date': True,
            })

        class_rating = request.POST.get('class_rating', '').strip()

        if not class_feedback:
            return render(request, 'certificates/cert_request_form.html', {
                'cert_req': cert_req,
                'error_feedback': True,
                'post_data': request.POST,
            })

        class_starting_date = request.POST.get('class_starting_date', '').strip()
        parsed_start = None
        if class_starting_date:
            try:
                parsed_start = _dt.date.fromisoformat(class_starting_date)
            except ValueError:
                pass

        cert_req.course_completed = True
        cert_req.completion_date = parsed_date
        cert_req.class_starting_date = parsed_start
        cert_req.class_rating = class_rating
        cert_req.class_feedback = class_feedback
        cert_req.client_notes = client_notes
        cert_req.submitted_at = timezone.now()
        cert_req.status = 'submitted'
        cert_req.save()

        # Notify admin by email
        _notify_admin_cert_request(cert_req, request)

        return render(request, 'certificates/cert_request_done.html', {
            'cert_req': cert_req,
            'already_done': False,
        })

    return render(request, 'certificates/cert_request_form.html', {'cert_req': cert_req})


def _notify_admin_cert_request(cert_req, request):
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _s
    try:
        admin_url = request.build_absolute_uri(reverse('cert_requests_admin'))
        reg = cert_req.registration
        subject = f"New Cert Request: {reg.first_name} {reg.last_name} — {cert_req.course_name}"
        body = (
            f"A certification request has been submitted.\n\n"
            f"Student: {reg.first_name} {reg.last_name} ({reg.registration_number})\n"
            f"Course: {cert_req.course_name}\n"
            f"Completion Date: {cert_req.completion_date}\n\n"
            f"Review: {admin_url}"
        )
        msg = EmailMultiAlternatives(subject, body, _s.DEFAULT_FROM_EMAIL, [_s.DEFAULT_FROM_EMAIL])
        msg.send(fail_silently=True)
    except Exception:
        pass


@login_required
def cert_requests_admin(request):
    """Admin page to review and generate certificates from submitted requests."""
    from invoices.models import CertificationRequest
    try:
        role = request.user.profile.role
    except Exception:
        role = ''
    if request.user.username != 'admin' and role != 'admin':
        messages.error(request, "Admin access only.")
        return redirect('student_dashboard')

    requests_qs = CertificationRequest.objects.select_related(
        'registration', 'sent_by', 'generated_certificate'
    ).order_by('-sent_at')

    status_filter = request.GET.get('status', 'submitted')
    if status_filter and status_filter != 'all':
        requests_qs = requests_qs.filter(status=status_filter)

    return render(request, 'certificates/cert_requests_admin.html', {
        'cert_requests': requests_qs,
        'status_filter': status_filter,
    })


@login_required
@require_POST
def cert_request_generate(request, pk):
    """Admin generates a certificate from a submitted certification request."""
    from invoices.models import CertificationRequest
    try:
        role = request.user.profile.role
    except Exception:
        role = ''
    if request.user.username != 'admin' and role != 'admin':
        messages.error(request, "Admin access only.")
        return redirect('cert_requests_admin')

    cert_req = get_object_or_404(CertificationRequest, pk=pk)
    grade = request.POST.get('grade', 'A').strip()
    from_date = request.POST.get('from_date', '').strip()
    end_date_val = request.POST.get('end_date', '').strip() or (
        str(cert_req.completion_date) if cert_req.completion_date else ''
    )

    import datetime as _dt
    try:
        parsed_from = _dt.date.fromisoformat(from_date) if from_date else None
        parsed_end = _dt.date.fromisoformat(end_date_val) if end_date_val else cert_req.completion_date
    except ValueError:
        parsed_from = None
        parsed_end = cert_req.completion_date

    reg = cert_req.registration
    certificate = Certificate.objects.create(
        register_number=reg.registration_number,
        student_name=f"{reg.first_name} {reg.last_name}",
        course_name=cert_req.course_name.title(),
        from_date=parsed_from or cert_req.class_starting_date,
        end_date=parsed_end,
        grade=grade,
    )

    cert_req.generated_certificate = certificate
    cert_req.status = 'approved'
    cert_req.save(update_fields=['generated_certificate', 'status'])

    messages.success(request, f"Certificate generated for {reg.first_name} {reg.last_name} — {cert_req.course_name}.")
    return redirect('cert_requests_admin')


@login_required
@require_POST
def cert_request_reject(request, pk):
    """Admin rejects a certification request."""
    from invoices.models import CertificationRequest
    try:
        role = request.user.profile.role
    except Exception:
        role = ''
    if request.user.username != 'admin' and role != 'admin':
        messages.error(request, "Admin access only.")
        return redirect('cert_requests_admin')

    cert_req = get_object_or_404(CertificationRequest, pk=pk)
    cert_req.status = 'rejected'
    cert_req.save(update_fields=['status'])
    messages.success(request, "Certification request rejected.")
    return redirect('cert_requests_admin')


def _send_welcome_email(registration, request=None):
    """Send a welcome email to a newly registered student."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings as _s
    if not registration.email:
        return
    courses = list(registration.courses.values_list('name', flat=True))
    reg_courses = list(registration.registration_courses.select_related('course').all())
    if request:
        letter_url = request.build_absolute_uri(f'/portal/welcome-letter/{registration.pk}/')
    else:
        letter_url = ''
    has_logo = _find_logo_path() is not None
    ctx = {
        'first_name':          registration.first_name,
        'last_name':           registration.last_name,
        'registration_number': registration.registration_number,
        'class_type':          registration.class_type,
        'registration_date':   registration.date.strftime('%d %B %Y') if registration.date else '',
        'courses':             courses,
        'reg_courses':         reg_courses,
        'logo_src':            'cid:orbit_logo' if has_logo else '',
        'letter_url':          letter_url,
    }
    subject   = f"Welcome to Orbit Training Centre, {registration.first_name}!"
    html_body = render_to_string('emails/welcome_email.html', ctx)
    text_body = (
        f"Dear {registration.first_name} {registration.last_name},\n\n"
        f"Welcome to Orbit Training Centre! Your registration is confirmed.\n"
        f"Registration No: {registration.registration_number}\n"
        f"Courses: {', '.join(courses)}\n\n"
        "For any queries contact training@orbittraining.ae or call +971-582274991.\n\n"
        "Orbit Training Centre"
    )
    try:
        msg = EmailMultiAlternatives(subject, text_body, _s.DEFAULT_FROM_EMAIL, [registration.email])
        msg.attach_alternative(html_body, 'text/html')
        _attach_logo_inline(msg)
        msg.send(fail_silently=True)
    except Exception:
        pass


def welcome_letter_printable(request, pk):
    """Public printable welcome letter page — no login required."""
    registration = get_object_or_404(Registration, pk=pk)
    courses = list(registration.courses.values_list('name', flat=True))
    reg_courses = list(registration.registration_courses.select_related('course').all())
    ctx = {
        'first_name':          registration.first_name,
        'last_name':           registration.last_name,
        'registration_number': registration.registration_number,
        'class_type':          registration.class_type,
        'registration_date':   registration.date.strftime('%d %B %Y') if registration.date else '',
        'courses':             courses,
        'reg_courses':         reg_courses,
    }
    return render(request, 'portal/welcome_letter_printable.html', ctx)


_ENRL_LETTER_SALT = 'orbit-enrl-letter-v1'
_ENRL_LETTER_MAX_AGE = 10 * 24 * 3600  # 10 days in seconds


def _make_enrollment_letter_url(request, pk, schedule_data=None):
    """Return a signed, 10-day expiring URL for the printable enrollment letter.

    schedule_data dict (all optional): d=duration, tr=trainer, sc=schedule,
    st=start_date (ISO), en=end_date (ISO), mo=mode_of_training.
    Embedded in the token so the printable page shows the same detail as the email.
    """
    from django.core import signing
    payload = {'pk': pk}
    if schedule_data:
        payload['s'] = schedule_data
    token = signing.dumps(payload, salt=_ENRL_LETTER_SALT)
    return request.build_absolute_uri(f'/portal/enrollment-letter/{token}/')


def enrollment_letter_printable(request, token):
    """Public printable enrollment letter — link expires after 10 days."""
    from django.core import signing
    from django.db.models import Sum as _Sum
    import datetime as _dt
    try:
        data = signing.loads(token, salt=_ENRL_LETTER_SALT, max_age=_ENRL_LETTER_MAX_AGE)
        pk = data['pk']
    except signing.SignatureExpired:
        return render(request, 'portal/letter_expired.html', {'reason': 'expired'})
    except Exception:
        return render(request, 'portal/letter_expired.html', {'reason': 'invalid'})

    registration = get_object_or_404(Registration, pk=pk)
    year = registration.date.strftime('%Y') if registration.date else timezone.now().strftime('%Y')
    num  = registration.registration_number.split('/')[-1] if registration.registration_number else '001'
    ref_number   = f"ORBIT/ENR/{year}/{num}"
    invoices_qs  = Invoice.objects.filter(registration=registration)
    fee_paid     = invoices_qs.aggregate(t=_Sum('amount_paid'))['t'] or 0
    total_due    = (invoices_qs.aggregate(t=_Sum('total_amount'))['t'] or 0) - fee_paid
    payment_status = "Full Payment" if total_due <= 0 else f"Installment — Balance Due: AED {total_due:,.2f}"
    course_names = ', '.join(registration.courses.values_list('name', flat=True))

    # Unpack schedule details packed into the token when the email was sent
    s = data.get('s', {})
    def _fmt(ds):
        if not ds:
            return ''
        try:
            return _dt.date.fromisoformat(ds).strftime('%d %B %Y')
        except Exception:
            return ds

    ctx = {
        'letter_date':      timezone.now().strftime('%d %B %Y'),
        'ref_number':       ref_number,
        'student_name':     f"{registration.first_name} {registration.last_name}",
        'student_id':       registration.registration_number,
        'course_names':     course_names,
        'mode_of_training': s.get('mo', '') or registration.class_type.capitalize(),
        'duration':         s.get('d', ''),
        'start_date':       _fmt(s.get('st', '')),
        'end_date':         _fmt(s.get('en', '')),
        'schedule':         s.get('sc', ''),
        'trainer':          s.get('tr', ''),
        'fee_paid':         f"{float(fee_paid):,.2f}",
        'payment_status':   payment_status,
    }
    return render(request, 'portal/enrollment_letter_printable.html', ctx)


@login_required
def send_enrollment_letter(request, pk):
    """Send a formal enrollment confirmation letter email to the student."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings as _s
    from django.db.models import Sum as _Sum

    registration = get_object_or_404(Registration, pk=pk)
    if request.method != 'POST':
        return redirect('registration_invoice_detail', registration_id=pk)

    # Build ref number: ORBIT/ENR/YYYY/XXX
    year = registration.date.strftime('%Y') if registration.date else timezone.now().strftime('%Y')
    num  = registration.registration_number.split('/')[-1] if registration.registration_number else '001'
    ref_number = f"ORBIT/ENR/{year}/{num}"

    # Payment totals from linked invoices
    invoices   = Invoice.objects.filter(registration=registration)
    fee_paid   = invoices.aggregate(t=_Sum('amount_paid'))['t'] or 0
    total_due  = (invoices.aggregate(t=_Sum('total_amount'))['t'] or 0) - fee_paid
    if total_due <= 0:
        payment_status = "Full Payment"
    else:
        payment_status = f"Installment — Balance Due: AED {total_due:,.2f}"

    # Course names
    course_names = ', '.join(registration.courses.values_list('name', flat=True))

    # Mode of training — prefer admin override
    mode = request.POST.get('mode_override', '').strip() or registration.class_type.capitalize()

    # Optional schedule fields from modal
    duration   = request.POST.get('duration', '').strip()
    trainer    = request.POST.get('trainer', '').strip()
    schedule   = request.POST.get('schedule', '').strip()
    raw_start  = request.POST.get('start_date', '').strip()
    raw_end    = request.POST.get('end_date', '').strip()

    def _fmt_date(ds):
        if not ds:
            return ''
        try:
            import datetime as _dt
            return _dt.date.fromisoformat(ds).strftime('%d %B %Y')
        except ValueError:
            return ds

    # Pack schedule details into the signed token so the printable page shows them
    schedule_data = {
        'd':  duration,
        'tr': trainer,
        'sc': schedule,
        'st': raw_start,
        'en': raw_end,
        'mo': mode,
    }
    has_logo = _find_logo_path() is not None
    ctx = {
        'letter_date':    timezone.now().strftime('%d/%m/%Y'),
        'ref_number':     ref_number,
        'student_name':   f"{registration.first_name} {registration.last_name}",
        'student_id':     registration.registration_number,
        'course_names':   course_names,
        'duration':       duration,
        'mode_of_training': mode,
        'start_date':     _fmt_date(raw_start),
        'end_date':       _fmt_date(raw_end),
        'schedule':       schedule,
        'trainer':        trainer,
        'fee_paid':       f"{float(fee_paid):,.2f}",
        'payment_status': payment_status,
        'logo_src':       'cid:orbit_logo' if has_logo else '',
        'print_url':      _make_enrollment_letter_url(request, registration.pk, schedule_data=schedule_data),
    }
    subject   = f"Enrollment Confirmation Letter — {registration.registration_number}"
    html_body = render_to_string('emails/enrollment_letter_email.html', ctx)
    text_body = (
        f"Dear {registration.first_name} {registration.last_name},\n\n"
        f"Please find your Enrollment Confirmation for {registration.registration_number}.\n"
        f"Ref: {ref_number}\n"
        f"Course(s): {course_names}\n"
        f"Fee Paid: AED {float(fee_paid):,.2f}\n"
        f"Payment Status: {payment_status}\n\n"
        "Orbit Training Centre — training@orbittraining.ae"
    )
    sent = False
    try:
        msg = EmailMultiAlternatives(subject, text_body, _s.DEFAULT_FROM_EMAIL, [registration.email])
        msg.attach_alternative(html_body, 'text/html')
        _attach_logo_inline(msg)
        msg.send(fail_silently=False)
        sent = True
    except Exception as e:
        messages.error(request, f"Email could not be sent: {e}")

    if sent:
        messages.success(request, f"Enrollment letter sent to {registration.email}.")
    return redirect('registration_invoice_detail', registration_id=pk)


def _send_fee_reminder_email(inv, days_overdue, note, request):
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings as _s
    client_email = inv.client.email if inv.client else None
    if not client_email:
        return
    is_overdue = days_overdue > 0
    subject = (f"Overdue Payment Reminder — Invoice {inv.invoice_number}"
               if is_overdue else f"Payment Reminder — Invoice {inv.invoice_number}")
    ctx = {
        'client_name':     inv.client.name,
        'invoice_number':  inv.invoice_number,
        'amount_due':      inv.total_amount - inv.amount_paid,
        'due_date':        inv.due_date,
        'days_overdue':    days_overdue,
        'is_overdue':      is_overdue,
        'note':            note,
        'sent_by':         request.user.get_full_name() or request.user.username,
    }
    html_body  = render_to_string('emails/fee_reminder_email.html', ctx)
    text_body  = (
        f"Dear {inv.client.name},\n\n"
        f"This is a reminder for Invoice {inv.invoice_number}.\n"
        f"Amount Due: AED {inv.total_amount - inv.amount_paid:,.2f}\n"
        f"Due Date: {inv.due_date.strftime('%d %b %Y')}\n"
        + (f"\n{note}" if note else "")
        + "\n\nOrbit Training Point"
    )
    try:
        msg = EmailMultiAlternatives(subject, text_body, _s.DEFAULT_FROM_EMAIL, [client_email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# GATEWAY PAYOUT TRACKER (Tabby / Tamara)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin_user)
def gateway_payout_list(request):
    import datetime as _dt
    from .models import GatewayPayout

    TABBY_RATE   = Decimal('0.0707')
    TAMARA_RATE  = Decimal('0.0702')
    TABBY_FEE    = Decimal('6')
    TAMARA_FEE   = Decimal('0')
    TABBY_MIN    = Decimal('2500')
    VAT_RATE     = Decimal('0.05')

    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            try:
                gateway      = request.POST.get('gateway')
                week_start   = _dt.date.fromisoformat(request.POST.get('week_start'))
                total_sales  = Decimal(request.POST.get('total_sales', '0') or '0')
                notes        = request.POST.get('notes', '')

                # Ensure week_start is Monday
                if week_start.weekday() != 0:
                    week_start = week_start - _dt.timedelta(days=week_start.weekday())

                week_end = week_start + _dt.timedelta(days=6)

                if gateway == 'tabby':
                    rate        = TABBY_RATE
                    fee         = TABBY_FEE
                    payout_date = week_start + _dt.timedelta(days=7)   # next Monday
                else:
                    rate        = TAMARA_RATE
                    fee         = TAMARA_FEE
                    payout_date = week_start + _dt.timedelta(days=8)   # next Tuesday

                commission = (total_sales * rate).quantize(Decimal('0.01'))
                vat        = (commission * VAT_RATE).quantize(Decimal('0.01'))
                net        = (total_sales - commission - vat - fee).quantize(Decimal('0.01'))

                GatewayPayout.objects.create(
                    gateway=gateway, week_start=week_start, week_end=week_end,
                    payout_date=payout_date, total_sales=total_sales,
                    commission_rate=rate, commission_amount=commission,
                    vat_on_commission=vat, payout_fee=fee, net_payout=net,
                    status='pending', notes=notes, created_by=request.user,
                )
            except Exception as ex:
                error = str(ex)

        elif action == 'mark_received':
            payout = get_object_or_404(GatewayPayout, pk=request.POST.get('pk'))
            actual_str = request.POST.get('actual_received', '').strip()
            if actual_str:
                actual = Decimal(actual_str)
                payout.actual_received = actual
                payout.status = 'received' if actual >= payout.net_payout - Decimal('0.01') else 'short'
                payout.save()

        elif action == 'delete':
            get_object_or_404(GatewayPayout, pk=request.POST.get('pk')).delete()

        if not error:
            return redirect('gateway_payout_list')

    payouts  = GatewayPayout.objects.select_related('created_by').all()
    pending  = payouts.filter(status='pending')
    total_pending_net = sum(p.net_payout for p in pending)

    return render(request, 'finance/gateway_payout.html', {
        'payouts': payouts,
        'total_pending_net': total_pending_net,
        'tabby_rate': TABBY_RATE * 100,
        'tamara_rate': TAMARA_RATE * 100,
        'tabby_min': TABBY_MIN,
        'error': error,
    })
