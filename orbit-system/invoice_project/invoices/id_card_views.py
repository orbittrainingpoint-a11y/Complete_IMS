"""Student ID card views: verify a student's info, upload a photo, generate the printable
card. Visible to everyone (same convention as Trainer Schedule); generating/regenerating is
admin + sales_manager only."""
import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from . import id_cards as compositor
from .models import Course, Registration, RegistrationCourse, StudentIDCard

MAX_PHOTO_BYTES = 8 * 1024 * 1024
ALLOWED_PHOTO_TYPES = ('image/jpeg', 'image/png', 'image/webp')


def _can_edit(user):
    role = getattr(getattr(user, 'profile', None), 'role', '')
    return user.is_superuser or user.is_staff or role in ('admin', 'sales_manager')


@login_required
def id_card_list(request):
    q = (request.GET.get('q') or '').strip()
    qs = Registration.objects.select_related('id_card').order_by('-id')
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                       Q(registration_number__icontains=q) | Q(phone_no__icontains=q))
    else:
        qs = qs.filter(student_status='active')
    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'id_cards/list.html', {
        'page': page, 'q': q, 'can_edit': _can_edit(request.user), 'today': dt.date.today(),
    })


@login_required
def id_card_generate(request, registration_id):
    if not _can_edit(request.user):
        messages.error(request, 'Only admins and the sales manager can generate ID cards.')
        return redirect('id_card_list')
    reg = get_object_or_404(Registration, pk=registration_id)
    card = getattr(reg, 'id_card', None)
    courses = [rc.course for rc in RegistrationCourse.objects.filter(registration=reg).select_related('course') if rc.course]
    error = None

    if request.method == 'POST':
        course_id = request.POST.get('course')
        course = Course.objects.filter(pk=course_id).first() if course_id else (courses[0] if courses else None)
        valid_until_raw = request.POST.get('valid_until', '')
        try:
            valid_until = dt.date.fromisoformat(valid_until_raw)
        except ValueError:
            error = 'Choose a valid "Valid until" date.'
        photo = request.FILES.get('photo')
        if not error and not photo and not (card and card.photo):
            error = 'Please upload a photo.'
        if not error and photo:
            if photo.content_type not in ALLOWED_PHOTO_TYPES:
                error = 'Photo must be a JPEG, PNG or WebP image.'
            elif photo.size > MAX_PHOTO_BYTES:
                error = 'Photo is too large (max 8 MB).'
        if not error and not course:
            error = 'This student has no course on file — add one to their registration first.'

        if not error:
            if card is None:
                card = StudentIDCard(registration=reg)
            card.course = course
            card.valid_until = valid_until
            card.generated_by = request.user
            if photo:
                card.photo.save(photo.name, ContentFile(photo.read()), save=False)
            card.save()
            try:
                content, warnings = compositor.generate_card_image(card)
                card.card_image.save(content.name, content, save=True)
                for w in warnings:
                    messages.warning(request, w)
                messages.success(request, f'ID card generated for {reg.first_name} {reg.last_name}.')
                return redirect('id_card_view', registration_id=reg.pk)
            except FileNotFoundError:
                error = 'The card template or font files are missing on the server — contact an admin.'
            except Exception as e:
                error = f'Could not generate the card: {e}'

    return render(request, 'id_cards/generate.html', {
        'reg': reg, 'card': card, 'courses': courses, 'error': error,
        'default_valid_until': (card.valid_until if card else dt.date.today() + dt.timedelta(days=365)),
    })


@login_required
def id_card_view(request, registration_id):
    reg = get_object_or_404(Registration, pk=registration_id)
    card = getattr(reg, 'id_card', None)
    if not card or not card.card_image:
        messages.info(request, 'No ID card has been generated for this student yet.')
        return redirect('id_card_generate', registration_id=reg.pk)
    return render(request, 'id_cards/view.html', {'reg': reg, 'card': card, 'can_edit': _can_edit(request.user)})


@login_required
def id_card_download(request, registration_id):
    reg = get_object_or_404(Registration, pk=registration_id)
    card = getattr(reg, 'id_card', None)
    if not card or not card.card_image:
        raise Http404('No ID card has been generated for this student yet.')
    card.card_image.open('rb')
    filename = f'{reg.registration_number.replace("/", "-")}_id_card.png'
    return FileResponse(card.card_image, as_attachment=True, filename=filename, content_type='image/png')
