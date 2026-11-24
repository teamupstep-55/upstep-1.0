"""Rule-based review screening. No AI involved: every rule is listed here and every decision is logged and reversible."""
import re

import db
from services import automation_on, log_auto, setting

URL_RE = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|in|co|net|org|io|me|xyz)\b)", re.I)
PHONE_RE = re.compile(r"(\+?\d[\s-]?){10,}")
# Small starter list (English plus common transliterated Hindi/Marathi abuse). Extend freely.
BAD_WORDS = {"fuck", "fucking", "shit", "bastard", "bitch", "asshole", "scam", "scammer", "fraud", "cheater", "chutiya", "madarchod", "bhenchod",
             "gandu", "bhosdi", "harami", "randi", "saala", "kutta", "idiot", "stupid"}


def screen(class_id, user_id, rating, body, ip_hash):
    """-> (status, reason). status is 'live', 'held' (looks like spam/abuse) or 'pending' (auto-approve switched off)."""
    reasons = []
    words = set(re.findall(r"[a-z']+", body.lower()))
    if URL_RE.search(body):
        reasons.append("contains a link")
    if PHONE_RE.search(body):
        reasons.append("contains a phone number")
    if words & BAD_WORDS:
        reasons.append("abusive or accusatory words")
    letters = [c for c in body if c.isalpha()]
    if len(letters) > 25 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        reasons.append("mostly capital letters")
    if len(body) >= 15 and db.one("select 1 from class_reviews where lower(body)=lower(%s) and not (class_id=%s and user_id=%s) limit 1",
                                  (body, class_id, user_id)):
        reasons.append("same text as another review")
    if ip_hash:
        n = db.one("select count(*) as n from class_reviews where ip_hash=%s and created_at > now() - interval '1 hour'", (ip_hash,))["n"]
        if n >= 3:
            reasons.append("several reviews from one connection in an hour")
        # shared networks (hostels, college wifi) are normal, so only a cluster of different accounts on one class counts
        d = db.one("""select count(distinct user_id) as n from class_reviews where ip_hash=%s and class_id=%s and user_id<>%s
                      and created_at > now() - interval '1 day'""", (ip_hash, class_id, user_id))["n"]
        if d >= 2:
            reasons.append("three or more accounts on one connection reviewed this class today")
    if reasons:
        return "held", "; ".join(reasons)
    if not automation_on() or setting("review_auto_approve", "1") != "1":
        return "pending", "auto-approve is off"
    return "live", "no spam signals"


def record(review_id, status, reason):
    kind = {"live": "review_auto_approved", "held": "review_held"}.get(status)
    if kind:
        log_auto(kind, f"Review #{review_id}: {reason}", "review", review_id, reversible=True)
