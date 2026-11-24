"""Software-engineer internship journey on the applicant's private dashboard link (/status/<token>):

  apply -> MCQ test (30 questions, 30 s each, pass at 21, 3 attempts, then a 2-day wait)
        -> offer letter the next day -> start internship -> repo for THEIR timeline only -> submit their GitHub link.

The clock is kept by the server: a question that is not answered within 30 s (+2 s for network lag) counts as unanswered, even if the
tab is closed or the browser is tampered with. Correct answers are never sent to the browser."""
import calendar
import random
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

import automation
import db
import mailer
import services
from mcq_bank import QUOTAS
from security import allow, bad

bp = Blueprint("mcq", __name__, url_prefix="/api/applicant")

TOTAL_QUESTIONS = sum(QUOTAS.values())      # 30
SECONDS_PER_QUESTION = 30
GRACE_SECONDS = 2
PASS_MARK = 21
MAX_ATTEMPTS = 3
COOLDOWN = timedelta(days=2)                # wait after the 3rd failed attempt
OFFER_DELAY = timedelta(days=1)             # offer letter arrives the day after passing
GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?(?:/tree/[\w./-]+)?/?$")


def _now():
    return datetime.now(timezone.utc)


def _fmt(dt):
    return dt.astimezone(current_app.config["TZ"]).strftime("%d %b %Y, %I:%M %p")


def _load(token):
    if not allow(f"mcq:{(token or '-')[:12]}", 900, 3600):      # per applicant, so a whole college behind one IP is not blocked
        bad("Too many requests. Please wait a minute.", 429)
    a = db.one("""select a.*, r.track, r.requires_test from applications a left join open_roles r on r.title=a.role_applied
                  where a.access_token=%s""", (token or "-",))
    if not a:
        bad("This link is not valid. Please use the link from your email.", 404)
    return a


def _lock(t, aid):
    return t.one("""select a.*, r.track, r.requires_test from applications a left join open_roles r on r.title=a.role_applied
                    where a.id=%s for update of a""", (aid,))


def add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


# ===================================================================== picking and serving questions
def _pick_questions(t):
    """30 random questions, balanced by topic (QUOTAS). Falls back to any topic if one is short."""
    ids = []
    for topic, n in QUOTAS.items():
        ids += [r["id"] for r in t.q("select id from mcq_questions where active and topic=%s order by random() limit %s", (topic, n))]
    if len(ids) < TOTAL_QUESTIONS:
        more = t.q("select id from mcq_questions where active and id <> all(%s) order by random() limit %s", (ids or [0], TOTAL_QUESTIONS - len(ids)))
        ids += [r["id"] for r in more]
    if len(ids) < TOTAL_QUESTIONS:
        bad("The question bank is not ready yet. Please try again later.", 503)
    random.shuffle(ids)
    return ids


def _question_payload(t, att):
    idx = att["current_idx"]
    q = t.one("select id, question, option_a, option_b, option_c, option_d from mcq_questions where id=%s", (att["question_ids"][idx],))
    left = SECONDS_PER_QUESTION - (_now() - att["question_shown_at"]).total_seconds()
    return {"finished": False, "index": idx + 1, "total": len(att["question_ids"]), "seconds_per_question": SECONDS_PER_QUESTION,
            "seconds_left": max(0, round(left, 1)),
            "question": {"id": q["id"], "text": q["question"], "options": {k: q[f"option_{k}"] for k in "abcd"}}}


def _advance_expired(t, att):
    """Questions whose time ran out (tab closed, phone locked ...) are recorded as unanswered. The test runs in real time."""
    now, idx, shown, ids = _now(), att["current_idx"], att["question_shown_at"], att["question_ids"]
    moved = False
    while idx < len(ids) and now > shown + timedelta(seconds=SECONDS_PER_QUESTION + GRACE_SECONDS):
        t.run("insert into mcq_answers (attempt_id, question_id, answer, is_correct) values (%s,%s,null,false) on conflict do nothing", (att["id"], ids[idx]))
        idx += 1
        shown += timedelta(seconds=SECONDS_PER_QUESTION)
        moved = True
    if moved:
        att = t.one("update mcq_attempts set current_idx=%s, question_shown_at=%s where id=%s returning *", (idx, shown, att["id"]))
    return att


