from flask import Blueprint, current_app, jsonify, request

import ai
import automation
import db
import mailer
import services
import storage
from core import site_settings
from security import EMAIL_RE, allow, bad, client_ip, text

bp = Blueprint("public", __name__, url_prefix="/api")

PUBLIC_KEYS = ("company_name", "tagline", "contact_email", "adsense_client", "adsense_slot", "enrolment_fee_inr")


@bp.get("/public/info")
def info():
    s = site_settings()
    roles = [r["title"] for r in db.q("select title from open_roles where active order by title")]
    import gateway
    pay_ok = gateway.mode() == "razorpay" or not current_app.config.get("PRODUCTION")      # false = no way to take real money yet
    return jsonify(settings={k: s.get(k, "") for k in PUBLIC_KEYS}, roles=roles, payments_enabled=pay_ok)


@bp.post("/applications")
def apply():
    f = request.form
    if f.get("website"):                      # honeypot: real people never fill this hidden field
        return jsonify(message="Application received."), 201
    if not allow(f"apply:{client_ip()}", 5, 3600):
        bad("Too many applications from this connection. Please try again later.", 429)

    body = {k: f.get(k, "") for k in ("name", "email", "phone", "college", "role", "message")}
    name = text(body, "name", 120, True, "Full name")
    email = text(body, "email", 160, True, "Email").lower()
    phone = text(body, "phone", 20, True, "Phone number")
    college = text(body, "college", 200, True, "College name")
    role = text(body, "role", 120, True, "Role")
    message = text(body, "message", 1500)
    if len(name) < 2:
        bad("Please enter your full name.")
    if not EMAIL_RE.match(email):
        bad("Please enter a valid email address.")
    digits = "".join(c for c in phone if c.isdigit())
    if not 8 <= len(digits) <= 15:
        bad("Please enter a valid phone number.")
    if not db.one("select 1 from open_roles where title=%s and active", (role,)):
        bad("Please choose one of the listed roles.")
    if db.one("select 1 from applications where lower(email)=%s and role_applied=%s", (email, role)):
        bad("You have already applied for this role with this email. We will contact you if you are shortlisted.", 409)
    if f.get("accept_terms") not in ("1", "true", "on", "yes"):
        bad("Please tick the box to accept the Terms of Use, Privacy Policy and Internship Terms.")
    file = request.files.get("resume")
    if not file or not file.filename:
        bad("Please attach your resume.")
    try:
        ext, data = storage.validate_resume(file)
    except ValueError as e:
        bad(str(e))
    try:
        key = storage.save_resume(ext, data)
    except Exception:
        current_app.logger.exception("resume upload failed")
        bad("We could not save your resume right now. Please try again in a minute.", 502)

    row = db.one("""insert into applications (name,email,phone,college,role_applied,message,resume_path,resume_name)
                     values (%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
                 (name, email, phone, college, role, message, key, (file.filename or "resume")[:160]))
    services.record_consent(("terms", "privacy", "internship-terms"), "apply", None, email, client_ip())
    try:
        ai.screen_application(row["id"])              # sorts the admin list by skill match; never rejects anyone
    except Exception:
        current_app.logger.exception("resume screening failed")
    company = site_settings().get("company_name", "our team")
    link = automation.status_link(row["id"])
    sent_test = services.automation_on() and automation.send_test_invite(row)
    if not sent_test:
        mailer.send_mail(email, f"We received your application – {company}",
                         f"Hi {name},\n\nThank you for applying for {role} at {company}. We have received your application.\n"
                         f"Track your application any time: {link}\nIf you are shortlisted, we will get back to you on this email address.\n\n– {company}")
    return jsonify(message=("We have received your application and emailed you a link to take the short online test." if sent_test
                            else "We have received your application. If you are shortlisted, we will get back to you by email."),
                   status_url=f"/status/{row['access_token'] or link.rsplit('/', 1)[-1]}"), 201
