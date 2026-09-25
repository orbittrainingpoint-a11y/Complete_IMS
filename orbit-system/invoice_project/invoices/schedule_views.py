"""Views for recurring trainer schedules: calendar, create-schedule flow, schedule details,
pause / resume / reschedule / attendance actions, history, settings and utilization."""
import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import schedule_engine as eng
from .models import (
    WEEKDAY_CHOICES, Batch, Course, Registration, RegistrationCourse, ScheduleAudit, ScheduleOccurrence,
    ScheduleRule, SchedulingSetting, Trainer,
)
from .schedule_engine import fmt_hours, hhmm, mins
from .trainer_schedule import (
    can_create, can_manage, create_required, is_admin_role, manage_required, own_trainer, parse_date, parse_time, safe_next,
)


def _hours(v, default=0):
    try:
        return max(0, round(float(v) * 60))
    except (TypeError, ValueError):
        return default


def _weekdays(request, key='weekdays'):
    return sorted({int(x) for x in request.POST.getlist(key) if x.isdigit() and 0 <= int(x) <= 6})


# ── trainer calendar (day / week / month) ───────────────────────────────────

@login_required
def trainer_calendar(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    mine = own_trainer(request.user)
    if mine and not can_manage(request.user) and mine.pk != trainer.pk:
        messages.error(request, 'You can only open your own schedule.')
        return redirect('trainer_week', pk=mine.pk)
    today = eng.dubai_today()
    view = request.GET.get('view', 'week')
    view = view if view in ('day', 'week', 'month') else 'week'
    anchor = parse_date(request.GET.get('date') or request.GET.get('week'), today)
    filters = {k: request.GET.get(k, '').strip() for k in ('q', 'course', 'type', 'status')}

    if view == 'day':
        g0 = g1 = anchor
        prev_d, next_d = anchor - dt.timedelta(days=1), anchor + dt.timedelta(days=1)
        title = anchor.strftime('%A, %d %B %Y')
    elif view == 'week':
        g0 = anchor - dt.timedelta(days=anchor.weekday())
        g1 = g0 + dt.timedelta(days=6)
        prev_d, next_d = g0 - dt.timedelta(days=7), g0 + dt.timedelta(days=7)
        title = f'{g0:%d %b} - {g1:%d %b %Y}'
    else:
        first = anchor.replace(day=1)
        nxt = (first + dt.timedelta(days=32)).replace(day=1)
        last = nxt - dt.timedelta(days=1)
        g0, g1 = first - dt.timedelta(days=first.weekday()), last + dt.timedelta(days=6 - last.weekday())
        prev_d, next_d = (first - dt.timedelta(days=1)).replace(day=1), nxt
        title = anchor.strftime('%B %Y')

    from urllib.parse import quote
    fq = ''.join(f'&{k}={quote(val)}' for k, val in filters.items() if val)
    days = eng.build_days(trainer, g0, g1, filters)
    in_scope = [d for d in days if view != 'month' or d['date'].month == anchor.month]
    sm = lambda k: sum(d['stats'][k] for d in in_scope)
    working = sm('working')
    util = round(sum(d['stats']['util'] * d['stats']['working'] for d in in_scope) / working) if working else 0
    kpi = {'util': util, 'working': fmt_hours(working), 'free': fmt_hours(sm('free_min')), 'partial': fmt_hours(sm('partial_min')),
           'batch': fmt_hours(sm('batch_sched_min')), 'students_h': fmt_hours(sm('student_min')), 'occupied': fmt_hours(sm('occupied_min')),
           'delivered': fmt_hours(sm('delivered_min')), 'sessions': sm('sessions'), 'cancelled': sm('cancelled'),
           'paused': sm('paused'), 'absent': sm('absent')}
    busiest = max(in_scope, key=lambda d: d['stats']['occupied_min'], default=None)
    kpi['busiest'] = busiest['date'] if busiest and busiest['stats']['occupied_min'] else None

    events_json = []
    for d in in_scope:
        for e in d['all_events']:
            events_json.append({k: (v.isoformat() if isinstance(v, (dt.date,)) else v) for k, v in e.items()
                                if k not in ('students',) or True})
    rules = ScheduleRule.objects.filter(trainer=trainer, status__in=('active', 'paused')).select_related('registration', 'batch', 'course')
    rule_rows = []
    for r in rules:
        h = eng.rule_hours(r)
        rule_rows.append({'r': r, 'h': h})
    attention = [a for a in eng.attention_items()['leave_clash'] if a['leave'].trainer_id == trainer.pk]
    unmarked = len(eng.pending_attendance(trainer))
    no_hours = not trainer.working_hours.exists()
    day = days[0] if view == 'day' else None
    now_min = eng.dubai_now_minutes() if view == 'day' and anchor == today else None
    return render(request, 'trainer_schedule/trainer_week.html', {
        'trainer': trainer, 'view': view, 'anchor': anchor, 'title': title, 'days': days, 'day': day,
        'prev_d': prev_d, 'next_d': next_d, 'today': today, 'kpi': kpi, 'filters': filters, 'fq': fq,
        'hour_marks': [{'label': f'{h:02d}:00', 'top': eng.pct_top(h * 60)} for h in range(10, 21)],
        'now_top': eng.pct_top(now_min) if now_min is not None and eng.DAY_START <= now_min <= eng.DAY_END else None,
        'events_json': events_json, 'rule_rows': rule_rows, 'leaves': trainer.leaves.filter(date_to__gte=today),
        'attention': attention, 'unmarked': unmarked, 'no_hours': no_hours, 'courses': Course.objects.filter(pk__in=[x['r'].course_id for x in rule_rows if x['r'].course_id] +
                                                                 list(trainer.courses.values_list('pk', flat=True))).order_by('name'),
        'can_manage': can_manage(request.user), 'can_create': can_create(request.user), 'fmt': fmt_hours,
        'is_own': bool(mine and mine.pk == trainer.pk), 'setting': eng.settings_obj(),
        'next_url': request.get_full_path()})


# ── create schedule ─────────────────────────────────────────────────────────

def student_search(request):
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    from django.db.models import Q
    regs = (Registration.objects.filter(is_refunded=False)
            .filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(registration_number__icontains=q) |
                    Q(phone_no__icontains=q) | Q(email__icontains=q) | Q(courses__name__icontains=q)).distinct()[:15])
    out = []
    for r in regs:
        courses = []
        for rc in RegistrationCourse.objects.filter(registration=r).select_related('course'):
            rules = ScheduleRule.objects.filter(registration=r, course=rc.course).exclude(status='cancelled')
            rem = sum(eng.rule_hours(x)['remaining'] for x in rules if x.status in ('active', 'paused'))
            courses.append({'id': rc.course_id, 'name': rc.course.name, 'has_schedule': rules.filter(status__in=('active', 'paused')).exists(),
                            'remaining': rem})
        out.append({'id': r.pk, 'name': f'{r.first_name} {r.last_name}'.strip(), 'reg': r.registration_number, 'phone': r.phone_no,
                    'status': r.get_student_status_display(), 'courses': courses})
    return JsonResponse({'results': out})


