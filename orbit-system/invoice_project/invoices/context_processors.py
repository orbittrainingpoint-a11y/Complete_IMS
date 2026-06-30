import datetime
from .models import Invoice


def sidebar_data(request):
    if not request.user.is_authenticated:
        return {}
    try:
        today = datetime.date.today()
        overdue_count = Invoice.objects.filter(
            due_date__lt=today
        ).exclude(status='Full Payment').count()
        return {'sidebar_overdue_count': overdue_count}
    except Exception:
        return {'sidebar_overdue_count': 0}
