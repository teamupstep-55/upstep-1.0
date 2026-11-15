"""Payments: public checkout (Razorpay or demo), webhook, invoice, and the admin payments screen."""
import html
import json

from flask import Blueprint, Response, current_app, g, jsonify, request

import db
import gateway
import mailer
import services
from security import ApiError, allow, auth, bad, client_ip, text

bp = Blueprint("payments", __name__, url_prefix="/api")


def get_payment(token):
    p = db.one("select * from payments where token=%s", (token or "-",))
    if not p:
        bad("This payment link is not valid.", 404)
    return p


def mark_paid(pid, provider_payment_id):
    """Idempotent: webhook and browser may both report the same payment."""
    row = db.one("""update payments set status='paid', paid_at=now(), provider_payment_id=%s,
                       invoice_no='UP-' || to_char(now(),'YYYY') || '-' || nextval('invoice_seq')
                    where id=%s and status in ('created','failed') returning *""", (provider_payment_id, pid))
    if not row:
        return db.one("select * from payments where id=%s", (pid,)), False
    mailer.send_mail(row["payer_email"], f"Payment received – invoice {row['invoice_no']}",
                     f"Hi {row['payer_name']},\n\nWe received ₹{row['amount_paise'] / 100:,.2f} for: {row['description']}.\n"
                     f"Invoice: {services.site_url()}/api/pay/{row['token']}/invoice\n\n– {services.company()}")
    services.log_auto("payment_paid", f"{row['invoice_no']}: ₹{row['amount_paise'] / 100:,.0f} from {row['payer_name']} ({row['kind']})", "payment", row["id"])
    try:
        if row["kind"] == "enrolment" and row["application_id"]:
            meta = row["meta"] if isinstance(row["meta"], dict) else json.loads(row["meta"] or "{}")
            start = None
            if meta.get("start_date"):
                from datetime import date
                start = date.fromisoformat(meta["start_date"])
            services.enrol_application(row["application_id"], meta.get("mentor_id"), start, how="after payment")
        elif row["kind"] == "ad" and row["campaign_id"]:
            services.activate_campaign(row["campaign_id"])
    except ApiError as e:
        # money is safe and recorded; a person finishes the enrolment
        services.log_auto("payment_followup_failed", f"{row['invoice_no']}: {e.message} (needs a person)", "payment", row["id"])
    return db.one("select * from payments where id=%s", (pid,)), True


def _view(p):
    docs = ["refund", "internship-terms"] if p["kind"] == "enrolment" else ["refund", "terms"]
    return {"description": p["description"], "amount_inr": p["amount_paise"] / 100, "status": p["status"], "payer_name": p["payer_name"],
            "kind": p["kind"], "invoice_no": p["invoice_no"], "docs": [{"slug": d, "title": (services.latest_legal(d) or {}).get("title", d)} for d in docs]}


@bp.get("/pay/<token>")
def view(token):
    p = get_payment(token)
    return jsonify(payment=_view(p), mode=gateway.mode(), production=bool(current_app.config.get("PRODUCTION")))


@bp.post("/pay/<token>/start")
def start(token):
    p = get_payment(token)
    if p["status"] == "paid":
        bad("This payment is already complete.", 409)
    if p["status"] == "refunded":
        bad("This payment was refunded.", 409)
    if not allow(f"paystart:{client_ip()}", 20, 3600):
        bad("Too many attempts. Please wait.", 429)
    if not (request.get_json(silent=True) or {}).get("accept"):
        bad("Please accept the " + ("Refund Policy and Internship Terms" if p["kind"] == "enrolment" else "Terms and Refund Policy") + " to continue.")
    services.record_consent(("refund", "internship-terms") if p["kind"] == "enrolment" else ("refund", "terms"),
                            "enrolment" if p["kind"] == "enrolment" else "ad_purchase", None, p["payer_email"], client_ip())
    if not p["provider_order_id"] or p["status"] == "failed":
        provider, oid = gateway.create_order(p["amount_paise"], f"pay{p['id']}", {"payment_id": str(p["id"])})
        db.run("update payments set provider=%s, provider_order_id=%s, status='created' where id=%s", (provider, oid, p["id"]))
        p = get_payment(token)
    return jsonify(mode=p["provider"], order_id=p["provider_order_id"], amount_paise=p["amount_paise"], currency="INR",
                   key_id=current_app.config.get("RAZORPAY_KEY_ID") if p["provider"] == "razorpay" else None,
                   name=p["payer_name"], email=p["payer_email"], description=p["description"])


