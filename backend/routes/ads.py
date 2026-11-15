"""Ads: always labelled 'Sponsored', never affect organic order. Self-serve purchase -> payment -> automatic start/end -> report."""
from flask import Blueprint, g, jsonify, redirect, request

import db
import mailer
import services
from classes_common import clean_phone, clean_url
from core import today
from security import EMAIL_RE, allow, auth, bad, client_ip, hash_token, text

bp = Blueprint("ads", __name__, url_prefix="/api")


@bp.get("/ads/packages")
def packages():
    rows = db.q("select code, name, slot, days, price_paise from ad_packages where active order by price_paise")
    for r in rows:
        r["price_inr"] = r["price_paise"] / 100
    return jsonify(packages=rows)


@bp.get("/ads/serve")
def serve():
    slot = request.args.get("slot", "directory")
    if slot not in ("directory", "class_page"):
        bad("Unknown slot.")
    # rotation: the campaign with the fewest views so far goes first (fair share, no bidding)
    row = db.one("""update ad_campaigns set impressions = impressions + 1 where id = (
                      select c.id from ad_campaigns c join ad_packages p on p.id=c.package_id
                      where c.status='active' and p.slot=%s and c.starts_on <= %s and c.ends_on >= %s
                      order by c.impressions, c.id limit 1)
                    returning id, headline, body, advertiser_name""", (slot, today(), today()))
    return jsonify(ad=({**row, "label": "Sponsored", "go_url": f"/api/ads/{row['id']}/go"} if row else None))


@bp.get("/ads/<int:cid>/go")
def go(cid):
    row = db.one("update ad_campaigns set clicks = clicks + 1 where id=%s and status='active' returning link_url", (cid,))
    if not row:
        bad("This advertisement has ended.", 404)
    return redirect(row["link_url"], code=302)


@bp.post("/ads/purchase")
def purchase():
    b = request.get_json(silent=True) or {}
    if b.get("website_hp"):
        return jsonify(error="Rejected."), 400
    import gateway
    gateway.ensure_usable()                      # no real payment provider yet (production without Razorpay): refuse before creating anything
    if not allow(f"adbuy:{client_ip()}", 5, 3600):
        bad("Too many attempts. Please try again later.", 429)
    if not b.get("accept_terms"):
        bad("Please accept the Terms of Use and Refund Policy to continue.")
    pkg = db.one("select * from ad_packages where code=%s and active", (b.get("package_code"),))
    if not pkg:
        bad("Choose an advertising package.")
    name = text(b, "advertiser_name", 120, True, "Your name or institute")
    email = text(b, "contact_email", 160, True, "Email").lower()
    if not EMAIL_RE.match(email):
        bad("Please enter a valid email address.")
    phone = clean_phone(b.get("contact_phone"), "Phone number", False)
    headline = text(b, "headline", 60, True, "Headline")
    body = text(b, "body", 140, False, "Text")
    link = clean_url(b.get("link_url"), "Link", True)
    cls = db.one("select id from classes where slug=%s and status='live'", (b.get("class_slug"),)) if b.get("class_slug") else None
    c = db.one("""insert into ad_campaigns (class_id, advertiser_name, contact_email, contact_phone, headline, body, link_url, package_id)
                  values (%s,%s,%s,%s,%s,%s,%s,%s) returning id""", (cls["id"] if cls else None, name, email, phone, headline, body, link, pkg["id"]))
    p = services.create_payment("ad", name, email, pkg["price_paise"], f"Advertisement: {pkg['name']}", campaign_id=c["id"])
    return jsonify(pay_token=p["token"], pay_url=f"/pay/{p['token']}"), 201


@bp.get("/ads/report/<token>")
def report(token):
    c = db.one("""select c.headline, c.status, c.starts_on, c.ends_on, c.impressions, c.clicks, c.flag_reason, p.name as package
                  from ad_campaigns c join ad_packages p on p.id=c.package_id where c.manage_token=%s""", (hash_token(token),))
    if not c:
        bad("Report not found.", 404)
    c["ctr"] = round(100 * c["clicks"] / c["impressions"], 1) if c["impressions"] else 0
    return jsonify(report=c)


# ------------------------------------------------------------------ admin
@bp.get("/staff/ads")
@auth("admin")
def staff_list():
    rows = db.q("""select c.id, c.advertiser_name, c.contact_email, c.headline, c.body, c.link_url, c.status, c.flag_reason, c.starts_on, c.ends_on,
                          c.impressions, c.clicks, p.name as package, p.price_paise, c.created_at
                   from ad_campaigns c join ad_packages p on p.id=c.package_id order by c.id desc limit 200""")
    return jsonify(campaigns=rows)


@bp.post("/staff/ads/<int:cid>")
@auth("admin")
def staff_action(cid):
    c = db.one("select * from ad_campaigns where id=%s", (cid,))
    if not c:
        bad("Campaign not found.", 404)
    b = request.get_json(silent=True) or {}
    action = b.get("action")
    if action == "approve" and c["status"] == "pending_review":
        services.start_campaign(cid)
    elif action == "pause" and c["status"] == "active":
        db.run("update ad_campaigns set status='paused' where id=%s", (cid,))
    elif action == "resume" and c["status"] == "paused":
        db.run("update ad_campaigns set status='active' where id=%s", (cid,))
    elif action == "reject" and c["status"] in ("pending_review", "active", "paused"):
        reason = text(b, "reason", 300, True, "Reason")
        db.run("update ad_campaigns set status='rejected', flag_reason=%s where id=%s", (reason, cid))
        pay = db.one("select * from payments where campaign_id=%s and status='paid'", (cid,))
        if pay:      # Refund Policy: a rejected advertisement is refunded in full
            import gateway
            if gateway.refund(pay["provider"], pay["provider_payment_id"], pay["amount_paise"]):
                db.run("update payments set status='refunded', refunded_at=now(), refund_note=%s where id=%s", (f"Ad rejected: {reason}", pay["id"]))
        mailer.send_mail(c["contact_email"], f"About your advertisement – {services.company()}",
                         f"Hi {c['advertiser_name']},\n\nWe could not run your advertisement. Reason: {reason}\nYour payment has been refunded in full.\n\n– {services.company()}")
        services.log_auto("ad_rejected", f"Campaign #{cid} rejected by {g.user['name']}: {reason}", "campaign", cid)
    else:
        bad("That action is not possible for this campaign.")
    return jsonify(ok=True)