def _create_only(view):
    def wrapper(request, *a, **k):
        if not request.user.is_authenticated or not can_create(request.user):
            return JsonResponse({'results': [], 'ok': False}, status=403)
        return view(request, *a, **k)
    wrapper.__name__ = view.__name__
    return wrapper


student_search = _create_only(student_search)


def _schedule_inputs(request, data):
    """Parse + validate the create-schedule form. Returns (cleaned, errors)."""
    errors, c = [], {}
    c['trainer'] = Trainer.objects.filter(pk=data.get('trainer') or None, is_active=True).first()
    if not c['trainer']:
        errors.append('Choose a trainer - every schedule needs one.')
    c['type'] = data.get('schedule_type') if data.get('schedule_type') in ('individual', 'batch') else 'individual'
    c['registration'] = c['batch'] = c['course'] = None
    if c['type'] == 'individual':
        c['registration'] = Registration.objects.filter(pk=data.get('registration') or None).first()
        if not c['registration']:
            errors.append('Search and select the student.')
        else:
            c['course'] = Course.objects.filter(pk=data.get('course') or None, registrationcourse__registration=c['registration']).first()
            if not c['course']:
                errors.append("Select one of the student's registered courses.")
            elif c['registration'].is_refunded:
                errors.append('This registration is refunded.')
    else:
        c['batch'] = Batch.objects.filter(pk=data.get('batch') or None).first()
        if not c['batch']:
            errors.append('Select the batch.')
        else:
            c['course'] = c['batch'].course
            if ScheduleRule.objects.filter(batch=c['batch']).exclude(status='cancelled').exists():
                errors.append('This batch already has a schedule - edit or pause that one instead of creating a second.')
    c['start_date'] = parse_date(data.get('start_date'))
    if not c['start_date']:
        errors.append('Choose a valid start date.')
    c['weekdays'] = sorted({int(x) for x in data.getlist('weekdays') if x.isdigit() and 0 <= int(x) <= 6})
    if not c['weekdays']:
        errors.append('Select at least one training day.')
    try:
        c['start_time'] = parse_time(data.get('start_time') or '')
    except ValueError:
        c['start_time'] = None
        errors.append('Choose a valid start time.')
    c['session_minutes'] = _hours(data.get('session_hours'))
    if c['session_minutes'] <= 0:
        errors.append('Enter the session length.')
    c['total_minutes'] = _hours(data.get('total_hours'))
    if c['total_minutes'] <= 0:
        errors.append('Enter the total training hours required.')
    c['interval'] = int(data.get('teaching_interval') or eng.settings_obj().default_interval)
    c['end_date'] = parse_date(data.get('end_date'))
    c['notes'] = (data.get('notes') or '').strip()
    if c['start_time'] and c['session_minutes'] and mins(c['start_time']) + c['session_minutes'] > 24 * 60:
        errors.append('The session runs past midnight.')
    return c, errors


