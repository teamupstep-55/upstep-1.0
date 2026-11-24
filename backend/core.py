"""Logic shared by several route files."""
import secrets
import string
from datetime import date, datetime, timedelta

from flask import current_app

import db


def today():
    return datetime.now(current_app.config["TZ"]).date()


def temp_password():
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(9))
    return core + secrets.choice("ABCDEFGH") + secrets.choice("23456789")  # always has letters + digits


def site_settings():
    s = {r["key"]: r["value"] for r in db.q("select key, value from settings")}
    return s


# ---------------------------------------------------------------- programme progress
def day_number(student, on=None):
    sd = student.get("start_date")
    if not sd:
        return None
    return max(1, ((on or today()) - sd).days + 1)


UNLOCKED = "(ta.unlock_date is null or ta.unlock_date <= %s)"   # a scheduled task is visible from its unlock date


def performance_map(student_ids=None):
    """performance % = points earned / points available.
    'Available' = tasks already approved + tasks whose due date has passed (missed tasks count as zero)."""
    sql = """select ta.student_id,
               coalesce(sum(case when ta.status='approved' then least(coalesce(ta.points,0), t.max_points) end),0) as earned,
               coalesce(sum(case when ta.status='approved' or t.due_date < %s then t.max_points end),0) as possible,
               count(*) as total,
               count(*) filter (where ta.status='approved') as approved,
               count(*) filter (where ta.status='submitted') as submitted,
               count(*) filter (where ta.status in ('pending','rework') and t.due_date < %s) as overdue
             from task_assignments ta join tasks t on t.id = ta.task_id
             where (ta.unlock_date is null or ta.unlock_date <= %s)"""
    args = [today(), today(), today()]
    if student_ids is not None:
        sql += " and ta.student_id = any(%s)"
        args.append(list(student_ids))
    sql += " group by ta.student_id"
    out = {}
    for r in db.q(sql, args):
        r["performance"] = round(100 * r["earned"] / r["possible"]) if r["possible"] else None
        out[r["student_id"]] = r
    return out


# ---------------------------------------------------------------- events (with repeats)
def _occurrences(ev, start, end, tz):
    s = ev["starts_at"].astimezone(tz)
    dur = (ev["ends_at"] - ev["starts_at"]) if ev["ends_at"] else None
    until = ev["recur_until"] or end
    last = min(end, until)
    days = []
    if ev["recurrence"] == "none":
        if start <= s.date() <= end:
            days = [s.date()]
    else:
        d = max(start, s.date())
        while d <= last:
            if (ev["recurrence"] == "weekdays" and d.weekday() < 5) or (ev["recurrence"] == "weekly" and d.weekday() == s.weekday()):
                days.append(d)
            d += timedelta(days=1)
    for d in days:
        st = datetime.combine(d, s.timetz().replace(tzinfo=None), tzinfo=tz)
        yield {**ev, "starts_at": st, "ends_at": (st + dur) if dur else None, "occurrence_date": d, "repeats": ev["recurrence"] != "none"}


def events_between(where_sql, args, start, end):
    tz = current_app.config["TZ"]
    lo = datetime.combine(start - timedelta(days=1), datetime.min.time(), tzinfo=tz)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    rows = db.q(f"""select e.id, e.title, e.kind, e.category, e.description, e.link, e.starts_at, e.ends_at,
                           e.recurrence, e.recur_until, e.group_id, e.student_id, g.name as group_name
                    from events e left join student_groups g on g.id = e.group_id
                    where ({where_sql}) and (
                       (e.recurrence = 'none' and e.starts_at >= %s and e.starts_at < %s)
                       or (e.recurrence <> 'none' and e.starts_at < %s and (e.recur_until is null or e.recur_until >= %s)))""",
                tuple(args) + (lo, hi, hi, start))
    out = []
    for ev in rows:
        out.extend(_occurrences(ev, start, end, tz))
    out.sort(key=lambda e: e["starts_at"])
    return out


def visible_events_sql(user):
    """(where_sql, args) selecting the events this person is allowed to see."""
    if user["role"] == "admin":
        return "true", ()
    if user["role"] == "student":
        return ("(e.group_id is null and e.student_id is null) or e.student_id = %s "
                "or e.group_id in (select group_id from group_members where student_id = %s)"), (user["id"], user["id"])
    return ("(e.group_id is null and e.student_id is null) or e.created_by = %s "
            "or e.student_id in (select id from users where mentor_id = %s) "
            "or e.group_id in (select id from student_groups where mentor_id = %s)"), (user["id"],) * 3


# ---------------------------------------------------------------- chat access
def ensure_mentor_channel(student_id):
    db.run("insert into channels (kind, name, student_id) values ('mentor','Mentor chat',%s) on conflict do nothing", (student_id,))


def can_use_channel(user, ch):
    if ch["kind"] == "general" or user["role"] == "admin":
        return True
    if ch["kind"] == "group":
        return bool(db.one("""select 1 from student_groups g where g.id=%s and (g.mentor_id=%s
                              or exists (select 1 from group_members m where m.group_id=g.id and m.student_id=%s))""",
                           (ch["group_id"], user["id"], user["id"])))
    s = db.one("select id, mentor_id from users where id=%s", (ch["student_id"],))
    return bool(s) and (s["id"] == user["id"] or s["mentor_id"] == user["id"])
