"""Payment gateway. Razorpay when RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are set, otherwise a clearly-labelled DEMO gateway
(no real money). The demo gateway is refused when PRODUCTION=1."""
import hashlib
import hmac
import uuid

import requests
from flask import current_app

from security import bad

API = "https://api.razorpay.com/v1"


def mode():
    c = current_app.config
    return "razorpay" if c.get("RAZORPAY_KEY_ID") and c.get("RAZORPAY_KEY_SECRET") else "demo"


def _auth():
    c = current_app.config
    return (c["RAZORPAY_KEY_ID"], c["RAZORPAY_KEY_SECRET"])


def ensure_usable():
    if mode() == "demo" and current_app.config.get("PRODUCTION"):
        bad("Online payments are not configured yet. Please contact us.", 503)


def create_order(amount_paise, receipt, notes=None):
    """-> (provider, order_id)"""
    ensure_usable()
    if mode() == "demo":
        return "demo", f"demo_order_{uuid.uuid4().hex[:14]}"
    r = requests.post(f"{API}/orders", auth=_auth(), timeout=20,
                      json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40], "notes": notes or {}})
    if r.status_code >= 300:
        current_app.logger.error("Razorpay order failed: %s %s", r.status_code, r.text[:300])
        bad("The payment provider is not responding. Please try again in a minute.", 502)
    return "razorpay", r.json()["id"]


def _sig(secret, msg):
    return hmac.new(secret.encode(), msg.encode() if isinstance(msg, str) else msg, hashlib.sha256).hexdigest()


def demo_signature(order_id, payment_id):
    return _sig(current_app.config["SECRET_KEY"], f"{order_id}|{payment_id}")


def verify_payment(provider, order_id, payment_id, signature):
    """Checkout signature check (Razorpay: HMAC-SHA256 of 'order_id|payment_id' with the key secret)."""
    if not (order_id and payment_id and signature):
        return False
    secret = current_app.config["RAZORPAY_KEY_SECRET"] if provider == "razorpay" else current_app.config["SECRET_KEY"]
    if provider == "razorpay" and not secret:
        return False
    return hmac.compare_digest(_sig(secret, f"{order_id}|{payment_id}"), signature)


def verify_webhook(raw_body, signature):
    secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    return hmac.compare_digest(_sig(secret, raw_body), signature)


def refund(provider, payment_id, amount_paise):
    """-> True when the money was returned (or the payment was a demo one)."""
    if provider == "demo":
        return True
    r = requests.post(f"{API}/payments/{payment_id}/refund", auth=_auth(), json={"amount": amount_paise}, timeout=20)
    if r.status_code >= 300:
        current_app.logger.error("Razorpay refund failed: %s %s", r.status_code, r.text[:300])
        return False
    return True
