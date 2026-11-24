"""Error alerts to your phone: set ALERT_WEBHOOK_URL (Slack, Discord, Telegram bridge, ntfy.sh ...). Optional Sentry via SENTRY_DSN."""
import hashlib
import threading
import time

import requests
from flask import current_app

_last = {}


def init_sentry(dsn):
    if not dsn:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0, send_default_pii=False)
        return True
    except Exception:
        return False


def notify(message):
    """Fire-and-forget alert, at most one per distinct message per 5 minutes."""
    url = current_app.config.get("ALERT_WEBHOOK_URL")
    if not url:
        return
    key = hashlib.md5(message[:300].encode()).hexdigest()
    now = time.time()
    if now - _last.get(key, 0) < 300:
        return
    _last[key] = now
    payload = {"text": f"[UpStep] {message[:900]}", "content": f"[UpStep] {message[:900]}"}

    def go():
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()
