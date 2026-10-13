from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Check online sessions that ended in the last 2 hours against the LMS login '
            'tracker and record attendance. Meant to run every 15-30 minutes. No-ops '
            'cleanly if LMS_DB is not configured (e.g. local dev).')

    def handle(self, *args, **options):
        from invoices.online_attendance import sync_online_attendance
        checked, confirmed, skipped_no_email = sync_online_attendance()
        if checked == 0 and confirmed == 0:
            self.stdout.write('Nothing to check (LMS not configured, or no online sessions ended recently).')
            return
        self.stdout.write(self.style.SUCCESS(
            f'Checked {checked} online session(s): {confirmed} confirmed via LMS login, '
            f'{skipped_no_email} skipped (no email on file).'))
