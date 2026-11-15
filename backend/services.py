"""Business logic shared by routes and the automation jobs."""
import re
import secrets
from datetime import timedelta

from flask import current_app

import db
import mailer
from core import ensure_mentor_channel, performance_map, site_settings, temp_password, today
from security import bad, generate_password_hash


# ------------------------------------------------------------------ small helpers
def setting(key, default=""):
    r = db.one("select value from settings where key=%s", (key,))
    return r["value"] if r else default


def setting_int(key, default=0):
    try:
        return int(setting(key, str(default)))
    except (TypeError, ValueError):
        return default


def automation_on():
    return setting("automation_enabled", "1") == "1"


def company():
    return setting("company_name", "our team") or "our team"


def site_url():
    return current_app.config["SITE_URL"].rstrip("/")


def log_auto(kind, detail, ref_type=None, ref_id=None, student_id=None, dedupe=None, reversible=False):
    """Record an automatic decision. With `dedupe`, returns None if this exact action was already taken
    (so callers can skip sending the same email twice)."""
    r = db.one("""insert into automation_log (kind, ref_type, ref_id, student_id, detail, dedupe_key, reversible)
                  values (%s,%s,%s,%s,%s,%s,%s) on conflict (dedupe_key) do nothing returning id""",
               (kind, ref_type, ref_id, student_id, detail[:500], dedupe, reversible))
    return r["id"] if r else None


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "class"


