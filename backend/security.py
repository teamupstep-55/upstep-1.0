import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def bad(message, status=400):
    raise ApiError(message, status)


# ---------------------------------------------------------------- tokens & auth
def make_token(user):
    exp = datetime.now(timezone.utc) + timedelta(hours=current_app.config["TOKEN_HOURS"])
    return jwt.encode({"sub": str(user["id"]), "role": user["role"], "exp": exp},
                      current_app.config["SECRET_KEY"], algorithm="HS256")


def _load_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = jwt.decode(header[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
        uid = int(data["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
    return db.one("select * from users where id=%s and is_active", (uid,))


def auth(*roles):
    """@auth()  any signed-in user | @auth('admin') | @auth('staff') = admin or mentor | @auth('student')"""
    allowed = set()
    for r in roles:
        allowed |= {"admin", "mentor"} if r == "staff" else {r}

    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = _load_user()
            if not user:
                bad("Please sign in again.", 401)
            if allowed and user["role"] not in allowed:
                bad("You do not have access to this.", 403)
            g.user = user
            return fn(*a, **kw)
        return wrapper
    return deco


def staff_scope(alias="u"):
    """SQL fragment limiting students to those a mentor looks after (admins see everyone)."""
    u = g.user
    if u["role"] == "admin":
        return "", ()
    return f" and {alias}.mentor_id = %s", (u["id"],)


# ---------------------------------------------------------------- misc helpers
_hits = defaultdict(deque)


# Password hashing (scrypt) needs ~32 MB of memory per hash. Without a limit, 50 people logging in at the same moment would need
# ~300 MB and could get the app killed on a small free instance. At most 2 run at once; the others wait their turn (a login takes ~80 ms).
from werkzeug.security import check_password_hash as _check_hash, generate_password_hash as _make_hash   # noqa: E402

_HASH_SLOTS = threading.BoundedSemaphore(2)


def check_password_hash(stored, password):
    with _HASH_SLOTS:
        return _check_hash(stored, password)


def generate_password_hash(password):
    with _HASH_SLOTS:
        return _make_hash(password)


def allow(key, limit, window_s):
    """Rate limiter. Uses Redis when REDIS_URL is configured (shared by all instances), otherwise per-process memory."""
    if current_app.config.get("TESTING_NO_LIMITS"):
        return True
    r = current_app.config.get("REDIS")
    if r is not None:
        try:
            k = f"sp:rl:{key}"
            n = r.incr(k)
            if n == 1:
                r.expire(k, int(window_s))
            return n <= limit
        except Exception:               # Redis down: fall back to memory rather than blocking everyone
            current_app.logger.warning("Redis rate limiter unavailable, using memory")
    now, dq = time.time(), _hits[key]
    while dq and dq[0] < now - window_s:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def client_ip():
    """Only trust X-Forwarded-For when the app is behind a proxy you control (TRUST_PROXY=1)."""
    if current_app.config.get("TRUST_PROXY"):
        return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    return request.remote_addr or "?"


def ip_hash():
    """Stable, non-reversible id for an IP address (used for spam bursts without storing raw IPs)."""
    return hashlib.sha256(f"{client_ip()}|{current_app.config['SECRET_KEY']}".encode()).hexdigest()[:20]


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)


def password_problem(pw):
    if len(pw or "") < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain letters and numbers."
    return None


def text(body, key, maxlen, required=False, label=None):
    v = body.get(key)
    v = v.strip() if isinstance(v, str) else ""
    if required and not v:
        bad(f"{label or key.replace('_', ' ').capitalize()} is required.")
    if len(v) > maxlen:
        bad(f"{label or key.replace('_', ' ').capitalize()} is too long (max {maxlen} characters).")
    return v


def pick_date(value, label="Date", required=True):
    from datetime import date
    if not value:
        if required:
            bad(f"{label} is required.")
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        bad(f"{label} is not a valid date.")


def int_list(value):
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            bad("Invalid id in list.")
    return list(dict.fromkeys(out))
