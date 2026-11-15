"""Admin screens for the Class Directory: listings, approval queues, review moderation, enquiries, CSV import."""
import csv
import io
import json
from collections import OrderedDict

from flask import Blueprint, Response, g, jsonify, request

import db
import mailer
import services
from classes_common import CATEGORIES, clean_class, MODES
from security import ApiError, auth, bad, hash_token, new_token, text

bp = Blueprint("classes_admin", __name__, url_prefix="/api/staff")


@bp.get("/classes-stats")
@auth("admin")
def stats():
    one = lambda sql: db.one(sql)["n"]
    return jsonify(
        live=one("select count(*) n from classes where status='live'"),
        pending_classes=one("select count(*) n from classes where status='pending'"),
        pending_submissions=one("select count(*) n from class_submissions where status='pending'"),
        pending_reviews=one("select count(*) n from class_reviews where status in ('pending','held')"),
        new_enquiries=one("select count(*) n from class_enquiries where status='new'"),
        stale_fees=one("select count(*) n from classes where status='live' and fees_updated_at < now() - make_interval(days => %s)" % services.setting_int("stale_fee_days", 180)),
    )


# ======================================================================= listings
@bp.get("/classes")
@auth("admin")
def list_all():
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()[:60]
    where, args = ["true"], []
    if status in ("pending", "live", "hidden"):
        where.append("c.status=%s")
        args.append(status)
    if q:
        where.append("(c.name ilike %s or c.area ilike %s or c.phone like %s)")
        args += [f"%{q}%", f"%{q}%", f"%{q}%"]
    rows = db.q(f"""select c.id, c.slug, c.name, c.category, c.area, c.phone, c.mode, c.status, c.verified, c.source, c.rating_count,
                           (select count(*) from class_courses where class_id=c.id) as courses,
                           (select count(*) from class_enquiries where class_id=c.id and status='new') as new_enquiries,
                           c.fees_updated_at, c.created_at, (c.manage_token_hash is not null) as claimed
                    from classes c where {' and '.join(where)} order by c.id desc limit 300""", tuple(args))
    return jsonify(classes=rows, known_categories=CATEGORIES)


@bp.get("/classes/<int:cid>")
@auth("admin")
def get_one(cid):
    c = db.one("select * from classes where id=%s", (cid,))
    if not c:
        bad("Class not found.", 404)
    c.pop("manage_token_hash", None)
    c["courses"] = db.q("select title, duration, fee_min, fee_max, batch_timing from class_courses where class_id=%s order by sort_order, id", (cid,))
    return jsonify(**c)


def _apply(cid, b):
    f = clean_class(b, partial=True)
    if "status" in b:
        if b["status"] not in ("pending", "live", "hidden"):
            bad("Invalid status.")
        f["status"] = b["status"]
    if "verified" in b:
        f["verified"] = bool(b["verified"])
    courses = services.clean_courses(b["courses"]) if "courses" in b else None
    with db.tx() as t:
        if f:
            sets = ", ".join(f"{k}=%s" for k in f)
            t.run(f"update classes set {sets}, updated_at=now() where id=%s", tuple(f.values()) + (cid,))
        if courses is not None:
            services.replace_courses(t, cid, courses)


@bp.post("/classes")
@auth("admin")
def create():
    b = request.get_json(silent=True) or {}
    f = clean_class(b)
    status = b.get("status", "live")
    if status not in ("pending", "live", "hidden"):
        bad("Invalid status.")
    slug = services.unique_class_slug(f["name"], f["area"])
    row = db.one("""insert into classes (slug,name,category,area,address,phone,whatsapp,email,website,mode,description,verified,status,source)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin') returning id""",
                 (slug, f["name"], f["category"], f["area"], f["address"], f["phone"], f["whatsapp"], f["email"], f["website"], f["mode"],
                  f["description"], bool(b.get("verified")), status))
    courses = services.clean_courses(b.get("courses"))
    if courses:
        with db.tx() as t:
            services.replace_courses(t, row["id"], courses)
    return jsonify(id=row["id"], slug=slug), 201


@bp.put("/classes/<int:cid>")
@auth("admin")
def update(cid):
    if not db.one("select 1 from classes where id=%s", (cid,)):
        bad("Class not found.", 404)
    _apply(cid, request.get_json(silent=True) or {})
    return jsonify(ok=True)


@bp.delete("/classes/<int:cid>")
@auth("admin")
def delete(cid):
    db.run("delete from classes where id=%s", (cid,))
    return jsonify(ok=True)


@bp.post("/classes/<int:cid>/reset-owner")
@auth("admin")
def reset_owner(cid):
    """Ownership dispute: removes the owner link so the institute has to prove ownership again by OTP."""
    db.run("update classes set manage_token_hash=null, claimed_at=null, verified=false, updated_at=now() where id=%s", (cid,))
    return jsonify(ok=True)