@bp.post("/pay/<token>/verify")
def verify(token):
    p = get_payment(token)
    b = request.get_json(silent=True) or {}
    if not p["provider_order_id"] or b.get("razorpay_order_id") != p["provider_order_id"]:
        bad("This payment does not match the order.", 400)
    if not gateway.verify_payment(p["provider"], p["provider_order_id"], b.get("razorpay_payment_id"), b.get("razorpay_signature")):
        db.run("update payments set status='failed' where id=%s and status='created'", (p["id"],))
        bad("We could not confirm this payment. If money was deducted it will be refunded automatically by your bank, or contact us with your payment reference.", 400)
    row, _ = mark_paid(p["id"], b["razorpay_payment_id"])
    return jsonify(status=row["status"], invoice_no=row["invoice_no"])


@bp.post("/pay/<token>/demo")
def demo(token):
    """Demo gateway only (no real money). Refused in production and whenever Razorpay is configured."""
    p = get_payment(token)
    if gateway.mode() != "demo" or current_app.config.get("PRODUCTION"):
        bad("Not available.", 404)
    if p["provider"] != "demo" or not p["provider_order_id"]:
        bad("Start the payment first.", 409)
    if (request.get_json(silent=True) or {}).get("outcome") == "fail":
        db.run("update payments set status='failed' where id=%s and status='created'", (p["id"],))
        return jsonify(status="failed")
    pid = f"demo_pay_{p['id']}"
    sig = gateway.demo_signature(p["provider_order_id"], pid)
    if not gateway.verify_payment("demo", p["provider_order_id"], pid, sig):
        bad("Demo signature failed.", 500)
    row, _ = mark_paid(p["id"], pid)
    return jsonify(status=row["status"], invoice_no=row["invoice_no"])


