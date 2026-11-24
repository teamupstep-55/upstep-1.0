"""Lets a free outside scheduler (GitHub Actions, cron-job.org ...) run the automations. Needed on hosts that put the app to sleep when idle,
because the in-process scheduler (AUTO_SCHEDULER=1) cannot run while the app is asleep. The request itself also wakes the app."""
import hmac

from flask import Blueprint, current_app, jsonify, request

import automation
from security import allow, bad, client_ip

bp = Blueprint("cron", __name__, url_prefix="/api/cron")


def _key():
    h = request.headers.get("Authorization", "")
    return h[7:] if h.lower().startswith("bearer ") else (request.headers.get("X-Cron-Key") or request.args.get("key") or "")


@bp.route("/run", methods=["GET", "POST"])
def run():
    secret = current_app.config.get("CRON_SECRET")
    if not secret:
        return jsonify(error="Not found."), 404                   # switched off unless you set CRON_SECRET
    if not allow(f"cron:{client_ip()}", 60, 3600):
        bad("Too many requests.", 429)
    if not hmac.compare_digest(_key().encode(), secret.encode()):
        bad("Forbidden.", 403)
    return jsonify(results=automation.run_all())