# ======================================================================= 'List your class' queue
@bp.get("/submissions")
@auth("admin")
def submissions():
    status = request.args.get("status", "pending")
    rows = db.q("select * from class_submissions where status=%s order by id desc limit 200", (status,))
    return jsonify(submissions=rows)


@bp.post("/submissions/<int:sid>/approve")
@auth("admin")
def approve_submission(sid):
    s = db.one("select * from class_submissions where id=%s", (sid,))
    if not s:
        bad("Submission not found.", 404)
    if s["status"] != "pending":
        bad("This submission was already handled.")
    b = request.get_json(silent=True) or {}
    # admin may fix typos while approving
    f = clean_class({k: b.get(k, s[k]) for k in ("name", "category", "area", "address", "phone", "whatsapp", "email", "website", "mode", "description")})
    slug = services.unique_class_slug(f["name"], f["area"])
    token = new_token()
    verified = bool(s["phone_verified"])
    with db.tx() as t:
        c = t.one("""insert into classes (slug,name,category,area,address,phone,whatsapp,email,website,mode,description,verified,status,source,manage_token_hash,claimed_at)
                     values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'live','submission',%s,%s) returning id""",
                  (slug, f["name"], f["category"], f["area"], f["address"], f["phone"], f["whatsapp"], f["email"], f["website"], f["mode"],
                   f["description"], verified, hash_token(token), db.one("select now() as n")["n"] if verified else None))
        courses = services.clean_courses(s["courses"] if isinstance(s["courses"], list) else json.loads(s["courses"]))
        if courses:
            services.replace_courses(t, c["id"], courses)
        t.run("update class_submissions set status='approved', class_id=%s where id=%s", (c["id"], sid))
    to = s["submitter_email"] or f["email"]
    link = f"{services.site_url()}/manage/{token}"
    if to:
        mailer.send_mail(to, f"{f['name']} is now listed", f"Hi {s['submitter_name']},\n\nYour class is live: {services.site_url()}/classes/{slug}\n\n"
                         f"Update fees, courses and see enquiries here (keep this link private):\n{link}\n\n– {services.company()}")
    services.log_auto("listing_approved", f"{f['name']} approved by {g.user['name']}", "class", c["id"])
    return jsonify(class_id=c["id"], slug=slug, manage_url=link)


@bp.post("/submissions/<int:sid>/reject")
@auth("admin")
def reject_submission(sid):
    s = db.one("select * from class_submissions where id=%s and status='pending'", (sid,))
    if not s:
        bad("Submission not found.", 404)
    reason = text(request.get_json(silent=True) or {}, "reason", 300)
    db.run("update class_submissions set status='rejected' where id=%s", (sid,))
    if s["submitter_email"]:
        mailer.send_mail(s["submitter_email"], f"About your listing for {s['name']}",
                         f"Hi {s['submitter_name']},\n\nWe could not publish your listing this time." + (f"\nReason: {reason}" if reason else "") +
                         f"\nYou can submit it again with corrections.\n\n– {services.company()}")
    return jsonify(ok=True)


# ======================================================================= reviews
@bp.get("/reviews")
@auth("admin")
def reviews():
    status = request.args.get("status", "attention")
    where = "r.status in ('pending','held')" if status == "attention" else "r.status=%s"
    rows = db.q(f"""select r.id, r.rating, r.body, r.status, r.flag_reason, r.created_at, c.name as class_name, c.slug, u.name as reviewer, u.email as reviewer_email
                    from class_reviews r join classes c on c.id=r.class_id join users u on u.id=r.user_id
                    where {where} order by r.created_at desc limit 200""", () if status == "attention" else (status,))
    return jsonify(reviews=rows)


@bp.post("/reviews/<int:rid>")
@auth("admin")
def decide_review(rid):
    r = db.one("select * from class_reviews where id=%s", (rid,))
    if not r:
        bad("Review not found.", 404)
    action = (request.get_json(silent=True) or {}).get("action")
    status = {"approve": "live", "remove": "removed", "hold": "held"}.get(action)
    if not status:
        bad("Invalid action.")
    db.run("update class_reviews set status=%s, flag_reason=%s where id=%s", (status, None if status == "live" else r["flag_reason"], rid))
    services.refresh_rating(r["class_id"])
    return jsonify(ok=True)


# ======================================================================= enquiries
@bp.get("/enquiries")
@auth("admin")
def enquiries():
    status = request.args.get("status")
    where, args = ("where e.status=%s", (status,)) if status in ("new", "contacted", "closed") else ("", ())
    rows = db.q(f"""select e.id, e.name, e.phone, e.message, e.status, e.created_at, e.contacted_at, c.name as class_name, c.phone as class_phone, c.whatsapp
                    from class_enquiries e join classes c on c.id=e.class_id {where} order by e.id desc limit 300""", args)
    for r in rows:
        r["whatsapp_link"] = services.wa_link(r["whatsapp"] or r["class_phone"], f"Hi, a student ({r['name']}, {r['phone']}) asked about your classes.")
    return jsonify(enquiries=rows)