@bp.get("/pay/<token>/invoice")
def invoice(token):
    p = get_payment(token)
    if p["status"] not in ("paid", "refunded", "disputed"):
        bad("No invoice yet: the payment is not complete.", 404)
    e = html.escape
    co = e(services.company())
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Invoice {e(p['invoice_no'] or '')}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 20px;color:#12263f}}h1{{margin:0}}table{{width:100%;border-collapse:collapse;margin:24px 0}}
td,th{{padding:10px;border-bottom:1px solid #dde3ea;text-align:left}}.r{{text-align:right}}.m{{color:#5f6f84;font-size:.9rem}}@media print{{button{{display:none}}}}</style></head><body>
<button onclick="print()" style="float:right">Print / save as PDF</button><h1>{co}</h1><p class="m">Invoice / receipt</p>
<p><b>Invoice no:</b> {e(p['invoice_no'] or '')}<br><b>Date:</b> {p['paid_at']:%d %b %Y}<br><b>Billed to:</b> {e(p['payer_name'])} ({e(p['payer_email'])})<br>
<b>Payment reference:</b> {e(p['provider_payment_id'] or '')}<br><b>Status:</b> {e(p['status'].capitalize())}</p>
<table><tr><th>Description</th><th class="r">Amount</th></tr><tr><td>{e(p['description'])}</td><td class="r">₹{p['amount_paise'] / 100:,.2f}</td></tr>
<tr><th>Total paid</th><th class="r">₹{p['amount_paise'] / 100:,.2f}</th></tr></table>
<p class="m">This is a computer-generated receipt. Refunds follow the Refund Policy on our website.</p></body></html>"""
    return Response(body, mimetype="text/html")


# ------------------------------------------------------------------ Razorpay webhook (money state is decided here, not by the browser)
@bp.post("/webhooks/razorpay")
def webhook():
    raw = request.get_data()
    if not gateway.verify_webhook(raw, request.headers.get("X-Razorpay-Signature", "")):
        return jsonify(error="bad signature"), 400
    ev = json.loads(raw or b"{}")
    kind = ev.get("event", "")
    ent = ((ev.get("payload") or {}).get("payment") or {}).get("entity") or {}
    order_id = ent.get("order_id")
    p = db.one("select * from payments where provider_order_id=%s", (order_id,)) if order_id else None
    if p:
        if kind in ("payment.captured", "order.paid"):
            mark_paid(p["id"], ent.get("id") or "webhook")
        elif kind == "payment.failed":
            db.run("update payments set status='failed' where id=%s and status='created'", (p["id"],))
        elif kind == "payment.dispute.created":
            db.run("update payments set status='disputed' where id=%s and status='paid'", (p["id"],))
            services.log_auto("payment_disputed", f"{p['invoice_no']} disputed. A person must respond.", "payment", p["id"])
        elif kind in ("refund.processed", "payment.refunded"):
            db.run("update payments set status='refunded', refunded_at=now() where id=%s and status in ('paid','disputed')", (p["id"],))
    return jsonify(ok=True)


# ------------------------------------------------------------------ admin
@bp.get("/staff/payments")
@auth("admin")
def staff_list():
    status = request.args.get("status")
    rows = db.q(f"""select id, kind, payer_name, payer_email, description, amount_paise, status, provider, invoice_no, created_at, paid_at, refunded_at, token
                    from payments {'where status=%s' if status else ''} order by id desc limit 300""", (status,) if status else ())
    tot = db.one("""select coalesce(sum(amount_paise) filter (where status='paid'),0) as paid,
                           coalesce(sum(amount_paise) filter (where status='refunded'),0) as refunded,
                           count(*) filter (where status in ('disputed','failed')) as attention from payments""")
    return jsonify(payments=rows, totals={"paid_inr": tot["paid"] / 100, "refunded_inr": tot["refunded"] / 100, "attention": tot["attention"]}, mode=gateway.mode())


@bp.post("/staff/payments/<int:pid>/refund")
@auth("admin")
def staff_refund(pid):
    """Refund decisions stay with a person."""
    p = db.one("select * from payments where id=%s", (pid,))
    if not p or p["status"] not in ("paid", "disputed"):
        bad("Only paid or disputed payments can be refunded.")
    note = text(request.get_json(silent=True) or {}, "note", 300, True, "Reason")
    if not gateway.refund(p["provider"], p["provider_payment_id"], p["amount_paise"]):
        bad("The payment provider did not accept the refund. Try again or refund from the provider dashboard.", 502)
    db.run("update payments set status='refunded', refunded_at=now(), refund_note=%s where id=%s", (note, pid))
    if p["kind"] == "ad" and p["campaign_id"]:
        db.run("update ad_campaigns set status='rejected' where id=%s and status in ('active','pending_review','paused')", (p["campaign_id"],))
    mailer.send_mail(p["payer_email"], f"Refund issued – {services.company()}",
                     f"Hi {p['payer_name']},\n\nWe have refunded ₹{p['amount_paise'] / 100:,.2f} for: {p['description']}. It reaches your account in 5-7 working days.\n\n– {services.company()}")
    services.log_auto("payment_refunded", f"{p['invoice_no']} refunded by {g.user['name']}: {note}", "payment", pid)
    return jsonify(ok=True)


@bp.post("/staff/payments/<int:pid>/resolve-dispute")
@auth("admin")
def staff_resolve(pid):
    db.run("update payments set status='paid' where id=%s and status='disputed'", (pid,))
    return jsonify(ok=True)