def _finish(t, a, att):
    """Mark the attempt done, update the applicant. Returns (result dict, email to send after the transaction commits)."""
    score = t.one("select count(*) c from mcq_answers where attempt_id=%s and is_correct", (att["id"],))["c"]
    passed = score >= PASS_MARK
    t.run("update mcq_attempts set finished_at=now(), score=%s, passed=%s where id=%s", (score, passed, att["id"]))
    used = a["mcq_attempts_used"]
    result = {"finished": True, "score": score, "total": len(att["question_ids"]), "pass_mark": PASS_MARK, "passed": passed,
              "attempt_no": att["attempt_no"]}
    co, link = services.company(), automation.status_link(a["id"])
    if passed:
        due = _now() + OFFER_DELAY
        t.run("""update applications set mcq_stage='passed', offer_due_at=%s, mcq_retry_after=null, pipeline='test_taken', status='test_taken',
                 auto_note=%s where id=%s""", (due, f"MCQ test passed: {score}/{len(att['question_ids'])} (attempt {att['attempt_no']})", a["id"]))
        result.update(offer_due_at=due)
        mail = (f"You passed the test – {co}",
                f"Hi {a['name']},\n\nCongratulations! You scored {score}/{result['total']} and passed the test for {a['role_applied']}.\n\n"
                f"Your offer letter for the {a['timeline_months']}-month internship will be on your dashboard tomorrow, and we will email you when it is ready.\n"
                f"Your dashboard: {link}\n\n– {co}")
    elif used >= MAX_ATTEMPTS:
        retry = _now() + COOLDOWN
        t.run("update applications set mcq_stage='cooldown', mcq_retry_after=%s, auto_note=%s where id=%s",
              (retry, f"MCQ test: {score}/{result['total']} on attempt {att['attempt_no']}; all {MAX_ATTEMPTS} attempts used", a["id"]))
        result.update(attempts_left=0, retry_after=retry)
        mail = (f"Test result – {co}",
                f"Hi {a['name']},\n\nYou scored {score}/{result['total']}; the pass mark is {PASS_MARK}. You have used all {MAX_ATTEMPTS} attempts.\n"
                f"You can try again after {_fmt(retry)}. Revise the basics and come back stronger.\n{link}\n\n– {co}")
    else:
        t.run("update applications set auto_note=%s where id=%s", (f"MCQ test: {score}/{result['total']} on attempt {att['attempt_no']}", a["id"]))
        result.update(attempts_left=MAX_ATTEMPTS - used)
        mail = None
    return result, (mail and (a["email"],) + mail)


def _send(mail):
    if mail:
        try:
            mailer.send_mail(*mail)
        except Exception:                                # noqa: BLE001 - never lose a test result because email failed
            pass


# ===================================================================== offer letter
def release_offer(a):
    """Turn 'passed' into 'offer_sent' once the next-day moment has arrived. Safe to call any number of times (also used by the cron job)."""
    if a["mcq_stage"] != "passed" or not a["offer_due_at"] or a["offer_due_at"] > _now():
        return a
    got = db.one("update applications set mcq_stage='offer_sent', offer_sent_at=now() where id=%s and mcq_stage='passed' returning *", (a["id"],))
    if not got:
        return db.one("select * from applications where id=%s", (a["id"],))
    co = services.company()
    _send((a["email"], f"Your internship offer letter – {co}",
           f"Hi {a['name']},\n\nCongratulations again! Your offer letter for the {got['timeline_months']}-month {a['role_applied']} internship is ready on your dashboard.\n"
           f"Open it, accept it and start your internship here: {automation.status_link(a['id'])}\n\n– {co}"))
    services.log_auto("offer_letter", f"Offer letter released to {a['name']} ({got['timeline_months']} months)", "application", a["id"])
    return got