@create_required
def schedule_create(request):
    setting = eng.settings_obj()
    data = request.POST if request.method == 'POST' else request.GET
    stage = 'form'
    errors, prev = [], None
    if request.method == 'POST' and data.get('stage') in ('review', 'confirm'):
        c, errors = _schedule_inputs(request, data)
        if not errors:
            planned = eng.plan_occurrences(c['start_date'], c['weekdays'], mins(c['start_time']), c['session_minutes'],
                                           c['total_minutes'], until=c['end_date'])
            if not planned:
                errors.append('No sessions could be generated - check the days, dates and end date.')
            else:
                res = eng.check_conflicts(c['trainer'], planned, c['type'], registration=c['registration'], setting=setting)
                if c['registration'] and c['course']:
                    dup = ScheduleRule.objects.filter(registration=c['registration'], course=c['course'], status__in=('active', 'paused'))
                    for r in dup:
                        h = eng.rule_hours(r)
                        res['confirms'].append(f'{c["registration"].first_name} already has a {r.get_status_display().lower()} schedule for '
                                               f'{c["course"].name} with {r.trainer.name} ({fmt_hours(h["remaining"])} remaining).')
                mgr, adm = can_manage(request.user), is_admin_role(request.user)
                override = adm and data.get('override') == '1'
                confirmed = data.get('confirm_ok') == '1' and mgr
                blocked_reason = ''
                if res['errors'] and not override:
                    blocked_reason = 'errors'
                elif res['confirms'] and not confirmed:
                    blocked_reason = 'confirm' if mgr else 'needs_manager'
                prev = {'planned': planned, 'first': planned[0][0], 'last': planned[-1][0], 'sessions': len(planned),
                        'minutes': sum(e - s for _, s, e in planned), 'res': res, 'blocked': blocked_reason,
                        'sample': [{'d': d, 'label': f'{hhmm(s)}-{hhmm(e)}'} for d, s, e in planned[:8]], 'can_override': adm,
                        'can_confirm': mgr}
                stage = 'review'
                if request.method == 'POST' and data.get('stage') == 'confirm' and not blocked_reason:
                    rule = eng.create_rule(
                        request.user, trainer=c['trainer'], schedule_type=c['type'], registration=c['registration'], batch=c['batch'],
                        course=c['course'], start_date=c['start_date'], end_date=c['end_date'] or planned[-1][0],
                        end_date_manual=bool(c['end_date']), weekdays=','.join(map(str, c['weekdays'])), start_time=c['start_time'],
                        session_minutes=c['session_minutes'], teaching_interval=c['interval'], total_minutes=c['total_minutes'],
                        auto_extend=setting.auto_extend, notes=c['notes'])
                    if override and res['errors']:
                        eng.audit(rule, 'override', 'Admin override: ' + ' | '.join(res['errors']), request.user)
                    if confirmed and res['confirms']:
                        eng.audit(rule, 'exception_confirmed', ' | '.join(res['confirms']), request.user)
                    messages.success(request, f'Schedule created: {len(planned)} session(s) for {rule.subject} with {rule.trainer.name}, '
                                              f'last on {planned[-1][0]:%d %b %Y}.')
                    return redirect(safe_next(request, f'/schedules/{rule.pk}/'))
    trainer = Trainer.objects.filter(pk=data.get('trainer') or None).first()
    selected_reg = Registration.objects.filter(pk=data.get('registration') or None).first()
    start_time = data.get('start_time') or (data.get('start') and hhmm(int(data.get('start')))) or '10:00'
    stype = data.get('schedule_type') if data.get('schedule_type') in ('individual', 'batch') else 'individual'
    weekdays_sel = set(int(x) for x in data.getlist('weekdays') if x.isdigit()) if hasattr(data, 'getlist') else set()
    start_date = data.get('start_date') or data.get('date') or ''
    if not weekdays_sel and start_date:
        d0 = parse_date(start_date)
        weekdays_sel = {d0.weekday()} if d0 else set()
    return render(request, 'trainer_schedule/schedule_create.html', {
        'stage': stage, 'errors': errors, 'prev': prev, 'trainer': trainer, 'trainers': Trainer.objects.filter(is_active=True),
        'selected_reg': selected_reg, 'batches': Batch.objects.exclude(status__in=('cancelled', 'completed')).order_by('name'),
        'courses_of_reg': [rc.course for rc in RegistrationCourse.objects.filter(registration=selected_reg).select_related('course')] if selected_reg else [],
        'v': {'schedule_type': stype, 'batch': data.get('batch', ''), 'course': data.get('course', ''), 'start_date': start_date,
              'start_time': start_time, 'session_hours': data.get('session_hours') or ('2' if stype == 'individual' else '1'),
              'total_hours': data.get('total_hours') or '20', 'teaching_interval': data.get('teaching_interval') or setting.default_interval,
              'end_date': data.get('end_date', ''), 'notes': data.get('notes', '')},
        'weekdays': WEEKDAY_CHOICES, 'sel_days': weekdays_sel, 'setting': setting, 'next': data.get('next', ''),
        'is_admin': is_admin_role(request.user), 'is_manager': can_manage(request.user)})


