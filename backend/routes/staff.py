"""Admin + mentor API. Admins see everything; mentors see only their own mentees.
Only admins ever receive students' email addresses and phone numbers."""
import json
import random
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, current_app, g, jsonify, request

import automation
import db
import mailer
import services
import storage
from core import (day_number, ensure_mentor_channel, performance_map, site_settings, temp_password, today)
from security import EMAIL_RE, auth, bad, int_list, pick_date, staff_scope, text, generate_password_hash

bp = Blueprint("staff", __name__, url_prefix="/api/staff")
is_admin = lambda: g.user["role"] == "admin"


def _scoped_student_ids(ids):
    """Keep only the student ids this person may act on."""
    if not ids:
        return []
    sql, args = staff_scope("u")
    rows = db.q("select u.id from users u where u.role='student' and u.is_active and u.id = any(%s)" + sql, (ids,) + args)
    return [r["id"] for r in rows]


# ======================================================================= overview
@bp.get("/overview")
@auth("staff")
def overview():
    sql, args = staff_scope("u")
    students = db.one("select count(*) c from users u where u.role='student' and u.is_active" + sql, args)["c"]
    review = db.one("""select count(*) c from task_assignments ta join users u on u.id=ta.student_id
                       where ta.status='submitted'""" + sql, args)["c"]
    out = {"students": students, "to_review": review}
    if is_admin():
        out["new_applications"] = db.one("select count(*) c from applications where status='new'")["c"]
        out["shortlisted"] = db.one("select count(*) c from applications where status='shortlisted'")["c"]
        out["test_taken"] = db.one("select count(*) c from applications where pipeline='test_taken'")["c"]
        out["interviews_pending"] = db.one("select count(*) c from interviews where result='pending'")["c"]
        out["onboarded"] = db.one("select count(*) c from applications where pipeline='onboarded'")["c"]
        out["mentors"] = db.one("select count(*) c from users where role='mentor' and is_active")["c"]
        out["groups"] = db.one("select count(*) c from student_groups")["c"]
        out["unassigned_students"] = db.one("select count(*) c from users where role='student' and is_active and mentor_id is null")["c"]
    if students:
        perf = performance_map()
        mine = db.q("select u.id from users u where u.role='student' and u.is_active" + sql, args)
        vals = [perf[r["id"]]["performance"] for r in mine if r["id"] in perf and perf[r["id"]]["performance"] is not None]
        out["avg_performance"] = round(sum(vals) / len(vals)) if vals else None
    return jsonify(out)


# ======================================================================= applications (admin)
@bp.get("/applications")
@auth("admin")
def applications():
    status = request.args.get("status")
    search = (request.args.get("q") or "").strip().lower()
    sql, args = "select id,name,email,phone,college,role_applied,status,pipeline,created_at,user_id from applications where true", []
    if status in ("new", "shortlisted", "test_sent", "test_taken", "interview_scheduled", "selected", "onboarded", "rejected"):
        sql += " and status=%s"; args.append(status)
    if search:
        sql += " and (lower(name) like %s or lower(college) like %s or lower(email) like %s)"
        args += [f"%{search}%"] * 3
    counts = {r["status"]: r["c"] for r in db.q("select status, count(*) c from applications group by status")}
    return jsonify(applications=db.q(sql + " order by created_at desc limit 300", args), counts=counts)