def unique_class_slug(name, area=""):
    base = slugify(f"{name}-{area}" if area else name)
    slug, n = base, 2
    while db.one("select 1 from classes where slug=%s", (slug,)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def digits(phone):
    return "".join(c for c in (phone or "") if c.isdigit())


def wa_link(phone, text=""):
    d = digits(phone)
    if len(d) == 10:
        d = "91" + d
    from urllib.parse import quote
    return f"https://wa.me/{d}" + (f"?text={quote(text)}" if text else "")


# ------------------------------------------------------------------ legal + consent
def latest_legal(slug):
    return db.one("select slug, version, title, body, published_at from legal_documents where slug=%s order by version desc limit 1", (slug,))


def record_consent(slugs, context, user_id=None, email=None, ip=None):
    for slug in slugs:
        d = latest_legal(slug)
        if d:
            db.run("insert into consents (user_id, email, doc_slug, doc_version, context, ip) values (%s,%s,%s,%s,%s,%s)",
                   (user_id, (email or "").lower() or None, slug, d["version"], context, ip))


# ------------------------------------------------------------------ class directory
def refresh_rating(class_id):
    db.run("""update classes set
                rating_sum = coalesce((select sum(rating) from class_reviews where class_id=%s and status='live'),0),
                rating_count = (select count(*) from class_reviews where class_id=%s and status='live')
              where id=%s""", (class_id, class_id, class_id))


def touch_fees(class_id):
    db.run("update classes set fees_updated_at=now(), updated_at=now() where id=%s", (class_id,))


def replace_courses(t, class_id, courses):
    """courses: list of dicts already cleaned by clean_courses(). `t` is a db runner (inside a transaction)."""
    t.run("delete from class_courses where class_id=%s", (class_id,))
    for i, c in enumerate(courses):
        t.run("""insert into class_courses (class_id,title,duration,fee_min,fee_max,batch_timing,sort_order)
                 values (%s,%s,%s,%s,%s,%s,%s)""", (class_id, c["title"], c["duration"], c["fee_min"], c["fee_max"], c["batch_timing"], i))
    t.run("update classes set fees_updated_at=now(), updated_at=now() where id=%s", (class_id,))


def _fee(v, label):
    if v in (None, ""):
        return None
    try:
        n = int(float(str(v).replace(",", "").replace("₹", "").strip()))
    except ValueError:
        bad(f"{label} must be a number.")
    if not 0 <= n <= 5_000_000:
        bad(f"{label} looks wrong. Enter the fee in rupees.")
    return n


def clean_courses(raw):
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw[:30]:
        if not isinstance(c, dict):
            continue
        title = str(c.get("title") or "").strip()[:160]
        if not title:
            continue
        lo, hi = _fee(c.get("fee_min"), "Minimum fee"), _fee(c.get("fee_max"), "Maximum fee")
        if lo is not None and hi is None:
            hi = lo
        if hi is not None and lo is None:
            lo = hi
        if lo is not None and hi < lo:
            bad(f"For '{title}', the maximum fee is lower than the minimum fee.")
        out.append({"title": title, "duration": str(c.get("duration") or "").strip()[:60] or None,
                    "fee_min": lo, "fee_max": hi, "batch_timing": str(c.get("batch_timing") or "").strip()[:120] or None})
    return out


# ------------------------------------------------------------------ task templates
def apply_template(student_id, template_id, start_date):
    """Create every item of the template for this student. Day N unlocks on start + N - 1. Safe to call twice."""
    items = db.q("select * from task_template_items where template_id=%s order by day_no, id", (template_id,))
    made = 0
    with db.tx() as t:
        for it in items:
            if t.one("""select 1 from task_assignments ta join tasks tk on tk.id=ta.task_id
                        where ta.student_id=%s and tk.template_item_id=%s""", (student_id, it["id"])):
                continue
            unlock = start_date + timedelta(days=it["day_no"] - 1)
            due = unlock + timedelta(days=it["due_in_days"])
            tk = t.one("""insert into tasks (title, description, due_date, max_points, kind, source, template_item_id, grace_days, rubric)
                          values (%s,%s,%s,%s,'training','template',%s,%s,%s) returning id""",
                       (f"Day {it['day_no']}: {it['title']}", it["description"], due, it["max_points"], it["id"], it["grace_days"], it["rubric"]))
            t.run("insert into task_assignments (task_id, student_id, unlock_date) values (%s,%s,%s)", (tk["id"], student_id, unlock))
            made += 1
    return made


def default_template_id():
    r = db.one("select id from task_templates where is_default order by id limit 1") or db.one("select id from task_templates order by id limit 1")
    return r["id"] if r else None


# ------------------------------------------------------------------ enrolment (account + mentor + group + schedule)
def pick_mentor():
    r = db.one("""select m.id from users m where m.role='mentor' and m.is_active
                  order by (select count(*) from users s where s.mentor_id=m.id and s.is_active), m.id limit 1""")
    return r["id"] if r else None


def pick_group(mentor_id):
    if not mentor_id:
        return None
    r = db.one("""select g.id from student_groups g where g.mentor_id=%s and g.kind='training'
                  and (select count(*) from group_members m where m.group_id=g.id) < 8
                  order by g.id desc limit 1""", (mentor_id,))
    return r["id"] if r else None


def enrol_application(aid, mentor_id=None, start_date=None, how="selected by admin"):
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        bad("Application not found.", 404)
    if a["user_id"]:
        bad("This applicant already has a student account.")
    if db.one("select 1 from users where lower(email)=%s", (a["email"].lower(),)):
        bad("A user with this email already exists.", 409)
    if mentor_id and not db.one("select 1 from users where id=%s and role='mentor' and is_active", (mentor_id,)):
        bad("Choose a valid mentor.")
    mentor_id = mentor_id or pick_mentor()
    start = start_date or today()
    tpl = default_template_id()
    pw = temp_password()
    with db.tx() as t:
        u = t.one("""insert into users (name,email,phone,password_hash,role,college,mentor_id,start_date,must_change_password,template_id)
                     values (%s,%s,%s,%s,'student',%s,%s,%s,true,%s) returning id""",
                  (a["name"], a["email"].lower(), a["phone"], generate_password_hash(pw), a["college"], mentor_id, start, tpl))
        t.run("update applications set status='selected', pipeline='onboarded', user_id=%s where id=%s", (u["id"], aid))
        gid = pick_group(mentor_id)
        if gid:
            t.run("insert into group_members (group_id, student_id) values (%s,%s) on conflict do nothing", (gid, u["id"]))
    ensure_mentor_channel(u["id"])
    made = apply_template(u["id"], tpl, start) if tpl else 0
    co = company()
    mailer.send_mail(a["email"], f"Welcome to {co} – your login",
                     f"Hi {a['name']},\n\nCongratulations! You are selected for {a['role_applied']}.\n\nSign in at {site_url()}/login\n"
                     f"Email: {a['email']}\nTemporary password: {pw}\n\nYou will be asked to set a new password the first time you sign in.\n"
                     f"Your daily tasks unlock automatically from {start:%d %b %Y}.\n\n– {co}")
    log_auto("enrolled", f"{a['name']} enrolled ({how}); mentor #{mentor_id or '-'}; {made} scheduled tasks", "application", aid, u["id"])
    return {"student_id": u["id"], "temp_password": pw, "scheduled_tasks": made, "mentor_id": mentor_id}


# ------------------------------------------------------------------ certificates
GRADES = ((90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (0, "C"))


def grade_for(score):
    return next(g for lo, g in GRADES if score >= lo)


def new_cert_no():
    alpha = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    while True:
        no = f"UP{today():%y}-" + "".join(secrets.choice(alpha) for _ in range(4)) + "-" + "".join(secrets.choice(alpha) for _ in range(4))
        if not db.one("select 1 from certificates where cert_no=%s", (no,)):
            return no


def certificate_check(student):
    """-> dict(finished, score, eligible, reason)"""
    sd = student.get("start_date")
    perf = performance_map([student["id"]]).get(student["id"], {})
    score = perf.get("performance")
    pass_mark = setting_int("cert_pass_mark", 60)
    out = {"score": score, "pass_mark": pass_mark, "finished": False, "eligible": False, "reason": ""}
    if not sd:
        out["reason"] = "No start date."
        return out
    end = sd + timedelta(days=student["training_days"])
    out["finished"] = today() >= end
    out["ends_on"] = end
    if not out["finished"]:
        out["reason"] = f"Programme ends on {end:%d %b %Y}."
    elif score is None:
        out["reason"] = "No scored tasks."
    elif perf.get("submitted"):
        out["reason"] = "Some submitted work is still waiting for the mentor."
    elif score < pass_mark:
        out["reason"] = f"Performance {score}% is below the pass mark of {pass_mark}%."
    else:
        out["eligible"] = True
    return out


def issue_certificate(student, auto=True):
    existing = db.one("select * from certificates where user_id=%s", (student["id"],))
    if existing:
        return existing
    perf = performance_map([student["id"]]).get(student["id"], {})
    score = perf.get("performance") or 0
    row = db.one("insert into certificates (cert_no, user_id, score, grade, auto) values (%s,%s,%s,%s,%s) returning *",
                 (new_cert_no(), student["id"], score, grade_for(score), auto))
    co = company()
    mailer.send_mail(student["email"], f"Your certificate – {co}",
                     f"Hi {student['name']},\n\nCongratulations on completing the programme with grade {row['grade']} ({score}%).\n"
                     f"View and print your certificate: {site_url()}/certificate/{row['cert_no']}\n"
                     f"Anyone can verify it at: {site_url()}/verify/{row['cert_no']}\n\n– {co}")
    return row


# ------------------------------------------------------------------ payments + ads
AD_FLAGS = ("100% placement", "guaranteed", "job guarantee", "assured placement", "assured job", "no.1", "no. 1", "number one", "#1",
            "best in pune", "cheapest", "100% result", "100% selection")


def ad_flag_reason(headline, body):
    t = f"{headline} {body}".lower()
    hits = [f for f in AD_FLAGS if f in t]
    return ("Claims that need checking: " + ", ".join(hits)) if hits else None


def create_payment(kind, payer_name, payer_email, amount_paise, description, application_id=None, campaign_id=None, meta=None):
    import json
    from security import new_token
    return db.one("""insert into payments (kind, application_id, campaign_id, payer_name, payer_email, description, amount_paise, token, meta)
                     values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
                  (kind, application_id, campaign_id, payer_name, payer_email, description, amount_paise, new_token(18), json.dumps(meta or {})))


def pay_url(payment):
    return f"{site_url()}/pay/{payment['token']}"


def activate_campaign(cid):
    """After payment: start on its own unless the copy needs a human look (then it waits in 'pending_review')."""
    from security import new_token, hash_token
    c = db.one("select c.*, p.days from ad_campaigns c join ad_packages p on p.id=c.package_id where c.id=%s", (cid,))
    if not c or c["status"] not in ("awaiting_payment",):
        return
    reason = ad_flag_reason(c["headline"], c["body"])
    if reason:
        db.run("update ad_campaigns set status='pending_review', flag_reason=%s where id=%s", (reason, cid))
        log_auto("ad_held", f"Campaign #{cid} '{c['headline']}' held for review. {reason}", "campaign", cid)
        mailer.send_mail(c["contact_email"], f"Your advertisement is being checked – {company()}",
                         f"Hi {c['advertiser_name']},\n\nPayment received. A person will check your advertisement shortly. If we cannot approve it you get a full refund.\n\n– {company()}")
        return
    start_campaign(cid)


def start_campaign(cid):
    from security import new_token, hash_token
    c = db.one("select c.*, p.days from ad_campaigns c join ad_packages p on p.id=c.package_id where c.id=%s", (cid,))
    start = today()
    end = start + timedelta(days=c["days"] - 1)
    tok = new_token(18)
    db.run("update ad_campaigns set status='active', starts_on=%s, ends_on=%s, flag_reason=null, manage_token=%s where id=%s", (start, end, hash_token(tok), cid))
    mailer.send_mail(c["contact_email"], f"Your advertisement is live – {company()}",
                     f"Hi {c['advertiser_name']},\n\nYour advertisement '{c['headline']}' is live from {start:%d %b} to {end:%d %b %Y}.\n"
                     f"Live report (views and clicks): {site_url()}/ad-report/{tok}\n\n– {company()}")
    log_auto("ad_started", f"Campaign #{cid} '{c['headline']}' started automatically ({start} to {end})", "campaign", cid)
