"""Admin/mentor screens for automation: switches, run-now, decision log + undo, templates, interview slots, flags, screening, AI drafts, digests."""
import csv
import io
from datetime import date, datetime, time, timedelta

from flask import Blueprint, current_app, g, jsonify, request

import ai
import automation
import db
import mailer
import services
from core import today
from security import auth, bad, int_list, pick_date, staff_scope, text

bp = Blueprint("automation_admin", __name__, url_prefix="/api/staff")

SETTING_RULES = {            # key -> (min, max) for numbers, or None for text/bool
    "automation_enabled": "bool", "auto_decline_enabled": "bool", "review_auto_approve": "bool",
    "test_borderline_margin": (0, 30), "stale_fee_days": (30, 730), "cert_pass_mark": (1, 100), "enrolment_fee_inr": (0, 500000),
    "adsense_client": "text", "adsense_slot": "text",
}


@bp.get("/automation/settings")
@auth("admin")
def get_settings():
    return jsonify(settings={k: services.setting(k) for k in SETTING_RULES},
                   notes={"ai_model": current_app.config.get("ANTHROPIC_MODEL") if ai.llm_available() else None,
                          "scheduler": bool(current_app.config.get("AUTO_SCHEDULER")), "sms_webhook": bool(current_app.config.get("SMS_WEBHOOK_URL")),
                          "smtp": bool(current_app.config.get("SMTP_HOST")), "redis": current_app.config.get("REDIS") is not None})


@bp.put("/automation/settings")
@auth("admin")
def put_settings():
    b = request.get_json(silent=True) or {}
    for k, rule in SETTING_RULES.items():
        if k not in b:
            continue
        v = b[k]
        if rule == "bool":
            v = "1" if str(v).lower() in ("1", "true", "yes", "on") else "0"
        elif rule == "text":
            v = str(v or "").strip()[:80]
            if v and not all(c.isalnum() or c in "-_." for c in v):
                bad(f"{k} contains invalid characters.")
        else:
            try:
                v = int(v)
            except (TypeError, ValueError):
                bad(f"{k} must be a number.")
            if not rule[0] <= v <= rule[1]:
                bad(f"{k} must be between {rule[0]} and {rule[1]}.")
            v = str(v)
        db.run("insert into settings (key,value) values (%s,%s) on conflict (key) do update set value=excluded.value", (k, v))
    return jsonify(ok=True)


@bp.post("/automation/run")
@auth("admin")
def run_now():
    return jsonify(results=automation.run_all(force=bool((request.get_json(silent=True) or {}).get("force"))))


@bp.get("/automation/log")
@auth("admin")
def log():
    kind = request.args.get("kind")
    only = request.args.get("reversible") == "1"
    where, args = ["true"], []
    if kind:
        where.append("l.kind=%s"); args.append(kind)
    if only:
        where.append("l.reversible and l.undone_at is null")
    rows = db.q(f"""select l.id, l.kind, l.detail, l.reversible, l.undone_at, l.created_at, l.ref_type, l.ref_id, u.name as student_name
                    from automation_log l left join users u on u.id=l.student_id where {' and '.join(where)} order by l.id desc limit 200""", tuple(args))
    kinds = [r["kind"] for r in db.q("select distinct kind from automation_log order by kind")]
    return jsonify(log=rows, kinds=kinds)