def job_offer_letters():
    """Scheduled job: release every offer whose day has come."""
    n = 0
    for a in db.q("select * from applications where mcq_stage='passed' and offer_due_at <= now()"):
        before = a["mcq_stage"]
        if release_offer(a)["mcq_stage"] != before:
            n += 1
    return n


# ===================================================================== dashboard data
def _program(a):
    if not a["requires_test"]:
        return {"enabled": False, "track": a["track"], "timeline_months": a["timeline_months"]}
    a = release_offer(a) | {"track": a["track"], "requires_test": True}
    now = _now()
    retry = a["mcq_retry_after"]
    waiting = bool(retry and retry > now)
    used = 0 if (retry and not waiting) else a["mcq_attempts_used"]
    open_att = db.one("select id, attempt_no from mcq_attempts where application_id=%s and finished_at is null", (a["id"],))
    history = db.q("select attempt_no, score, passed, finished_at from mcq_attempts where application_id=%s and finished_at is not null order by id", (a["id"],))
    stage = a["mcq_stage"]
    out = {"enabled": True, "track": a["track"], "role": a["role_applied"], "timeline_months": a["timeline_months"], "stage": stage,
           "rejected": a["pipeline"] == "rejected",
           "test": {"total": TOTAL_QUESTIONS, "seconds_per_question": SECONDS_PER_QUESTION, "pass_mark": PASS_MARK, "max_attempts": MAX_ATTEMPTS,
                    "cooldown_days": COOLDOWN.days, "attempts_used": used, "attempts_left": max(0, MAX_ATTEMPTS - used) if not waiting else 0,
                    "retry_after": retry if waiting else None, "in_progress": bool(open_att),
                    "can_start": stage in ("test_open", "cooldown") and not waiting and (bool(open_att) or used < MAX_ATTEMPTS),
                    "history": history}}
    if stage == "passed":
        out["offer_due_at"] = a["offer_due_at"]
    if stage in ("offer_sent", "working", "submitted"):
        start = a["internship_started_at"]
        out["offer"] = {"ref": f"OFR-{a['id']:05d}", "name": a["name"], "role": a["role_applied"], "months": a["timeline_months"],
                        "issued_at": a["offer_sent_at"], "company": services.company(), "college": a["college"]}
        if start:
            out["internship"] = {"started_at": start, "complete_by": add_months(start, a["timeline_months"])}
    if stage in ("working", "submitted"):
        repo = db.one("select title, github_url, instructions from internship_repos where track=%s and timeline_months=%s and active", (a["track"], a["timeline_months"]))
        out["repo"] = repo                                   # ONLY the repo for this person's own timeline
        out["submission"] = db.one("select github_url, submitted_at, review_status, review_note from repo_submissions where application_id=%s", (a["id"],))
    return out


@bp.get("/<token>/program")
def program(token):
    return jsonify(_program(_load(token)))


# ===================================================================== the test
@bp.post("/<token>/mcq/start")
def start(token):
    a = _load(token)
    if not a["requires_test"]:
        bad("This role does not have an online test.", 409)
    with db.tx() as t:
        a = _lock(t, a["id"])
        if a["pipeline"] == "rejected":
            bad("This application is closed.", 409)
        if a["mcq_stage"] not in ("test_open", "cooldown"):
            bad("You have already passed the test." if a["mcq_stage"] else "The test is not open for this application.", 409)
        att = t.one("select * from mcq_attempts where application_id=%s and finished_at is null for update", (a["id"],))
        if not att:
            used = a["mcq_attempts_used"]
            if a["mcq_retry_after"]:
                if a["mcq_retry_after"] > _now():
                    bad("You can take the test again after " + _fmt(a["mcq_retry_after"]) + ".", 409)
                used = 0                                         # the 2-day wait is over: a fresh set of 3 attempts
            if used >= MAX_ATTEMPTS:
                bad("You have used all your attempts.", 409)
            ids = _pick_questions(t)
            att = t.one("insert into mcq_attempts (application_id, attempt_no, question_ids, question_shown_at) values (%s,%s,%s,%s) returning *", (a["id"], used + 1, ids, _now()))
            t.run("update applications set mcq_attempts_used=%s, mcq_retry_after=null, mcq_stage='test_open' where id=%s", (used + 1, a["id"]))
            a["mcq_attempts_used"] = used + 1
        att = _advance_expired(t, att)
        if att["current_idx"] >= len(att["question_ids"]):
            result, mail = _finish(t, a, att)
        else:
            return jsonify(_question_payload(t, att))
    _send(mail)
    return jsonify(result)


