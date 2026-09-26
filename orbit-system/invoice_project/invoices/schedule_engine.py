"""Trainer scheduling engine: recurrence, occurrences, conflicts, rotation capacity, hours.

Two operating models (see the Orbit scheduling spec):
  * INDIVIDUAL - a student has an attendance window (e.g. 2h); the trainer rotates between
    several students in short teaching intervals. Overlapping individual windows are normal.
  * BATCH - one continuous block that fully occupies the trainer.

A ScheduleRule is the recurring instruction; ScheduleOccurrence rows are the actual dated
sessions generated from it. Occurrences can be paused / cancelled / rescheduled / completed
one by one, and history is never rewritten.
"""
import datetime as dt
import math
from collections import defaultdict

from django.db import transaction

from .models import (
    Batch, BatchStudent, ClassSession, ScheduleAudit, ScheduleOccurrence, ScheduleRule, SchedulingSetting,
    TrainerLeave, TrainerWorkingHours,
)

DAY_START, DAY_END = 10 * 60, 21 * 60
DUBAI = dt.timezone(dt.timedelta(hours=4))   # UAE has no DST; the server clock is UTC


def dubai_today():
    return dt.datetime.now(DUBAI).date()


def dubai_now_minutes():
    n = dt.datetime.now(DUBAI)
    return n.hour * 60 + n.minute

CELL = 15                                    # capacity grid resolution (minutes)
OCCUPY = ('scheduled', 'rescheduled', 'completed', 'absent')
ACTIVE_FUTURE = ('scheduled', 'rescheduled')
GHOST = ('paused', 'cancelled')
STATUS_LABEL = dict(ScheduleOccurrence.STATUS_CHOICES)


# ── small helpers ───────────────────────────────────────────────────────────

def mins(t):
    return t.hour * 60 + t.minute


def hhmm(m):
    return f'{int(m) // 60:02d}:{int(m) % 60:02d}'