@bp.post("/automation/log/<int:lid>/undo")
@auth("admin")
def undo(lid):
    e = db.one("select * from automation_log where id=%s", (lid,))
    if not e or not e["reversible"] or e["undone_at"]:
        bad("This decision cannot be undone.", 409)
    k, rid = e["kind"], e["ref_id"]
    if k in ("auto_shortlist", "auto_decline"):
        db.run("update applications set pipeline='test_taken', status='test_taken', auto_note=%s where id=%s", (f"Automatic decision undone by {g.user['name']}. Needs a person.", rid))
    elif k == "review_auto_approved":
        db.run("update class_reviews set status='pending' where id=%s", (rid,))
        r = db.one("select class_id from class_reviews where id=%s", (rid,))
        r and services.refresh_rating(r["class_id"])
    elif k == "review_held":
        db.run("update class_reviews set status='live', flag_reason=null where id=%s", (rid,))
        r = db.one("select class_id from class_reviews where id=%s", (rid,))
        r and services.refresh_rating(r["class_id"])
    elif k == "task_incomplete":
        db.run("update task_assignments set status='pending' where id=%s and status='incomplete'", (rid,))
    elif k == "certificate_issued":
        db.run("update certificates set revoked_at=now(), revoked_reason=%s where user_id=%s and revoked_at is null", (f"Undone by {g.user['name']}", e["student_id"] or rid))
    else:
        bad("Nothing to undo for this kind of decision.")
    db.run("update automation_log set undone_at=now() where id=%s", (lid,))
    services.log_auto("undo", f"{g.user['name']} undid #{lid}: {e['detail']}")
    return jsonify(ok=True)


@bp.get("/weekly-report")
@auth("admin")
def weekly_report():
    r = automation.build_weekly_report()
    return jsonify(report=r, text=automation.report_text(r))


@bp.post("/weekly-report/send")
@auth("admin")
def weekly_send():
    body = automation.report_text(automation.build_weekly_report())
    db.run("insert into reports (kind, body) values ('weekly', %s)", (body,))
    to = automation.admin_emails()
    for e in to:
        mailer.send_mail(e, f"Weekly report – {services.company()}", body)
    return jsonify(sent_to=to)


# ======================================================================= task templates
def _clean_items(raw):
    if not isinstance(raw, list) or not raw:
        bad("Add at least one day to the template.")
    out = []
    for it in raw[:120]:
        title = text(it, "title", 200, True, "Task title")
        try:
            day, pts = int(it.get("day_no")), int(it.get("max_points", 10))
            due, grace = int(it.get("due_in_days", 1)), int(it.get("grace_days", 1))
        except (TypeError, ValueError):
            bad("Day, points, due days and grace days must be numbers.")
        if day < 1 or day > 365 or not 1 <= pts <= 1000 or not 0 <= due <= 30 or not 0 <= grace <= 14:
            bad("A day, points, due-in or grace value is out of range.")
        out.append((day, title, text(it, "description", 3000), pts, due, grace, text(it, "rubric", 1000)))
    return sorted(out)


@bp.get("/templates")
@auth("admin")
def templates():
    rows = db.q("""select t.id, t.name, t.description, t.is_default, count(i.id) as days, max(i.day_no) as last_day,
                          (select count(*) from users u where u.template_id=t.id) as students
                   from task_templates t left join task_template_items i on i.template_id=t.id group by t.id order by t.id""")
    return jsonify(templates=rows)


@bp.get("/templates/<int:tid>")
@auth("admin")
def template_get(tid):
    t = db.one("select * from task_templates where id=%s", (tid,))
    if not t:
        bad("Template not found.", 404)
    t["items"] = db.q("select day_no, title, description, max_points, due_in_days, grace_days, rubric from task_template_items where template_id=%s order by day_no, id", (tid,))
    return jsonify(**t)


def _save_items(t, tid, items):
    t.run("delete from task_template_items where template_id=%s", (tid,))
    for day, title, desc, pts, due, grace, rubric in items:
        t.run("""insert into task_template_items (template_id, day_no, title, description, max_points, due_in_days, grace_days, rubric)
                 values (%s,%s,%s,%s,%s,%s,%s,%s)""", (tid, day, title, desc, pts, due, grace, rubric))