@bp.post("/enquiries/<int:eid>")
@auth("admin")
def set_enquiry(eid):
    st = (request.get_json(silent=True) or {}).get("status")
    if st not in ("new", "contacted", "closed"):
        bad("Invalid status.")
    db.run("update class_enquiries set status=%s, contacted_at=case when %s='contacted' then now() else contacted_at end where id=%s", (st, st, eid))
    return jsonify(ok=True)


# ======================================================================= CSV import
CSV_COLUMNS = ["name", "category", "area", "address", "phone", "whatsapp", "email", "website", "mode", "description",
               "course_title", "duration", "fee_min", "fee_max", "batch_timing"]


@bp.get("/classes-import-template.csv")
@auth("admin")
def import_template():
    sample = [["Example Coding Academy", "Coding & IT", "Kothrud", "Paud Road, Pune", "9800000001", "9800000001", "hello@example.com", "https://example.com",
               "hybrid", "Hands-on web development classes.", "Full-stack web development", "4 months", "18000", "24000", "Weekdays 6-8 pm"],
              ["Example Coding Academy", "", "", "", "9800000001", "", "", "", "", "", "Python basics", "6 weeks", "6000", "6000", "Sat-Sun 10-12"]]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    w.writerows(sample)
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="classes-template.csv"'})


@bp.post("/classes-import")
@auth("admin")
def import_csv():
    """One row per course. Rows with the same class name + phone are merged into one listing.
    Existing listings (same name + phone) are skipped unless update=1, in which case their courses are replaced."""
    f = request.files.get("file")
    if not f:
        bad("Choose a CSV file.")
    raw = f.read(1_000_001)
    if len(raw) > 1_000_000:
        bad("The CSV is larger than 1 MB. Split it into smaller files.")
    try:
        text_data = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        bad("The file must be saved as CSV (UTF-8).")
    reader = csv.DictReader(io.StringIO(text_data))
    if not reader.fieldnames:
        bad("The CSV is empty.")
    reader.fieldnames = [(h or "").strip().lower().replace(" ", "_") for h in reader.fieldnames]
    missing = [c for c in ("name", "category", "area", "phone") if c not in reader.fieldnames]
    if missing:
        bad("The CSV needs these columns: " + ", ".join(missing) + ". Download the template for the exact layout.")
    publish = request.form.get("publish", "1") == "1"
    update = request.form.get("update") == "1"

    groups = OrderedDict()
    errors = []
    for i, row in enumerate(reader, start=2):
        if i > 2002:
            errors.append({"line": i, "error": "Stopped at 2000 rows."})
            break
        row = {k: (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        key = (row.get("name", "").lower(), services.digits(row.get("phone", ""))[-10:])
        g_ = groups.setdefault(key, {"line": i, "base": row, "courses": []})
        if row.get("course_title"):
            g_["courses"].append({"title": row["course_title"], "duration": row.get("duration"), "fee_min": row.get("fee_min"),
                                  "fee_max": row.get("fee_max"), "batch_timing": row.get("batch_timing")})
        for k in ("category", "area", "address", "whatsapp", "email", "website", "mode", "description"):
            if row.get(k) and not g_["base"].get(k):
                g_["base"][k] = row[k]

    created = updated = skipped = 0
    for key, grp in groups.items():
        try:
            base = {k: v for k, v in grp["base"].items() if k in ("name", "category", "area", "address", "phone", "whatsapp", "email", "website", "mode", "description")}
            base["mode"] = (base.get("mode") or "offline").lower()
            fields = clean_class(base)
            courses = services.clean_courses(grp["courses"])
            existing = db.one("select id from classes where lower(name)=lower(%s) and phone=%s", (fields["name"], fields["phone"]))
            if existing and not update:
                skipped += 1
                continue
            with db.tx() as t:
                if existing:
                    cid = existing["id"]
                    sets = ", ".join(f"{k}=%s" for k in fields)
                    t.run(f"update classes set {sets}, updated_at=now() where id=%s", tuple(fields.values()) + (cid,))
                    updated += 1
                else:
                    slug = services.unique_class_slug(fields["name"], fields["area"])
                    cid = t.one("""insert into classes (slug,name,category,area,address,phone,whatsapp,email,website,mode,description,status,source)
                                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'csv') returning id""",
                                (slug, fields["name"], fields["category"], fields["area"], fields["address"], fields["phone"], fields["whatsapp"],
                                 fields["email"], fields["website"], fields["mode"], fields["description"], "live" if publish else "pending"))["id"]
                    created += 1
                if courses:
                    services.replace_courses(t, cid, courses)
        except ApiError as e:
            errors.append({"line": grp["line"], "name": grp["base"].get("name", ""), "error": e.message})
    return jsonify(created=created, updated=updated, skipped=skipped, errors=errors[:50], error_count=len(errors))
