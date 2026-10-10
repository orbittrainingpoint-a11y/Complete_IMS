from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Send every active student their class schedule for the current week '
            '(Monday-Sunday). Meant to run once, every Monday morning. Safe to re-run '
            '(e.g. after a crash) — only students not yet notified this week are processed.')

    def handle(self, *args, **options):
        from invoices.models import Registration, WeeklyScheduleNotice
        from invoices.views import _send_weekly_schedule_email
        from invoices.weekly_schedule import week_range, week_sessions

        monday, sunday = week_range()
        already_notified = set(WeeklyScheduleNotice.objects.filter(week_start=monday)
                                .values_list('registration_id', flat=True))

        students = Registration.objects.filter(
            student_status='active', email__isnull=False,
        ).exclude(email='')

        sent = skipped = failed = already = 0
        for reg in students:
            if reg.id in already_notified:
                already += 1
                continue
            sessions = week_sessions(reg, monday, sunday)
            if not sessions:
                skipped += 1
                continue
            try:
                ok = _send_weekly_schedule_email(reg, monday, sunday, sessions)
                WeeklyScheduleNotice.objects.create(registration=reg, week_start=monday, session_count=len(sessions))
                if ok:
                    sent += 1
                    self.stdout.write(f'  Sent to {reg.first_name} {reg.last_name} ({reg.registration_number}) — {len(sessions)} session(s)')
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                self.stderr.write(f'  Failed for {reg.registration_number}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Done — {sent} sent, {skipped} with no classes this week, {already} already notified, '
            f'{failed} failed. Week of {monday}.'))
