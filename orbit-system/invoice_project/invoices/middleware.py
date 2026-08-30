from datetime import timedelta, timezone as dt_timezone

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

# Fixed UTC+4 offset (not zoneinfo) — the UAE has no DST, and this avoids depending
# on an IANA tzdata package that isn't always present in every environment.
_DUBAI_TZ = dt_timezone(timedelta(hours=4))
_CURFEW_HOUR = 21
_CURFEW_MINUTE = 30


def _is_after_dubai_curfew():
    now = timezone.now().astimezone(_DUBAI_TZ)
    return now.hour > _CURFEW_HOUR or (now.hour == _CURFEW_HOUR and now.minute >= _CURFEW_MINUTE)


def _is_admin(user):
    try:
        return user.profile.role == 'admin' or user.is_superuser
    except Exception:
        return user.is_superuser


class DubaiCurfewMiddleware:
    """Daily 9:30 PM (Dubai time) curfew — every non-admin user gets logged out and
    can't do anything else until the next day. Admins are exempt."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not _is_admin(user) and _is_after_dubai_curfew():
            logout(request)
            messages.warning(request, 'Daily access ends at 9:30 PM (Dubai time). Please log in again tomorrow.')
            return redirect('login')
        return self.get_response(request)
