"""Public Class Directory API: search, class page, enquiries, reviews, 'list your class', ownership claim, owner page."""
import json
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request

import db
import mailer
import moderation
import services
from classes_common import CATEGORIES, clean_class, clean_phone
from security import EMAIL_RE, allow, auth, bad, client_ip, hash_token, ip_hash, new_token, text

bp = Blueprint("classes", __name__, url_prefix="/api")

LIST_SELECT = """select c.id, c.slug, c.name, c.category, c.area, c.mode, c.verified, c.rating_count,
       case when c.rating_count > 0 then round(c.rating_sum::numeric / c.rating_count, 1) end as rating,
       f.fee_from, f.fee_to, f.course_count, c.fees_updated_at, left(c.description, 200) as blurb,
       (c.fees_updated_at is not null and c.fees_updated_at < now() - make_interval(days => %s)) as fees_stale
  from classes c
  left join lateral (select min(fee_min) as fee_from, max(fee_max) as fee_to, count(*) as course_count
                     from class_courses where class_id = c.id) f on true"""


def _like(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _int(name, default=None, lo=0, hi=10**9):
    v = request.args.get(name)
    if v in (None, ""):
        return default
    try:
        return max(lo, min(hi, int(v)))
    except ValueError:
        bad(f"{name} must be a number.")


def stale_days():
    return services.setting_int("stale_fee_days", 180)


def short_name(name):
    parts = (name or "Anonymous").split()
    return parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")


# ======================================================================= search
@bp.get("/classes")
def list_classes():
    q = (request.args.get("q") or "").strip()[:80]
    where, args = ["c.status = 'live'"], []
    if q:
        like = _like(q)
        where.append("""(c.name ilike %s or c.category ilike %s or c.area ilike %s or c.description ilike %s
                        or exists (select 1 from class_courses cc where cc.class_id = c.id and cc.title ilike %s))""")
        args += [like] * 5
    for col, key in (("c.category", "category"), ("c.area", "area")):
        v = (request.args.get(key) or "").strip()
        if v:
            where.append(f"lower({col}) = lower(%s)")
            args.append(v)
    mode = (request.args.get("mode") or "").strip().lower()
    if mode:
        modes = {"offline": ["offline", "hybrid"], "online": ["online", "hybrid"], "hybrid": ["hybrid"]}.get(mode)
        if not modes:
            bad("Mode must be offline, online or hybrid.")
        where.append("c.mode = any(%s)")
        args.append(modes)
    lo, hi = _int("fee_min"), _int("fee_max")
    if lo is not None:
        where.append("f.fee_to >= %s")
        args.append(lo)
    if hi is not None:
        where.append("f.fee_from <= %s")
        args.append(hi)
    if request.args.get("verified") == "1":
        where.append("c.verified")
    # Organic order can never be bought: ratings are smoothed (so 1 five-star review does not beat 40 good ones) and nothing else ranks.
    order = {
        "fee_low": "f.fee_from asc nulls last, c.name",
        "fee_high": "f.fee_to desc nulls last, c.name",
        "newest": "c.created_at desc",
        "name": "c.name",
    }.get(request.args.get("sort"), "(c.rating_sum + 3 * 3.5)::numeric / (c.rating_count + 3) desc, c.rating_count desc, c.name")
    page = _int("page", 1, 1, 1000)
    per = _int("per_page", 12, 1, 30)
    base = f" where {' and '.join(where)}"
    total = db.one(f"select count(*) as n from classes c left join lateral (select min(fee_min) as fee_from, max(fee_max) as fee_to from class_courses where class_id=c.id) f on true{base}", tuple(args))["n"]
    rows = db.q(f"{LIST_SELECT}{base} order by {order} limit %s offset %s", (stale_days(),) + tuple(args) + (per, (page - 1) * per))
    return jsonify(classes=rows, total=total, page=page, per_page=per, pages=max(1, -(-total // per)))


@bp.get("/classes/facets")
def facets():
    cats = db.q("select category as name, count(*) as n from classes where status='live' group by category order by n desc, category")
    areas = db.q("select area as name, count(*) as n from classes where status='live' group by area order by n desc, area")
    return jsonify(categories=cats, areas=areas, known_categories=CATEGORIES,
                   modes=[{"name": m, "n": db.one("select count(*) as n from classes where status='live' and mode=%s", (m,))["n"]} for m in ("offline", "online", "hybrid")])


def class_detail(slug, include_hidden=False):
    c = db.one("select * from classes where slug=%s" + ("" if include_hidden else " and status='live'"), (slug,))
    if not c:
        bad("Class not found.", 404)
    courses = db.q("select id, title, duration, fee_min, fee_max, batch_timing from class_courses where class_id=%s order by sort_order, id", (c["id"],))
    reviews = db.q("""select r.id, r.rating, r.body, r.created_at, u.name from class_reviews r join users u on u.id=r.user_id
                      where r.class_id=%s and r.status='live' order by r.created_at desc limit 50""", (c["id"],))
    for r in reviews:
        r["name"] = short_name(r["name"])
    dist = {str(i): 0 for i in range(1, 6)}
    for r in db.q("select rating, count(*) as n from class_reviews where class_id=%s and status='live' group by rating", (c["id"],)):
        dist[str(r["rating"])] = r["n"]
    out = {k: c[k] for k in ("id", "slug", "name", "category", "area", "address", "phone", "whatsapp", "website", "mode", "description",
                             "verified", "status", "fees_updated_at", "rating_count", "created_at")}
    out["rating"] = round(c["rating_sum"] / c["rating_count"], 1) if c["rating_count"] else None
    out["claimed"] = bool(c["manage_token_hash"])
    out["fees_stale"] = bool(c["fees_updated_at"] and c["fees_updated_at"] < datetime.now(timezone.utc) - timedelta(days=stale_days()))
    out["whatsapp_link"] = services.wa_link(c["whatsapp"], f"Hi, I found {c['name']} on the class directory.") if c["whatsapp"] else None
    return {"class": out, "courses": courses, "reviews": reviews, "rating_distribution": dist}


@bp.get("/classes/<slug>")
def get_class(slug):
    return jsonify(class_detail(slug))


# ======================================================================= enquiry (lead to the institute)
@bp.post("/classes/<slug>/enquiry")
def enquiry(slug):
    b = request.get_json(silent=True) or {}
    if b.get("website"):                                   # honeypot
        return jsonify(message="Thanks! The institute will call you back."), 201
    c = db.one("select * from classes where slug=%s and status='live'", (slug,))
    if not c:
        bad("Class not found.", 404)
    if not allow(f"enq:{client_ip()}", 6, 3600):
        bad("Too many enquiries from this connection. Please try again later.", 429)
    name = text(b, "name", 80, True, "Your name")
    phone = clean_phone(b.get("phone"), "Your phone number")
    message = text(b, "message", 600)
    if not allow(f"enq:{c['id']}:{phone}", 1, 86400):
        bad("You have already sent an enquiry to this institute today. They will call you back soon.", 429)
    row = db.one("insert into class_enquiries (class_id, name, phone, message, ip_hash) values (%s,%s,%s,%s,%s) returning id",
                 (c["id"], name, phone, message, ip_hash()))
    note = (f"New enquiry for {c['name']}\nName: {name}\nPhone: {phone}\n" + (f"Message: {message}\n" if message else "")
            + "Please call back within 24 hours.")
    if c["email"]:
        mailer.send_mail(c["email"], f"New enquiry for {c['name']}", note + f"\n\nMark it as contacted: {services.site_url()}/manage")
    mailer.send_whatsapp(c["whatsapp"] or c["phone"], note)
    services.log_auto("enquiry_forwarded", f"Enquiry #{row['id']} sent to {c['name']}", "enquiry", row["id"])
    return jsonify(message="Thanks! The institute has been notified and will call you back."), 201


# ======================================================================= reviews
@bp.post("/classes/<slug>/review")
@auth("member", "student")
def review(slug):
    u = g.user
    c = db.one("select * from classes where slug=%s and status='live'", (slug,))
    if not c:
        bad("Class not found.", 404)
    if not u["email_verified"]:
        bad("Please confirm your email address before posting a review. Check your inbox for the link.", 403)
    if c["email"] and c["email"].lower() == u["email"].lower():
        bad("You cannot review your own institute.", 403)
    if not allow(f"review:{u['id']}", 5, 3600):
        bad("You are posting too fast. Please try again later.", 429)
    b = request.get_json(silent=True) or {}
    try:
        rating = int(b.get("rating"))
    except (TypeError, ValueError):
        bad("Choose a star rating from 1 to 5.")
    if not 1 <= rating <= 5:
        bad("Choose a star rating from 1 to 5.")
    body = text(b, "body", 1200)
    if body and len(body) < 10:
        bad("Please write a little more, or leave the text empty and give only a rating.")
    ih = ip_hash()
    status, reason = moderation.screen(c["id"], u["id"], rating, body, ih)
    row = db.one("""insert into class_reviews (class_id, user_id, rating, body, status, flag_reason, ip_hash)
                    values (%s,%s,%s,%s,%s,%s,%s)
                    on conflict (class_id, user_id) do update set rating=excluded.rating, body=excluded.body, status=excluded.status,
                       flag_reason=excluded.flag_reason, ip_hash=excluded.ip_hash, created_at=now()
                    returning id, (xmax = 0) as is_new""",
                 (c["id"], u["id"], rating, body, status, reason if status != "live" else None, ih))
    moderation.record(row["id"], status, reason)
    services.refresh_rating(c["id"])
    msg = {"live": "Thanks! Your review is now live.",
           "held": "Thanks! Your review is being checked by our team before it appears.",
           "pending": "Thanks! Your review will appear once our team approves it."}[status]
    return jsonify(status=status, message=msg, updated=not row["is_new"]), 201


# ======================================================================= OTP (proves the institute owns the phone)
def _pepper(scope, ref_id, code):
    return hash_token(f"{code}:{scope}:{ref_id}:{current_app.config['SECRET_KEY']}")


def send_otp(scope, ref_id, phone, email=None):
    if not allow(f"otp:{phone}", 3, 3600):
        bad("Too many codes requested for this number. Please try again in an hour.", 429)
    code = f"{secrets.randbelow(900000) + 100000}"
    db.run("""insert into class_otps (scope, ref_id, phone, code_hash, expires_at) values (%s,%s,%s,%s,%s)""",
           (scope, ref_id, phone, _pepper(scope, ref_id, code), datetime.now(timezone.utc) + timedelta(minutes=10)))
    msg = f"{services.company()} verification code: {code}. Valid for 10 minutes. Do not share it."
    mailer.send_sms(phone, msg)
    if email:
        mailer.send_mail(email, "Your verification code", msg)
    return code


def check_otp(scope, ref_id, code):
    row = db.one("""select * from class_otps where scope=%s and ref_id=%s and used_at is null and expires_at > now()
                    order by id desc limit 1""", (scope, ref_id))
    code = (code or "").strip()
    if not row or row["attempts"] >= 5:
        bad("That code has expired or too many wrong attempts were made. Please request a new code.", 400)
    db.run("update class_otps set attempts = attempts + 1 where id=%s", (row["id"],))
    import hmac
    if not hmac.compare_digest(row["code_hash"], _pepper(scope, ref_id, code)):
        bad("That code is not correct.", 400)
    db.run("update class_otps set used_at=now() where id=%s", (row["id"],))
    return row


def _dev(code):
    """In development (DEV_SHOW_OTP=1, never in production) the code is returned so you can try the flow without an SMS gateway."""
    return {"dev_otp": code} if current_app.config.get("DEV_SHOW_OTP") and not current_app.config.get("PRODUCTION") else {}


def mask(phone):
    return phone[:2] + "x" * max(0, len(phone) - 4) + phone[-2:]


# ======================================================================= list your class
@bp.post("/classes/submit")
def submit_class():
    b = request.get_json(silent=True) or {}
    if b.get("website_hp"):
        return jsonify(message="Thanks! We will review your listing."), 201
    if not allow(f"submit:{client_ip()}", 4, 3600):
        bad("Too many submissions from this connection. Please try again later.", 429)
    if not b.get("accept_terms"):
        bad("Please accept the Terms of Use and Privacy Policy to continue.")
    f = clean_class(b)
    courses = services.clean_courses(b.get("courses"))
    sname = text(b, "submitter_name", 80, True, "Your name")
    sphone = clean_phone(b.get("submitter_phone") or f["phone"], "Your phone number")
    semail = text(b, "submitter_email", 160).lower() or f.get("email")
    if semail and not EMAIL_RE.match(semail):
        bad("Please enter a valid email address.")
    row = db.one("""insert into class_submissions (name,category,area,address,phone,whatsapp,email,website,mode,description,courses,
                      submitter_name,submitter_phone,submitter_email) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                 (f["name"], f["category"], f["area"], f["address"], f["phone"], f["whatsapp"], f["email"], f["website"], f["mode"],
                  f["description"], json.dumps(courses), sname, sphone, semail))
    services.record_consent(("terms", "privacy"), "class_submission", None, semail, client_ip())
    code = send_otp("submission", row["id"], sphone, semail)
    return jsonify(submission_id=row["id"], otp_sent_to=mask(sphone),
                   message="Thanks! Enter the code we sent to your phone to get the Verified badge. We review every listing before it goes live.",
                   **_dev(code)), 201


@bp.post("/classes/submit/<int:sid>/verify")
def verify_submission(sid):
    s = db.one("select * from class_submissions where id=%s and status='pending'", (sid,))
    if not s:
        bad("Submission not found.", 404)
    if not allow(f"otpv:{client_ip()}", 20, 3600):
        bad("Too many attempts. Please try again later.", 429)
    check_otp("submission", sid, (request.get_json(silent=True) or {}).get("code"))
    db.run("update class_submissions set phone_verified=true where id=%s", (sid,))
    return jsonify(ok=True, message="Phone verified. Your listing will get a Verified badge once it is approved.")


@bp.post("/classes/submit/<int:sid>/resend")
def resend_submission_otp(sid):
    s = db.one("select * from class_submissions where id=%s and status='pending' and not phone_verified", (sid,))
    if not s:
        bad("Submission not found.", 404)
    code = send_otp("submission", sid, s["submitter_phone"], s["submitter_email"])
    return jsonify(ok=True, **_dev(code))


# ======================================================================= claim a listing (institute proves ownership)
@bp.post("/classes/<slug>/claim")
def claim_start(slug):
    c = db.one("select id, phone, email, name from classes where slug=%s and status='live'", (slug,))
    if not c:
        bad("Class not found.", 404)
    code = send_otp("claim", c["id"], c["phone"], c["email"])
    return jsonify(otp_sent_to=mask(c["phone"]), **_dev(code))


@bp.post("/classes/<slug>/claim/verify")
def claim_verify(slug):
    c = db.one("select * from classes where slug=%s and status='live'", (slug,))
    if not c:
        bad("Class not found.", 404)
    if not allow(f"otpv:{client_ip()}", 20, 3600):
        bad("Too many attempts. Please try again later.", 429)
    check_otp("claim", c["id"], (request.get_json(silent=True) or {}).get("code"))
    token = new_token()
    db.run("update classes set verified=true, claimed_at=now(), manage_token_hash=%s, updated_at=now() where id=%s", (hash_token(token), c["id"]))
    link = f"{services.site_url()}/manage/{token}"
    if c["email"]:
        mailer.send_mail(c["email"], f"You can now manage {c['name']}",
                         f"Your phone number was verified and your listing now has the Verified badge.\n\nManage fees, courses and enquiries here:\n{link}\n\nKeep this link private.")
    services.log_auto("listing_verified", f"{c['name']} verified by phone OTP (claim)", "class", c["id"])
    return jsonify(manage_token=token, manage_url=link)


# ======================================================================= owner page (token link, no account needed)
def _owned(token):
    if not allow(f"manage:{client_ip()}", 120, 3600):
        bad("Too many requests.", 429)
    c = db.one("select * from classes where manage_token_hash=%s", (hash_token(token or "-"),))
    if not c:
        bad("This management link is not valid. Use 'Claim this listing' on your class page to get a new one.", 404)
    return c


@bp.get("/manage/<token>")
def manage_get(token):
    c = _owned(token)
    d = class_detail(c["slug"], include_hidden=True)
    d["enquiries"] = db.q("select id, name, phone, message, status, created_at, contacted_at from class_enquiries where class_id=%s order by id desc limit 100", (c["id"],))
    d["class"].update(email=c["email"], status=c["status"])
    d["known_categories"] = CATEGORIES
    return jsonify(d)


@bp.put("/manage/<token>")
def manage_update(token):
    c = _owned(token)
    b = request.get_json(silent=True) or {}
    b = {k: v for k, v in b.items() if k in ("name", "category", "area", "address", "whatsapp", "email", "website", "mode", "description")}
    f = clean_class(b, partial=True)
    if f:
        sets = ", ".join(f"{k}=%s" for k in f)
        db.run(f"update classes set {sets}, updated_at=now() where id=%s", tuple(f.values()) + (c["id"],))
    return jsonify(ok=True)


@bp.put("/manage/<token>/courses")
def manage_courses(token):
    c = _owned(token)
    courses = services.clean_courses((request.get_json(silent=True) or {}).get("courses"))
    with db.tx() as t:
        services.replace_courses(t, c["id"], courses)
    return jsonify(ok=True, count=len(courses))


@bp.post("/manage/<token>/enquiries/<int:eid>/contacted")
def manage_contacted(token, eid):
    c = _owned(token)
    n = db.run("update class_enquiries set status='contacted', contacted_at=now() where id=%s and class_id=%s and status='new'", (eid, c["id"]))
    return jsonify(ok=True, changed=n)