@bp.post("/<token>/mcq/answer")
def answer(token):
    a = _load(token)
    body = request.get_json(silent=True) or {}
    ans = str(body.get("answer") or "").lower().strip()
    ans = ans if ans in ("a", "b", "c", "d") else None
    try:
        qid = int(body.get("question_id"))
    except (TypeError, ValueError):
        bad("Question missing.")
    with db.tx() as t:
        a = _lock(t, a["id"])
        att = t.one("select * from mcq_attempts where application_id=%s and finished_at is null for update", (a["id"],))
        if not att:
            bad("There is no test in progress.", 409)
        att = _advance_expired(t, att)                          # if this question already timed out, it is recorded as unanswered here
        if att["current_idx"] < len(att["question_ids"]):
            current = att["question_ids"][att["current_idx"]]
            if qid != current:                                  # out of sync (timed out meanwhile): hand back the real current question
                return jsonify({**_question_payload(t, att), "resync": True})
            correct = bool(ans) and t.one("select correct from mcq_questions where id=%s", (current,))["correct"] == ans
            t.run("insert into mcq_answers (attempt_id, question_id, answer, is_correct) values (%s,%s,%s,%s)", (att["id"], current, ans, correct))
            att = t.one("update mcq_attempts set current_idx=current_idx+1, question_shown_at=%s where id=%s returning *", (_now(), att["id"]))
        if att["current_idx"] < len(att["question_ids"]):
            return jsonify(_question_payload(t, att))
        result, mail = _finish(t, a, att)
    _send(mail)
    return jsonify(result)


# ===================================================================== internship: start + submit the GitHub link
@bp.post("/<token>/internship/start")
def start_internship(token):
    a = _load(token)
    a = release_offer(a) | {"requires_test": a["requires_test"]}
    if a["mcq_stage"] != "offer_sent":
        bad("Your offer letter is not available yet." if a["mcq_stage"] == "passed" else "You cannot start the internship yet.", 409)
    db.run("update applications set mcq_stage='working', internship_started_at=now() where id=%s and mcq_stage='offer_sent'", (a["id"],))
    services.log_auto("internship_start", f"{a['name']} accepted the offer and started ({a['timeline_months']} months)", "application", a["id"])
    return jsonify(ok=True)


@bp.post("/<token>/internship/submit")
def submit_repo(token):
    a = _load(token)
    if a["mcq_stage"] not in ("working", "submitted"):
        bad("Start your internship first.", 409)
    url = str((request.get_json(silent=True) or {}).get("github_url") or "").strip()
    if len(url) > 300 or not GITHUB_RE.match(url):
        bad("Paste the link of your GitHub repository, for example https://github.com/your-name/your-project")
    with db.tx() as t:
        t.run("""insert into repo_submissions (application_id, github_url) values (%s,%s)
                 on conflict (application_id) do update set github_url=excluded.github_url, submitted_at=now(), review_status='submitted', review_note=null""", (a["id"], url))
        t.run("update applications set mcq_stage='submitted' where id=%s", (a["id"],))
    services.log_auto("repo_submitted", f"{a['name']} submitted {url}", "application", a["id"])
    return jsonify(ok=True)