@bp.post("/templates")
@auth("admin")
def template_create():
    b = request.get_json(silent=True) or {}
    name, items = text(b, "name", 80, True, "Template name"), _clean_items(b.get("items"))
    if db.one("select 1 from task_templates where lower(name)=lower(%s)", (name,)):
        bad("A template with this name already exists.", 409)
    with db.tx() as t:
        tid = t.one("insert into task_templates (name, description) values (%s,%s) returning id", (name, text(b, "description", 300)))["id"]
        _save_items(t, tid, items)
    return jsonify(id=tid), 201


@bp.put("/templates/<int:tid>")
@auth("admin")
def template_update(tid):
    """Editing affects students enrolled from now on; tasks already created for current students are left alone."""
    b = request.get_json(silent=True) or {}
    if not db.one("select 1 from task_templates where id=%s", (tid,)):
        bad("Template not found.", 404)
    name, items = text(b, "name", 80, True, "Template name"), _clean_items(b.get("items"))
    with db.tx() as t:
        t.run("update task_templates set name=%s, description=%s where id=%s", (name, text(b, "description", 300), tid))
        _save_items(t, tid, items)
    return jsonify(ok=True)


@bp.delete("/templates/<int:tid>")
@auth("admin")
def template_delete(tid):
    t = db.one("select is_default from task_templates where id=%s", (tid,))
    if not t:
        bad("Template not found.", 404)
    if t["is_default"]:
        bad("This is the default template. Make another one the default first.")
    db.run("update users set template_id=null where template_id=%s", (tid,))
    db.run("delete from task_templates where id=%s", (tid,))
    return jsonify(ok=True)


@bp.post("/templates/<int:tid>/default")
@auth("admin")
def template_default(tid):
    with db.tx() as t:
        t.run("update task_templates set is_default=false")
        t.run("update task_templates set is_default=true where id=%s", (tid,))
    return jsonify(ok=True)


@bp.post("/students/<int:sid>/apply-template")
@auth("staff")
def apply_template(sid):
    sql, args = staff_scope("u")
    s = db.one(f"select u.* from users u where u.id=%s and u.role='student' {sql}", (sid,) + args)
    if not s:
        bad("Student not found.", 404)
    b = request.get_json(silent=True) or {}
    tid = b.get("template_id")
    if not db.one("select 1 from task_templates where id=%s", (tid,)):
        bad("Choose a template.")
    start = pick_date(b.get("start_date"), "Start date", False) or s["start_date"] or today()
    n = services.apply_template(sid, tid, start)
    db.run("update users set template_id=%s, start_date=%s where id=%s", (tid, start, sid))
    return jsonify(created=n)


# ======================================================================= interview slots
@bp.get("/slots")
@auth("staff")
def slots():
    mine, args = ("", ()) if g.user["role"] == "admin" else ("and s.mentor_id=%s", (g.user["id"],))
    rows = db.q(f"""select s.id, s.starts_at, s.duration_mins, s.meeting_link, s.mentor_id, m.name as mentor_name, s.application_id, a.name as applicant
                    from interview_slots s left join users m on m.id=s.mentor_id left join applications a on a.id=s.application_id
                    where s.starts_at > now() - interval '1 day' {mine} order by s.starts_at limit 400""", args)
    return jsonify(slots=rows)


