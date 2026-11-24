from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request

import db
import mailer
import services
from security import (EMAIL_RE, allow, auth, bad, check_password_hash, client_ip, generate_password_hash, hash_token, make_token, new_token,
                      password_problem, text)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def me_payload(u):
    out = {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
           "must_change_password": u["must_change_password"], "email_verified": u["email_verified"]}
    if u["role"] == "student" and u["mentor_id"]:
        m = db.one("select name from users where id=%s", (u["mentor_id"],))
        out["mentor_name"] = m["name"] if m else None
    return out


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    pw = body.get("password") or ""
    if not allow(f"login:{client_ip()}:{email}", 8, 300):
        bad("Too many attempts. Please wait a few minutes and try again.", 429)
    u = db.one("select * from users where lower(email)=%s", (email,))
    if not u or not u["is_active"] or not check_password_hash(u["password_hash"], pw):
        bad("Email or password is incorrect.", 401)
    return jsonify(token=make_token(u), user=me_payload(u))


@bp.get("/me")
@auth()
def me():
    return jsonify(user=me_payload(g.user))


@bp.post("/change-password")
@auth()
def change_password():
    body = request.get_json(silent=True) or {}
    if not check_password_hash(g.user["password_hash"], body.get("current") or ""):
        bad("Current password is incorrect.", 400)
    new = body.get("new") or ""
    problem = password_problem(new)
    if problem:
        bad(problem)
    if new == body.get("current"):
        bad("Choose a password different from the current one.")
    db.run("update users set password_hash=%s, must_change_password=false where id=%s",
           (generate_password_hash(new), g.user["id"]))
    return jsonify(ok=True)


# ---------------------------------------------------------------- directory members (public sign-up)
def _issue_token(user_id, kind, hours):
    raw = new_token()
    db.run("insert into auth_tokens (user_id, kind, token_hash, expires_at) values (%s,%s,%s,%s)",
           (user_id, kind, hash_token(raw), datetime.now(timezone.utc) + timedelta(hours=hours)))
    return raw


def _send_verification(u):
    raw = _issue_token(u["id"], "verify", 48)
    co = services.company()
    mailer.send_mail(u["email"], f"Confirm your email – {co}",
                     f"Hi {u['name']},\n\nPlease confirm your email address so you can post reviews:\n"
                     f"{services.site_url()}/verify-email/{raw}\n\nThis link works for 48 hours.\n\n– {co}")


@bp.post("/register")
def register():
    """Anyone can create a free account to review classes. These accounts cannot see any internship data."""
    b = request.get_json(silent=True) or {}
    if not allow(f"register:{client_ip()}", 5, 3600):
        bad("Too many sign-ups from this connection. Please try again later.", 429)
    name = text(b, "name", 80, True, "Name")
    email = text(b, "email", 160, True, "Email").lower()
    pw = b.get("password") or ""
    if len(name) < 2:
        bad("Please enter your name.")
    if not EMAIL_RE.match(email):
        bad("Please enter a valid email address.")
    problem = password_problem(pw)
    if problem:
        bad(problem)
    if not b.get("accept_terms"):
        bad("Please accept the Terms of Use and Privacy Policy to continue.")
    if db.one("select 1 from users where lower(email)=%s", (email,)):
        bad("An account with this email already exists. Try signing in or resetting your password.", 409)
    u = db.one("""insert into users (name,email,password_hash,role,email_verified) values (%s,%s,%s,'member',false) returning *""",
               (name, email, generate_password_hash(pw)))
    services.record_consent(("terms", "privacy"), "register", u["id"], email, client_ip())
    _send_verification(u)
    return jsonify(token=make_token(u), user=me_payload(u),
                   message="Account created. We emailed you a link to confirm your address."), 201


@bp.post("/verify-email")
def verify_email():
    raw = (request.get_json(silent=True) or {}).get("token") or ""
    row = db.one("select * from auth_tokens where token_hash=%s and kind='verify'", (hash_token(raw),))
    if not row or row["used_at"] or row["expires_at"] < datetime.now(timezone.utc):
        bad("This confirmation link is invalid or has expired. Request a new one from your account.", 400)
    with db.tx() as t:
        t.run("update auth_tokens set used_at=now() where id=%s", (row["id"],))
        t.run("update users set email_verified=true where id=%s", (row["user_id"],))
    return jsonify(ok=True)


@bp.post("/resend-verification")
@auth()
def resend_verification():
    if g.user["email_verified"]:
        return jsonify(ok=True, message="Your email is already confirmed.")
    if not allow(f"resend:{g.user['id']}", 3, 3600):
        bad("Please wait before requesting another email.", 429)
    _send_verification(g.user)
    return jsonify(ok=True, message="We sent you a new confirmation link.")


# ---------------------------------------------------------------- password reset by email link
@bp.post("/forgot-password")
def forgot_password():
    """Always answers the same way, so nobody can use this to find out who has an account."""
    b = request.get_json(silent=True) or {}
    email = (b.get("email") or "").strip().lower()
    if not allow(f"forgot:{client_ip()}", 5, 3600):
        bad("Too many requests. Please try again later.", 429)
    u = db.one("select * from users where lower(email)=%s and is_active", (email,)) if EMAIL_RE.match(email) else None
    if u and allow(f"forgot-user:{u['id']}", 3, 3600):
        raw = _issue_token(u["id"], "reset", 1)
        co = services.company()
        mailer.send_mail(u["email"], f"Reset your password – {co}",
                         f"Hi {u['name']},\n\nSomeone asked to reset the password for this account. If it was you, open:\n"
                         f"{services.site_url()}/reset-password/{raw}\n\nThe link works once and expires in 1 hour. "
                         f"If it was not you, ignore this email: your password has not changed.\n\n– {co}")
    return jsonify(ok=True, message="If an account exists for that email, we have sent a reset link.")


@bp.post("/reset-password")
def reset_password():
    b = request.get_json(silent=True) or {}
    raw, new = b.get("token") or "", b.get("password") or ""
    row = db.one("select * from auth_tokens where token_hash=%s and kind='reset'", (hash_token(raw),))
    if not row or row["used_at"] or row["expires_at"] < datetime.now(timezone.utc):
        bad("This reset link is invalid or has expired. Please request a new one.", 400)
    problem = password_problem(new)
    if problem:
        bad(problem)
    with db.tx() as t:
        t.run("update auth_tokens set used_at=now() where id=%s", (row["id"],))
        t.run("update auth_tokens set used_at=now() where user_id=%s and kind='reset' and used_at is null", (row["user_id"],))
        t.run("update users set password_hash=%s, must_change_password=false where id=%s", (generate_password_hash(new), row["user_id"]))
    return jsonify(ok=True)
