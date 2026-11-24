from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request

import db
from core import UNLOCKED, day_number, events_between, performance_map, today, visible_events_sql
from security import auth, bad, text

bp = Blueprint("student", __name__, url_prefix="/api/student")


def _status(row):
    """Student-facing status: adds 'overdue' on top of the stored status."""
    if row["status"] in ("pending", "rework") and row["due_date"] < today():
        return "overdue"
    return row["status"]


def _cert_summary(u):
    c = db.one("select cert_no, grade, score, issued_at, revoked_at from certificates where user_id=%s", (u["id"],))
    return c if c and not c["revoked_at"] else None


@bp.get("/dashboard")
@auth("student")
def dashboard():
    u = g.user
    me = {"name": u["name"], "phase": u["phase"], "start_date": u["start_date"], "training_days": u["training_days"],
          "day": day_number(u), "outcome": u["outcome"]}
    mentor = db.one("select name from users where id=%s", (u["mentor_id"],)) if u["mentor_id"] else None
    perf = performance_map([u["id"]]).get(u["id"], {})
    rows = db.q("""select ta.id, ta.status, t.title, t.due_date, t.max_points, t.kind
                   from task_assignments ta join tasks t on t.id=ta.task_id
                   where ta.student_id=%s and ta.status in ('pending','rework') and """ + UNLOCKED + """
                   order by t.due_date, ta.id limit 6""", (u["id"], today()))
    nxt = db.one("""select min(unlock_date) as d from task_assignments where student_id=%s and unlock_date > %s""", (u["id"], today()))
    for r in rows:
        r["display_status"] = _status(r)
    stats = {"total": perf.get("total", 0), "completed": perf.get("approved", 0), "in_review": perf.get("submitted", 0),
             "overdue": perf.get("overdue", 0), "performance": perf.get("performance"),
             "due_soon": sum(1 for r in rows if today() <= r["due_date"] <= today() + timedelta(days=3))}
    where, args = visible_events_sql(u)
    upcoming = events_between(where, args, today(), today() + timedelta(days=7))
    now = datetime.now(current_app.config["TZ"])
    upcoming = [e for e in upcoming if (e["ends_at"] or e["starts_at"]) >= now][:6]
    ann = db.q("select id, title, body, created_at from announcements order by id desc limit 3")
    groups = db.q("""select g.id, g.name, g.kind from student_groups g join group_members m on m.group_id=g.id
                     where m.student_id=%s order by g.id""", (u["id"],))
    done_today = bool(db.one("select 1 from standups where student_id=%s and day=%s", (u["id"], today())))
    return jsonify(me=me, mentor=mentor, stats=stats, due_tasks=rows, upcoming=upcoming,
                   announcements=ann, groups=groups, standup_done=done_today,
                   next_unlock=nxt["d"] if nxt else None, certificate=_cert_summary(u))


@bp.get("/tasks")
@auth("student")
def tasks():
    rows = db.q("""select ta.id, ta.status, ta.submission_text, ta.submission_link, ta.submitted_at, ta.is_late,
                          ta.feedback, ta.points, t.title, t.description, t.due_date, t.max_points, t.kind,
                          c.name as assigned_by
                   from task_assignments ta join tasks t on t.id=ta.task_id left join users c on c.id=t.created_by
                   where ta.student_id=%s and """ + UNLOCKED + """ order by t.due_date, ta.id""", (g.user["id"], today()))
    for r in rows:
        r["display_status"] = _status(r)
    return jsonify(tasks=rows)


@bp.post("/tasks/<int:aid>/submit")
@auth("student")
def submit(aid):
    row = db.one("""select ta.*, t.due_date from task_assignments ta join tasks t on t.id=ta.task_id
                    where ta.id=%s and ta.student_id=%s""", (aid, g.user["id"]))
    if not row:
        bad("Task not found.", 404)
    if row["unlock_date"] and row["unlock_date"] > today():
        bad("This task is not open yet. It unlocks on " + row["unlock_date"].strftime("%d %b") + ".")
    if row["status"] == "incomplete":
        bad("The deadline for this task has passed. Ask your mentor to reopen it.")
    if row["status"] not in ("pending", "rework"):
        bad("This task has already been submitted.")
    body = request.get_json(silent=True) or {}
    note = text(body, "text", 4000)
    link = text(body, "link", 500)
    if not note and not link:
        bad("Add a note or a link to your work before submitting.")
    if link and not link.lower().startswith(("http://", "https://")):
        bad("The link must start with http:// or https://")
    db.run("""update task_assignments set status='submitted', submission_text=%s, submission_link=%s,
              submitted_at=now(), is_late=%s where id=%s""", (note, link, today() > row["due_date"], aid))
    return jsonify(ok=True)