@bp.post("/slots")
@auth("staff")
def slots_create():
    """Open many slots at once: a date range x daily start times."""
    b = request.get_json(silent=True) or {}
    d1, d2 = pick_date(b.get("date_from"), "From date"), pick_date(b.get("date_to"), "To date")
    if d2 < d1 or (d2 - d1).days > 60:
        bad("Choose a date range of at most 60 days.")
    times = b.get("times") or []
    if not isinstance(times, list) or not times:
        bad("Add at least one start time, for example 10:00.")
    try:
        parsed = [time.fromisoformat(str(t)[:5]) for t in times[:20]]
        dur = int(b.get("duration_mins", 30))
    except ValueError:
        bad("Times must look like 10:00, and the length must be a number.")
    if not 10 <= dur <= 180:
        bad("Interview length must be between 10 and 180 minutes.")
    mentor_id = g.user["id"] if g.user["role"] == "mentor" else (b.get("mentor_id") or None)
    if mentor_id and not db.one("select 1 from users where id=%s and role in ('mentor','admin')", (mentor_id,)):
        bad("Choose a valid interviewer.")
    link = text(b, "meeting_link", 500)
    tz = current_app.config["TZ"]
    made, d = 0, d1
    while d <= d2:
        if not (b.get("skip_weekends", True) and d.weekday() >= 5):
            for t in parsed:
                at = datetime.combine(d, t, tzinfo=tz)
                if at > datetime.now(tz):
                    made += db.run("""insert into interview_slots (mentor_id, starts_at, duration_mins, meeting_link) values (%s,%s,%s,%s)
                                      on conflict (mentor_id, starts_at) do nothing""", (mentor_id, at, dur, link or None))
        d += timedelta(days=1)
    return jsonify(created=made), 201


@bp.delete("/slots/<int:sid>")
@auth("staff")
def slots_delete(sid):
    mine, args = ("", ()) if g.user["role"] == "admin" else (" and mentor_id=%s", (g.user["id"],))
    n = db.run(f"delete from interview_slots where id=%s and application_id is null{mine}", (sid,) + args)
    if not n:
        bad("Only your own unbooked slots can be removed.", 409)
    return jsonify(ok=True)


# ======================================================================= flags, screening, AI drafts, digest
@bp.get("/flags")
@auth("staff")
def flags():
    sql, args = staff_scope("u")
    rows = db.q(f"""select f.id, f.kind, f.note, f.created_at, u.id as student_id, u.name from student_flags f join users u on u.id=f.student_id
                    where f.resolved_at is null {sql} order by f.created_at""", args)
    return jsonify(flags=rows)


@bp.post("/flags/<int:fid>/resolve")
@auth("staff")
def flag_resolve(fid):
    sql, args = staff_scope("u")
    n = db.run(f"update student_flags f set resolved_at=now() from users u where u.id=f.student_id and f.id=%s and f.resolved_at is null {sql}", (fid,) + args)
    return jsonify(ok=True, changed=n)


@bp.get("/screening")
@auth("admin")
def screening():
    rows = db.q("""select id, name, role_applied, college, pipeline, status, screening, created_at from applications
                   where status <> 'rejected' order by (screening->>'score')::int desc nulls last, created_at limit 200""")
    return jsonify(applications=rows)


@bp.post("/applications/<int:aid>/screen")
@auth("admin")
def screen_one(aid):
    r = ai.screen_application(aid)
    if r is None:
        bad("Application not found.", 404)
    return jsonify(screening=r)


@bp.post("/assignments/<int:aid>/ai-draft")
@auth("staff")
def ai_draft(aid):
    sql, args = staff_scope("u")
    if not db.one(f"select 1 from task_assignments ta join users u on u.id=ta.student_id where ta.id=%s and ta.status='submitted' {sql}", (aid,) + args):
        bad("Submission not found.", 404)
    return jsonify(draft=ai.draft_review(aid))


@bp.get("/digest")
@auth("staff")
def digest():
    day = pick_date(request.args.get("day"), "Day", False) or today()
    mentors = [g.user] if g.user["role"] == "mentor" else db.q("select id, name from users where role='mentor' and is_active order by name")
    out = [{"mentor": m["name"], **ai.standup_digest(m["id"], day)} for m in mentors]
    return jsonify(digests=out)


@bp.post("/tests/draft-questions")
@auth("admin")
def draft_questions():
    b = request.get_json(silent=True) or {}
    topic = text(b, "topic", 120, True, "Topic")
    try:
        n = max(1, min(15, int(b.get("count", 5))))
    except (TypeError, ValueError):
        bad("Count must be a number.")
    return jsonify(questions=ai.draft_questions(topic, n, text(b, "level", 20) or "beginner"), note="Drafts only: review and edit before you save them to a test.")
