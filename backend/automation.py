"""Rule-based automation. Principle: automate every step that is a rule; keep humans for judgment, money disputes and reputation.
Every job is idempotent (safe to run every few minutes), every automatic decision is written to `automation_log`,
and reversible ones can be undone by an admin from the Automation page."""
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import current_app

import alerts
import db
import mailer
import services
from core import performance_map, today
from services import automation_on, company, log_auto, setting_int, site_url


def _now():
    return datetime.now(current_app.config["TZ"])


# ===================================================================== applicant pipeline
def ensure_token(aid):
    from security import new_token
    r = db.one("select access_token from applications where id=%s", (aid,))
    if r and r["access_token"]:
        return r["access_token"]
    tok = new_token(18)
    db.run("update applications set access_token=%s where id=%s and access_token is null", (tok, aid))
    return db.one("select access_token from applications where id=%s", (aid,))["access_token"]


def status_link(aid):
    return f"{site_url()}/status/{ensure_token(aid)}"


def send_test_invite(a, how="automatically"):
    """Email the applicant a personal test link (no account needed). Returns False if no test exists for the role."""
    test = db.one("select * from tests where role_title=%s", (a["role_applied"],))
    if not test:
        return False
    db.run("update applications set pipeline='test_sent', status='test_sent' where id=%s and pipeline in ('applied','test_sent')", (a["id"],))
    mailer.send_mail(a["email"], f"Your assessment test is ready – {company()}",
                     f"Hi {a['name']},\n\nThank you for applying for {a['role_applied']} at {company()}. The next step is a short online test.\n\n"
                     f"Open your personal link: {status_link(a['id'])}\n\n"
                     f"- Duration: {test['duration_mins']} minutes (the timer starts when you open the test)\n- Pass mark: {test['passing_score']}%\n"
                     f"- You can take it once.\n\nGood luck!\n\n– {company()}")
    log_auto("test_invite", f"Test link sent to {a['name']} ({how})", "application", a["id"], dedupe=f"invite:{a['id']}:{how}")
    return True


def decide_after_test(aid):
    """Score at/above the pass mark -> shortlist; clearly below -> polite decline; borderline -> a person decides."""
    a = db.one("select * from applications where id=%s", (aid,))
    sub = db.one("select ts.*, t.passing_score from test_submissions ts join tests t on t.id=ts.test_id where ts.application_id=%s", (aid,))
    if not a or not sub or not automation_on():
        return "manual"
    pct, need = float(sub["percentage"]), sub["passing_score"]
    margin = setting_int("test_borderline_margin", 5)
    co = company()
    if pct >= need:
        db.run("update applications set pipeline='shortlisted', status='shortlisted', auto_note=%s where id=%s", (f"Auto-shortlisted: scored {pct:.0f}% (pass mark {need}%)", aid))
        mailer.send_mail(a["email"], f"Congratulations! You are shortlisted – {co}",
                         f"Hi {a['name']},\n\nYou scored {pct:.0f}% in the test and have been shortlisted for {a['role_applied']}.\n\n"
                         f"Next step: choose an interview time that suits you:\n{status_link(aid)}\n\nBest of luck!\n\n– {co}")
        log_auto("auto_shortlist", f"{a['name']} scored {pct:.0f}% (pass {need}%) -> shortlisted", "application", aid, reversible=True)
        return "shortlisted"
    if need - pct <= margin:
        db.run("update applications set auto_note=%s where id=%s", (f"Borderline: scored {pct:.0f}% (pass mark {need}%). Needs a person.", aid))
        log_auto("borderline_held", f"{a['name']} scored {pct:.0f}% (pass {need}%) -> left for a person to decide", "application", aid)
        return "borderline"
    if setting_int("auto_decline_enabled", 1):
        db.run("update applications set pipeline='rejected', status='rejected', auto_note=%s where id=%s", (f"Auto-declined: scored {pct:.0f}% (pass mark {need}%)", aid))
        mailer.send_mail(a["email"], f"Update on your application – {co}",
                         f"Hi {a['name']},\n\nThank you for taking the test for {a['role_applied']}. This time your score did not reach the level we need for the next round.\n\n"
                         f"We really appreciate your effort and encourage you to apply again in the future.\n\nBest wishes,\n– {co}")
        log_auto("auto_decline", f"{a['name']} scored {pct:.0f}% (pass {need}%) -> polite decline sent", "application", aid, reversible=True)
        return "declined"
    return "manual"


