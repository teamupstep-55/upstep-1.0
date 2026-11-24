"""Applicant portal. Applicants have no account yet, so each application has a private link (/status/<token>):
take the test, see the result stage, pick an interview slot, pay the enrolment fee."""
import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, current_app, jsonify, request

import automation
import db
import mailer
import services
from core import today
from security import allow, bad, client_ip

bp = Blueprint("applicant", __name__, url_prefix="/api/applicant")


def _app(token):
    if not allow(f"applicant:{client_ip()}", 200, 3600):
        bad("Too many requests.", 429)
    a = db.one("select * from applications where access_token=%s", (token or "-",))
    if not a:
        bad("This link is not valid. Please use the link from your email.", 404)
    return a


def _test_for(a):
    return db.one("select id, title, duration_mins, passing_score from tests where role_title=%s", (a["role_applied"],))


@bp.get("/<token>")
def status(token):
    a = _app(token)
    test = _test_for(a)
    sub = db.one("select score, total_marks, percentage, passed, submitted_at from test_submissions where application_id=%s", (a["id"],))
    iv = db.one("""select i.scheduled_date, i.scheduled_time, i.meeting_link, i.result, s.starts_at, s.duration_mins from interviews i
                   left join interview_slots s on s.id=i.slot_id where i.application_id=%s""", (a["id"],))
    slots = []
    if a["pipeline"] in ("shortlisted", "interview_scheduled") and (not iv or iv["result"] == "pending"):
        slots = db.q("""select id, starts_at, duration_mins from interview_slots where application_id is null and starts_at > now() + interval '2 hours'
                        order by starts_at limit 60""")
    pay = db.one("select token, amount_paise, status, description from payments where application_id=%s and kind='enrolment' order by id desc limit 1", (a["id"],))
    return jsonify(
        application={"name": a["name"], "role_applied": a["role_applied"], "pipeline": a["pipeline"], "status": a["status"], "created_at": a["created_at"]},
        test={"available": bool(test) and a["pipeline"] == "test_sent" and not sub, "duration_mins": test["duration_mins"] if test else None,
              "passing_score": test["passing_score"] if test else None, "started": bool(a["test_started_at"])},
        test_result=({"percentage": float(sub["percentage"]), "passed": sub["passed"]} if sub else None),
        interview=iv, slots=slots,
        payment=({"token": pay["token"], "amount_inr": pay["amount_paise"] / 100, "status": pay["status"], "description": pay["description"]} if pay else None),
        account_created=bool(a["user_id"]), tz=str(current_app.config["TZ"]))


# ------------------------------------------------------------------ the test
def _grade(a, test, answers, on_time=True):
    questions = db.q("select id, correct, marks from test_questions where test_id=%s", (test["id"],))
    score = total = 0
    for q in questions:
        total += q["marks"]
        if on_time and str(answers.get(str(q["id"]), "")).lower().strip() == q["correct"]:
            score += q["marks"]
    pct = round(score / total * 100, 2) if total else 0
    passed = pct >= test["passing_score"]
    with db.tx() as t:
        ok = t.one("""insert into test_submissions (application_id,test_id,answers,score,total_marks,percentage,passed) values (%s,%s,%s,%s,%s,%s,%s)
                      on conflict (application_id) do nothing returning id""", (a["id"], test["id"], json.dumps(answers if on_time else {}), score, total, pct, passed))
        if not ok:
            bad("You have already submitted this test.", 409)
        t.run("update applications set pipeline='test_taken', status='test_taken' where id=%s", (a["id"],))
    outcome = automation.decide_after_test(a["id"])
    return {"score": score, "total_marks": total, "percentage": float(pct), "passed": passed, "outcome": outcome}


def _deadline(a, test):
    return a["test_started_at"] + timedelta(minutes=test["duration_mins"])


@bp.get("/<token>/test")
def get_test(token):
    a = _app(token)
    test = _test_for(a)
    if not test or a["pipeline"] != "test_sent":
        bad("There is no test open for this application.", 409)
    if db.one("select 1 from test_submissions where application_id=%s", (a["id"],)):
        bad("You have already submitted this test.", 409)
    db.run("update applications set test_started_at=coalesce(test_started_at, now()) where id=%s", (a["id"],))
    a = db.one("select * from applications where id=%s", (a["id"],))
    now = datetime.now(timezone.utc)
    if now > _deadline(a, test) + timedelta(minutes=2):
        # the timer ran out while the page was closed: record it as a zero so the applicant is not stuck
        r = _grade(a, test, {}, on_time=False)
        return jsonify(expired=True, result=r)
    qs = db.q("select id, question, option_a, option_b, option_c, option_d, marks from test_questions where test_id=%s order by sort_order, id", (test["id"],))
    return jsonify(test={"title": test["title"], "duration_mins": test["duration_mins"], "passing_score": test["passing_score"]}, questions=qs,
                   seconds_left=max(0, int((_deadline(a, test) - now).total_seconds())))


