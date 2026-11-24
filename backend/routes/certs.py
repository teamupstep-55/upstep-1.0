"""Certificates: automatic issue (see automation.job_certificates), public verify page + QR, admin revoke."""
import io

import segno
from flask import Blueprint, Response, g, jsonify, request

import db
import services
from core import performance_map
from security import allow, auth, bad, client_ip, text

bp = Blueprint("certs", __name__, url_prefix="/api")


@bp.get("/certificates/<cert_no>")
def verify(cert_no):
    """Public: anyone (an employer, say) can check a certificate. Shows only name, grade and dates."""
    if not allow(f"verify:{client_ip()}", 60, 600):
        bad("Too many checks. Please wait a few minutes.", 429)
    c = db.one("select c.*, u.name, u.start_date, u.training_days from certificates c join users u on u.id=c.user_id where c.cert_no=%s", (cert_no.upper(),))
    if not c:
        return jsonify(valid=False, found=False), 404
    if c["revoked_at"]:
        return jsonify(valid=False, found=True, revoked=True, cert_no=c["cert_no"], message="This certificate has been revoked.")
    return jsonify(valid=True, found=True, cert_no=c["cert_no"], holder=c["name"], grade=c["grade"], score=c["score"], issued_at=c["issued_at"],
                   programme=f"{c['training_days']}-day internship training", company=services.company(), start_date=c["start_date"])


@bp.get("/certificates/<cert_no>/qr.svg")
def qr(cert_no):
    if not db.one("select 1 from certificates where cert_no=%s", (cert_no.upper(),)):
        bad("Not found.", 404)
    buf = io.BytesIO()
    segno.make(f"{services.site_url()}/verify/{cert_no.upper()}", error="m").save(buf, kind="svg", scale=5, border=1, dark="#12263f", xmldecl=False)
    return Response(buf.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@bp.get("/student/certificate")
@auth("student")
def mine():
    u = g.user
    c = db.one("select cert_no, grade, score, issued_at, revoked_at from certificates where user_id=%s", (u["id"],))
    chk = services.certificate_check(u)
    return jsonify(certificate=c if c and not c["revoked_at"] else None, revoked=bool(c and c["revoked_at"]),
                   progress={k: chk.get(k) for k in ("score", "pass_mark", "finished", "ends_on", "reason", "eligible")})


# ------------------------------------------------------------------ admin
@bp.get("/staff/certificates")
@auth("admin")
def staff_list():
    rows = db.q("""select c.id, c.cert_no, c.grade, c.score, c.auto, c.issued_at, c.revoked_at, c.revoked_reason, u.id as student_id, u.name, u.email
                   from certificates c join users u on u.id=c.user_id order by c.id desc limit 300""")
    waiting = []
    for s in db.q("select * from users where role='student' and is_active and start_date is not null and not exists (select 1 from certificates c where c.user_id=users.id)"):
        chk = services.certificate_check(s)
        waiting.append({"student_id": s["id"], "name": s["name"], "score": chk["score"], "finished": chk["finished"], "reason": chk["reason"], "eligible": chk["eligible"]})
    return jsonify(certificates=rows, waiting=waiting, pass_mark=services.setting_int("cert_pass_mark", 60))


@bp.post("/staff/certificates/issue")
@auth("admin")
def staff_issue():
    """Manual override (for example a student who finished early). Logged like any other decision."""
    sid = (request.get_json(silent=True) or {}).get("student_id")
    s = db.one("select * from users where id=%s and role='student'", (sid,))
    if not s:
        bad("Student not found.", 404)
    c = services.issue_certificate(s, auto=False)
    services.log_auto("certificate_issued", f"{s['name']}: certificate {c['cert_no']} issued manually by {g.user['name']}", "student", s["id"], s["id"], reversible=True)
    return jsonify(cert_no=c["cert_no"]), 201


@bp.post("/staff/certificates/<int:cid>/revoke")
@auth("admin")
def staff_revoke(cid):
    reason = text(request.get_json(silent=True) or {}, "reason", 200, True, "Reason")
    n = db.run("update certificates set revoked_at=now(), revoked_reason=%s where id=%s and revoked_at is null", (reason, cid))
    if not n:
        bad("Certificate not found or already revoked.", 404)
    return jsonify(ok=True)


@bp.post("/staff/certificates/<int:cid>/reinstate")
@auth("admin")
def staff_reinstate(cid):
    db.run("update certificates set revoked_at=null, revoked_reason=null where id=%s", (cid,))
    return jsonify(ok=True)