def ics_for(summary, starts_at, minutes, location="", uid="x"):
    fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end = starts_at + timedelta(minutes=minutes)
    esc = lambda s: (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//UpStep//EN\r\nBEGIN:VEVENT\r\n"
            f"UID:{uid}@upstep\r\nDTSTAMP:{fmt(datetime.now(timezone.utc))}\r\nDTSTART:{fmt(starts_at)}\r\nDTEND:{fmt(end)}\r\n"
            f"SUMMARY:{esc(summary)}\r\nLOCATION:{esc(location)}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").encode()


# ===================================================================== daily rules for students
def job_flush_email_queue():
    """Yesterday's queued reminders go out first, within the daily email budget (EMAIL_DAILY_LIMIT)."""
    return mailer.flush_queue()


def job_daily_task_emails():
    """ONE email per student per run: tasks that just unlocked, tasks due tomorrow, tasks overdue.
    (Separate emails for each would double the volume, and free email plans cap sending.) Each item is logged once, so nothing repeats."""
    people = {}

    def bucket(r):
        return people.setdefault(r["student_id"], {"name": r["name"], "email": r["email"], "new": [], "soon": [], "late": []})

    for r in db.q("""select ta.student_id, ta.unlock_date, u.name, u.email, array_agg(t.title order by t.id) as titles
                     from task_assignments ta join tasks t on t.id=ta.task_id join users u on u.id=ta.student_id
                     where ta.unlock_date between %s and %s and ta.status='pending' and u.is_active
                     group by ta.student_id, ta.unlock_date, u.name, u.email""", (today() - timedelta(days=2), today())):
        if log_auto("task_unlocked", f"{len(r['titles'])} task(s) unlocked for {r['name']}", "student", r["student_id"], r["student_id"],
                    dedupe=f"unlock:{r['student_id']}:{r['unlock_date']}"):
            bucket(r)["new"] += r["titles"]
    for r in db.q("""select ta.id, ta.student_id, t.title, t.due_date, u.name, u.email
                     from task_assignments ta join tasks t on t.id=ta.task_id join users u on u.id=ta.student_id
                     where ta.status in ('pending','rework') and u.is_active and (ta.unlock_date is null or ta.unlock_date <= %s)
                       and (t.due_date = %s or (t.due_date < %s and t.due_date + t.grace_days >= %s))""",
                  (today(), today() + timedelta(days=1), today(), today())):
        soon = r["due_date"] >= today()
        if log_auto("due_reminder" if soon else "overdue_reminder", f"{r['title']} -> {r['name']}", "assignment", r["id"], r["student_id"],
                    dedupe=f"due24:{r['id']}" if soon else f"late:{r['id']}"):
            bucket(r)["soon" if soon else "late"].append(r["title"])
    sent = 0
    for p in people.values():
        lines = []
        if p["new"]:
            lines += ["New today:"] + [f"  - {t}" for t in p["new"]]
        if p["soon"]:
            lines += ["Due tomorrow:"] + [f"  - {t}" for t in p["soon"]]
        if p["late"]:
            lines += ["Overdue (submit now so it is not marked incomplete):"] + [f"  - {t}" for t in p["late"]]
        if lines:
            mailer.send_mail(p["email"], f"Your tasks for today – {company()}",
                             f"Hi {p['name']},\n\n" + "\n".join(lines) + f"\n\nOpen your tasks: {site_url()}/app/tasks\n\n– {company()}", low=True)
            sent += 1
    return sent