@bp.post("/<token>/test")
def submit_test(token):
    a = _app(token)
    test = _test_for(a)
    if not test or a["pipeline"] != "test_sent" or not a["test_started_at"]:
        bad("There is no open test for this link.", 409)
    answers = (request.get_json(silent=True) or {}).get("answers")
    if not isinstance(answers, dict):
        answers = {}
    on_time = datetime.now(timezone.utc) <= _deadline(a, test) + timedelta(minutes=2)
    r = _grade(a, test, answers, on_time)
    r["late"] = not on_time
    return jsonify(r)


# ------------------------------------------------------------------ interview slot
@bp.post("/<token>/book")
def book(token):
    a = _app(token)
    if a["pipeline"] not in ("shortlisted", "interview_scheduled"):
        bad("Interview booking is not open for this application.", 409)
    try:
        sid = int((request.get_json(silent=True) or {}).get("slot_id"))
    except (TypeError, ValueError):
        bad("Choose a time slot.")
    tz = current_app.config["TZ"]
    with db.tx() as t:
        old = t.one("select * from interview_slots where application_id=%s", (a["id"],))
        if old:
            if old["starts_at"] < datetime.now(timezone.utc) + timedelta(hours=24):
                bad("It is too late to change your slot online. Please contact us.", 409)
            t.run("update interview_slots set application_id=null where id=%s", (old["id"],))
        slot = t.one("""update interview_slots set application_id=%s where id=%s and application_id is null
                        and starts_at > now() + interval '2 hours' returning *""", (a["id"], sid))
        if not slot:
            bad("That time was just taken or is no longer available. Please choose another.", 409)
        local = slot["starts_at"].astimezone(tz)
        t.run("""insert into interviews (application_id, scheduled_date, scheduled_time, meeting_link, slot_id, result)
                 values (%s,%s,%s,%s,%s,'pending')
                 on conflict (application_id) do update set scheduled_date=excluded.scheduled_date, scheduled_time=excluded.scheduled_time,
                    meeting_link=excluded.meeting_link, slot_id=excluded.slot_id, result='pending'""",
              (a["id"], local.date(), local.time().replace(second=0, microsecond=0), slot["meeting_link"], slot["id"]))
        t.run("update applications set pipeline='interview_scheduled', status='interview_scheduled' where id=%s", (a["id"],))
        t.run("delete from events where kind='meeting' and description=%s", (f"application:{a['id']}",))
        t.run("""insert into events (title, kind, description, link, starts_at, ends_at, created_by) values (%s,'meeting',%s,%s,%s,%s,%s)""",
              (f"Interview: {a['name']} ({a['role_applied']})", f"application:{a['id']}", slot["meeting_link"], slot["starts_at"],
               slot["starts_at"] + timedelta(minutes=slot["duration_mins"]), slot["mentor_id"]))
    co = services.company()
    ics = automation.ics_for(f"Interview – {co}", slot["starts_at"], slot["duration_mins"], slot["meeting_link"] or "", f"iv{a['id']}")
    mailer.send_mail(a["email"], f"Interview confirmed – {co}",
                     f"Hi {a['name']},\n\nYour interview for {a['role_applied']} is booked for {local:%A %d %b %Y at %I:%M %p} ({tz}).\n"
                     + (f"Join: {slot['meeting_link']}\n" if slot["meeting_link"] else "") + f"You will get reminders 24 hours and 1 hour before.\n\n– {co}",
                     attachments=[("interview.ics", "text/calendar", ics)])
    services.log_auto("interview_booked", f"{a['name']} booked {local:%d %b %H:%M}", "application", a["id"])
    return jsonify(ok=True, starts_at=slot["starts_at"], meeting_link=slot["meeting_link"])


@bp.get("/<token>/calendar.ics")
def ics(token):
    a = _app(token)
    s = db.one("select * from interview_slots where application_id=%s", (a["id"],))
    if not s:
        bad("No interview is booked.", 404)
    return Response(automation.ics_for(f"Interview – {services.company()}", s["starts_at"], s["duration_mins"], s["meeting_link"] or "", f"iv{a['id']}"),
                    mimetype="text/calendar", headers={"Content-Disposition": 'attachment; filename="interview.ics"'})
