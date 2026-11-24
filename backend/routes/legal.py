from flask import Blueprint, g, jsonify, request

import db
import services
from security import auth, bad, text

bp = Blueprint("legal", __name__, url_prefix="/api")

SLUGS = ("terms", "privacy", "refund", "internship-terms")


@bp.get("/legal")
def legal_list():
    rows = db.q("""select distinct on (slug) slug, title, version, published_at from legal_documents
                   order by slug, version desc""")
    return jsonify(documents=rows)


@bp.get("/legal/<slug>")
def legal_get(slug):
    d = services.latest_legal(slug)
    if not d:
        bad("Page not found.", 404)
    return jsonify(document=d)


# ---------------------------------------------------------------- admin: publish a new version
@bp.get("/staff/legal")
@auth("admin")
def staff_legal():
    docs = db.q("""select distinct on (slug) slug, title, body, version, published_at from legal_documents order by slug, version desc""")
    for d in docs:
        d["accepted"] = db.one("select count(*) as n from consents where doc_slug=%s and doc_version=%s", (d["slug"], d["version"]))["n"]
    return jsonify(documents=docs)


@bp.post("/staff/legal/<slug>")
@auth("admin")
def staff_legal_publish(slug):
    if slug not in SLUGS:
        bad("Unknown document.", 404)
    b = request.get_json(silent=True) or {}
    title = text(b, "title", 120, True, "Title")
    body = text(b, "body", 30000, True, "Text")
    cur = services.latest_legal(slug)
    if cur and cur["body"].strip() == body and cur["title"] == title:
        bad("Nothing changed, so no new version was published.")
    v = (cur["version"] if cur else 0) + 1
    db.run("insert into legal_documents (slug, version, title, body) values (%s,%s,%s,%s)", (slug, v, title, body))
    return jsonify(version=v), 201


@bp.get("/staff/consents")
@auth("admin")
def staff_consents():
    """Who accepted which version, when."""
    email = (request.args.get("email") or "").strip().lower()
    where, args = ("where lower(c.email) like %s", (f"%{email}%",)) if email else ("", ())
    rows = db.q(f"""select c.id, c.email, c.doc_slug, c.doc_version, c.context, c.created_at, u.name
                    from consents c left join users u on u.id=c.user_id {where} order by c.id desc limit 300""", args)
    return jsonify(consents=rows)