def job_inactivity():
    """No submission for 2 days -> nudge the student; 4 days -> flag to the mentor."""
    nudged = flagged = 0
    students = db.q("""select u.id, u.name, u.email, u.start_date, u.mentor_id,
                         (select max(submitted_at::date) from task_assignments where student_id=u.id) as last_sub,
                         exists (select 1 from task_assignments ta where ta.student_id=u.id and ta.status in ('pending','rework')
                                 and (ta.unlock_date is null or ta.unlock_date <= %s)) as has_open
                       from users u where u.role='student' and u.is_active and u.start_date is not null and u.start_date <= %s and u.outcome='in_progress'""",
                     (today(), today()))
    for s in students:
        last = max([d for d in (s["last_sub"], s["start_date"]) if d])
        gap = (today() - last).days
        if gap < 2 or not s["has_open"]:
            db.run("update student_flags set resolved_at=now() where student_id=%s and kind='inactive' and resolved_at is null", (s["id"],))
            continue
        if gap >= 4:
            if log_auto("inactive_flag", f"{s['name']}: no submission for {gap} days", "student", s["id"], s["id"], dedupe=f"flag:{s['id']}:{last}"):
                db.run("insert into student_flags (student_id, kind, note) values (%s,'inactive',%s) on conflict do nothing",
                       (s["id"], f"No submission for {gap} days"))
                m = db.one("select name, email from users where id=%s", (s["mentor_id"],)) if s["mentor_id"] else None
                if m:
                    mailer.send_mail(m["email"], f"Needs a call: {s['name']} has been quiet for {gap} days",
                                     f"{s['name']} has not submitted any task for {gap} days.\nPlease check in: {site_url()}/admin/students/{s['id']}")
                flagged += 1
        elif log_auto("inactive_nudge", f"Nudged {s['name']} ({gap} days without a submission)", "student", s["id"], s["id"], dedupe=f"nudge:{s['id']}:{last}"):
            mailer.send_mail(s["email"], f"We miss your work – {company()}",
                             f"Hi {s['name']},\n\nYou have not submitted a task for {gap} days. A small submission today keeps you on track.\n"
                             f"Stuck? Tell your mentor in the chat.\n{site_url()}/app/tasks\n\n– {company()}", low=True)
            nudged += 1
    return {"nudged": nudged, "flagged": flagged}


def job_mark_incomplete():
    """Scheduled task still not submitted after due date + grace days -> 'incomplete' (scores zero; mentor can reopen)."""
    rows = db.q("""select ta.id, ta.student_id, t.title from task_assignments ta join tasks t on t.id=ta.task_id
                   where ta.status in ('pending','rework') and t.source='template' and %s > t.due_date + t.grace_days""", (today(),))
    n = 0
    for r in rows:
        if log_auto("task_incomplete", f"'{r['title']}' marked incomplete (deadline passed)", "assignment", r["id"], r["student_id"],
                    dedupe=f"incomplete:{r['id']}", reversible=True):
            db.run("update task_assignments set status='incomplete' where id=%s and status in ('pending','rework')", (r["id"],))
            n += 1
    return n


def job_certificates():
    issued = 0
    for s in db.q("""select u.* from users u where u.role='student' and u.is_active and u.start_date is not null
                     and not exists (select 1 from certificates c where c.user_id=u.id)"""):
        chk = services.certificate_check(s)
        if chk["eligible"]:
            c = services.issue_certificate(s, auto=True)
            log_auto("certificate_issued", f"{s['name']}: grade {c['grade']} ({chk['score']}%) -> {c['cert_no']}", "student", s["id"], s["id"],
                     dedupe=f"cert:{s['id']}", reversible=True)
            issued += 1
        elif chk["finished"] and chk["reason"]:
            log_auto("certificate_not_issued", f"{s['name']}: {chk['reason']}", "student", s["id"], s["id"], dedupe=f"certno:{s['id']}:{chk['reason'][:40]}")
    return issued


# ===================================================================== applicants and interviews
def job_applicant_reminders():
    n = 0
    for a in db.q("""select * from applications where pipeline='test_sent' and access_token is not null and test_started_at is null
                     and created_at < now() - interval '2 days'"""):
        if log_auto("test_reminder", f"Reminded {a['name']} to take the test", "application", a["id"], dedupe=f"testrem:{a['id']}"):
            mailer.send_mail(a["email"], f"Your test is still waiting – {company()}",
                             f"Hi {a['name']},\n\nYou have not taken your assessment yet. Your personal link: {status_link(a['id'])}\n\n– {company()}", low=True)
            n += 1
    for a in db.q("""select a.* from applications a where a.pipeline='shortlisted' and a.created_at < now() - interval '2 days'
                     and not exists (select 1 from interview_slots s where s.application_id=a.id)"""):
        if log_auto("slot_reminder", f"Reminded {a['name']} to book an interview", "application", a["id"], dedupe=f"slotrem:{a['id']}"):
            mailer.send_mail(a["email"], f"Please choose your interview time – {company()}",
                             f"Hi {a['name']},\n\nYou are shortlisted. Choose a slot here: {status_link(a['id'])}\n\n– {company()}", low=True)
            n += 1
    return n