def to_time(m):
    m = max(0, min(int(m), 23 * 60 + 59))
    return dt.time(m // 60, m % 60)


def fmt_hours(m):
    m = int(round(m or 0))
    h, r = divmod(m, 60)
    return f'{h}h {r:02d}m' if r else f'{h}h'


def pct_top(m):
    return max(0.0, (m - DAY_START) / (DAY_END - DAY_START) * 100)


def pct_height(a, b):
    a, b = max(a, DAY_START), min(b, DAY_END)
    return max(0.0, (b - a) / (DAY_END - DAY_START) * 100)


def overlaps(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def union_minutes(intervals):
    total, cur_s, cur_e = 0, None, None
    for s, e in sorted(intervals):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def audit(rule, action, detail='', user=None, occ=None):
    ScheduleAudit.objects.create(rule=rule, occurrence=occ, action=action, detail=detail[:2000], user=user)


def settings_obj():
    return SchedulingSetting.get()


# ── recurrence ──────────────────────────────────────────────────────────────

def plan_occurrences(start_date, weekdays, start_min, session_minutes, total_minutes, until=None, min_date=None):
    """[(date, start_min, end_min)] covering `total_minutes` (last session shortened to the
    remainder). With `until`, every matching date up to it is planned instead."""
    if not weekdays or session_minutes <= 0:
        return []
    out, d = [], max(start_date, min_date or start_date)
    remaining = total_minutes
    guard = 0
    while guard < 4000:
        guard += 1
        if until and d > until:
            break
        if d.weekday() in weekdays:
            if until:
                out.append((d, start_min, start_min + session_minutes))
            else:
                if remaining <= 0:
                    break
                length = min(session_minutes, remaining)
                out.append((d, start_min, start_min + length))
                remaining -= length
        d += dt.timedelta(days=1)
        if not until and remaining <= 0:
            break
    return out


def expected_completion(start_date, weekdays, start_min, session_minutes, total_minutes, until=None):
    rows = plan_occurrences(start_date, weekdays, start_min, session_minutes, total_minutes, until)
    return {'sessions': len(rows), 'first': rows[0][0] if rows else None, 'last': rows[-1][0] if rows else None,
            'minutes': sum(e - s for _, s, e in rows), 'rows': rows}


# ── hours accounting ────────────────────────────────────────────────────────

def rule_hours(rule, today=None):
    today = today or dubai_today()
    occs = list(rule.occurrences.all())
    dur = lambda o: mins(o.end_time) - mins(o.start_time)
    delivered = sum(o.delivered_minutes for o in occs if o.status == 'completed')
    future_active = sum(dur(o) for o in occs if o.status in ACTIVE_FUTURE)
    scheduled = sum(dur(o) for o in occs if o.status in ('scheduled', 'rescheduled', 'completed'))
    remaining = max(0, rule.total_minutes - delivered)
    return {'required': rule.total_minutes, 'scheduled': scheduled, 'delivered': delivered, 'remaining': remaining,
            'future_active': future_active, 'unscheduled': max(0, remaining - future_active),
            'sessions_total': len(occs), 'sessions_done': sum(1 for o in occs if o.status == 'completed'),
            'absent': sum(1 for o in occs if o.status == 'absent'),
            'cancelled': sum(1 for o in occs if o.status == 'cancelled'),
            'paused': sum(1 for o in occs if o.status == 'paused'),
            'pct': round(min(100, delivered / rule.total_minutes * 100)) if rule.total_minutes else 0}


def rule_trace(rule, today=None):
    """Everything needed to follow a schedule at a glance: a strip of coloured session dots,
    the next upcoming session and the last one that happened. Works on prefetched occurrences."""
    today = today or dubai_today()
    occs = sorted(rule.occurrences.all(), key=lambda o: (o.date, o.start_time))
    strip = [{'status': o.status, 'label': f'{o.date:%a %d %b} {o.start_time:%H:%M} - {STATUS_LABEL.get(o.status, o.status)}',
              'today': o.date == today} for o in occs]
    nxt = next((o for o in occs if o.status in ACTIVE_FUTURE and o.date >= today), None)
    last = next((o for o in reversed(occs) if o.status in ('completed', 'absent')), None)
    overdue = sum(1 for o in occs if o.status in ACTIVE_FUTURE and o.date < today)
    return {'strip': strip[:80], 'strip_more': max(0, len(strip) - 80), 'next': nxt, 'last': last, 'overdue': overdue}


def _touch_end_date(rule):
    if rule.end_date_manual:
        return
    last = rule.occurrences.filter(status__in=OCCUPY).order_by('-date').values_list('date', flat=True).first()
    rule.end_date = last or rule.end_date
    rule.save(update_fields=['end_date', 'updated_at'])


def _generate(rule, from_date, minutes_needed, user=None):
    rows = plan_occurrences(rule.start_date, rule.weekday_list, mins(rule.start_time), rule.session_minutes,
                            minutes_needed, until=rule.end_date if rule.end_date_manual else None, min_date=from_date)
    created = [ScheduleOccurrence(rule=rule, trainer=rule.trainer, date=d, start_time=to_time(s), end_time=to_time(e),
                                  status='scheduled', updated_by=user) for d, s, e in rows]
    ScheduleOccurrence.objects.bulk_create(created)
    return len(created)


# ── rule lifecycle ──────────────────────────────────────────────────────────

@transaction.atomic
def create_rule(user, **f):
    rule = ScheduleRule.objects.create(created_by=user, updated_by=user, **f)
    _generate(rule, rule.start_date, rule.total_minutes, user)
    _touch_end_date(rule)
    if rule.schedule_type == 'batch' and rule.batch:
        mirror_rule_to_batch(rule)
    audit(rule, 'created', f'{rule.get_schedule_type_display()} schedule for {rule.subject} with {rule.trainer.name}: '
                           f'{rule.weekday_names} from {rule.start_date:%d %b %Y} at {rule.start_time:%H:%M}, '
                           f'{fmt_hours(rule.total_minutes)} required.', user)
    return rule


def mirror_rule_to_batch(rule):
    """Keep the Batch summary fields in step with its schedule rule."""
    b = rule.batch
    if not b:
        return
    b.trainer = rule.trainer
    b.start_date = rule.start_date
    b.end_date = rule.end_date or rule.start_date
    b.weekdays = rule.weekdays
    b.start_time = rule.start_time
    b.end_time = to_time(mins(rule.start_time) + rule.session_minutes)
    if rule.course and not b.course:
        b.course = rule.course
    b.save()


@transaction.atomic
def regenerate_future(rule, effective, user, reason='Recurrence changed', keep_exceptions=False):
    """Replace future scheduled sessions from `effective` using the rule's current settings.
    Completed / absent / cancelled / paused history is left untouched; with keep_exceptions,
    sessions that were moved by hand are kept too."""
    doomed = rule.occurrences.filter(date__gte=effective, status__in=ACTIVE_FUTURE)
    if keep_exceptions:
        doomed = doomed.filter(is_exception=False)
    removed = doomed.delete()[0]
    h = rule_hours(rule)
    needed = h['remaining'] - h['future_active']
    added = _generate(rule, effective, needed, user) if rule.status == 'active' and needed > 0 else 0
    _touch_end_date(rule)
    if rule.schedule_type == 'batch':
        mirror_rule_to_batch(rule)
    audit(rule, 'rule_edited', f'{reason}. {removed} future session(s) replaced by {added} new session(s) from {effective:%d %b %Y}.', user)
    return removed, added


@transaction.atomic
def pause_rule(rule, pause_date, reason, notes, expected_resume, user):
    n = rule.occurrences.filter(date__gte=max(pause_date, dubai_today()), status__in=ACTIVE_FUTURE).update(status='paused', updated_by=user)
    rule.status, rule.pause_date, rule.pause_reason = 'paused', pause_date, reason[:200]
    rule.pause_notes, rule.expected_resume, rule.paused_by, rule.updated_by = notes, expected_resume, user, user
    rule.save()
    audit(rule, 'paused', f'Paused from {pause_date:%d %b %Y}: {reason}. {n} future slot(s) released.'
                          f'{" Expected resume " + expected_resume.strftime("%d %b %Y") if expected_resume else ""}', user)
    return n


@transaction.atomic
def resume_rule(rule, start_date, user, changes=None):
    changes = changes or {}
    for k in ('weekdays', 'start_time', 'session_minutes', 'trainer'):
        if k in changes and changes[k] is not None:
            setattr(rule, k, changes[k])
    rule.status, rule.resume_date, rule.updated_by = 'active', start_date, user
    rule.save()
    h = rule_hours(rule)
    added = _generate(rule, start_date, max(0, h['remaining'] - h['future_active']), user)
    _touch_end_date(rule)
    if rule.schedule_type == 'batch':
        mirror_rule_to_batch(rule)
    audit(rule, 'resumed', f'Resumed from {start_date:%d %b %Y}; {added} session(s) generated for the remaining '
                           f'{fmt_hours(h["remaining"])}.', user)
    return added


@transaction.atomic
def cancel_rule(rule, cancel_date, reason, user):
    n = rule.occurrences.filter(date__gte=cancel_date, status__in=ACTIVE_FUTURE + ('paused',)).update(status='cancelled', updated_by=user)
    rule.status, rule.cancel_date, rule.cancel_reason, rule.updated_by = 'cancelled', cancel_date, reason[:200], user
    rule.save()
    audit(rule, 'cancelled', f'Future schedule cancelled from {cancel_date:%d %b %Y}: {reason}. {n} slot(s) released.', user)
    return n


@transaction.atomic
def extend_rule(rule, user=None, note='Extended to cover remaining hours'):
    """Add sessions after the last one so the remaining training hours are fully scheduled."""
    if rule.status != 'active':
        return 0
    h = rule_hours(rule)
    if h['unscheduled'] <= 0:
        return 0
    last = rule.occurrences.exclude(status='cancelled').order_by('-date').values_list('date', flat=True).first()
    start = max(dubai_today(), (last + dt.timedelta(days=1)) if last else rule.start_date)
    added = _generate(rule, start, h['unscheduled'], user)
    _touch_end_date(rule)
    if added:
        audit(rule, 'extended', f'{note}: {added} session(s) added for {fmt_hours(h["unscheduled"])}.', user)
    return added


def _finish_if_done(rule):
    h = rule_hours(rule)
    if rule.status == 'active' and rule.total_minutes and h['remaining'] == 0 and h['future_active'] == 0:
        rule.status = 'completed'
        rule.save(update_fields=['status', 'updated_at'])


@transaction.atomic
def set_occurrence_status(occ, status, user, delivered=None, note='', actual_start=None, actual_end=None):
    old = occ.status
    occ.status = status
    occ.note = (note or occ.note)[:2000]
    occ.updated_by = user
    dur = mins(occ.end_time) - mins(occ.start_time)
    if status == 'completed':
        occ.delivered_minutes = dur if delivered is None else max(0, int(delivered))
        occ.attendance = 'present'
        occ.actual_start, occ.actual_end = actual_start, actual_end
    elif status in ('absent', 'cancelled', 'scheduled'):
        occ.delivered_minutes = 0
        occ.attendance = 'absent' if status == 'absent' else ''
    occ.save()
    rule = occ.rule
    extra = ''
    if status in ('absent', 'cancelled') and rule.status == 'active' and rule.auto_extend:
        n = extend_rule(rule, user, 'Make-up session added after a missed/cancelled class')
        extra = f' {n} make-up session(s) added.' if n else ''
    if status == 'completed':
        _finish_if_done(rule)
    audit(rule, f'session_{status}', f'{occ.date:%d %b %Y} {occ.start_time:%H:%M}-{occ.end_time:%H:%M}: {old} -> {status}.{extra} {note}', user, occ)


@transaction.atomic
def reschedule_occurrence(occ, new_date, new_start_min, scope, user, new_minutes=None, note=''):
    rule = occ.rule
    old_start = mins(occ.start_time)
    dur = new_minutes or (mins(occ.end_time) - old_start)
    detail = f'{occ.date:%d %b %H:%M} -> {new_date:%d %b} {hhmm(new_start_min)}'
    occ.original_date = occ.original_date or occ.date
    occ.date, occ.start_time, occ.end_time = new_date, to_time(new_start_min), to_time(new_start_min + dur)
    occ.status, occ.is_exception, occ.updated_by = 'rescheduled', True, user
    if note:
        occ.note = note
    occ.save()
    shifted = 0
    if scope == 'future':
        delta = new_start_min - old_start
        for o in rule.occurrences.filter(date__gt=occ.date, status__in=ACTIVE_FUTURE, is_exception=False):
            o.start_time, o.end_time = to_time(mins(o.start_time) + delta), to_time(mins(o.end_time) + delta)
            o.save(update_fields=['start_time', 'end_time', 'updated_at'])
            shifted += 1
        rule.start_time = to_time(mins(rule.start_time) + delta)
        rule.updated_by = user
        rule.save(update_fields=['start_time', 'updated_by', 'updated_at'])
    _touch_end_date(rule)
    audit(rule, 'rescheduled', f'{detail} ({"this and future sessions" if scope == "future" else "this session only"}'
                               f'{"; " + str(shifted) + " later session(s) shifted" if shifted else ""}). {note}', user, occ)


@transaction.atomic
def change_trainer(rule, new_trainer, effective, user):
    old = rule.trainer
    n = rule.occurrences.filter(date__gte=effective, status__in=ACTIVE_FUTURE + ('paused',)).update(trainer=new_trainer)
    rule.trainer, rule.updated_by = new_trainer, user
    rule.save()
    if rule.schedule_type == 'batch':
        mirror_rule_to_batch(rule)
    audit(rule, 'trainer_changed', f'{old.name} -> {new_trainer.name} from {effective:%d %b %Y} ({n} session(s) moved).', user)


# ── conflicts ───────────────────────────────────────────────────────────────

def _leave_dates(trainer, d0, d1):
    return list(TrainerLeave.objects.filter(trainer=trainer, date_from__lte=d1, date_to__gte=d0))


def on_leave(d, leaves):
    return any(lv.date_from <= d <= lv.date_to for lv in leaves)


def hours_map(trainer):
    return {w.weekday: (mins(w.start_time), mins(w.end_time)) for w in TrainerWorkingHours.objects.filter(trainer=trainer)}


def check_conflicts(trainer, planned, schedule_type, exclude_rule=None, exclude_session=None, registration=None, setting=None):
    """Classify problems for booking `trainer` on planned=[(date, start, end)].
    errors    - blocked unless an admin overrides
    confirms  - must be confirmed by the user
    warnings  - shown, no confirmation needed
    info      - allowed by design (e.g. individual students overlapping)"""
    setting = setting or settings_obj()
    res = {'errors': [], 'confirms': [], 'warnings': [], 'info': []}
    if not trainer or not planned:
        return res
    for _, s, e in planned:
        if e <= s:
            res['errors'].append('End time must be after start time.')
            return res
    dates = sorted({d for d, _, _ in planned})
    d0, d1 = dates[0], dates[-1]

    leaves = _leave_dates(trainer, d0, d1)
    bad = [d for d in dates if on_leave(d, leaves)]
    if bad:
        res['errors'].append(f'{trainer.name} is on leave on {len(bad)} of these date(s) (first {bad[0]:%a %d %b %Y}).')

    if setting.working_hours_policy != 'allow':
        wh = hours_map(trainer)
        out = [d for d, s, e in planned if d.weekday() not in wh or s < wh[d.weekday()][0] or e > wh[d.weekday()][1]]
        if out:
            msg = f'{len(out)} session(s) fall outside {trainer.name}\'s working hours (first {out[0]:%a %d %b}).'
            res['errors' if setting.working_hours_policy == 'block' else 'confirms'].append(msg)

    existing = (ScheduleOccurrence.objects.filter(trainer=trainer, date__gte=d0, date__lte=d1, status__in=('scheduled', 'rescheduled', 'completed'))
                .select_related('rule', 'rule__batch', 'rule__registration'))
    if exclude_rule:
        existing = existing.exclude(rule_id=exclude_rule.pk)
    by_date = defaultdict(list)
    for o in existing:
        by_date[o.date].append(('rule', o))
    for cs in ClassSession.objects.filter(trainer=trainer, date__gte=d0, date__lte=d1).exclude(status='cancelled'):
        if exclude_session and cs.pk == exclude_session:
            continue
        by_date[cs.date].append(('session', cs))

    groups = defaultdict(lambda: {'n': 0, 'first': None})
    max_conc, over_conc = setting.max_concurrent_individuals, None
    for d, s, e in planned:
        concurrent = 0
        for kind, o in by_date.get(d, []):
            if not overlaps(s, e, mins(o.start_time), mins(o.end_time)):
                continue
            o_type = o.rule.schedule_type if kind == 'rule' else 'individual'
            name = (o.rule.subject if kind == 'rule' else (o.student_name or 'one-off session'))
            if o_type == 'individual':
                concurrent += 1
            if schedule_type == 'batch' and o_type == 'batch':
                key = ('bb', name)
            elif 'batch' in (schedule_type, o_type):
                key = ('bi', name)
            else:
                key = ('ii', name)
            g = groups[key]
            g['n'] += 1
            g['first'] = g['first'] or d
        if schedule_type == 'individual' and concurrent >= max_conc and over_conc is None:
            over_conc = d
    for (kind, name), g in groups.items():
        line = f'{name} ({g["n"]} overlapping session(s), first {g["first"]:%a %d %b})'
        if kind == 'ii':
            res['info'].append(f'Overlaps with individual student {line} - allowed, trainer rotates between students.')
        elif kind == 'bb':
            msg = f'Batch conflict: {line}. A trainer cannot run two batches at once.'
            pol = setting.batch_batch_policy
            (res['errors'] if pol == 'block' else res['confirms'] if pol == 'confirm' else res['info']).append(msg)
        else:
            msg = f'Batch/individual clash with {line}. The batch needs the trainer for its whole block.'
            pol = setting.batch_individual_policy
            (res['errors'] if pol == 'block' else res['confirms'] if pol == 'confirm' else res['info']).append(msg)
    if over_conc:
        res['confirms'].append(f'Rotation is already at its limit of {max_conc} students at the same time '
                               f'(first on {over_conc:%a %d %b}). Adding another may stretch teaching time.')

    if registration:
        mine = ScheduleOccurrence.objects.filter(rule__registration=registration, date__gte=d0, date__lte=d1,
                                                 status__in=('scheduled', 'rescheduled')).select_related('rule', 'trainer')
        if exclude_rule:
            mine = mine.exclude(rule_id=exclude_rule.pk)
        clash = [o for o in mine for d, s, e in planned if o.date == d and overlaps(s, e, mins(o.start_time), mins(o.end_time))]
        if clash:
            res['confirms'].append(f'This student already has {len(clash)} overlapping session(s) with {clash[0].trainer.name} '
                                   f'(first {clash[0].date:%a %d %b}).')
    return res


def conflicts_blocking(res, is_admin, override=False, confirmed=False):
    """Can the schedule be saved given the conflict result and who is saving it?"""
    if res['errors'] and not (is_admin and override):
        return False
    if res['confirms'] and not confirmed:
        return False
    return True


# ── day model: events, rotation capacity, free windows ──────────────────────

def _assign_lanes(events):
    events.sort(key=lambda e: (e['start'], e['end']))
    active, cluster = [], []

    def close():
        n = (max(e['lane'] for e in cluster) + 1) if cluster else 1
        for e in cluster:
            e['lanes'] = n

    for ev in events:
        active = [a for a in active if a['end'] > ev['start']]
        if not active:
            close()
            cluster = []
        used = {a['lane'] for a in active}
        lane = next(i for i in range(len(events) + 1) if i not in used)
        ev['lane'] = lane
        active.append(ev)
        cluster.append(ev)
    close()


def _event_from_occ(o, stu_map=None):
    r = o.rule
    s, e = mins(o.start_time), mins(o.end_time)
    is_batch = r.schedule_type == 'batch'
    reg = r.registration
    names = []
    if is_batch and r.batch_id:
        if stu_map is not None:
            names = stu_map.get(r.batch_id, [])
        else:
            names = [f'{l.registration.first_name} {l.registration.last_name}'.strip()
                     for l in r.batch.students.filter(status='active').select_related('registration')][:20]
    return {
        'kind': 'batch' if is_batch else 'individual', 'id': o.pk, 'rule_id': r.pk, 'date': o.date,
        'title': r.subject, 'student': r.subject if not is_batch else '', 'reg_no': reg.registration_number if reg else '',
        'course': r.course.name if r.course else (r.batch.course.name if r.batch and r.batch.course else ''),
        'status': o.status, 'status_label': STATUS_LABEL.get(o.status, o.status), 'ghost': o.status in GHOST,
        'start': s, 'end': e, 'dur': e - s, 'label': f'{hhmm(s)}-{hhmm(e)}', 'students': names or ([r.subject] if not is_batch else []),
        'student_count': len(names) if is_batch else 1, 'mode': r.batch.mode if is_batch and r.batch else '',
        'venue': r.batch.venue if is_batch and r.batch else '', 'note': o.note, 'delivered': o.delivered_minutes,
        'interval': r.teaching_interval, 'exception': o.is_exception, 'original_date': o.original_date,
        'url': f'/schedules/{r.pk}/', 'oneoff': False,
    }


def _event_from_session(c):
    s, e = mins(c.start_time), mins(c.end_time)
    return {
        'kind': 'individual', 'id': c.pk, 'rule_id': None, 'date': c.date, 'title': c.student_name or c.get_session_type_display(),
        'student': c.student_name, 'reg_no': c.registration.registration_number if c.registration else '',
        'course': c.course.name if c.course else '', 'status': 'scheduled' if c.status == 'scheduled' else c.status,
        'status_label': c.get_status_display(), 'ghost': False, 'start': s, 'end': e, 'dur': e - s,
        'label': f'{hhmm(s)}-{hhmm(e)}', 'students': [c.student_name] if c.student_name else [], 'student_count': 1 if c.student_name else 0,
        'mode': c.mode, 'venue': c.venue, 'note': c.notes, 'delivered': 0, 'interval': 30, 'exception': False,
        'original_date': None, 'url': f'/sessions/{c.pk}/edit/', 'oneoff': True,
    }


def _matches(ev, f):
    if not f:
        return True
    q = (f.get('q') or '').strip().lower()
    if q and q not in (ev['title'] + ' ' + ev['reg_no'] + ' ' + ' '.join(ev['students'])).lower():
        return False
    if f.get('course') and str(f['course']).lower() not in ev['course'].lower():
        return False
    if f.get('type') and f['type'] != ev['kind']:
        return False
    if f.get('status') and f['status'] not in (ev['status'],):
        return False
    return True


def build_days(trainer, d0, d1, filters=None, setting=None):
    """One dict per date in [d0, d1] with events, lanes, capacity segments, free windows and stats."""
    setting = setting or settings_obj()
    hmap = hours_map(trainer)
    leaves = _leave_dates(trainer, d0, d1)
    occs = defaultdict(list)
    rows = list(ScheduleOccurrence.objects.filter(trainer=trainer, date__gte=d0, date__lte=d1)
                .select_related('rule', 'rule__registration', 'rule__batch', 'rule__course', 'rule__batch__course'))
    batch_ids = {o.rule.batch_id for o in rows if o.rule.schedule_type == 'batch' and o.rule.batch_id}
    stu_map = defaultdict(list)
    if batch_ids:
        for l in BatchStudent.objects.filter(batch_id__in=batch_ids, status='active').select_related('registration'):
            if len(stu_map[l.batch_id]) < 20:
                stu_map[l.batch_id].append(f'{l.registration.first_name} {l.registration.last_name}'.strip())
    for o in rows:
        occs[o.date].append(_event_from_occ(o, stu_map))
    for c in ClassSession.objects.filter(trainer=trainer, date__gte=d0, date__lte=d1).exclude(status='cancelled').select_related('course', 'registration'):
        occs[c.date].append(_event_from_session(c))
    days, d = [], d0
    while d <= d1:
        days.append(_day(trainer, d, occs.get(d, []), hmap, leaves, setting, filters))
        d += dt.timedelta(days=1)
    return days


def _day(trainer, d, events, hmap, leaves, setting, filters):
    wh = hmap.get(d.weekday())
    leave = on_leave(d, leaves)
    w0, w1 = (max(wh[0], DAY_START), min(wh[1], DAY_END)) if wh else (0, 0)
    working = 0 if (not wh or leave) else max(0, w1 - w0)
    occupying = [e for e in events if e['status'] in OCCUPY or (e['oneoff'] and e['status'] == 'scheduled')]
    ghosts = [e for e in events if e['ghost']]
    max_conc = max(1, setting.max_concurrent_individuals)

    # capacity grid (only inside the trainer's working window)
    cells = []
    for t in range(w0, w1, CELL) if working else []:
        batch = any(e['kind'] == 'batch' and overlaps(t, t + CELL, e['start'], e['end']) for e in occupying)
        stu = [e for e in occupying if e['kind'] == 'individual' and overlaps(t, t + CELL, e['start'], e['end'])]
        n = len(stu)
        state = 'batch' if batch else 'free' if n == 0 else 'full' if n >= max_conc else 'partial'
        cells.append({'t': t, 'state': state, 'n': n, 'ev': stu})
    segs = []
    for c in cells:
        key = (c['state'], c['n'])
        if segs and (segs[-1]['state'], segs[-1]['n']) == key and segs[-1]['end'] == c['t']:
            segs[-1]['end'] = c['t'] + CELL
        else:
            segs.append({'state': c['state'], 'n': c['n'], 'start': c['t'], 'end': c['t'] + CELL})
    minfree = max(CELL, setting.default_interval)
    for s in segs:
        s.update({'top': pct_top(s['start']), 'height': pct_height(s['start'], s['end']), 'label': f'{hhmm(s["start"])}-{hhmm(s["end"])}',
                  'dur': s['end'] - s['start']})
    free = [s for s in segs if s['state'] == 'free' and s['dur'] >= minfree]
    partial = [s for s in segs if s['state'] == 'partial' and s['dur'] >= minfree]

    load = sum((1 if c['state'] == 'batch' else min(1, c['n'] / max_conc)) * CELL for c in cells)
    stats = {
        'working': working, 'off': not wh, 'leave': leave,
        'free_min': sum(s['dur'] for s in segs if s['state'] == 'free'),
        'partial_min': sum(s['dur'] for s in segs if s['state'] == 'partial'),
        'full_min': sum(s['dur'] for s in segs if s['state'] in ('full',)),
        'batch_min': sum(s['dur'] for s in segs if s['state'] == 'batch'),
        'occupied_min': sum(s['dur'] for s in segs if s['state'] != 'free'),
        'student_min': sum(e['dur'] for e in occupying if e['kind'] == 'individual'),
        'batch_sched_min': sum(e['dur'] for e in occupying if e['kind'] == 'batch'),
        'delivered_min': sum(e['delivered'] for e in occupying if e['status'] == 'completed'),
        'cancelled': sum(1 for e in ghosts if e['status'] == 'cancelled'), 'paused': sum(1 for e in ghosts if e['status'] == 'paused'),
        'absent': sum(1 for e in occupying if e['status'] == 'absent'), 'sessions': len(occupying),
        'students': len({(e['reg_no'] or e['title']) for e in occupying if e['kind'] == 'individual'}) +
                    sum(e['student_count'] for e in occupying if e['kind'] == 'batch'),
        'util': round(min(100, load / working * 100)) if working else 0,
    }
    # rotation plan: who the trainer teaches in each interval slot
    rotation = []
    interval = max(15, min(60, setting.default_interval))
    if working:
        for t in range(w0, w1, interval):
            here = sorted([e for e in occupying if e['kind'] == 'individual' and overlaps(t, t + interval, e['start'], e['end'])],
                          key=lambda e: (e['start'], e['title']))
            batch = [e for e in occupying if e['kind'] == 'batch' and overlaps(t, t + interval, e['start'], e['end'])]
            if batch:
                rotation.append({'start': t, 'end': t + interval, 'label': hhmm(t), 'who': batch[0]['title'], 'kind': 'batch', 'others': []})
            elif here:
                pick = here[((t - w0) // interval) % len(here)]
                rotation.append({'start': t, 'end': t + interval, 'label': hhmm(t), 'who': pick['title'], 'kind': 'individual',
                                 'others': [e['title'] for e in here if e is not pick]})
            else:
                rotation.append({'start': t, 'end': t + interval, 'label': hhmm(t), 'who': None, 'kind': 'free', 'others': []})

    shown = [e for e in events if _matches(e, filters)]
    lane_ev = [e for e in shown if not e['ghost']]
    _assign_lanes(lane_ev)
    for e in shown:
        e['top'], e['height'] = pct_top(e['start']), pct_height(e['start'], e['end'])
        if e['ghost']:
            e['lane'], e['lanes'] = 0, 1
        e['left'] = (e['lane'] / e['lanes'] * 100) if not e['ghost'] else 78
        e['width'] = (100 / e['lanes']) if not e['ghost'] else 22
    for e in events:
        e['iso'] = d.isoformat()
    return {'date': d, 'events': sorted(shown, key=lambda e: (e['start'], e['title'])), 'all_events': events, 'segments': segs,
            'free': free, 'partial': partial, 'stats': stats, 'rotation': rotation, 'window': (w0, w1) if working else None,
            'work_top': pct_top(w0) if wh else 0, 'work_height': pct_height(w0, w1) if wh else 0,
            'leave': leave, 'off': not wh}


# ── aggregates for cards, reports, alerts ───────────────────────────────────

def trainer_snapshot(trainer, today=None, day=None, setting=None):
    today = today or dubai_today()
    day = day or build_days(trainer, today, today, setting=setting)[0]
    rules = list(ScheduleRule.objects.filter(trainer=trainer, status='active').select_related('registration', 'batch')
                 .prefetch_related('occurrences'))
    students = {r.registration_id for r in rules if r.schedule_type == 'individual' and r.registration_id}
    batch_ids = [r.batch_id for r in rules if r.schedule_type == 'batch' and r.batch_id]
    batch_students = BatchStudent.objects.filter(batch_id__in=batch_ids, status='active').count() if batch_ids else 0
    tot = {'required': 0, 'scheduled': 0, 'delivered': 0, 'remaining': 0}
    for r in rules:
        h = rule_hours(r)
        for k in tot:
            tot[k] += h[k]
    return {'day': day, 'today_count': day['stats']['sessions'], 'active_students': len(students) + batch_students,
            'active_batches': sum(1 for r in rules if r.schedule_type == 'batch'), 'free_slots': len(day['free']),
            'status': ('leave' if day['leave'] else 'off' if day['off'] else None), **{'hours_' + k: v for k, v in tot.items()}}


def utilization_report(d0, d1, trainers):
    rows = []
    setting = settings_obj()
    for t in trainers:
        days = build_days(t, d0, d1, setting=setting)
        agg = defaultdict(int)
        for d in days:
            for k, v in d['stats'].items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    agg[k] += v
        working = agg['working']
        load = sum(d['stats']['util'] * d['stats']['working'] for d in days) / working if working else 0
        rows.append({'trainer': t, 'working': working, 'batch': agg['batch_sched_min'], 'student_min': agg['student_min'],
                     'occupied': agg['occupied_min'], 'free': agg['free_min'], 'partial': agg['partial_min'],
                     'delivered': agg['delivered_min'], 'cancelled': agg['cancelled'], 'paused': agg['paused'],
                     'absent': agg['absent'], 'util': round(load)})
    return rows


def pending_attendance(trainer=None, limit=300):
    """Past sessions still marked scheduled - nobody recorded whether they happened."""
    today = dubai_today()
    now_min = dubai_now_minutes()
    qs = (ScheduleOccurrence.objects.filter(status__in=ACTIVE_FUTURE, date__lte=today)
          .select_related('rule', 'rule__registration', 'rule__batch', 'rule__course', 'trainer').order_by('date', 'start_time'))
    if trainer:
        qs = qs.filter(trainer=trainer)
    out = []
    for o in qs[:limit * 2]:
        if o.date < today or mins(o.end_time) <= now_min:
            out.append(o)
    return out[:limit]


def attention_items(setting=None):
    """Things management should act on: repeated absences, low remaining hours, leave clashes,
    and past sessions nobody marked."""
    setting = setting or settings_obj()
    today = dubai_today()
    items = {'absences': [], 'low_hours': [], 'leave_clash': [], 'unmarked': 0}
    for r in (ScheduleRule.objects.filter(status='active').select_related('registration', 'trainer', 'batch')
              .prefetch_related('occurrences')):
        h = rule_hours(r)
        past = sorted((o for o in r.occurrences.all() if o.status in ('completed', 'absent') and o.date <= today),
                      key=lambda o: (o.date, o.start_time), reverse=True)[:10]
        streak = 0
        for o in past:
            if o.status != 'absent':
                break
            streak += 1
        if streak >= setting.absence_alert_count and r.schedule_type == 'individual':
            items['absences'].append({'rule': r, 'streak': streak})
        if 0 < h['remaining'] <= setting.low_hours_threshold and h['pct'] > 0:
            items['low_hours'].append({'rule': r, 'remaining': h['remaining']})
    for lv in TrainerLeave.objects.filter(date_to__gte=today).select_related('trainer'):
        n = ScheduleOccurrence.objects.filter(trainer=lv.trainer, date__gte=max(today, lv.date_from), date__lte=lv.date_to,
                                              status__in=ACTIVE_FUTURE).count()
        if n:
            items['leave_clash'].append({'leave': lv, 'count': n})
    items['unmarked'] = len(pending_attendance())
    return items