@_create_only
def schedule_preview(request):
    """Live expected-completion + conflict preview for the create form."""
    g = request.GET
    trainer = Trainer.objects.filter(pk=g.get('trainer') or None).first()
    try:
        start_date = parse_date(g.get('start_date'))
        wd = sorted({int(x) for x in g.get('weekdays', '').split(',') if x.isdigit()})
        s = mins(parse_time(g.get('start_time', '')))
        session = _hours(g.get('session_hours'))
        total = _hours(g.get('total_hours'))
        end = parse_date(g.get('end_date'))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False})
    if not (start_date and wd and session and total):
        return JsonResponse({'ok': False})
    planned = eng.plan_occurrences(start_date, wd, s, session, total, until=end)
    if not planned:
        return JsonResponse({'ok': False})
    reg = Registration.objects.filter(pk=g.get('registration') or None).first()
    res = eng.check_conflicts(trainer, planned, g.get('schedule_type', 'individual'), registration=reg) if trainer else \
        {'errors': [], 'confirms': [], 'warnings': [], 'info': []}
    return JsonResponse({'ok': True, 'sessions': len(planned), 'first': planned[0][0].strftime('%a %d %b %Y'),
                         'last': planned[-1][0].strftime('%a %d %b %Y'), 'end_iso': planned[-1][0].isoformat(),
                         'minutes': sum(b - a for _, a, b in planned), 'errors': res['errors'], 'confirms': res['confirms'],
                         'warnings': res['warnings'], 'info': res['info']})


# ── schedule details / lifecycle ────────────────────────────────────────────