def job_interview_reminders():
    n = 0
    now = _now()
    rows = db.q("""select i.application_id, i.scheduled_date, i.scheduled_time, i.meeting_link, a.name, a.email, a.role_applied, s.mentor_id,
                          m.email as mentor_email
                   from interviews i join applications a on a.id=i.application_id
                   left join interview_slots s on s.id=i.slot_id left join users m on m.id=s.mentor_id
                   where i.result='pending' and i.scheduled_date between %s and %s""", (today(), today() + timedelta(days=1)))
    for r in rows:
        if not r["scheduled_time"]:
            continue
        start = datetime.combine(r["scheduled_date"], r["scheduled_time"], tzinfo=current_app.config["TZ"])
        delta = start - now
        for label, limit in (("1h", timedelta(hours=1)), ("24h", timedelta(hours=24))):
            if timedelta(0) < delta <= limit:
                if log_auto("interview_reminder", f"{label} reminder: {r['name']} at {start:%d %b %H:%M}", "application", r["application_id"],
                            dedupe=f"iv{label}:{r['application_id']}:{start:%Y%m%d%H%M}"):
                    body = (f"Reminder: interview for {r['role_applied']} on {start:%A %d %b at %I:%M %p}.\n"
                            + (f"Join: {r['meeting_link']}\n" if r["meeting_link"] else "") + f"\n– {company()}")
                    mailer.send_mail(r["email"], f"Interview reminder ({label}) – {company()}", f"Hi {r['name']},\n\n" + body)
                    if r["mentor_email"]:
                        mailer.send_mail(r["mentor_email"], f"Interview with {r['name']} at {start:%I:%M %p}", body)
                    n += 1
                break
    return n


# ===================================================================== class directory + ads
def job_enquiry_followups():
    n = 0
    for e in db.q("""select e.id, e.name, e.phone, c.name as class_name, c.email, c.whatsapp, c.phone as cphone
                     from class_enquiries e join classes c on c.id=e.class_id
                     where e.status='new' and e.created_at < now() - interval '24 hours'"""):
        if log_auto("enquiry_followup", f"{e['class_name']} has not contacted {e['name']} after 24h", "enquiry", e["id"], dedupe=f"enqrem:{e['id']}"):
            msg = f"Reminder: {e['name']} ({e['phone']}) asked about {e['class_name']} more than 24 hours ago. Please call back and mark it contacted."
            if e["email"]:
                mailer.send_mail(e["email"], f"Please call back {e['name']}", msg, low=True)
            mailer.send_whatsapp(e["whatsapp"] or e["cphone"], msg)
            n += 1
    return n


def job_stale_fees():
    n = 0
    days = setting_int("stale_fee_days", 180)
    month = today().strftime("%Y-%m")
    for c in db.q("""select id, name, email, slug from classes where status='live' and fees_updated_at < now() - make_interval(days => %s)""", (days,)):
        if log_auto("fees_stale_reminder", f"Fees for {c['name']} older than {days} days", "class", c["id"], dedupe=f"stale:{c['id']}:{month}"):
            if c["email"]:
                mailer.send_mail(c["email"], f"Are the fees for {c['name']} still correct?",
                                 f"The fees on your listing were last updated more than {days // 30} months ago. Students rely on them.\n"
                                 f"Please review them from your management link (use 'Claim this listing' on {site_url()}/classes/{c['slug']} if you need a new one).", low=True)
            n += 1
    return n


def ad_report_text(c):
    ctr = f"{100 * c['clicks'] / c['impressions']:.1f}%" if c["impressions"] else "0%"
    return (f"Campaign '{c['headline']}' report\nRan: {c['starts_on']} to {c['ends_on']}\nViews: {c['impressions']}\nClicks: {c['clicks']}\nClick rate: {ctr}\n")


