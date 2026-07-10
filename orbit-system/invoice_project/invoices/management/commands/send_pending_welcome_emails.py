from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Send welcome emails to students registered more than 1 hour ago'

    def handle(self, *args, **options):
        from invoices.models import Registration
        from invoices.views import _send_welcome_email

        cutoff = timezone.now() - timedelta(hours=1)
        pending = Registration.objects.filter(
            welcome_email_sent=False,
            created_at__isnull=False,
            created_at__lte=cutoff,
            email__isnull=False,
        ).exclude(email='')

        count = pending.count()
        if not count:
            self.stdout.write('No pending welcome emails.')
            return

        sent = 0
        for reg in pending:
            try:
                _send_welcome_email(reg, request=None)
                reg.welcome_email_sent = True
                reg.save(update_fields=['welcome_email_sent'])
                sent += 1
                self.stdout.write(f'  Sent to {reg.first_name} {reg.last_name} ({reg.registration_number})')
            except Exception as e:
                self.stderr.write(f'  Failed for {reg.registration_number}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Done — {sent}/{count} welcome emails sent.'))
