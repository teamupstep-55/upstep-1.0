"""Validation shared by the public form, the owner page, the admin screens and the CSV import."""
import re

from security import EMAIL_RE, bad
from services import digits

CATEGORIES = ["Coding & IT", "Data Science & AI", "Design & Creative", "Digital Marketing", "Spoken English", "IELTS & Foreign Languages",
              "Competitive Exams", "School Tuition", "Commerce & Accounting", "Music", "Dance", "Fitness & Yoga", "Skills & Hobbies", "Other"]
_CAT_LOOKUP = {c.lower(): c for c in CATEGORIES}
MODES = ("offline", "online", "hybrid")


def clean_phone(v, label="Phone number", required=True):
    v = (v or "").strip() if isinstance(v, str) else ""
    if not v:
        if required:
            bad(f"{label} is required.")
        return None
    d = digits(v)
    if d.startswith("91") and len(d) == 12:
        d = d[2:]
    if d.startswith("0") and len(d) == 11:
        d = d[1:]
    if not 10 <= len(d) <= 12:
        bad(f"{label} does not look right. Enter a 10-digit mobile number.")
    return d


def clean_url(v, label="Website", required=False):
    v = (v or "").strip() if isinstance(v, str) else ""
    if not v:
        if required:
            bad(f"{label} is required.")
        return None
    if not re.match(r"^https?://", v, re.I):
        if "." in v and " " not in v and not re.match(r"^[a-z]+:", v, re.I):
            v = "https://" + v
        else:
            bad(f"{label} must start with http:// or https://")
    if len(v) > 300 or " " in v or not re.match(r"^https?://[^\s/]+\.[^\s/]+", v, re.I):
        bad(f"{label} does not look like a valid web address.")
    return v


def clean_category(v):
    v = (v or "").strip()
    if not v:
        bad("Category is required.")
    return _CAT_LOOKUP.get(v.lower()) or v[:60]


def clean_class(b, partial=False):
    """Returns a dict of cleaned class fields. With partial=True only keys present in `b` are validated."""
    out = {}

    def has(k):
        return (k in b) or not partial

    def s(k, maxlen, label, required=False):
        v = b.get(k)
        v = v.strip() if isinstance(v, str) else ""
        if required and not v:
            bad(f"{label} is required.")
        if len(v) > maxlen:
            bad(f"{label} is too long (max {maxlen} characters).")
        return v

    if has("name"):
        out["name"] = s("name", 120, "Class name", True)
        if len(out["name"]) < 3:
            bad("Class name is too short.")
    if has("category"):
        out["category"] = clean_category(b.get("category"))
    if has("area"):
        out["area"] = s("area", 60, "Area", True)
    if has("address"):
        out["address"] = s("address", 240, "Address") or None
    if has("phone"):
        out["phone"] = clean_phone(b.get("phone"))
    if has("whatsapp"):
        out["whatsapp"] = clean_phone(b.get("whatsapp"), "WhatsApp number", False)
    if has("email"):
        e = s("email", 160, "Email").lower()
        if e and not EMAIL_RE.match(e):
            bad("Please enter a valid email address.")
        out["email"] = e or None
    if has("website"):
        out["website"] = clean_url(b.get("website"))
    if has("mode"):
        m = (b.get("mode") or "offline").strip().lower()
        if m not in MODES:
            bad("Mode must be offline, online or hybrid.")
        out["mode"] = m
    if has("description"):
        out["description"] = s("description", 2000, "Description")
    return out