def job_ads():
    n = 0
    for c in db.q("select * from ad_campaigns where status='active' and ends_on < %s", (today(),)):
        db.run("update ad_campaigns set status='ended', report_sent_at=now() where id=%s", (c["id"],))
        mailer.send_mail(c["contact_email"], f"Your campaign has finished – {company()}", f"Hi {c['advertiser_name']},\n\n" + ad_report_text(c) + f"\nThank you for advertising with {company()}.", low=True)
        log_auto("ad_ended", f"Campaign #{c['id']} ended; report emailed ({c['impressions']} views, {c['clicks']} clicks)", "campaign", c["id"])
        n += 1
    return n


# ===================================================================== AI-assisted (mentor still decides)
def job_ai_drafts():
    import ai
    n = 0
    for r in db.q("""select ta.id from task_assignments ta where ta.status='submitted' and ta.ai_draft is null order by ta.submitted_at limit 15"""):
        try:
            ai.draft_review(r["id"])
            n += 1
        except Exception:
            current_app.logger.exception("AI draft failed for assignment %s", r["id"])
    return n


# ===================================================================== reports and digests
def admin_emails():
    out = {r["email"] for r in db.q("select email from users where role='admin' and is_active")}
    ce = services.setting("contact_email")
    if ce and "@" in ce and ce != "hello@example.com":
        out.add(ce)
    return sorted(out)


def build_weekly_report():
    one = lambda sql, *a: db.one(sql, a)["n"]
    wk = "now() - interval '7 days'"
    paid = db.one(f"select coalesce(sum(amount_paise) filter (where created_at > {wk} and kind='enrolment'),0) as e, "
                  f"coalesce(sum(amount_paise) filter (where created_at > {wk} and kind='ad'),0) as a, coalesce(sum(amount_paise),0) as total "
                  "from payments where status='paid'")
    perf = performance_map()
    open_flags = one("select count(*) n from student_flags where resolved_at is null")
    approved = sum(p["approved"] for p in perf.values())
    released = sum(p["total"] for p in perf.values())
    r = {
        "week_ending": today().isoformat(),
        "applications_this_week": one(f"select count(*) n from applications where created_at > {wk}"),
        "applications_total": one("select count(*) n from applications"),
        "tests_taken_this_week": one(f"select count(*) n from test_submissions where submitted_at > {wk}"),
        "shortlisted_waiting_interview": one("select count(*) n from applications where pipeline='shortlisted'"),
        "borderline_for_review": one("select count(*) n from applications where auto_note like 'Borderline%%' and pipeline='test_taken'"),
        "active_students": one("select count(*) n from users where role='student' and is_active and outcome='in_progress'"),
        "overdue_tasks": sum(p["overdue"] for p in perf.values()),
        "completion_percent": round(100 * approved / released) if released else None,
        "students_flagged_inactive": open_flags,
        "certificates_issued_this_week": one(f"select count(*) n from certificates where issued_at > {wk} and revoked_at is null"),
        "revenue_enrolment_this_week_inr": paid["e"] / 100,
        "revenue_ads_this_week_inr": paid["a"] / 100,
        "revenue_total_inr": paid["total"] / 100,
        "directory_live_listings": one("select count(*) n from classes where status='live'"),
        "directory_new_listings_this_week": one(f"select count(*) n from classes where created_at > {wk}"),
        "directory_reviews_waiting": one("select count(*) n from class_reviews where status in ('pending','held')"),
        "directory_enquiries_this_week": one(f"select count(*) n from class_enquiries where created_at > {wk}"),
        "directory_enquiries_not_contacted": one("select count(*) n from class_enquiries where status='new'"),
        "ads_active": one("select count(*) n from ad_campaigns where status='active'"),
        "automatic_decisions_this_week": one(f"select count(*) n from automation_log where created_at > {wk}"),
    }
    return r


