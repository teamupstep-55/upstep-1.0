"""Outgoing messages.
Email: SMTP when SMTP_HOST is set, otherwise only saved in the `outbox` table.
SMS / WhatsApp: saved in `outbox`; also POSTed as JSON {"to","message"} to SMS_WEBHOOK_URL / WHATSAPP_WEBHOOK_URL when set,
so any gateway (MSG91, Twilio, WhatsApp Cloud API wrapper, n8n ...) can be plugged in without code changes."""
import smtplib
from email.message import EmailMessage

import requests
from flask import current_app

import db


def _log(channel, to, subject, body, status):
    db.run("insert into outbox (to_email, subject, body, status, channel) values (%s,%s,%s,%s,%s)",
           (to, subject[:200], body, status, channel))


def _smtp_send(cfg, to_email, subject, body, attachments=None):
    msg = EmailMessage()
    msg["From"] = cfg.get("SMTP_FROM") or cfg.get("SMTP_USER") or "no-reply@example.com"
    msg["To"], msg["Subject"] = to_email, subject
    msg.set_content(body)
    for name, mime, data in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream", filename=name)
    with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as s:
        s.starttls()
        if cfg.get("SMTP_USER"):
            s.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD", ""))
        s.send_message(msg)


def sent_last_24h():
    return db.one("select count(*) as n from outbox where channel='email' and status='sent' and sent_at > now() - interval '24 hours'")["n"]


def send_mail(to_email, subject, body, attachments=None, low=False):
    """attachments: [(filename, mime 'type/subtype', bytes)].
    EMAIL_DAILY_LIMIT (free email plans cap sending, e.g. 100 a day): reminders and digests (low=True) are queued once 80% of the
    budget is used, everything else is sent until the full budget is used; queued mail goes out later (see flush_queue)."""
    cfg = current_app.config
    status, sent_at = "logged", None
    if cfg.get("SMTP_HOST") and to_email:
        limit = int(cfg.get("EMAIL_DAILY_LIMIT") or 0)
        used = sent_last_24h() if limit else 0
        if limit and (used >= limit or (low and used >= int(limit * 0.8))):
            status = "queued"
        else:
            try:
                _smtp_send(cfg, to_email, subject, body, attachments)
                status, sent_at = "sent", True
            except Exception:
                current_app.logger.exception("SMTP send failed")
                status = "failed"
    db.run("insert into outbox (to_email, subject, body, status, channel, sent_at) values (%s,%s,%s,%s,'email', case when %s then now() end)",
           (to_email or "", subject[:200], body, status, bool(sent_at)))
    return status


def flush_queue(max_items=50):
    """Send queued emails, oldest first, while the daily budget (minus 20% headroom for important mail) allows."""
    cfg = current_app.config
    limit = int(cfg.get("EMAIL_DAILY_LIMIT") or 0)
    if not cfg.get("SMTP_HOST"):
        return 0
    sent = 0
    for row in db.q("select id, to_email, subject, body from outbox where status='queued' and channel='email' order by id limit %s", (max_items,)):
        if limit and sent_last_24h() >= int(limit * 0.8):
            break
        try:
            _smtp_send(cfg, row["to_email"], row["subject"], row["body"])
            db.run("update outbox set status='sent', sent_at=now() where id=%s", (row["id"],))
            sent += 1
        except Exception:
            current_app.logger.exception("SMTP send failed for queued mail %s", row["id"])
            db.run("update outbox set status='failed' where id=%s", (row["id"],))
    return sent


def _webhook(channel, to, body):
    url = current_app.config.get(f"{channel.upper()}_WEBHOOK_URL")
    if not url:
        return "logged"
    try:
        r = requests.post(url, json={"to": to, "message": body}, timeout=10)
        return "sent" if r.status_code < 300 else "failed"
    except Exception:
        current_app.logger.exception("%s webhook failed", channel)
        return "failed"


def send_sms(phone, body):
    status = _webhook("sms", phone, body)
    _log("sms", phone, "SMS", body, status)
    return status


def send_whatsapp(phone, body):
    status = _webhook("whatsapp", phone, body)
    _log("whatsapp", phone, "WhatsApp", body, status)
    return status
