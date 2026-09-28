from django import template
from django.core.cache import cache

from invoices import schedule_engine as eng
from invoices.models import ScheduleOccurrence, ScheduleRule, StudentCheckIn

register = template.Library()


def _counts():
    data = cache.get('sched_nav_counts')
    if data is None:
        today = eng.dubai_today()
        data = {
            'active': ScheduleRule.objects.filter(status='active').count(),
            'paused': ScheduleRule.objects.filter(status='paused').count(),
            'to_mark': ScheduleOccurrence.objects.filter(status__in=eng.ACTIVE_FUTURE, date__lt=today).count(),
            'checkins_today': StudentCheckIn.objects.filter(scheduled_date=today, status='confirmed').count(),
        }
        cache.set('sched_nav_counts', data, 60)
    return data


# Every page's tab bar used to repeat the same ~11 destinations, which is now pure duplication
# of the Training sidebar (base_generic.html) — each of those is its own sidebar item. What's
# still worth a page's own tab row is quick, IN-CONTEXT jumps to that page's close siblings, not
# a full site map. Group each 'active' page into the cluster its siblings belong to; a page whose
# cluster is 'settings' gets no tab row at all — there is nothing else in that cluster to jump to.
SECTION_MAP = {
    'schedules': 'schedule', 'batches': 'schedule', 'sessions': 'schedule', '': 'schedule',
    'trainers': 'trainer', 'board': 'trainer', 'find': 'trainer', 'util': 'trainer',
    'waiting': 'action', 'pending': 'action', 'checkins': 'action',
    'settings': 'settings',
}


@register.inclusion_tag('trainer_schedule/_nav_tabs.html', takes_context=True)
def schedule_nav(context, active=''):
    user = context['request'].user if 'request' in context else context.get('user')
    profile = getattr(user, 'profile', None)
    role = 'admin' if getattr(user, 'is_superuser', False) else (profile.role if profile else '')
    return {
        'active': active, 'section': SECTION_MAP.get(active, 'schedule'), 'counts': _counts(),
        'q': context['request'].GET.get('q', '') if 'request' in context else '',
        'can_edit': role in ('admin', 'sales_manager'), 'is_admin': role == 'admin',
        'is_trainer': bool(getattr(user, 'trainer_record', None)),
    }