@login_required
def rule_detail(request, pk):
    rule = get_object_or_404(ScheduleRule.objects.select_related('trainer', 'registration', 'batch', 'course', 'paused_by'), pk=pk)
    mine = own_trainer(request.user)
    if mine and not can_manage(request.user) and mine.pk != rule.trainer_id:
        messages.error(request, 'You can only open your own schedules.')
        return redirect('trainer_list')
    today = eng.dubai_today()
    occs = list(rule.occurrences.select_related('trainer').order_by('date', 'start_time'))
    for o in occs:
        o.dur = mins(o.end_time) - mins(o.start_time)
        o.is_past = o.date < today
    h = eng.rule_hours(rule)
    roster = list(rule.batch.students.filter(status='active').select_related('registration')) if rule.batch else []
    return render(request, 'trainer_schedule/rule_detail.html', {
        'rule': rule, 'h': h, 'hf': {k: fmt_hours(h[k]) for k in ('required', 'scheduled', 'delivered', 'remaining', 'unscheduled')}, 'occs': occs, 'audit': rule.audit.select_related('user')[:60], 'roster': roster, 'today': today,
        'next_upcoming': next((o for o in occs if o.date >= today and o.status in eng.ACTIVE_FUTURE), None),
        'can_manage': can_manage(request.user), 'is_admin': is_admin_role(request.user),
        'is_own': bool(mine and mine.pk == rule.trainer_id), 'fmt': fmt_hours, 'trainers': Trainer.objects.filter(is_active=True),
        'weekdays': WEEKDAY_CHOICES, 'next_url': request.get_full_path(),
        'others': ScheduleRule.objects.filter(registration=rule.registration).exclude(pk=rule.pk).select_related('trainer')[:8] if rule.registration_id else []})


@manage_required
def rule_edit(request, pk):
    rule = get_object_or_404(ScheduleRule, pk=pk)
    setting = eng.settings_obj()
    errors, prev = [], None
    today = eng.dubai_today()
    if request.method == 'POST':
        eff = parse_date(request.POST.get('effective'), today)
        wd = _weekdays(request)
        try:
            st = parse_time(request.POST.get('start_time') or '')
        except ValueError:
            st = None
        session = _hours(request.POST.get('session_hours'))
        total = _hours(request.POST.get('total_hours'))
        end = parse_date(request.POST.get('end_date'))
        trainer = Trainer.objects.filter(pk=request.POST.get('trainer') or None, is_active=True).first() or rule.trainer
        if not (wd and st and session and total):
            errors.append('Days, start time, session length and total hours are required.')
        else:
            new = ScheduleRule(trainer=trainer, schedule_type=rule.schedule_type, weekdays=','.join(map(str, wd)), start_time=st,
                               session_minutes=session, total_minutes=total, start_date=rule.start_date)
            h = eng.rule_hours(rule)
            needed = max(0, total - h['delivered'])
            planned = eng.plan_occurrences(rule.start_date, wd, mins(st), session, needed, until=end, min_date=eff)
            res = eng.check_conflicts(trainer, planned, rule.schedule_type, exclude_rule=rule, registration=rule.registration, setting=setting)
            adm, mgr = is_admin_role(request.user), can_manage(request.user)
            blocked = bool(res['errors'] and not (adm and request.POST.get('override') == '1')) or \
                bool(res['confirms'] and request.POST.get('confirm_ok') != '1')
            prev = {'res': res, 'sessions': len(planned), 'last': planned[-1][0] if planned else None, 'blocked': blocked}
            if request.POST.get('stage') == 'confirm' and not blocked:
                if trainer.pk != rule.trainer_id:
                    if not adm:
                        errors.append('Only admins can change the trainer.')
                    else:
                        eng.change_trainer(rule, trainer, eff, request.user)
                if not errors:
                    rule.weekdays, rule.start_time, rule.session_minutes = ','.join(map(str, wd)), st, session
                    rule.teaching_interval = int(request.POST.get('teaching_interval') or rule.teaching_interval)
                    rule.total_minutes, rule.notes = total, request.POST.get('notes', '').strip()
                    rule.end_date, rule.end_date_manual = (end, True) if end else (rule.end_date, False)
                    rule.auto_extend = request.POST.get('auto_extend') == '1'
                    rule.updated_by = request.user
                    rule.save()
                    removed, added = eng.regenerate_future(rule, eff, request.user, f'Schedule edited (effective {eff:%d %b %Y}); history kept')
                    messages.success(request, f'Schedule updated from {eff:%d %b %Y}: {removed} future session(s) replaced by {added}.')
                    return redirect(safe_next(request, f'/schedules/{rule.pk}/'))
    return render(request, 'trainer_schedule/rule_edit.html', {
        'rule': rule, 'errors': errors, 'prev': prev, 'today': today, 'weekdays': WEEKDAY_CHOICES, 'is_admin': is_admin_role(request.user),
        'sel_days': set(_weekdays(request)) if request.method == 'POST' else set(rule.weekday_list),
        'trainers': Trainer.objects.filter(is_active=True), 'fmt': fmt_hours, 'hours': eng.rule_hours(rule),
        'v': request.POST if request.method == 'POST' else {}, 'next': request.GET.get('next', '')})