@bp.get("/applications/<int:aid>")
@auth("admin")
def application(aid):
    a = db.one("select id,name,email,phone,college,role_applied,message,resume_name,status,pipeline,admin_note,user_id,created_at from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    # Include test submission if exists
    sub = db.one("select score, total_marks, percentage, passed, submitted_at from test_submissions where application_id=%s", (aid,))
    # Include interview if exists
    iv = db.one("select scheduled_date, scheduled_time, meeting_link, result, notes from interviews where application_id=%s", (aid,))
    return jsonify(application=a, test_submission=sub, interview=iv)


@bp.get("/applications/<int:aid>/resume")
@auth("admin")
def resume(aid):
    a = db.one("select resume_path, resume_name from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    data = storage.read_resume(a["resume_path"])
    if data is None:
        bad("Resume file could not be found in storage.", 404)
    ext = a["resume_path"].rsplit(".", 1)[-1]
    mime = {"pdf": "application/pdf", "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[ext]
    return Response(data, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="resume-{aid}.{ext}"'})


@bp.patch("/applications/<int:aid>")
@auth("admin")
def update_application(aid):
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    b = request.get_json(silent=True) or {}
    status = b.get("status", a["status"])
    valid_statuses = ("new", "shortlisted", "test_sent", "test_taken", "interview_scheduled", "selected", "onboarded", "rejected")
    if status not in valid_statuses:
        bad("Invalid status.")
    note = text(b, "admin_note", 2000) if "admin_note" in b else a["admin_note"]
    db.run("update applications set status=%s, admin_note=%s where id=%s", (status, note, aid))
    if status == "shortlisted" and a["status"] != "shortlisted":
        company = site_settings().get("company_name", "our team")
        mailer.send_mail(a["email"], f"You are shortlisted – {company}",
                         f"Hi {a['name']},\n\nGood news: you have been shortlisted for {a['role_applied']} at {company}.\n"
                         f"Our team will contact you shortly with the next steps.\n\n– {company}")
    return jsonify(ok=True)


@bp.post("/applications/<int:aid>/convert")
@auth("admin")
def convert(aid):
    """Final selection click. Free programme: creates the account, assigns mentor + group and starts the daily schedule.
    Paid programme: sends the payment link first; the account is created automatically when the payment is confirmed."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    if a["user_id"]:
        bad("This applicant already has a student account.")
    b = request.get_json(silent=True) or {}
    mentor_id = b.get("mentor_id") or None
    if mentor_id and not db.one("select 1 from users where id=%s and role='mentor' and is_active", (mentor_id,)):
        bad("Choose a valid mentor.")
    start = pick_date(b.get("start_date"), "Start date", required=False)
    if db.one("select 1 from users where lower(email)=%s", (a["email"].lower(),)):
        bad("A user with this email already exists.", 409)
    fee = services.setting_int("enrolment_fee_inr", 0)
    if fee > 0 and not b.get("waive_fee"):
        pay = db.one("select * from payments where application_id=%s and kind='enrolment' and status in ('created','failed') order by id desc limit 1", (aid,))
        if not pay:
            pay = services.create_payment("enrolment", a["name"], a["email"], fee * 100, f"Internship enrolment – {a['role_applied']}", application_id=aid,
                                          meta={"mentor_id": mentor_id, "start_date": start.isoformat() if start else None})
        co = services.company()
        mailer.send_mail(a["email"], f"Congratulations, you are selected – complete your enrolment – {co}",
                         f"Hi {a['name']},\n\nYou are selected for {a['role_applied']} at {co}!\n\nTo confirm your place, pay the enrolment fee of ₹{fee:,}:\n{services.pay_url(pay)}\n\n"
                         f"Your account and your daily schedule are created automatically as soon as the payment is confirmed.\n\n– {co}")
        db.run("update applications set status='selected' where id=%s", (aid,))
        return jsonify(payment_required=True, pay_url=services.pay_url(pay), amount_inr=fee), 202
    if fee > 0:
        services.log_auto("fee_waived", f"Fee waived for {a['name']} by {g.user['name']}", "application", aid)
    r = services.enrol_application(aid, mentor_id, start, how="selected by " + g.user["name"])
    return jsonify(**r)


# ======================================================================= pipeline: tests
@bp.post("/tests")
@auth("admin")
def create_test():
    """Create/update a test for a role with MCQ questions."""
    b = request.get_json(silent=True) or {}
    role_title = text(b, "role_title", 120, True, "Role")
    title = text(b, "title", 200) or "Internship Assessment"
    try:
        duration = int(b.get("duration_mins", 60))
        passing = int(b.get("passing_score", 50))
    except (TypeError, ValueError):
        bad("Duration and passing score must be numbers.")
    questions = b.get("questions", [])
    if not questions:
        bad("Add at least one question.")
    with db.tx() as t:
        # Upsert test
        existing = t.one("select id from tests where role_title=%s", (role_title,))
        if existing:
            tid = existing["id"]
            t.run("update tests set title=%s, duration_mins=%s, passing_score=%s where id=%s", (title, duration, passing, tid))
            t.run("delete from test_questions where test_id=%s", (tid,))
        else:
            tid = t.one("insert into tests (role_title, title, duration_mins, passing_score, created_by) values (%s,%s,%s,%s,%s) returning id",
                        (role_title, title, duration, passing, g.user["id"]))["id"]
        for i, q in enumerate(questions):
            t.run("""insert into test_questions (test_id, question, option_a, option_b, option_c, option_d, correct, marks, sort_order)
                     values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (tid, q["question"], q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                   q["correct"].lower(), q.get("marks", 1), i))
    return jsonify(test_id=tid), 201


@bp.get("/tests")
@auth("admin")
def list_tests():
    rows = db.q("select id, role_title, title, duration_mins, passing_score, created_at from tests order by role_title")
    for r in rows:
        r["question_count"] = db.one("select count(*) c from test_questions where test_id=%s", (r["id"],))["c"]
    return jsonify(tests=rows)


@bp.get("/tests/<int:tid>/questions")
@auth("admin")
def test_questions(tid):
    t = db.one("select * from tests where id=%s", (tid,))
    if not t:
        bad("Test not found.", 404)
    qs = db.q("select id, question, option_a, option_b, option_c, option_d, correct, marks from test_questions where test_id=%s order by sort_order", (tid,))
    return jsonify(test=t, questions=qs)


@bp.post("/applications/<int:aid>/send-test")
@auth("admin")
def send_test(aid):
    """Email the applicant a personal test link. (Applicants have no account yet, so the link is the login.)"""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    if not automation.send_test_invite(a, how="manually"):
        bad(f"No test configured for the role '{a['role_applied']}'. Create a test first.")
    return jsonify(ok=True, message="Test email sent")


# ======================================================================= pipeline: test results
@bp.get("/test-results")
@auth("admin")
def test_results():
    """All test submissions with student names and marks."""
    rows = db.q("""select ts.id, ts.application_id, ts.score, ts.total_marks, ts.percentage, ts.passed, ts.submitted_at,
                          a.name, a.email, a.role_applied, a.pipeline
                   from test_submissions ts join applications a on a.id=ts.application_id
                   order by ts.submitted_at desc""")
    return jsonify(submissions=rows)


# ======================================================================= pipeline: shortlist after test
@bp.post("/applications/<int:aid>/shortlist")
@auth("admin")
def shortlist_after_test(aid):
    """Shortlist a student who has taken the test – sends congratulations email."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    db.run("update applications set pipeline='shortlisted', status='shortlisted' where id=%s", (aid,))
    company = site_settings().get("company_name", "our team")
    mailer.send_mail(a["email"], f"Congratulations! You've been shortlisted – {company}",
                     f"Hi {a['name']},\n\nCongratulations! We are thrilled to inform you that you have been shortlisted "
                     f"for the {a['role_applied']} internship at {company}!\n\n"
                     f"Please choose an interview time that suits you:\n{automation.status_link(aid)}\n\n"
                     f"Prepare for a brief technical + HR discussion.\n\n"
                     f"Best of luck!\n\n– {company}")
    return jsonify(ok=True, message="Student shortlisted and email sent")


# ======================================================================= pipeline: interviews
@bp.post("/applications/<int:aid>/schedule-interview")
@auth("admin")
def schedule_interview(aid):
    """Schedule an interview for a shortlisted student (default: next business day)."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    b = request.get_json(silent=True) or {}
    tomorrow = today() + timedelta(days=1)
    # Skip weekends
    while tomorrow.weekday() >= 5:
        tomorrow += timedelta(days=1)
    sched_date = pick_date(b.get("scheduled_date"), "Interview date", False)
    sched_time = b.get("scheduled_time") or "10:00"
    if b.get("scheduled_at"):                      # the admin screens send one datetime-local value: 2026-11-05T10:30
        stamp = str(b["scheduled_at"])
        sched_date = pick_date(stamp[:10], "Interview date")
        sched_time = stamp[11:16] or "10:00"
    sched_date = sched_date or tomorrow
    link = text(b, "meeting_link", 500)
    notes = text(b, "notes", 2000)
    # Upsert interview
    existing = db.one("select id from interviews where application_id=%s", (aid,))
    if existing:
        db.run("update interviews set scheduled_date=%s, scheduled_time=%s, meeting_link=%s, notes=%s, result='pending' where id=%s",
               (sched_date, sched_time, link, notes, existing["id"]))
    else:
        db.run("""insert into interviews (application_id, scheduled_date, scheduled_time, meeting_link, notes)
                  values (%s,%s,%s,%s,%s)""", (aid, sched_date, sched_time, link, notes))
    db.run("update applications set pipeline='interview_scheduled', status='interview_scheduled' where id=%s", (aid,))
    company = site_settings().get("company_name", "our team")
    mailer.send_mail(a["email"], f"Your interview is scheduled – {company}",
                     f"Hi {a['name']},\n\nYour interview for {a['role_applied']} at {company} has been scheduled!\n\n"
                     f"Date: {sched_date}\nTime: {sched_time}\n"
                     + (f"Meeting Link: {link}\n" if link else "") +
                     f"\nPlease be on time and prepared. Good luck!\n\n– {company}")
    return jsonify(ok=True, message="Interview scheduled and email sent")


@bp.get("/interviews")
@auth("admin")
def list_interviews():
    rows = db.q("""select i.id, i.application_id, i.scheduled_date, i.scheduled_time, i.meeting_link, i.result, i.notes,
                          a.name, a.email, a.role_applied, a.pipeline
                   from interviews i join applications a on a.id=i.application_id
                   order by i.scheduled_date desc""")
    return jsonify(interviews=rows)


@bp.post("/applications/<int:aid>/interview-result")
@auth("admin")
def interview_result(aid):
    """Post interview result: 'passed' (onboard) or 'failed' (reject)."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    iv = db.one("select * from interviews where application_id=%s", (aid,))
    if not iv:
        bad("No interview found for this application.", 404)
    b = request.get_json(silent=True) or {}
    result = b.get("result")
    if result not in ("passed", "failed"):
        bad("Result must be 'passed' or 'failed'.")
    notes = text(b, "notes", 2000)
    db.run("update interviews set result=%s, notes=%s where id=%s", (result, notes, iv["id"]))
    company = site_settings().get("company_name", "our team")
    if result == "passed":
        db.run("update applications set pipeline='onboarded', status='onboarded' where id=%s", (aid,))
        mailer.send_mail(a["email"], f"Welcome aboard! Your internship starts now – {company}",
                         f"Hi {a['name']},\n\nCongratulations on passing the interview! You've been officially "
                         f"onboarded for the {a['role_applied']} internship at {company}!\n\n"
                         f"Your 3-Month Plan:\n- Month 1: Training & Learning\n- Month 2-3: Real Project Work\n\n"
                         f"Check your dashboard for your task assignments. Let's build something amazing!\n\n– {company}")
    else:
        db.run("update applications set pipeline='rejected', status='rejected' where id=%s", (aid,))
        mailer.send_mail(a["email"], f"Update on your application – {company}",
                         f"Hi {a['name']},\n\nThank you for taking the time to interview with us for the {a['role_applied']} role at {company}.\n\n"
                         f"After careful consideration, we've decided not to move forward at this time. "
                         f"We encourage you to apply again in the future.\n\nBest wishes,\n– {company}")
    return jsonify(ok=True, pipeline="onboarded" if result == "passed" else "rejected")


# ======================================================================= pipeline: generate 3-month tasks
@bp.post("/applications/<int:aid>/generate-tasks")
@auth("admin")
def generate_tasks(aid):
    """Auto-generate a 3-month internship task plan: 1 month training + 2 months project."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    if not a["user_id"]:
        bad("This applicant doesn't have a student account yet. Select them first.")
    sid = a["user_id"]
    start = today()
    with db.tx() as t:
        # Month 1: Training (4 weeks)
        training = [
            ("Week 1: Onboarding & Environment Setup",
             "Set up development environment, read documentation, understand team workflow and tools."),
            ("Week 2: Fundamentals & Best Practices",
             "Study core technologies, complete tutorials, and learn coding standards used by the team."),
            ("Week 3: Guided Practice Project",
             "Build a small guided practice project to apply learned concepts under mentorship."),
            ("Week 4: Training Assessment",
             "Complete the training assessment, present learnings, and prepare for real project work."),
        ]
        for i, (title, desc) in enumerate(training):
            due = start + timedelta(weeks=i + 1)
            tid = t.one("insert into tasks (title, description, due_date, max_points, kind, created_by, source) values (%s,%s,%s,10,'training',%s,'plan') returning id",
                        (title, desc, due, g.user["id"]))["id"]
            t.run("insert into task_assignments (task_id, student_id) values (%s,%s)", (tid, sid))
        # Month 2-3: Project (8 weeks)
        project = [
            ("Week 5: Project Kickoff & Planning",
             "Understand project requirements, set up repository, create initial architecture plan."),
            ("Week 6: Core Feature Development – Phase 1",
             "Implement the first set of core features with proper testing."),
            ("Week 7: Core Feature Development – Phase 2",
             "Continue feature development, code review sessions, iterate based on feedback."),
            ("Week 8: Integration & Testing",
             "Integrate modules, write integration tests, fix bugs from QA feedback."),
            ("Week 9: Advanced Features & Optimization",
             "Implement advanced features, performance optimization, security review."),
            ("Week 10: User Testing & Feedback",
             "Conduct user testing, gather feedback, implement high-priority changes."),
            ("Week 11: Final Polish & Documentation",
             "Final bug fixes, code documentation, deployment preparation."),
            ("Week 12: Project Presentation & Review",
             "Final project presentation, code handoff, performance review and feedback."),
        ]
        for i, (title, desc) in enumerate(project):
            due = start + timedelta(weeks=i + 5)
            tid = t.one("insert into tasks (title, description, due_date, max_points, kind, created_by, source) values (%s,%s,%s,10,'project',%s,'plan') returning id",
                        (title, desc, due, g.user["id"]))["id"]
            t.run("insert into task_assignments (task_id, student_id) values (%s,%s)", (tid, sid))
    return jsonify(ok=True, message="12-week task plan generated"), 201


# ======================================================================= students
def _student_rows(extra_sql="", extra_args=()):
    sql, args = staff_scope("u")
    cols = "u.id, u.name, u.college, u.phase, u.start_date, u.training_days, u.outcome, u.is_active, u.mentor_id, mu.name as mentor_name"
    if is_admin():
        cols += ", u.email, u.phone"
    rows = db.q(f"""select {cols} from users u left join users mu on mu.id=u.mentor_id
                    where u.role='student' {sql} {extra_sql} order by u.is_active desc, u.name""", args + tuple(extra_args))
    perf = performance_map([r["id"] for r in rows]) if rows else {}
    for r in rows:
        p = perf.get(r["id"], {})
        r.update(day=day_number(r), performance=p.get("performance"), tasks_total=p.get("total", 0),
                 tasks_done=p.get("approved", 0), tasks_overdue=p.get("overdue", 0))
    return rows


@bp.get("/students")
@auth("staff")
def students():
    return jsonify(students=_student_rows())


@bp.post("/students")
@auth("admin")
def create_student():
    b = request.get_json(silent=True) or {}
    name = text(b, "name", 120, True, "Name")
    email = text(b, "email", 160, True, "Email").lower()
    if not EMAIL_RE.match(email):
        bad("Enter a valid email address.")
    if db.one("select 1 from users where lower(email)=%s", (email,)):
        bad("A user with this email already exists.", 409)
    mentor_id = b.get("mentor_id") or None
    if mentor_id and not db.one("select 1 from users where id=%s and role='mentor'", (mentor_id,)):
        bad("Choose a valid mentor.")
    pw = temp_password()
    u = db.one("""insert into users (name,email,phone,password_hash,role,college,mentor_id,start_date,must_change_password)
                  values (%s,%s,%s,%s,'student',%s,%s,%s,true) returning id""",
               (name, email, text(b, "phone", 20), generate_password_hash(pw), text(b, "college", 200), mentor_id,
                pick_date(b.get("start_date"), "Start date", False) or today()))
    return jsonify(student_id=u["id"], temp_password=pw), 201


@bp.patch("/students/<int:sid>")
@auth("admin")
def update_student(sid):
    s = db.one("select * from users where id=%s and role='student'", (sid,))
    if not s:
        bad("Student not found.", 404)
    b = request.get_json(silent=True) or {}
    f = {}
    if "mentor_id" in b:
        m = b["mentor_id"] or None
        if m and not db.one("select 1 from users where id=%s and role='mentor' and is_active", (m,)):
            bad("Choose a valid mentor.")
        f["mentor_id"] = m
    if "phase" in b:
        if b["phase"] not in ("training", "project"):
            bad("Invalid phase.")
        f["phase"] = b["phase"]
    if "outcome" in b:
        if b["outcome"] not in ("in_progress", "offered", "not_offered"):
            bad("Invalid outcome.")
        f["outcome"] = b["outcome"]
    if "start_date" in b:
        f["start_date"] = pick_date(b["start_date"], "Start date", False)
    if "is_active" in b:
        f["is_active"] = bool(b["is_active"])
    if "training_days" in b:
        try:
            f["training_days"] = max(1, min(120, int(b["training_days"])))
        except (TypeError, ValueError):
            bad("Training days must be a number.")
    if not f:
        bad("Nothing to update.")
    db.run("update users set " + ", ".join(f"{k}=%s" for k in f) + " where id=%s", tuple(f.values()) + (sid,))
    if f.get("mentor_id"):
        ensure_mentor_channel(sid)
    return jsonify(ok=True)


@bp.post("/students/<int:sid>/reset-password")
@auth("admin")
def reset_password(sid):
    if not db.one("select 1 from users where id=%s and role in ('student','mentor')", (sid,)):
        bad("User not found.", 404)
    pw = temp_password()
    db.run("update users set password_hash=%s, must_change_password=true where id=%s", (generate_password_hash(pw), sid))
    return jsonify(temp_password=pw)


@bp.get("/students/<int:sid>")
@auth("staff")
def student_detail(sid):
    rows = [r for r in _student_rows("and u.id=%s", (sid,))]
    if not rows:
        bad("Student not found.", 404)
    tasks = db.q("""select ta.id, ta.status, ta.points, ta.is_late, t.title, t.due_date, t.max_points
                    from task_assignments ta join tasks t on t.id=ta.task_id where ta.student_id=%s order by t.due_date desc""", (sid,))
    stands = db.q("select day, yesterday, today, blockers from standups where student_id=%s order by day desc limit 7", (sid,))
    groups = db.q("select g.id, g.name from student_groups g join group_members m on m.group_id=g.id where m.student_id=%s", (sid,))
    return jsonify(student=rows[0], tasks=tasks, standups=stands, groups=groups)


# ======================================================================= mentors (admin)
@bp.get("/mentors")
@auth("admin")
def mentors():
    rows = db.q("""select m.id, m.name, m.email, m.phone, m.is_active, count(s.id) as mentees
                   from users m left join users s on s.mentor_id=m.id and s.role='student'
                   where m.role='mentor' group by m.id order by m.is_active desc, m.name""")
    return jsonify(mentors=rows)


@bp.post("/mentors")
@auth("admin")
def create_mentor():
    b = request.get_json(silent=True) or {}
    name = text(b, "name", 120, True, "Name")
    email = text(b, "email", 160, True, "Email").lower()
    if not EMAIL_RE.match(email):
        bad("Enter a valid email address.")
    if db.one("select 1 from users where lower(email)=%s", (email,)):
        bad("A user with this email already exists.", 409)
    pw = temp_password()
    u = db.one("""insert into users (name,email,phone,password_hash,role,must_change_password)
                  values (%s,%s,%s,%s,'mentor',true) returning id""",
               (name, email, text(b, "phone", 20), generate_password_hash(pw)))
    return jsonify(mentor_id=u["id"], temp_password=pw), 201


# ======================================================================= tasks
@bp.get("/tasks")
@auth("staff")
def tasks():
    sql, args = staff_scope("u")
    rows = db.q(f"""select t.id, t.title, t.due_date, t.max_points, t.kind, c.name as created_by_name,
                      count(ta.id) as assigned,
                      count(*) filter (where ta.status='submitted') as submitted,
                      count(*) filter (where ta.status='approved') as approved
                    from tasks t join task_assignments ta on ta.task_id=t.id join users u on u.id=ta.student_id
                    left join users c on c.id=t.created_by where true {"" if request.args.get("auto") == "1" else "and t.source <> 'template'"} {sql}
                    group by t.id, c.name order by t.due_date desc, t.id desc limit 200""", args)
    return jsonify(tasks=rows)


@bp.post("/tasks")
@auth("staff")
def create_task():
    b = request.get_json(silent=True) or {}
    title = text(b, "title", 200, True, "Title")
    desc = text(b, "description", 4000)
    due = pick_date(b.get("due_date"), "Due date")
    kind = b.get("kind", "training")
    if kind not in ("training", "project"):
        bad("Invalid task type.")
    try:
        points = int(b.get("max_points", 10))
    except (TypeError, ValueError):
        bad("Points must be a number.")
    if not 1 <= points <= 1000:
        bad("Points must be between 1 and 1000.")
    target = b.get("target") or {}
    ttype = target.get("type")
    sql, args = staff_scope("u")
    if ttype == "all":
        ids = [r["id"] for r in db.q("select u.id from users u where u.role='student' and u.is_active" + sql, args)]
    elif ttype == "group":
        gid = target.get("group_id")
        ids = [r["id"] for r in db.q("""select u.id from group_members m join users u on u.id=m.student_id
                                        where m.group_id=%s and u.is_active""" + sql, (gid,) + args)]
    elif ttype == "students":
        ids = _scoped_student_ids(int_list(target.get("student_ids")))
    else:
        bad("Choose who this task is for.")
    if not ids:
        bad("No students matched. Check the group or your mentees and try again.")
    with db.tx() as t:
        task = t.one("insert into tasks (title,description,due_date,max_points,kind,created_by) values (%s,%s,%s,%s,%s,%s) returning id",
                     (title, desc, due, points, kind, g.user["id"]))
        t.run("insert into task_assignments (task_id, student_id) select %s, unnest(%s::bigint[])", (task["id"], ids))
    return jsonify(task_id=task["id"], assigned=len(ids)), 201


@bp.get("/tasks/<int:tid>")
@auth("staff")
def task_detail(tid):
    sql, args = staff_scope("u")
    t = db.one("select id,title,description,due_date,max_points,kind,created_by from tasks where id=%s", (tid,))
    if not t:
        bad("Task not found.", 404)
    subs = db.q(f"""select ta.id, ta.status, ta.submission_text, ta.submission_link, ta.submitted_at, ta.is_late,
                           ta.feedback, ta.points, u.name as student_name
                    from task_assignments ta join users u on u.id=ta.student_id
                    where ta.task_id=%s {sql} order by u.name""", (tid,) + args)
    if not subs:
        bad("Task not found.", 404)
    return jsonify(task=t, assignments=subs)


@bp.delete("/tasks/<int:tid>")
@auth("staff")
def delete_task(tid):
    t = db.one("select created_by from tasks where id=%s", (tid,))
    if not t:
        bad("Task not found.", 404)
    if not is_admin() and t["created_by"] != g.user["id"]:
        bad("Only the person who created a task can delete it.", 403)
    db.run("delete from tasks where id=%s", (tid,))
    return jsonify(ok=True)


@bp.get("/submissions")
@auth("staff")
def submissions():
    sql, args = staff_scope("u")
    rows = db.q(f"""select ta.id, ta.submission_text, ta.submission_link, ta.submitted_at, ta.is_late, ta.status, ta.ai_draft, t.rubric,
                           t.title, t.max_points, t.due_date, u.name as student_name
                    from task_assignments ta join tasks t on t.id=ta.task_id join users u on u.id=ta.student_id
                    where ta.status='submitted' {sql} order by ta.submitted_at""", args)
    return jsonify(submissions=rows)


@bp.patch("/assignments/<int:aid>")
@auth("staff")
def review(aid):
    sql, args = staff_scope("u")
    row = db.one(f"""select ta.id, ta.status, t.max_points from task_assignments ta join tasks t on t.id=ta.task_id
                     join users u on u.id=ta.student_id where ta.id=%s {sql}""", (aid,) + args)
    if not row:
        bad("Submission not found.", 404)
    b = request.get_json(silent=True) or {}
    action = b.get("action")
    if action == "reopen":
        if row["status"] != "incomplete":
            bad("Only a task marked incomplete can be reopened.")
        db.run("update task_assignments set status='pending' where id=%s", (aid,))
        db.run("update tasks set due_date = %s, grace_days = 0 where id = (select task_id from task_assignments where id=%s) and source='template'",
               (today() + timedelta(days=1), aid))
        return jsonify(ok=True)
    if row["status"] not in ("submitted", "approved", "rework"):
        bad("The student has not submitted this task yet.")
    feedback = text(b, "feedback", 2000)
    if action == "approve":
        try:
            pts = int(b.get("points"))
        except (TypeError, ValueError):
            bad("Enter the points to award.")
        if not 0 <= pts <= row["max_points"]:
            bad(f"Points must be between 0 and {row['max_points']}.")
        db.run("update task_assignments set status='approved', points=%s, feedback=%s, reviewed_at=now(), reviewed_by=%s where id=%s",
               (pts, feedback, g.user["id"], aid))
    elif action == "rework":
        if not feedback:
            bad("Tell the student what to change.")
        db.run("update task_assignments set status='rework', points=null, feedback=%s, reviewed_at=now(), reviewed_by=%s where id=%s",
               (feedback, g.user["id"], aid))
    else:
        bad("Invalid action.")
    return jsonify(ok=True)


# ======================================================================= groups (names only for students; admin manages)
def _groups_with_members(where="true", args=()):
    rows = db.q(f"""select g.id, g.name, g.kind, g.description, g.mentor_id, mu.name as mentor_name
                    from student_groups g left join users mu on mu.id=g.mentor_id where {where} order by g.kind, g.name""", args)
    for r in rows:
        r["members"] = db.q("""select u.id, u.name from group_members m join users u on u.id=m.student_id
                               where m.group_id=%s order by u.name""", (r["id"],))
    return rows


@bp.get("/groups")
@auth("staff")
def groups():
    if is_admin():
        return jsonify(groups=_groups_with_members())
    return jsonify(groups=_groups_with_members("g.mentor_id=%s", (g.user["id"],)))


def _save_group(t, gid, b):
    name = text(b, "name", 80, True, "Group name")
    kind = b.get("kind", "training")
    if kind not in ("training", "project"):
        bad("Invalid group type.")
    mentor = b.get("mentor_id") or None
    if mentor and not t.one("select 1 from users where id=%s and role='mentor'", (mentor,)):
        bad("Choose a valid mentor.")
    ids = int_list(b.get("student_ids"))
    if ids:
        ok = {r["id"] for r in t.q("select id from users where role='student' and id = any(%s)", (ids,))}
        if ok != set(ids):
            bad("One or more students were not found.")
    desc = text(b, "description", 1000)
    if gid is None:
        gid = t.one("insert into student_groups (name,kind,description,mentor_id) values (%s,%s,%s,%s) returning id",
                    (name, kind, desc, mentor))["id"]
        t.run("insert into channels (kind,name,group_id) values ('group',%s,%s)", (name, gid))
    else:
        t.run("update student_groups set name=%s, kind=%s, description=%s, mentor_id=%s where id=%s", (name, kind, desc, mentor, gid))
        t.run("update channels set name=%s where group_id=%s", (name, gid))
        t.run("delete from group_members where group_id=%s", (gid,))
    if ids:
        t.run("insert into group_members (group_id, student_id) select %s, unnest(%s::bigint[])", (gid, ids))
    return gid


@bp.post("/groups")
@auth("admin")
def create_group():
    with db.tx() as t:
        gid = _save_group(t, None, request.get_json(silent=True) or {})
    return jsonify(group_id=gid), 201


@bp.put("/groups/<int:gid>")
@auth("admin")
def update_group(gid):
    if not db.one("select 1 from student_groups where id=%s", (gid,)):
        bad("Group not found.", 404)
    with db.tx() as t:
        _save_group(t, gid, request.get_json(silent=True) or {})
    return jsonify(ok=True)


@bp.delete("/groups/<int:gid>")
@auth("admin")
def delete_group(gid):
    db.run("delete from student_groups where id=%s", (gid,))
    return jsonify(ok=True)


@bp.post("/groups/generate")
@auth("admin")
def generate_groups():
    """Proposes balanced random groups (nothing is saved). The admin reviews, edits, then saves them."""
    b = request.get_json(silent=True) or {}
    try:
        size = int(b.get("size", 4))
    except (TypeError, ValueError):
        bad("Group size must be a number.")
    if not 2 <= size <= 20:
        bad("Group size must be between 2 and 20.")
    kind = b.get("kind", "training")
    if kind not in ("training", "project"):
        bad("Invalid group type.")
    prefix = text(b, "prefix", 40) or ("Team" if kind == "project" else "Batch")
    only_free = bool(b.get("only_ungrouped", True))
    phase = b.get("phase")
    sql = "select u.id, u.name, u.mentor_id from users u where u.role='student' and u.is_active"
    args = []
    if phase in ("training", "project"):
        sql += " and u.phase=%s"; args.append(phase)
    if only_free:
        sql += " and not exists (select 1 from group_members m join student_groups g on g.id=m.group_id where m.student_id=u.id and g.kind=%s)"
        args.append(kind)
    pool = db.q(sql, args)
    if len(pool) < 2:
        bad("Not enough students to form groups with these filters.")
    random.shuffle(pool)
    n = max(1, round(len(pool) / size))
    buckets = [[] for _ in range(n)]
    for i, s in enumerate(pool):
        buckets[i % n].append(s)
    mentors_list = [m["id"] for m in db.q("select id from users where role='mentor' and is_active order by id")] if b.get("assign_mentors") else []
    out = []
    for i, members in enumerate(buckets, 1):
        out.append({"name": f"{prefix} {i}", "kind": kind, "mentor_id": mentors_list[(i - 1) % len(mentors_list)] if mentors_list else None,
                    "members": [{"id": m["id"], "name": m["name"]} for m in sorted(members, key=lambda m: m["name"])]})
    return jsonify(groups=out)


@bp.post("/groups/bulk")
@auth("admin")
def bulk_groups():
    groups_in = (request.get_json(silent=True) or {}).get("groups") or []
    if not groups_in or len(groups_in) > 100:
        bad("Nothing to save.")
    with db.tx() as t:
        for gr in groups_in:
            _save_group(t, None, {**gr, "student_ids": [m["id"] for m in gr.get("members", [])]})
    return jsonify(saved=len(groups_in)), 201


# ======================================================================= schedule
@bp.get("/events")
@auth("staff")
def events():
    u = g.user
    if u["role"] == "admin":
        where, args = "true", ()
    else:
        where, args = "e.created_by=%s", (u["id"],)
    rows = db.q(f"""select e.id, e.title, e.kind, e.category, e.starts_at, e.recurrence, e.recur_until, e.link,
                           e.group_id, e.student_id, gr.name as group_name, s.name as student_name
                    from events e left join student_groups gr on gr.id=e.group_id left join users s on s.id=e.student_id
                    where {where} and (e.recurrence <> 'none' or e.starts_at >= now() - interval '1 day')
                    order by e.starts_at limit 200""", args)
    return jsonify(events=rows)


@bp.post("/events")
@auth("staff")
def create_event():
    b = request.get_json(silent=True) or {}
    title = text(b, "title", 200, True, "Title")
    kind = b.get("kind", "class")
    if kind not in ("class", "standup", "mock_interview", "workshop", "meeting", "other"):
        bad("Invalid event type.")
    try:
        starts = datetime.fromisoformat(str(b.get("starts_at")).replace("Z", "+00:00"))
        ends = datetime.fromisoformat(str(b["ends_at"]).replace("Z", "+00:00")) if b.get("ends_at") else None
    except ValueError:
        bad("Enter a valid start time.")
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=current_app.config["TZ"])
    if ends and ends.tzinfo is None:
        ends = ends.replace(tzinfo=current_app.config["TZ"])
    if ends and ends <= starts:
        bad("The end time must be after the start time.")
    rec = b.get("recurrence", "none")
    if rec not in ("none", "weekdays", "weekly"):
        bad("Invalid repeat option.")
    until = pick_date(b.get("recur_until"), "Repeat until", False)
    link = text(b, "link", 500)
    if link and not link.lower().startswith(("http://", "https://")):
        bad("The meeting link must start with http:// or https://")
    aud = b.get("audience") or {}
    gid = sid = None
    if aud.get("type") == "group":
        gid = aud.get("group_id")
        ok = db.one("select 1 from student_groups where id=%s" + ("" if is_admin() else " and mentor_id=%s"),
                    (gid,) if is_admin() else (gid, g.user["id"]))
        if not ok:
            bad("Choose one of your groups.")
    elif aud.get("type") == "student":
        sid = aud.get("student_id")
        if not _scoped_student_ids([int(sid)] if str(sid).isdigit() else []):
            bad("Choose one of your students.")
    elif not is_admin():
        bad("Mentors can schedule for a group or a single student. Ask an admin to schedule for everyone.")
    row = db.one("""insert into events (title,kind,category,description,link,starts_at,ends_at,recurrence,recur_until,group_id,student_id,created_by)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                 (title, kind, text(b, "category", 60), text(b, "description", 2000), link, starts, ends, rec, until, gid, sid, g.user["id"]))
    return jsonify(event_id=row["id"]), 201


@bp.delete("/events/<int:eid>")
@auth("staff")
def delete_event(eid):
    ev = db.one("select created_by from events where id=%s", (eid,))
    if not ev:
        bad("Event not found.", 404)
    if not is_admin() and ev["created_by"] != g.user["id"]:
        bad("You can only delete events you created.", 403)
    db.run("delete from events where id=%s", (eid,))
    return jsonify(ok=True)


# ======================================================================= announcements, standups, settings
@bp.post("/announcements")
@auth("admin")
def post_announcement():
    b = request.get_json(silent=True) or {}
    row = db.one("insert into announcements (title, body, created_by) values (%s,%s,%s) returning id",
                 (text(b, "title", 160, True, "Title"), text(b, "body", 3000), g.user["id"]))
    return jsonify(id=row["id"]), 201


@bp.delete("/announcements/<int:aid>")
@auth("admin")
def delete_announcement(aid):
    db.run("delete from announcements where id=%s", (aid,))
    return jsonify(ok=True)


@bp.get("/standups")
@auth("staff")
def standups():
    day = pick_date(request.args.get("day"), "Day", False) or today()
    sql, args = staff_scope("u")
    rows = db.q(f"""select u.id as student_id, u.name, s.yesterday, s.today, s.blockers, (s.id is not null) as posted
                    from users u left join standups s on s.student_id=u.id and s.day=%s
                    where u.role='student' and u.is_active {sql} order by posted desc, u.name""", (day,) + args)
    return jsonify(day=day, standups=rows)


SETTING_KEYS = ("company_name", "tagline", "contact_email")


@bp.get("/settings")
@auth("admin")
def get_settings():
    s = site_settings()
    return jsonify(settings={k: s.get(k, "") for k in SETTING_KEYS},
                   roles=db.q("select id, title, active from open_roles order by title"))


@bp.put("/settings")
@auth("admin")
def put_settings():
    b = request.get_json(silent=True) or {}
    for k in SETTING_KEYS:
        if k in b:
            v = text(b, k, 300, k == "company_name", k.replace("_", " ").capitalize())
            db.run("insert into settings (key,value) values (%s,%s) on conflict (key) do update set value=excluded.value", (k, v))
    return jsonify(ok=True)


@bp.post("/roles")
@auth("admin")
def add_role():
    title = text(request.get_json(silent=True) or {}, "title", 80, True, "Role name")
    db.run("insert into open_roles (title) values (%s) on conflict (title) do update set active=true", (title,))
    return jsonify(ok=True), 201


@bp.patch("/roles/<int:rid>")
@auth("admin")
def toggle_role(rid):
    b = request.get_json(silent=True) or {}
    db.run("update open_roles set active=%s where id=%s", (bool(b.get("active")), rid))
    return jsonify(ok=True)
