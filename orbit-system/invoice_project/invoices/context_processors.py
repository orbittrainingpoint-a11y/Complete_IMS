import datetime
from .models import Invoice, UserProfile

_ROLE_DISPLAY = {
    'admin': 'Admin',
    'sales_manager': 'Sales Manager',
    'accounts': 'Accounts',
    'sales_executive': 'Sales Executive',
}


def sidebar_data(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user

    # Safely resolve role — auto-create profile if missing so sidebar never breaks
    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        default_role = 'admin' if (user.is_superuser or user.is_staff) else 'sales_executive'
        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={'role': default_role}
        )
        role = profile.role
    except Exception:
        role = 'admin' if (user.is_superuser or user.is_staff) else 'sales_executive'

    is_admin = (role == 'admin') or user.is_superuser or user.is_staff

    try:
        today = datetime.date.today()
        overdue_count = Invoice.objects.filter(
            due_date__lt=today
        ).exclude(status='Full Payment').count()
    except Exception:
        overdue_count = 0

    return {
        'sidebar_overdue_count': overdue_count,
        'is_admin': is_admin,
        'user_role': role,
        'user_role_display': _ROLE_DISPLAY.get(role, role.replace('_', ' ').title()),
    }