@manage_required
@require_POST
def rule_pause(request, pk):
    rule = get_object_or_404(ScheduleRule, pk=pk)
    d = parse_date(request.POST.get('pause_date'), eng.dubai_today())
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'Please give a reason for the pause.')
    elif rule.status != 'active':
        messages.error(request, 'Only an active schedule can be paused.')
    else:
        n = eng.pause_rule(rule, d, reason, request.POST.get('notes', ''), parse_date(request.POST.get('expected_resume')), request.user)
        messages.success(request, f'Schedule paused. {n} future slot(s) are free again; remaining hours are kept.')
    return redirect(safe_next(request, f'/schedules/{pk}/'))


@manage_required
@require_POST
def rule_resume(request, pk):
    rule = get_object_or_404(ScheduleRule, pk=pk)
    if rule.status != 'paused':
        messages.error(request, 'This schedule is not paused.')
        return redirect('rule_detail', pk=pk)
    start = parse_date(request.POST.get('start_date'), eng.dubai_today())
    changes = {}
    wd = _weekdays(request)
    if wd:
        changes['weekdays'] = ','.join(map(str, wd))
    if request.POST.get('start_time'):
        try:
            changes['start_time'] = parse_time(request.POST['start_time'])
        except ValueError:
            pass
    if request.POST.get('session_hours'):
        changes['session_minutes'] = _hours(request.POST['session_hours']) or None
    new_trainer = Trainer.objects.filter(pk=request.POST.get('trainer') or None, is_active=True).first()
    if new_trainer and new_trainer.pk != rule.trainer_id:
        if is_admin_role(request.user):
            changes['trainer'] = new_trainer
        else:
            messages.warning(request, 'Only admins can change the trainer - kept the original trainer.')
    # check the new slots first
    tmp_wd = [int(x) for x in (changes.get('weekdays') or rule.weekdays).split(',') if x]
    h = eng.rule_hours(rule)
    planned = eng.plan_occurrences(rule.start_date, tmp_wd, mins(changes.get('start_time') or rule.start_time),
                                   changes.get('session_minutes') or rule.session_minutes, h['remaining'], min_date=start)
    res = eng.check_conflicts(changes.get('trainer') or rule.trainer, planned, rule.schedule_type, exclude_rule=rule, registration=rule.registration)
    if res['errors'] and not (is_admin_role(request.user) and request.POST.get('override') == '1'):
        messages.error(request, 'Cannot resume: ' + ' '.join(res['errors']) + ' Adjust the days/time or ask an admin to override.')
        return redirect(safe_next(request, f'/schedules/{pk}/'))
    if res['confirms'] and request.POST.get('confirm_ok') != '1':
        messages.warning(request, 'Resume needs confirmation: ' + ' '.join(res['confirms']) + ' Tick "confirm exceptions" and resume again.')
        return redirect(safe_next(request, f'/schedules/{pk}/'))
    n = eng.resume_rule(rule, start, request.user, changes)
    messages.success(request, f'Schedule resumed from {start:%d %b %Y}: {n} session(s) generated for the remaining {fmt_hours(h["remaining"])}.')
    return redirect(safe_next(request, f'/schedules/{pk}/'))


