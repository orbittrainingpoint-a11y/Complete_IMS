from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or None


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    from .models import AuditLog
    AuditLog.objects.create(
        user=user,
        action='login',
        model_name='User',
        object_id=str(user.pk),
        object_repr=user.username,
        changes='',
        ip_address=_get_ip(request),
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    from .models import AuditLog
    if not user:
        return
    AuditLog.objects.create(
        user=user,
        action='logout',
        model_name='User',
        object_id=str(user.pk),
        object_repr=user.username,
        changes='',
        ip_address=_get_ip(request),
    )