def report_text(r):
    lines = [f"Weekly report – week ending {r['week_ending']}", "", "SELECTION"]
    lines += [f"  Applications: {r['applications_this_week']} this week ({r['applications_total']} total)",
              f"  Tests taken: {r['tests_taken_this_week']}", f"  Shortlisted, waiting for interview: {r['shortlisted_waiting_interview']}",
              f"  Borderline scores needing you: {r['borderline_for_review']}", "", "PROGRAMME",
              f"  Active students: {r['active_students']}", f"  Overdue tasks: {r['overdue_tasks']}",
              f"  Completion: {r['completion_percent'] if r['completion_percent'] is not None else '-'}%",
              f"  Students flagged inactive: {r['students_flagged_inactive']}", f"  Certificates issued: {r['certificates_issued_this_week']}", "", "REVENUE (INR)",
              f"  Enrolment this week: {r['revenue_enrolment_this_week_inr']:.0f}", f"  Ads this week: {r['revenue_ads_this_week_inr']:.0f}",
              f"  All time: {r['revenue_total_inr']:.0f}", "", "CLASS DIRECTORY",
              f"  Live listings: {r['directory_live_listings']} (+{r['directory_new_listings_this_week']} this week)",
              f"  Reviews waiting for you: {r['directory_reviews_waiting']}",
              f"  Enquiries: {r['directory_enquiries_this_week']} this week, {r['directory_enquiries_not_contacted']} not yet contacted",
              f"  Active ad campaigns: {r['ads_active']}", "", f"The system made {r['automatic_decisions_this_week']} automatic decisions this week. Review them: {site_url()}/admin/automation"]
    return "\n".join(lines)


def job_weekly_report(force=False):
    now = _now()
    if not force and not (now.weekday() == 0 and now.hour >= 8):
        return 0
    key = f"weekly:{now.isocalendar().year}-{now.isocalendar().week}"
    if not log_auto("weekly_report", "Weekly report emailed to admins", dedupe=key):
        return 0
    r = build_weekly_report()
    body = report_text(r)
    db.run("insert into reports (kind, body) values ('weekly', %s)", (body,))
    for e in admin_emails():
        mailer.send_mail(e, f"Weekly report – {company()}", body)
    return 1


def job_standup_digests(force=False):
    import ai
    now = _now()
    if not force and (now.weekday() >= 5 or now.hour < 11):
        return 0
    n = 0
    for m in db.q("select id, name, email from users where role='mentor' and is_active"):
        d = ai.standup_digest(m["id"], today())
        if not d["students"]:
            continue
        if log_auto("standup_digest", f"Digest sent to {m['name']}", "mentor", m["id"], dedupe=f"digest:{m['id']}:{today()}"):
            mailer.send_mail(m["email"], f"Stand-up digest – {today():%d %b}", ai.digest_text(d), low=True)
            n += 1
    return n


# ===================================================================== runner
JOBS = [
    ("flush_email_queue", job_flush_email_queue), ("daily_task_emails", job_daily_task_emails), ("inactivity", job_inactivity),
    ("mark_incomplete", job_mark_incomplete), ("certificates", job_certificates), ("applicant_reminders", job_applicant_reminders),
    ("interview_reminders", job_interview_reminders), ("enquiry_followups", job_enquiry_followups), ("stale_fees", job_stale_fees),
    ("ads", job_ads), ("ai_drafts", job_ai_drafts), ("standup_digests", job_standup_digests), ("weekly_report", job_weekly_report),
]


def run_all(force=False):
    """Run every job once. Returns {job: result}. A failing job never stops the others. Only one runner at a time (Postgres advisory lock)."""
    if not automation_on() and not force:
        return {"skipped": "Automation is switched off in Settings."}
    out = {}
    with db._pool.connection() as lock:
        if not lock.execute("select pg_try_advisory_lock(7241001) as ok").fetchone()["ok"]:
            return {"skipped": "Another run is in progress."}
        try:
            for name, fn in JOBS:
                try:
                    out[name] = fn(force=True) if force and name in ("weekly_report", "standup_digests") else fn()
                except Exception as e:                      # noqa: BLE001 - keep going, but make noise
                    current_app.logger.exception("automation job %s failed", name)
                    alerts.notify(f"Automation job '{name}' failed: {e}")
                    out[name] = f"error: {e}"
        finally:
            lock.execute("select pg_advisory_unlock(7241001)")
    return out


def start_scheduler(app, every_minutes):
    """Optional in-process scheduler (AUTO_SCHEDULER=1). With several instances only one runs a given tick thanks to the advisory lock."""
    def loop():
        time.sleep(15)
        while True:
            try:
                with app.app_context():
                    run_all()
            except Exception:
                app.logger.exception("scheduler tick failed")
            time.sleep(max(1, every_minutes) * 60)
    threading.Thread(target=loop, daemon=True, name="upstep-scheduler").start()