@manage_required
@require_POST
def rule_cancel(request, pk):
    rule = get_object_or_404(ScheduleRule, pk=pk)
    reason = request.POST.get('reason', '').strip() or 'Cancelled by management'
    n = eng.cancel_rule(rule, parse_date(request.POST.get('cancel_date'), eng.dubai_today()), reason, request.user)
    messages.success(request, f'Future schedule cancelled; {n} slot(s) are free again. History is kept.')
    return redirect(safe_next(request, f'/schedules/{pk}/'))


@manage_required
@require_POST
def rule_extend(request, pk):
    rule = get_object_or_404(ScheduleRule, pk=pk)
    n = eng.extend_rule(rule, request.user)
    messages.success(request, f'{n} session(s) added to cover the remaining hours.' if n else 'Nothing to add - all remaining hours are already scheduled.')
    return redirect(safe_next(request, f'/schedules/{pk}/'))


@login_required
@require_POST
def occurrence_action(request, pk):
    occ = get_object_or_404(ScheduleOccurrence.objects.select_related('rule', 'trainer'), pk=pk)
    action = request.POST.get('action')
    mgr = can_manage(request.user)
    mine = own_trainer(request.user)
    trainer_ok = bool(mine and mine.pk == occ.trainer_id)
    nxt = safe_next(request, f'/schedules/{occ.rule_id}/')
    if action in ('completed', 'absent', 'note') and not (mgr or trainer_ok):
        messages.error(request, 'You cannot update this session.')
        return redirect(nxt)
    if action in ('cancelled', 'scheduled', 'reschedule') and not mgr:
        messages.error(request, 'Only admins and centre managers can change or cancel sessions.')
        return redirect(nxt)
    if occ.status == 'completed' and not is_admin_role(request.user) and action != 'note':
        messages.error(request, 'Completed sessions are history - only an admin can change them.')
        return redirect(nxt)
    note = request.POST.get('note', '').strip()
    if action in ('completed', 'absent', 'cancelled', 'scheduled'):
        delivered = _hours(request.POST.get('delivered_hours'), None) if request.POST.get('delivered_hours') not in (None, '') else None
        eng.set_occurrence_status(occ, action, request.user, delivered=delivered, note=note)
        messages.success(request, f'Session marked {action}.')
    elif action == 'note':
        occ.note = note
        occ.save(update_fields=['note', 'updated_at'])
        eng.audit(occ.rule, 'note', f'{occ.date:%d %b}: {note}', request.user, occ)
        messages.success(request, 'Note saved.')
    elif action == 'reschedule':
        nd = parse_date(request.POST.get('new_date'))
        try:
            ns = mins(parse_time(request.POST.get('new_start') or ''))
        except ValueError:
            ns = None
        if not nd or ns is None:
            messages.error(request, 'Choose a new date and time.')
            return redirect(nxt)
        dur = mins(occ.end_time) - mins(occ.start_time)
        res = eng.check_conflicts(occ.trainer, [(nd, ns, ns + dur)], occ.rule.schedule_type, exclude_rule=occ.rule, registration=occ.rule.registration)
        if res['errors'] and not (is_admin_role(request.user) and request.POST.get('override') == '1'):
            messages.error(request, 'Cannot move there: ' + ' '.join(res['errors']))
            return redirect(nxt)
        if res['confirms'] and request.POST.get('confirm_ok') != '1':
            messages.warning(request, 'Needs confirmation: ' + ' '.join(res['confirms']) + ' Tick "confirm" and try again.')
            return redirect(nxt)
        eng.reschedule_occurrence(occ, nd, ns, request.POST.get('scope', 'one'), request.user, note=note)
        messages.success(request, 'Session rescheduled.')
    return redirect(nxt)


@login_required
def student_history(request, reg_pk):
    reg = get_object_or_404(Registration, pk=reg_pk)
    rules = list(ScheduleRule.objects.filter(registration=reg).select_related('trainer', 'course').order_by('-created_at'))
    for r in rules:
        r.h = eng.rule_hours(r)
    audit = ScheduleAudit.objects.filter(rule__in=rules).select_related('rule', 'user').order_by('-created_at')[:100]
    return render(request, 'trainer_schedule/student_history.html', {'reg': reg, 'rules': rules, 'audit': audit, 'fmt': fmt_hours})


# ── settings / reports ──────────────────────────────────────────────────────