# ======================================================================= test taking
@bp.get("/test")
@auth("student")
def get_test():
    """Get the test assigned to this student (matched by their application's role)."""
    u = g.user
    # Find the application for this student (via user_id link in applications)
    app = db.one("select id, role_applied, pipeline from applications where user_id=%s", (u["id"],))
    if not app:
        return jsonify(available=False, reason="no_application")

    # Check pipeline stage
    if app["pipeline"] not in ("test_sent", "test_taken"):
        return jsonify(available=False, reason="not_ready", pipeline=app["pipeline"])

    # Check if already submitted
    existing = db.one("select id, score, total_marks, percentage, passed, submitted_at from test_submissions where application_id=%s", (app["id"],))
    if existing:
        return jsonify(available=False, already_submitted=True, submission=existing)

    # Get test for this role
    test = db.one("select id, title, duration_mins, passing_score from tests where role_title=%s", (app["role_applied"],))
    if not test:
        return jsonify(available=False, reason="no_test")

    # Get questions (without correct answers!)
    questions = db.q("""select id, question, option_a, option_b, option_c, option_d, marks
                        from test_questions where test_id=%s order by sort_order""", (test["id"],))

    return jsonify(available=True, test=test, questions=questions, application_id=app["id"])


@bp.post("/test")
@auth("student")
def submit_test():
    """Submit test answers and auto-grade."""
    u = g.user
    app = db.one("select id, role_applied, pipeline from applications where user_id=%s", (u["id"],))
    if not app:
        bad("No application found.", 404)
    if app["pipeline"] not in ("test_sent",):
        bad("Test not available or already submitted.")

    # Check not already submitted
    if db.one("select 1 from test_submissions where application_id=%s", (app["id"],)):
        bad("Test already submitted.")

    # Get test + questions with correct answers
    test = db.one("select id, passing_score from tests where role_title=%s", (app["role_applied"],))
    if not test:
        bad("No test configured.", 404)

    questions = db.q("select id, correct, marks from test_questions where test_id=%s", (test["id"],))

    # Grade
    body = request.get_json(silent=True) or {}
    answers = body.get("answers", {})  # {"question_id": "a", ...}

    score = 0
    total_marks = 0
    for q in questions:
        total_marks += q["marks"]
        student_answer = str(answers.get(str(q["id"]), "")).lower().strip()
        if student_answer == q["correct"]:
            score += q["marks"]

    percentage = round((score / total_marks * 100), 2) if total_marks > 0 else 0
    passed = percentage >= test["passing_score"]

    import json
    db.run("""insert into test_submissions (application_id, test_id, answers, score, total_marks, percentage, passed)
              values (%s,%s,%s,%s,%s,%s,%s)""",
           (app["id"], test["id"], json.dumps(answers), score, total_marks, percentage, passed))

    # Update pipeline
    db.run("update applications set pipeline='test_taken', status='test_taken' where id=%s", (app["id"],))

    return jsonify(score=score, total_marks=total_marks, percentage=float(percentage), passed=passed)


# ======================================================================= pipeline status
@bp.get("/pipeline")
@auth("student")
def pipeline_status():
    """Get pipeline status for this student's application."""
    u = g.user
    app = db.one("select id, role_applied, pipeline, status, created_at from applications where user_id=%s", (u["id"],))
    if not app:
        return jsonify(application=None)
    sub = db.one("select score, total_marks, percentage, passed, submitted_at from test_submissions where application_id=%s", (app["id"],))
    iv = db.one("select scheduled_date, scheduled_time, meeting_link, result from interviews where application_id=%s", (app["id"],))
    return jsonify(application=app, test_submission=sub, interview=iv)


@bp.get("/groups")
@auth("student")
def my_groups():
    """Teammates are returned by NAME only. Email and phone are never sent to other students."""
    out = []
    for gr in db.q("""select g.id, g.name, g.kind, g.description, mu.name as mentor_name
                      from student_groups g join group_members m on m.group_id=g.id
                      left join users mu on mu.id=g.mentor_id where m.student_id=%s order by g.id""", (g.user["id"],)):
        gr["members"] = [r["name"] for r in db.q("""select u.name from group_members m join users u on u.id=m.student_id
                                                    where m.group_id=%s order by u.name""", (gr["id"],))]
        out.append(gr)
    return jsonify(groups=out)


@bp.route("/standup", methods=["GET", "POST"])
@auth("student")
def standup():
    uid = g.user["id"]
    if request.method == "POST":
        b = request.get_json(silent=True) or {}
        y, t, bl = text(b, "yesterday", 1500), text(b, "today", 1500), text(b, "blockers", 1500)
        if not y and not t:
            bad("Tell us what you did or what you plan to do today.")
        db.run("""insert into standups (student_id, day, yesterday, today, blockers) values (%s,%s,%s,%s,%s)
                  on conflict (student_id, day) do update set yesterday=excluded.yesterday, today=excluded.today, blockers=excluded.blockers""",
               (uid, today(), y, t, bl))
    rows = db.q("select day, yesterday, today, blockers from standups where student_id=%s order by day desc limit 10", (uid,))
    return jsonify(standups=rows, today=today())
