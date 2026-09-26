from django import template
from django.core.cache import cache

from invoices import schedule_engine as eng
from invoices.models import ScheduleOccurrence, ScheduleRule

register = template.Library()


def _counts():
    data = cache.get('sched_nav_counts')
    if data is None:
        today = eng.dubai_today()
        data = {
            'active': ScheduleRule.objects.filter(status='active').count(),
            'paused': ScheduleRule.objects.filter(status='paused').count(),
            'to_mark': ScheduleOccurrence.objects.filter(status__in=eng.ACTIVE_FUTURE, date__lt=today).count(),
        }
        cache.set('sched_nav_counts', data, 60)
    return data


@register.inclusion_tag('trainer_schedule/_nav_tabs.html', takes_context=True)
def schedule_nav(context, active=''):
    user = context['request'].user if 'request' in context else context.get('user')
    profile = getattr(user, 'profile', None)
    role = 'admin' if getattr(user, 'is_superuser', False) else (profile.role if profile else '')
    return {
        'active': active, 'counts': _counts(), 'q': context['request'].GET.get('q', '') if 'request' in context else '',
        'can_edit': role in ('admin', 'sales_manager'), 'is_admin': role == 'admin',
        'is_trainer': bool(getattr(user, 'trainer_record', None)),
    }