@login_required
def scheduling_settings(request):
    if not is_admin_role(request.user):
        messages.error(request, 'Only admins can change scheduling settings.')
        return redirect('trainer_list')
    s = SchedulingSetting.get()
    if request.method == 'POST':
        p = request.POST
        s.default_interval = int(p.get('default_interval') or 30) if int(p.get('default_interval') or 30) in (15, 30, 45, 60) else 30
        s.max_concurrent_individuals = max(1, int(p.get('max_concurrent_individuals') or 3))
        for f in ('batch_batch_policy', 'batch_individual_policy', 'working_hours_policy'):
            if p.get(f) in ('block', 'confirm', 'allow'):
                setattr(s, f, p[f])
        s.auto_extend = p.get('auto_extend') == '1'
        s.low_hours_threshold = max(0, int(p.get('low_hours_threshold') or 120))
        s.absence_alert_count = max(1, int(p.get('absence_alert_count') or 3))
        s.save()
        messages.success(request, 'Scheduling settings saved.')
        return redirect('scheduling_settings')
    return render(request, 'trainer_schedule/settings.html', {'s': s, 'policies': SchedulingSetting.POLICY_CHOICES})


@login_required
def utilization(request):
    if not can_manage(request.user):
        messages.error(request, 'Only admins and centre managers can view utilization reports.')
        return redirect('trainer_list')
    today = eng.dubai_today()
    d0 = parse_date(request.GET.get('from'), today - dt.timedelta(days=today.weekday()))
    d1 = parse_date(request.GET.get('to'), d0 + dt.timedelta(days=6))
    rows = eng.utilization_report(d0, min(d1, d0 + dt.timedelta(days=92)), Trainer.objects.filter(is_active=True))
    att = eng.attention_items()
    tot = {k: sum(r[k] for r in rows) for k in ('working', 'batch', 'student_min', 'occupied', 'free', 'partial', 'delivered', 'cancelled', 'paused', 'absent')}
    for r in rows:
        r.update({'working_f': fmt_hours(r['working']), 'batch_f': fmt_hours(r['batch']), 'student_f': fmt_hours(r['student_min']),
                  'free_f': fmt_hours(r['free']), 'partial_f': fmt_hours(r['partial']), 'delivered_f': fmt_hours(r['delivered'])})
    return render(request, 'trainer_schedule/utilization.html', {
        'rows': rows, 'd0': d0, 'd1': d1, 'att': att, 'tot': tot, 'tot_f': {k: fmt_hours(v) for k, v in tot.items()}, 'fmt': fmt_hours,
        'avg_util': round(sum(r['util'] * r['working'] for r in rows) / tot['working']) if tot['working'] else 0})


# ── sessions awaiting attendance ────────────────────────────────────────────

@login_required
def pending_sessions(request):
    mine = own_trainer(request.user)
    if not (can_manage(request.user) or mine):
        messages.error(request, 'Only admins, centre managers and trainers can record attendance.')
        return redirect('trainer_list')
    trainer = mine if (mine and not can_manage(request.user)) else Trainer.objects.filter(pk=request.GET.get('trainer') or None).first()
    occs = eng.pending_attendance(trainer)
    for o in occs:
        o.dur = mins(o.end_time) - mins(o.start_time)
    return render(request, 'trainer_schedule/pending.html', {
        'occs': occs, 'trainer': trainer, 'trainers': Trainer.objects.filter(is_active=True),
        'can_manage': can_manage(request.user), 'next_url': request.get_full_path()})


@login_required
@require_POST
def pending_bulk(request):
    action = request.POST.get('action')
    if action not in ('completed', 'absent'):
        return redirect(safe_next(request, '/schedule-pending/'))
    mine = own_trainer(request.user)
    done = 0
    for o in ScheduleOccurrence.objects.filter(pk__in=request.POST.getlist('occ'), status__in=eng.ACTIVE_FUTURE).select_related('rule', 'trainer'):
        if not (can_manage(request.user) or (mine and mine.pk == o.trainer_id)):
            continue
        if o.date > eng.dubai_today():
            continue
        eng.set_occurrence_status(o, action, request.user)
        done += 1
    messages.success(request, f'{done} session(s) marked {action}.')
    return redirect(safe_next(request, '/schedule-pending/'))
