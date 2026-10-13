import datetime as dt

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Nightly fee/attendance schedule enforcement: (1) resolve yesterday\'s un-marked '
            'attendance (completed if a confirmed check-in exists, absent otherwise - this also '
            'drives the 4-consecutive-absence auto-pause and the 3-more-after-resume auto-cancel '
            'inside set_occurrence_status), (2) auto-pause every active schedule for a '
            'registration whose fee is overdue, (3) auto-suspend a registration that is still '
            'unpaid 14+ days after that fee pause. Meant to run once nightly, just after '
            'midnight Dubai time. Safe to re-run - every step only acts on rows still in the '
            'state it checks for.')

    def add_arguments(self, parser):
        parser.add_argument('--registration-ids', type=str, default='',
                            help='Comma-separated Registration ids to limit this run to (a manual catch-up '
                                 'or test run) - omit to process every eligible registration system-wide, '
                                 'exactly as the nightly cron does.')

    def handle(self, *args, **options):
        from invoices import schedule_engine as eng
        from invoices.models import AuditLog, Registration, ScheduleRule
        from invoices.views import sync_registration_to_crm

        today = eng.dubai_today()
        raw_ids = (options.get('registration_ids') or '').strip()
        reg_scope = {int(x) for x in raw_ids.split(',') if x.strip().isdigit()} if raw_ids else None

        rule_ids = None
        if reg_scope is not None:
            rule_ids = list(ScheduleRule.objects.filter(registration_id__in=reg_scope).values_list('pk', flat=True))
        completed, absent = eng.resolve_end_of_day_attendance(rule_ids=rule_ids)
        self.stdout.write(f'Attendance resolved: {completed} completed, {absent} absent.')

        paused = 0
        reg_ids = set(ScheduleRule.objects.filter(status='active', registration__isnull=False)
                      .values_list('registration_id', flat=True))
        if reg_scope is not None:
            reg_ids &= reg_scope
        for reg in Registration.objects.filter(pk__in=reg_ids):
            if not reg.is_fee_overdue(today):
                continue
            for rule in ScheduleRule.objects.filter(registration=reg, status='active'):
                eng.pause_rule(rule, today, 'Auto-paused: fee overdue', '', None, None, pause_kind='fee')
                paused += 1
        self.stdout.write(f'Fee-overdue auto-pause: {paused} schedule(s) paused.')

        deactivated = 0
        cutoff = today - dt.timedelta(days=14)
        stale = (ScheduleRule.objects.filter(status='paused', pause_kind='fee', fee_pause_date__lte=cutoff,
                                             registration__isnull=False)
                .select_related('registration'))
        if reg_scope is not None:
            stale = stale.filter(registration_id__in=reg_scope)
        seen = set()
        for rule in stale:
            reg = rule.registration
            if reg.pk in seen or reg.outstanding_balance() <= 0:
                continue
            seen.add(reg.pk)
            for r in ScheduleRule.objects.filter(registration=reg, status__in=('active', 'paused')):
                eng.cancel_rule(r, today, 'Auto-cancelled: unpaid 14+ days after fee pause', None)
            old_status = reg.student_status
            reg.student_status = 'suspended'
            reg.save(update_fields=['student_status'])
            AuditLog.objects.create(action='status_change', model_name='Registration', object_id=str(reg.pk),
                                    object_repr=str(reg), changes=f'{old_status} -> suspended (auto: unpaid 14+ days after fee pause)')
            sync_registration_to_crm(reg)
            deactivated += 1
            self.stdout.write(f'  Suspended {reg.first_name} {reg.last_name} ({reg.registration_number}) - still owing after 14 days.')
        self.stdout.write(f'Fee-overdue auto-deactivation: {deactivated} registration(s) suspended.')

        self.stdout.write(self.style.SUCCESS('Done.'))
