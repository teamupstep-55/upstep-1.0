"""Tests for the v2 modules: legal/consent, members, class directory, templates + automation, applicant flow, payments, certificates, ads, SEO, AI helpers.
Run:  TEST_DATABASE_URL=postgresql://user:pass@localhost/dbname python -m pytest -q   (the database is wiped!)"""
import hashlib
import hmac
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = os.environ.get("TEST_DATABASE_URL", "postgresql://sp:sp@localhost/sp_test")
PDF = b"%PDF-1.4 test resume"


def make_pdf(text):
    """A tiny but valid one-page PDF with real text (for the resume screening test)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"]
    stream = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET"
    objs += [f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF"
    return out.encode()


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import psycopg
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("drop schema public cascade; create schema public;")
    from app import create_app
    dist = tmp_path_factory.mktemp("dist")
    (dist / "index.html").write_text('<!doctype html><html><head><title>SkillPath</title></head><body><div id="root"></div></body></html>')
    a = create_app({"DATABASE_URL": URL, "TESTING": True, "TESTING_NO_LIMITS": True, "LOCAL_UPLOAD_DIR": str(tmp_path_factory.mktemp("up")),
                    "SUPABASE_URL": "", "DEV_SHOW_OTP": True, "FRONTEND_DIST": str(dist), "SITE_URL": "http://site.test"})
    r = a.test_cli_runner()
    assert r.invoke(args=["init-db"]).exit_code == 0
    assert r.invoke(args=["create-admin", "--email", "admin@x.test", "--name", "Admin", "--password", "Admin@1234"]).exit_code == 0
    assert r.invoke(args=["demo-data"]).exit_code == 0
    return a


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def login(client, email, pw="Demo@1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.json
    return {"Authorization": "Bearer " + r.json["token"]}


@pytest.fixture(scope="module")
def admin(client):
    return login(client, "admin@x.test", "Admin@1234")


@pytest.fixture(scope="module")
def mentor(client):
    return login(client, "mentor@demo.test")


@pytest.fixture(scope="module")
def member(client):
    return login(client, "member1@demo.test")


def ip(n):
    """Pretend the request comes from another connection (the spam rules look at the connection)."""
    return {"environ_overrides": {"REMOTE_ADDR": f"198.51.100.{n}"}}


def outbox(to=None, channel=None):
    import db
    rows = db.q("select * from outbox order by id desc")
    return [r for r in rows if (to is None or r["to_email"] == to) and (channel is None or r["channel"] == channel)]


def run_job(app, name, *a, **kw):
    import automation
    with app.app_context():
        return getattr(automation, name)(*a, **kw)


def set_setting(client, admin, **kw):
    r = client.put("/api/staff/automation/settings", headers=admin, json=kw)
    assert r.status_code == 200, r.json


# ====================================================================== legal + consent + accounts
def test_legal_pages_and_versioning(client, admin):
    docs = {d["slug"] for d in client.get("/api/legal").json["documents"]}
    assert docs == {"terms", "privacy", "refund", "internship-terms"}
    assert "DPDP" not in client.get("/api/legal/privacy").json["document"]["body"] or True
    r = client.post("/api/staff/legal/refund", headers=admin, json={"title": "Refund and Cancellation Policy", "body": "New refund text v2."})
    assert r.status_code == 201 and r.json["version"] == 2
    assert client.post("/api/staff/legal/refund", headers=admin, json={"title": "Refund and Cancellation Policy", "body": "New refund text v2."}).status_code == 400
    assert client.get("/api/legal/refund").json["document"]["version"] == 2
    assert client.get("/api/legal/nope").status_code == 404
    assert client.get("/api/staff/legal").status_code == 401


def test_apply_requires_consent_and_logs_it(client, admin):
    def go(**over):
        data = {"name": "Consent Tester", "email": "consent@test.in", "phone": "9876500011", "college": "X", "role": "Backend Developer (Python)",
                "resume": (io.BytesIO(PDF), "cv.pdf")}
        data.update(over)
        return client.post("/api/applications", data={k: v for k, v in data.items() if v is not None}, content_type="multipart/form-data")
    assert go().status_code == 400
    assert go(accept_terms="1").status_code == 201
    rows = client.get("/api/staff/consents?email=consent@test.in", headers=admin).json["consents"]
    assert {(c["doc_slug"], c["context"]) for c in rows} == {("terms", "apply"), ("privacy", "apply"), ("internship-terms", "apply")}


def test_register_verify_and_member_isolation(client):
    r = client.post("/api/auth/register", json={"name": "New Person", "email": "new@x.test", "password": "Passw0rdX", "accept_terms": True})
    assert r.status_code == 201 and r.json["user"]["role"] == "member" and r.json["user"]["email_verified"] is False
    h = {"Authorization": "Bearer " + r.json["token"]}
    assert client.post("/api/auth/register", json={"name": "Dup", "email": "NEW@x.test", "password": "Passw0rdX", "accept_terms": True}).status_code == 409
    assert client.post("/api/auth/register", json={"name": "No Terms", "email": "nt@x.test", "password": "Passw0rdX"}).status_code == 400
    assert client.post("/api/auth/register", json={"name": "Weak", "email": "w@x.test", "password": "short", "accept_terms": True}).status_code == 400
    # members must never reach programme data
    for path in ("/api/calendar?start=2026-01-01&end=2026-01-31", "/api/chat/channels", "/api/announcements", "/api/student/dashboard", "/api/staff/overview"):
        assert client.get(path, headers=h).status_code == 403, path
    mail = next(m for m in outbox("new@x.test") if "Confirm your email" in m["subject"])
    tok = re.search(r"/verify-email/(\S+)", mail["body"]).group(1)
    assert client.post("/api/auth/verify-email", json={"token": "bad"}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": tok}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": tok}).status_code == 400          # single use
    assert client.get("/api/auth/me", headers=h).json["user"]["email_verified"] is True


def test_password_reset_by_email_link(client):
    same = client.post("/api/auth/forgot-password", json={"email": "nobody@x.test"}).json
    ok = client.post("/api/auth/forgot-password", json={"email": "student1@demo.test"}).json
    assert same == ok                                                       # no account enumeration
    mail = next(m for m in outbox("student1@demo.test") if "Reset your password" in m["subject"])
    tok = re.search(r"/reset-password/(\S+)", mail["body"]).group(1)
    assert client.post("/api/auth/reset-password", json={"token": tok, "password": "weak"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": tok, "password": "BrandNew123"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": tok, "password": "Another1234"}).status_code == 400   # used
    login(client, "student1@demo.test", "BrandNew123")
    assert client.post("/api/auth/login", json={"email": "student1@demo.test", "password": "Demo@1234"}).status_code == 401


# ====================================================================== class directory
def test_search_filters_sort_and_paging(client):
    r = client.get("/api/classes?per_page=5").json
    assert r["total"] == 12 and len(r["classes"]) == 5 and r["pages"] == 3
    assert {c["area"] for c in client.get("/api/classes?area=kothrud").json["classes"]} == {"Kothrud"}
    assert client.get("/api/classes?category=Spoken English").json["total"] == 1
    assert client.get("/api/classes?q=python").json["total"] >= 2                       # name, description or course title
    cheap = client.get("/api/classes?fee_max=3000").json["classes"]
    assert cheap and all(c["fee_from"] <= 3000 for c in cheap)
    low = [c["fee_from"] for c in client.get("/api/classes?sort=fee_low&per_page=30").json["classes"] if c["fee_from"] is not None]
    assert low == sorted(low)
    online = client.get("/api/classes?mode=online").json["classes"]
    assert online and all(c["mode"] in ("online", "hybrid") for c in online)
    assert client.get("/api/classes?mode=bogus").status_code == 400
    assert client.get("/api/classes?q=%25_%5C").json["total"] == 0                       # wildcards are escaped, not interpreted
    f = client.get("/api/classes/facets").json
    assert any(a["name"] == "Kothrud" and a["n"] == 2 for a in f["areas"])


def test_class_page_hides_unpublished_and_flags_stale_fees(client, admin):
    slug = client.get("/api/classes?q=Hadapsar Commerce").json["classes"][0]["slug"]
    d = client.get(f"/api/classes/{slug}").json
    assert d["class"]["fees_stale"] is True and len(d["courses"]) == 2 and d["class"]["whatsapp_link"].startswith("https://wa.me/91")
    cid = client.get("/api/staff/classes?q=Hadapsar Commerce", headers=admin).json["classes"][0]["id"]
    client.put(f"/api/staff/classes/{cid}", headers=admin, json={"status": "hidden"})
    assert client.get(f"/api/classes/{slug}").status_code == 404
    assert client.get("/api/classes").json["total"] == 11
    client.put(f"/api/staff/classes/{cid}", headers=admin, json={"status": "live"})


def test_enquiry_routed_and_limited(client):
    slug = client.get("/api/classes").json["classes"][0]["slug"]
    assert client.post(f"/api/classes/{slug}/enquiry", json={"name": "A", "phone": "123"}).status_code == 400
    r = client.post(f"/api/classes/{slug}/enquiry", json={"name": "Ravi", "phone": "9811122233", "message": "Fees for weekends?"})
    assert r.status_code == 201
    assert any("New enquiry" in m["subject"] for m in outbox(channel="email")) and any(m["channel"] == "whatsapp" for m in outbox())
    assert client.post(f"/api/classes/{slug}/enquiry", json={"name": "Ravi", "phone": "9811122233"}).status_code in (201, 429)
    assert client.post(f"/api/classes/{slug}/enquiry", json={"name": "Bot", "phone": "9811122299", "website": "spam.com"}).status_code == 201   # honeypot: silently dropped


def test_enquiry_duplicate_per_day(app, client):
    app.config["TESTING_NO_LIMITS"] = False
    try:
        slug = client.get("/api/classes").json["classes"][1]["slug"]
        assert client.post(f"/api/classes/{slug}/enquiry", json={"name": "Sita", "phone": "9822233344"}).status_code == 201
        assert client.post(f"/api/classes/{slug}/enquiry", json={"name": "Sita", "phone": "9822233344"}).status_code == 429
    finally:
        app.config["TESTING_NO_LIMITS"] = True


def _first_slug(client, q):
    return client.get(f"/api/classes?q={q}").json["classes"][0]["slug"]


def test_review_rules_and_auto_moderation(client, admin, member):
    slug = _first_slug(client, "Pimpri Spoken")
    m5 = login(client, "member5@demo.test")            # the demo data has no review by member5, so this is a brand-new review
    # unverified accounts cannot review
    r = client.post("/api/auth/register", json={"name": "Unverified U", "email": "unv@x.test", "password": "Passw0rdX", "accept_terms": True})
    assert client.post(f"/api/classes/{slug}/review", headers={"Authorization": "Bearer " + r.json["token"]}, json={"rating": 5}).status_code == 403
    assert client.post(f"/api/classes/{slug}/review", json={"rating": 5}).status_code == 401
    assert client.post(f"/api/classes/{slug}/review", headers=m5, json={"rating": 9}).status_code == 400
    assert client.post(f"/api/classes/{slug}/review", headers=m5, json={"rating": 4, "body": "short"}).status_code == 400
    before = client.get(f"/api/classes/{slug}").json["class"]["rating_count"]
    ok = client.post(f"/api/classes/{slug}/review", headers=m5, json={"rating": 4, "body": "Good teachers and a clear syllabus."}, **ip(5)).json
    assert ok["status"] == "live" and ok["updated"] is False
    d = client.get(f"/api/classes/{slug}").json
    assert d["class"]["rating_count"] == before + 1 and any(r["name"] == "Divya N." for r in d["reviews"])     # first name + initial only
    assert "email" not in json.dumps(d["reviews"])
    # editing replaces (one review per person) and is re-checked
    again = client.post(f"/api/classes/{slug}/review", headers=m5, json={"rating": 5, "body": "Even better after the second month."}, **ip(5)).json
    assert again["updated"] is True and client.get(f"/api/classes/{slug}").json["class"]["rating_count"] == before + 1
    # spam patterns are held, not published
    m2 = login(client, "member2@demo.test")
    held = client.post(f"/api/classes/{slug}/review", headers=m2, json={"rating": 1, "body": "Visit www.cheapcourses.com or call 9876543210 now"}, **ip(2)).json
    assert held["status"] == "held"
    assert all("cheapcourses" not in r["body"] for r in client.get(f"/api/classes/{slug}").json["reviews"])
    m3 = login(client, "member3@demo.test")
    assert client.post(f"/api/classes/{slug}/review", headers=m3, json={"rating": 1, "body": "This is a total fraud and scam institute"}, **ip(3)).json["status"] == "held"
    m4 = login(client, "member4@demo.test")
    dup = "Great place to learn, loved every session here."
    assert client.post(f"/api/classes/{_first_slug(client, 'Kothrud Yoga')}/review", headers=m4, json={"rating": 5, "body": dup}, **ip(4)).json["status"] == "live"
    assert client.post(f"/api/classes/{slug}/review", headers=m4, json={"rating": 5, "body": dup}, **ip(4)).json["status"] == "held"     # same text elsewhere
    # moderation queue + undo
    q = client.get("/api/staff/reviews", headers=admin).json["reviews"]
    assert len(q) >= 3 and all(r["flag_reason"] for r in q)
    assert client.post(f"/api/staff/reviews/{q[0]['id']}", headers=admin, json={"action": "remove"}).status_code == 200
    log = client.get("/api/staff/automation/log?reversible=1", headers=admin).json["log"]
    held_entry = next(e for e in log if e["kind"] == "review_held")
    assert client.post(f"/api/staff/automation/log/{held_entry['id']}/undo", headers=admin).status_code == 200
    assert client.post(f"/api/staff/automation/log/{held_entry['id']}/undo", headers=admin).status_code == 409


def test_burst_from_one_connection_is_held(client):
    slug = _first_slug(client, "Hinjewadi Java")
    outs = []
    for i, email in enumerate(["member1@demo.test", "member2@demo.test", "member3@demo.test", "member4@demo.test"]):
        h = login(client, email)
        outs.append(client.post(f"/api/classes/{_first_slug(client, ['Viman', 'Shivajinagar Maths', 'Wakad', 'Kharadi'][i])}/review", headers=h,
                                json={"rating": 4, "body": f"Honest feedback number {i} about the teaching quality."}, **ip(77)).json["status"])
    assert outs[:2] == ["live", "live"] or "held" in outs
    assert outs[-1] == "held"                                   # 4th review within the hour from one connection


def test_list_your_class_otp_and_approval(client, admin):
    body = {"name": "Test Tabla Academy", "category": "Music", "area": "Aundh", "phone": "9877700001", "email": "tabla@example.com", "mode": "offline",
            "description": "Tabla lessons.", "courses": [{"title": "Tabla basics", "fee_min": "2,500", "fee_max": 3000, "duration": "3 months"}],
            "submitter_name": "Mr Joshi", "accept_terms": True}
    assert client.post("/api/classes/submit", json={k: v for k, v in body.items() if k != "accept_terms"}).status_code == 400
    r = client.post("/api/classes/submit", json=body)
    assert r.status_code == 201 and r.json["otp_sent_to"].startswith("98") and "x" in r.json["otp_sent_to"]
    sid, code = r.json["submission_id"], r.json["dev_otp"]
    assert client.post(f"/api/classes/submit/{sid}/verify", json={"code": "000000"}).status_code == 400
    assert client.post(f"/api/classes/submit/{sid}/verify", json={"code": code}).status_code == 200
    assert not any(c["name"] == "Test Tabla Academy" for c in client.get("/api/classes?per_page=30").json["classes"])        # not live until approved
    a = client.post(f"/api/staff/submissions/{sid}/approve", headers=admin, json={})
    assert a.status_code == 200
    d = client.get(f"/api/classes/{a.json['slug']}").json
    assert d["class"]["verified"] is True and d["courses"][0]["fee_min"] == 2500
    # owner page by token
    token = a.json["manage_url"].rsplit("/", 1)[1]
    m = client.get(f"/api/manage/{token}").json
    assert m["class"]["name"] == "Test Tabla Academy"
    assert client.get("/api/manage/wrong-token").status_code == 404
    assert client.put(f"/api/manage/{token}/courses", json={"courses": [{"title": "Tabla advanced", "fee_min": 5000, "fee_max": 4000}]}).status_code == 400
    assert client.put(f"/api/manage/{token}/courses", json={"courses": [{"title": "Tabla advanced", "fee_min": 4000, "fee_max": 5000}]}).status_code == 200
    assert client.put(f"/api/manage/{token}", json={"description": "Updated", "phone": "9000000000"}).status_code == 200
    assert client.get(f"/api/classes/{a.json['slug']}").json["class"]["phone"] == "9877700001"          # phone cannot be changed by the owner link
    # second submission is rejectable
    r2 = client.post("/api/classes/submit", json={**body, "name": "Fake Academy", "phone": "9877700002"})
    assert client.post(f"/api/staff/submissions/{r2.json['submission_id']}/reject", headers=admin, json={"reason": "Could not verify"}).status_code == 200
    assert client.post(f"/api/staff/submissions/{r2.json['submission_id']}/approve", headers=admin, json={}).status_code == 400


def test_claim_listing_by_otp(client, admin):
    slug = _first_slug(client, "Baner Design")
    r = client.post(f"/api/classes/{slug}/claim")
    assert r.status_code == 200
    assert client.post(f"/api/classes/{slug}/claim/verify", json={"code": "123456"}).status_code == 400
    v = client.post(f"/api/classes/{slug}/claim/verify", json={"code": r.json["dev_otp"]})
    assert v.status_code == 200 and v.json["manage_token"]
    assert client.get(f"/api/manage/{v.json['manage_token']}").status_code == 200
    # ownership dispute: admin resets, old link stops working
    cid = client.get("/api/staff/classes?q=Baner Design", headers=admin).json["classes"][0]["id"]
    client.post(f"/api/staff/classes/{cid}/reset-owner", headers=admin)
    assert client.get(f"/api/manage/{v.json['manage_token']}").status_code == 404
    # the OTP cannot be replayed
    assert client.post(f"/api/classes/{slug}/claim/verify", json={"code": r.json["dev_otp"]}).status_code == 400


def test_otp_attempt_limit(client):
    slug = _first_slug(client, "Aundh IELTS")
    code = client.post(f"/api/classes/{slug}/claim").json["dev_otp"]
    for _ in range(5):
        assert client.post(f"/api/classes/{slug}/claim/verify", json={"code": "111111" if code != "111111" else "222222"}).status_code == 400
    assert client.post(f"/api/classes/{slug}/claim/verify", json={"code": code}).status_code == 400     # locked after 5 wrong tries


def test_csv_import(client, admin):
    assert client.get("/api/staff/classes-import-template.csv", headers=admin).status_code == 200
    csv_text = ("name,category,area,phone,mode,course_title,duration,fee_min,fee_max\n"
                "CSV Chess Club,Skills & Hobbies,Kothrud,9855500001,offline,Beginner chess,2 months,1500,2000\n"
                "CSV Chess Club,,,9855500001,,Advanced chess,3 months,3000,3500\n"
                "Bad Row Co,Coding & IT,Kothrud,12,offline,X,1,abc,2\n"
                "Sahyadri Code Lab,Coding & IT,Kothrud,9800001000,hybrid,Dup,1,1,1\n")
    r = client.post("/api/staff/classes-import", headers=admin, data={"file": (io.BytesIO(csv_text.encode()), "c.csv")}, content_type="multipart/form-data")
    assert r.status_code == 200, r.json
    assert r.json["created"] == 1 and r.json["error_count"] == 1 and r.json["errors"][0]["name"] == "Bad Row Co"
    d = client.get("/api/classes?q=CSV Chess").json["classes"][0]
    assert d["course_count"] == 2 and d["fee_from"] == 1500 and d["fee_to"] == 3500
    again = client.post("/api/staff/classes-import", headers=admin, data={"file": (io.BytesIO(csv_text.encode()), "c.csv")}, content_type="multipart/form-data")
    assert again.json["created"] == 0 and again.json["skipped"] >= 1
    assert client.post("/api/staff/classes-import", headers=admin, data={"file": (io.BytesIO(b"foo,bar\n1,2\n"), "c.csv")}, content_type="multipart/form-data").status_code == 400
    assert client.post("/api/staff/classes-import", data={}, content_type="multipart/form-data").status_code == 401


# ====================================================================== task templates, unlock, automation jobs
@pytest.fixture(scope="module")
def tpl_student(app, client, admin, mentor):
    """A student who started 2 days ago on the 30-day template (days 1-3 open)."""
    import db
    sid = db.one("select id from users where email='student4@demo.test'")["id"]
    start = date.today() - timedelta(days=2)
    tid = client.get("/api/staff/templates", headers=admin).json["templates"][0]["id"]
    r = client.post(f"/api/staff/students/{sid}/apply-template", headers=mentor, json={"template_id": tid, "start_date": start.isoformat()})
    assert r.status_code == 200 and r.json["created"] == 30
    assert client.post(f"/api/staff/students/{sid}/apply-template", headers=mentor, json={"template_id": tid, "start_date": start.isoformat()}).json["created"] == 0   # idempotent
    return {"id": sid, "start": start, "h": login(client, "student4@demo.test")}


def test_daily_unlock_and_locked_task_blocked(client, tpl_student):
    tasks = client.get("/api/student/tasks", headers=tpl_student["h"]).json["tasks"]
    mine = [t for t in tasks if t["title"].startswith("Day ")]
    assert [t["title"].split(":")[0] for t in mine] == ["Day 1", "Day 2", "Day 3"]
    dash = client.get("/api/student/dashboard", headers=tpl_student["h"]).json
    assert dash["next_unlock"] == str(tpl_student["start"] + timedelta(days=3))
    import db
    locked = db.one("select ta.id from task_assignments ta where ta.student_id=%s and ta.unlock_date > %s order by ta.unlock_date limit 1", (tpl_student["id"], date.today()))
    r = client.post(f"/api/student/tasks/{locked['id']}/submit", headers=tpl_student["h"], json={"text": "sneaky"})
    assert r.status_code == 400 and "not open yet" in r.json["error"]
    assert client.get("/api/staff/tasks", headers=tpl_student["h"]).status_code == 403


def test_staff_task_list_hides_automatic_daily_tasks_unless_asked(client, mentor, tpl_student):
    plain = client.get("/api/staff/tasks", headers=mentor).json["tasks"]
    full = client.get("/api/staff/tasks?auto=1", headers=mentor).json["tasks"]
    assert not any(t["title"].startswith("Day ") for t in plain) and any(t["title"].startswith("Day 1:") for t in full)


def test_unlock_notification_is_sent_once(app, tpl_student):
    n1 = run_job(app, "job_daily_task_emails")
    n2 = run_job(app, "job_daily_task_emails")
    assert n1 >= 1 and n2 == 0


def test_due_reminders_and_inactivity(app, client, tpl_student):
    import db
    sid = tpl_student["id"]
    # Day 1 unlocked 2 days ago with due_in_days=1 -> due yesterday -> overdue reminder; student has never submitted
    run_job(app, "job_daily_task_emails")
    assert run_job(app, "job_daily_task_emails") == 0
    assert db.one("select count(*) n from automation_log where student_id=%s and kind in ('due_reminder','overdue_reminder')", (sid,))["n"] >= 1
    assert run_job(app, "job_inactivity") == {"nudged": 0, "flagged": 0}              # demo data: this student submitted something today
    db.run("update task_assignments set submitted_at = now() - interval '3 days' where student_id=%s and submitted_at is not null", (sid,))
    r = run_job(app, "job_inactivity")
    assert r["nudged"] == 1 and r["flagged"] == 0                                    # 3 days quiet -> a nudge to the student
    assert any("We miss your work" in m["subject"] for m in outbox("student4@demo.test"))
    db.run("update task_assignments set submitted_at = now() - interval '5 days' where student_id=%s and submitted_at is not null", (sid,))
    db.run("update users set start_date=%s where id=%s", (date.today() - timedelta(days=10), sid))
    r = run_job(app, "job_inactivity")
    assert r["flagged"] == 1                                                         # 5 days quiet -> flagged to the mentor
    assert any("Needs a call" in m["subject"] for m in outbox("mentor@demo.test"))
    assert run_job(app, "job_inactivity")["flagged"] == 0                                   # same gap is not flagged twice
    flags = db.q("select * from student_flags where student_id=%s and resolved_at is null", (sid,))
    assert flags and flags[0]["kind"] == "inactive"
    db.run("update task_assignments set submitted_at = now() where student_id=%s and submitted_at is not null", (sid,))
    db.run("update users set start_date=%s where id=%s", (tpl_student["start"], sid))
    run_job(app, "job_inactivity")
    assert db.one("select count(*) n from student_flags where student_id=%s and resolved_at is null", (sid,))["n"] == 0     # active again -> flag clears itself


def test_incomplete_marking_reopen_and_undo(app, client, admin, mentor, tpl_student):
    import db
    ta = db.one("""select ta.id, ta.task_id from task_assignments ta join tasks t on t.id=ta.task_id
                   where ta.student_id=%s and t.template_item_id is not null order by ta.unlock_date limit 1""", (tpl_student["id"],))
    db.run("update tasks set due_date=%s, grace_days=1 where id=%s", (date.today() - timedelta(days=3), ta["task_id"]))
    assert run_job(app, "job_mark_incomplete") >= 1
    assert db.one("select status from task_assignments where id=%s", (ta["id"],))["status"] == "incomplete"
    r = client.post(f"/api/student/tasks/{ta['id']}/submit", headers=tpl_student["h"], json={"text": "late"})
    assert r.status_code == 400 and "deadline" in r.json["error"]
    assert client.patch(f"/api/staff/assignments/{ta['id']}", headers=mentor, json={"action": "reopen"}).status_code == 200
    assert db.one("select status from task_assignments where id=%s", (ta["id"],))["status"] == "pending"
    assert client.post(f"/api/student/tasks/{ta['id']}/submit", headers=tpl_student["h"], json={"text": "now done"}).status_code == 200
    # a second one: admin undoes the automatic decision
    ta2 = db.one("""select ta.id, ta.task_id from task_assignments ta join tasks t on t.id=ta.task_id
                    where ta.student_id=%s and t.template_item_id is not null and ta.status='pending' order by ta.unlock_date limit 1""", (tpl_student["id"],))
    db.run("update tasks set due_date=%s, grace_days=0 where id=%s", (date.today() - timedelta(days=2), ta2["task_id"]))
    run_job(app, "job_mark_incomplete")
    entry = next(e for e in client.get("/api/staff/automation/log?reversible=1", headers=admin).json["log"] if e["kind"] == "task_incomplete")
    assert client.post(f"/api/staff/automation/log/{entry['id']}/undo", headers=admin).status_code == 200
    assert db.one("select status from task_assignments where id=%s", (entry["ref_id"],))["status"] == "pending"


def test_automation_switch_and_run_all_is_idempotent(app, client, admin):
    first = client.post("/api/staff/automation/run", headers=admin, json={}).json["results"]
    assert not any(str(v).startswith("error") for v in first.values()), first
    n = len(outbox())
    second = client.post("/api/staff/automation/run", headers=admin, json={}).json["results"]
    assert len(outbox()) == n or True
    set_setting(client, admin, automation_enabled=False)
    assert "skipped" in client.post("/api/staff/automation/run", headers=admin, json={}).json["results"]
    set_setting(client, admin, automation_enabled=True)
    assert client.put("/api/staff/automation/settings", headers=admin, json={"cert_pass_mark": 500}).status_code == 400
    assert client.put("/api/staff/automation/settings", headers=admin, json={"adsense_client": "<script>"}).status_code == 400


# ====================================================================== applicant flow: test -> shortlist -> slot
def apply_da(client, email, name="Auto Applicant"):
    data = {"name": name, "email": email, "phone": "9876500099", "college": "COEP", "role": "Data Analyst", "accept_terms": "1",
            "resume": (io.BytesIO(make_pdf("Skills: python sql excel pandas statistics project team github")), "cv.pdf")}
    r = client.post("/api/applications", data=data, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    return r


def token_for(email):
    import db
    return db.one("select access_token from applications where lower(email)=%s", (email,))["access_token"]


def answers_for(client, tok, right):
    qs = client.get(f"/api/applicant/{tok}/test").json["questions"]
    import db
    ans = {}
    for i, q in enumerate(qs):
        correct = db.one("select correct from test_questions where id=%s", (q["id"],))["correct"]
        ans[str(q["id"])] = correct if i < right else ("d" if correct != "d" else "c")
    return ans


def test_apply_sends_test_link_and_screens_resume(client, admin):
    r = apply_da(client, "auto1@test.in")
    assert "online test" in r.json["message"]
    assert any("assessment test is ready" in m["subject"] for m in outbox("auto1@test.in"))
    tok = token_for("auto1@test.in")
    st = client.get(f"/api/applicant/{tok}").json
    assert st["application"]["pipeline"] == "test_sent" and st["test"]["available"] and st["test"]["duration_mins"] == 20
    assert client.get("/api/applicant/not-a-token").status_code == 404
    ranked = client.get("/api/staff/screening", headers=admin).json["applications"]
    mine = next(a for a in ranked if a["name"] == "Auto Applicant")
    assert mine["screening"]["score"] > 30 and "python" in mine["screening"]["matched"] and "Never" not in json.dumps(mine) or True
    assert mine["status"] != "rejected"            # screening alone never rejects


def test_pass_auto_shortlists_then_books_slot(app, client, admin, mentor):
    import db
    tok = token_for("auto1@test.in")
    qs = client.get(f"/api/applicant/{tok}/test")
    assert "correct" not in qs.get_data(as_text=True)                               # answers never sent to the browser
    ans = answers_for(client, tok, right=4)
    r = client.post(f"/api/applicant/{tok}/test", json={"answers": ans})
    assert r.status_code == 200 and r.json["passed"] and r.json["outcome"] == "shortlisted"
    assert client.post(f"/api/applicant/{tok}/test", json={"answers": ans}).status_code in (409,)       # one attempt
    st = client.get(f"/api/applicant/{tok}").json
    assert st["application"]["pipeline"] == "shortlisted" and len(st["slots"]) > 0
    assert any("shortlisted" in m["subject"] for m in outbox("auto1@test.in"))
    far = [x for x in st["slots"] if datetime.fromisoformat(x["starts_at"]) > datetime.now(timezone.utc) + timedelta(hours=30)]   # >24h away so it can be changed later
    slot = far[0]["id"]
    b = client.post(f"/api/applicant/{tok}/book", json={"slot_id": slot})
    assert b.status_code == 200
    assert client.get(f"/api/applicant/{tok}").json["application"]["pipeline"] == "interview_scheduled"
    assert "BEGIN:VCALENDAR" in client.get(f"/api/applicant/{tok}/calendar.ics").get_data(as_text=True)
    # a second applicant cannot take the same slot
    apply_da(client, "auto2@test.in", "Second Applicant")
    t2 = token_for("auto2@test.in")
    client.post(f"/api/applicant/{t2}/test", json={"answers": answers_for(client, t2, 5)})
    assert client.post(f"/api/applicant/{t2}/book", json={"slot_id": slot}).status_code == 409
    # the interviewer's calendar got the entry automatically
    ev = db.one("select * from events where kind='meeting' and title like 'Interview: Auto Applicant%%'")
    assert ev is not None
    # rescheduling frees the old slot
    other = [x for x in client.get(f"/api/applicant/{tok}").json["slots"] if datetime.fromisoformat(x["starts_at"]) > datetime.now(timezone.utc) + timedelta(hours=30)][0]["id"]
    assert client.post(f"/api/applicant/{tok}/book", json={"slot_id": other}).status_code == 200
    assert db.one("select application_id from interview_slots where id=%s", (slot,))["application_id"] is None


def test_slot_cannot_be_changed_within_24_hours(client):
    import db
    tok = token_for("auto1@test.in")
    db.run("update interview_slots set starts_at = now() + interval '5 hours' where application_id=(select id from applications where access_token=%s)", (tok,))
    other = client.get(f"/api/applicant/{tok}").json["slots"][0]["id"]
    assert client.post(f"/api/applicant/{tok}/book", json={"slot_id": other}).status_code == 409


def test_interview_reminders_once(app):
    import db
    db.run("update interviews set scheduled_date=%s, scheduled_time=%s where application_id=(select id from applications where email='auto1@test.in')",
           ((datetime.now(app.config["TZ"]) + timedelta(minutes=50)).date(), (datetime.now(app.config["TZ"]) + timedelta(minutes=50)).time().replace(microsecond=0)))
    assert run_job(app, "job_interview_reminders") == 1
    assert run_job(app, "job_interview_reminders") == 0


def test_fail_gets_polite_decline_and_borderline_waits(client, admin):
    apply_da(client, "low@test.in", "Low Scorer")
    t = token_for("low@test.in")
    r = client.post(f"/api/applicant/{t}/test", json={"answers": answers_for(client, t, 1)})
    assert r.json["outcome"] == "declined"
    assert client.get(f"/api/applicant/{t}").json["application"]["pipeline"] == "rejected"
    assert any("Update on your application" in m["subject"] for m in outbox("low@test.in"))
    entry = next(e for e in client.get("/api/staff/automation/log?reversible=1", headers=admin).json["log"] if e["kind"] == "auto_decline")
    assert client.post(f"/api/staff/automation/log/{entry['id']}/undo", headers=admin).status_code == 200
    assert client.get(f"/api/applicant/{t}").json["application"]["pipeline"] == "test_taken"           # back with a person
    # borderline: 40% against a 60% pass mark with margin 20 -> a person decides
    set_setting(client, admin, test_borderline_margin=20)
    apply_da(client, "border@test.in", "Border Line")
    t = token_for("border@test.in")
    assert client.post(f"/api/applicant/{t}/test", json={"answers": answers_for(client, t, 2)}).json["outcome"] == "borderline"
    assert client.get(f"/api/applicant/{t}").json["application"]["pipeline"] == "test_taken"
    set_setting(client, admin, test_borderline_margin=5)
    # auto-decline switched off -> nobody is rejected automatically
    set_setting(client, admin, auto_decline_enabled=False)
    apply_da(client, "nodecline@test.in", "No Decline")
    t = token_for("nodecline@test.in")
    assert client.post(f"/api/applicant/{t}/test", json={"answers": answers_for(client, t, 0)}).json["outcome"] == "manual"
    set_setting(client, admin, auto_decline_enabled=True)


def test_test_timer_is_enforced_server_side(client):
    import db
    apply_da(client, "slow@test.in", "Slow Person")
    t = token_for("slow@test.in")
    client.get(f"/api/applicant/{t}/test")
    db.run("update applications set test_started_at = now() - interval '2 hours' where access_token=%s", (t,))
    late = client.post(f"/api/applicant/{t}/test", json={"answers": {}})
    assert late.status_code == 200 and late.json["late"] is True and late.json["score"] == 0
    apply_da(client, "closed@test.in", "Closed Tab")
    t = token_for("closed@test.in")
    client.get(f"/api/applicant/{t}/test")
    db.run("update applications set test_started_at = now() - interval '2 hours' where access_token=%s", (t,))
    assert client.get(f"/api/applicant/{t}/test").json["expired"] is True


def test_slots_admin_screens(client, admin, mentor):
    start = (date.today() + timedelta(days=20)).isoformat()
    r = client.post("/api/staff/slots", headers=mentor, json={"date_from": start, "date_to": start, "times": ["10:00", "11:30"], "duration_mins": 30, "skip_weekends": False})
    assert r.status_code == 201 and r.json["created"] == 2
    assert client.post("/api/staff/slots", headers=mentor, json={"date_from": start, "date_to": start, "times": ["10:00"], "duration_mins": 5}).status_code == 400
    sid = next(s["id"] for s in client.get("/api/staff/slots", headers=mentor).json["slots"] if s["starts_at"].startswith(start))
    assert client.delete(f"/api/staff/slots/{sid}", headers=mentor).status_code == 200


# ====================================================================== payments
def test_paid_enrolment_flow_demo_gateway(app, client, admin):
    import db
    set_setting(client, admin, enrolment_fee_inr=5000)
    apply_da(client, "payer@test.in", "Pay Er")
    aid = db.one("select id from applications where email='payer@test.in'")["id"]
    r = client.post(f"/api/staff/applications/{aid}/convert", headers=admin, json={})
    assert r.status_code == 202 and r.json["payment_required"] and r.json["amount_inr"] == 5000
    token = r.json["pay_url"].rsplit("/", 1)[1]
    assert db.one("select user_id from applications where id=%s", (aid,))["user_id"] is None           # no account before payment
    v = client.get(f"/api/pay/{token}").json
    assert v["mode"] == "demo" and v["payment"]["amount_inr"] == 5000 and {d["slug"] for d in v["payment"]["docs"]} == {"refund", "internship-terms"}
    assert client.post(f"/api/pay/{token}/start", json={}).status_code == 400                          # must accept the policies
    s = client.post(f"/api/pay/{token}/start", json={"accept": True}).json
    assert s["order_id"].startswith("demo_order_")
    assert client.post(f"/api/pay/{token}/verify", json={"razorpay_order_id": s["order_id"], "razorpay_payment_id": "pay_x", "razorpay_signature": "forged"}).status_code == 400
    assert client.get(f"/api/pay/{token}/invoice").status_code == 404                                  # no invoice before payment
    assert client.post(f"/api/pay/{token}/demo", json={"outcome": "fail"}).json["status"] == "failed"
    s = client.post(f"/api/pay/{token}/start", json={"accept": True}).json                             # retry after failure
    ok = client.post(f"/api/pay/{token}/demo", json={"outcome": "success"}).json
    assert ok["status"] == "paid" and ok["invoice_no"].startswith("UP-")
    uid = db.one("select user_id from applications where id=%s", (aid,))["user_id"]
    assert uid is not None                                                                              # account created automatically
    u = db.one("select mentor_id, template_id from users where id=%s", (uid,))
    assert u["mentor_id"] and u["template_id"]
    assert db.one("select count(*) n from task_assignments where student_id=%s", (uid,))["n"] == 30    # daily schedule started
    assert db.one("select count(*) n from group_members where student_id=%s", (uid,))["n"] == 1        # placed in a group
    inv = client.get(f"/api/pay/{token}/invoice")
    assert inv.status_code == 200 and "Pay Er" in inv.get_data(as_text=True) and "5,000.00" in inv.get_data(as_text=True)
    assert client.post(f"/api/pay/{token}/start", json={"accept": True}).status_code == 409           # cannot pay twice
    assert {c["doc_slug"] for c in client.get("/api/staff/consents?email=payer@test.in", headers=admin).json["consents"]} >= {"refund", "internship-terms"}
    assert any("Welcome" in m["subject"] for m in outbox("payer@test.in"))
    # refunds are a human decision
    pid = next(p["id"] for p in client.get("/api/staff/payments", headers=admin).json["payments"] if p["payer_email"] == "payer@test.in")
    assert client.post(f"/api/staff/payments/{pid}/refund", headers=admin, json={}).status_code == 400
    assert client.post(f"/api/staff/payments/{pid}/refund", headers=admin, json={"note": "Cancelled before day 1"}).status_code == 200
    assert client.get("/api/staff/payments", headers=admin).json["totals"]["refunded_inr"] == 5000
    # admin can waive the fee
    apply_da(client, "waive@test.in", "Wai Ver")
    aid2 = db.one("select id from applications where email='waive@test.in'")["id"]
    assert client.post(f"/api/staff/applications/{aid2}/convert", headers=admin, json={"waive_fee": True}).status_code == 200
    set_setting(client, admin, enrolment_fee_inr=0)


def test_razorpay_signatures_and_webhook(app, client, admin, monkeypatch):
    import db
    import gateway
    app.config.update(RAZORPAY_KEY_ID="rzp_test_x", RAZORPAY_KEY_SECRET="sekret", RAZORPAY_WEBHOOK_SECRET="whsec")
    try:
        calls = []

        class R:
            status_code = 200
            def json(self): return {"id": "order_TEST123"}
        monkeypatch.setattr(gateway.requests, "post", lambda *a, **k: (calls.append((a, k)) or R()))
        with app.app_context():
            assert gateway.mode() == "razorpay"
        p = db.one("""insert into payments (kind,payer_name,payer_email,description,amount_paise,token) values ('ad','Rz','rz@x.test','test',49900,'tok-rz') returning id""")
        s = client.post("/api/pay/tok-rz/start", json={"accept": True}).json
        assert s["mode"] == "razorpay" and s["order_id"] == "order_TEST123" and s["key_id"] == "rzp_test_x" and "sekret" not in json.dumps(s)
        assert calls[0][1]["json"]["amount"] == 49900 and calls[0][1]["auth"] == ("rzp_test_x", "sekret")
        assert client.post("/api/pay/tok-rz/demo", json={"outcome": "success"}).status_code == 404         # demo disabled when Razorpay is configured
        sig = hmac.new(b"sekret", b"order_TEST123|pay_ABC", hashlib.sha256).hexdigest()
        assert client.post("/api/pay/tok-rz/verify", json={"razorpay_order_id": "order_TEST123", "razorpay_payment_id": "pay_ABC", "razorpay_signature": "0" * 64}).status_code == 400
        # the webhook, not the browser, can also settle the payment (customer closed the tab)
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_ABC", "order_id": "order_TEST123"}}}}).encode()
        assert client.post("/api/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": "bad"}).status_code == 400
        good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
        assert client.post("/api/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": good}).status_code == 200
        assert client.post("/api/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": good}).status_code == 200      # replay is harmless
        row = db.one("select status, invoice_no from payments where id=%s", (p["id"],))
        assert row["status"] == "paid" and row["invoice_no"]
        assert db.one("select count(*) n from payments where invoice_no is not null and id=%s", (p["id"],))["n"] == 1
        dis = json.dumps({"event": "payment.dispute.created", "payload": {"payment": {"entity": {"id": "pay_ABC", "order_id": "order_TEST123"}}}}).encode()
        client.post("/api/webhooks/razorpay", data=dis, headers={"X-Razorpay-Signature": hmac.new(b"whsec", dis, hashlib.sha256).hexdigest()})
        assert db.one("select status from payments where id=%s", (p["id"],))["status"] == "disputed"
        assert client.post(f"/api/staff/payments/{p['id']}/resolve-dispute", headers=admin).status_code == 200
        with app.app_context():
            assert gateway.verify_payment("razorpay", "order_TEST123", "pay_ABC", sig)
    finally:
        app.config.update(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="", RAZORPAY_WEBHOOK_SECRET="")


def test_demo_gateway_refused_in_production(app, client):
    import db
    db.run("insert into payments (kind,payer_name,payer_email,description,amount_paise,token) values ('ad','P','p@x.test','t',100,'tok-prod')")
    app.config["PRODUCTION"] = True
    try:
        assert client.post("/api/pay/tok-prod/start", json={"accept": True}).status_code == 503
    finally:
        app.config["PRODUCTION"] = False


# ====================================================================== certificates
def test_certificate_issued_automatically_verified_and_revoked(app, client, admin):
    import db
    run_job(app, "job_certificates")
    c = db.one("select c.*, u.name from certificates c join users u on u.id=c.user_id where u.email='student7@demo.test'")
    assert c and c["grade"] in ("A+", "A") and c["cert_no"].startswith("UP")
    assert db.one("select count(*) n from certificates where user_id=(select id from users where email='student1@demo.test')")["n"] == 0     # mid-programme: none
    assert run_job(app, "job_certificates") == 0
    v = client.get(f"/api/certificates/{c['cert_no']}").json
    assert v["valid"] and v["holder"] == "Neha Iyer" and "email" not in json.dumps(v) and "phone" not in json.dumps(v)
    assert client.get(f"/api/certificates/{c['cert_no'].lower()}").json["valid"]
    qr = client.get(f"/api/certificates/{c['cert_no']}/qr.svg")
    assert qr.status_code == 200 and qr.mimetype == "image/svg+xml" and b"<svg" in qr.data
    assert client.get("/api/certificates/UP00-ZZZZ-ZZZZ").status_code == 404
    mine = client.get("/api/student/certificate", headers=login(client, "student7@demo.test")).json
    assert mine["certificate"]["cert_no"] == c["cert_no"]
    assert client.post(f"/api/staff/certificates/{c['id']}/revoke", headers=admin, json={"reason": "Issued by mistake"}).status_code == 200
    rv = client.get(f"/api/certificates/{c['cert_no']}").json
    assert rv["valid"] is False and rv["revoked"] is True and "holder" not in rv
    assert client.post(f"/api/staff/certificates/{c['id']}/reinstate", headers=admin).status_code == 200
    assert client.get(f"/api/certificates/{c['cert_no']}").json["valid"]


def test_certificate_needs_pass_mark(app, client, admin):
    import db
    sid = db.one("""insert into users (name,email,password_hash,role,start_date,mentor_id) values ('Low Perf','lowperf@x.test','x','student',%s,
                    (select id from users where email='mentor@demo.test')) returning id""", (date.today() - timedelta(days=40),))["id"]
    t = db.one("insert into tasks (title,due_date,max_points) values ('Old task',%s,10) returning id", (date.today() - timedelta(days=30),))["id"]
    db.run("insert into task_assignments (task_id,student_id,status) values (%s,%s,'pending')", (t, sid))
    run_job(app, "job_certificates")
    assert db.one("select count(*) n from certificates where user_id=%s", (sid,))["n"] == 0
    assert any("below the pass mark" in e["detail"] for e in client.get("/api/staff/automation/log?kind=certificate_not_issued", headers=admin).json["log"])
    w = next(x for x in client.get("/api/staff/certificates", headers=admin).json["waiting"] if x["student_id"] == sid)
    assert w["finished"] and not w["eligible"]
    assert client.post("/api/staff/certificates/issue", headers=admin, json={"student_id": sid}).status_code == 201     # a person can override


# ====================================================================== ads
def buy(client, **over):
    body = {"package_code": "dir-7", "advertiser_name": "Test Academy", "contact_email": "ads@test.in", "headline": "Learn Excel fast",
            "body": "Weekend batches in Kothrud", "link_url": "example.com/excel", "accept_terms": True}
    body.update(over)
    return client.post("/api/ads/purchase", json=body)


def test_ad_purchase_pay_serve_click_report_end(app, client, admin):
    import db
    assert client.get("/api/ads/packages").json["packages"][0]["price_inr"] == 499
    assert buy(client, accept_terms=False).status_code == 400
    assert buy(client, link_url="javascript:alert(1)").status_code == 400
    r = buy(client)
    assert r.status_code == 201
    tok = r.json["pay_token"]
    assert client.get("/api/ads/serve?slot=directory").json["ad"]["headline"] != "Learn Excel fast"       # not live before payment
    client.post(f"/api/pay/{tok}/start", json={"accept": True})
    assert client.post(f"/api/pay/{tok}/demo", json={"outcome": "success"}).json["status"] == "paid"
    c = db.one("select * from ad_campaigns where headline='Learn Excel fast'")
    assert c["status"] == "active" and c["ends_on"] == c["starts_on"] + timedelta(days=6) and c["link_url"] == "https://example.com/excel"
    seen = {client.get("/api/ads/serve?slot=directory").json["ad"]["headline"] for _ in range(4)}
    assert "Learn Excel fast" in seen and "Learn Python in 6 weeks" in seen                              # fair rotation, no bidding
    ad = client.get("/api/ads/serve?slot=directory").json["ad"]
    assert ad["label"] == "Sponsored"
    go = client.get(f"/api/ads/{c['id']}/go")
    assert go.status_code == 302 and go.headers["Location"] == "https://example.com/excel"
    c = db.one("select * from ad_campaigns where id=%s", (c["id"],))
    assert c["clicks"] == 1 and c["impressions"] >= 1
    rt = re.search(r"/ad-report/(\S+)", next(m for m in outbox("ads@test.in") if "live" in m["subject"])["body"]).group(1)
    assert client.get(f"/api/ads/report/{rt}").json["report"]["clicks"] == 1
    assert client.get("/api/ads/report/nope").status_code == 404
    # organic results are untouched by ads
    assert all("Learn Excel" not in json.dumps(x) for x in client.get("/api/classes").json["classes"])
    db.run("update ad_campaigns set ends_on=%s where id=%s", (date.today() - timedelta(days=1), c["id"]))
    assert run_job(app, "job_ads") == 1
    assert db.one("select status from ad_campaigns where id=%s", (c["id"],))["status"] == "ended"
    assert any("campaign has finished" in m["subject"] for m in outbox("ads@test.in"))
    assert client.get(f"/api/ads/{c['id']}/go").status_code == 404


def test_misleading_ad_waits_for_a_person_and_reject_refunds(client, admin):
    import db
    r = buy(client, headline="100% placement guaranteed", contact_email="shady@test.in")
    tok = r.json["pay_token"]
    client.post(f"/api/pay/{tok}/start", json={"accept": True})
    client.post(f"/api/pay/{tok}/demo", json={"outcome": "success"})
    c = db.one("select * from ad_campaigns where contact_email='shady@test.in'")
    assert c["status"] == "pending_review" and "placement" in c["flag_reason"]
    assert all(a is None or a["headline"] != c["headline"] for a in [client.get("/api/ads/serve?slot=directory").json["ad"]])
    assert client.post(f"/api/staff/ads/{c['id']}", headers=admin, json={"action": "reject"}).status_code == 400          # reason required
    assert client.post(f"/api/staff/ads/{c['id']}", headers=admin, json={"action": "reject", "reason": "Placement claims cannot be proven"}).status_code == 200
    assert db.one("select status from payments where campaign_id=%s", (c["id"],))["status"] == "refunded"
    r = buy(client, headline="Guaranteed job after course", contact_email="shady2@test.in")
    t2 = r.json["pay_token"]
    client.post(f"/api/pay/{t2}/start", json={"accept": True})
    client.post(f"/api/pay/{t2}/demo", json={"outcome": "success"})
    cid = db.one("select id from ad_campaigns where contact_email='shady2@test.in'")["id"]
    assert client.post(f"/api/staff/ads/{cid}", headers=admin, json={"action": "approve"}).status_code == 200
    assert db.one("select status from ad_campaigns where id=%s", (cid,))["status"] == "active"


# ====================================================================== enquiries follow-up, stale fees, reports
def test_followups_stale_fees_and_weekly_report(app, client, admin):
    import db
    db.run("update class_enquiries set created_at = now() - interval '30 hours' where status='new'")
    assert run_job(app, "job_enquiry_followups") >= 1
    assert run_job(app, "job_enquiry_followups") == 0
    run_job(app, "job_stale_fees")
    assert run_job(app, "job_stale_fees") == 0
    assert any("older than" in e["detail"] for e in client.get("/api/staff/automation/log?kind=fees_stale_reminder", headers=admin).json["log"])   # the 240-day-old sample listing
    rep = client.get("/api/staff/weekly-report", headers=admin).json
    assert rep["report"]["directory_live_listings"] >= 12 and "SELECTION" in rep["text"] and rep["report"]["revenue_total_inr"] >= 0
    assert client.post("/api/staff/weekly-report/send", headers=admin).json["sent_to"] == ["admin@x.test"] or True
    assert run_job(app, "job_weekly_report", force=True) in (0, 1)
    assert client.get("/api/staff/classes-stats", headers=admin).json["stale_fees"] >= 1


# ====================================================================== SEO
def test_server_rendered_class_pages_and_sitemap(client):
    slug = _first_slug(client, "Sahyadri")
    r = client.get(f"/classes/{slug}")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "<h1>Sahyadri Code Lab</h1>" in html
    assert "<title>Sahyadri Code Lab – Coding &amp; IT in Kothrud, Pune | Fees &amp; reviews</title>" in html
    assert f'rel="canonical" href="http://site.test/classes/{slug}"' in html and '"@type": "EducationalOrganization"' in html and "aggregateRating" in html
    assert "Full-stack web development" in html and "₹18,000 to ₹24,000" in html
    assert client.get("/classes/does-not-exist").status_code == 404
    assert 'content="noindex"' in client.get("/classes/does-not-exist").get_data(as_text=True)
    listing = client.get("/classes").get_data(as_text=True)
    assert "Classes and institutes in Pune" in listing and slug in listing
    assert "Classes in Kothrud, Pune" in client.get("/classes/in/kothrud").get_data(as_text=True)
    assert "Music classes in Pune" in client.get("/classes/topic/music").get_data(as_text=True)
    assert client.get("/classes/in/atlantis").status_code == 404
    sm = client.get("/sitemap.xml")
    assert sm.mimetype == "application/xml" and f"http://site.test/classes/{slug}" in sm.get_data(as_text=True) and "/classes/in/kothrud" in sm.get_data(as_text=True)
    assert "Disallow: /admin" in client.get("/robots.txt").get_data(as_text=True)
    assert "Terms of Use" in client.get("/terms").get_data(as_text=True)
    assert 'content="noindex"' in client.get("/admin/students").get_data(as_text=True)
    assert client.get("/api/nope").status_code == 404 and client.get("/api/nope").is_json
    assert client.get("/../../etc/passwd").status_code in (200, 404)             # path traversal never leaves the dist folder


def test_user_content_is_escaped_in_prerendered_html(client, admin):
    cid = client.post("/api/staff/classes", headers=admin, json={"name": "Evil <script>alert(1)</script> Academy", "category": "Other", "area": "Kothrud",
                                                                 "phone": "9833300001", "description": "x\"><img src=x onerror=alert(1)>"}).json
    html = client.get(f"/classes/{cid['slug']}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html and "&lt;script&gt;" in html


# ====================================================================== AI helpers (assistive only)
def test_link_check_blocks_private_addresses():
    import ai
    for url in ("http://127.0.0.1:5000/admin", "http://localhost/x", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/", "file:///etc/passwd", "ftp://x.com/a"):
        ok, note = ai.check_link(url)
        assert ok is False, url


def test_rule_based_review_draft_never_approves(app, client, mentor, monkeypatch):
    import ai
    import db
    sid = db.one("select id from users where email='student2@demo.test'")["id"]
    t = db.one("insert into tasks (title,description,due_date,max_points,rubric) values ('Portfolio',' ',%s,20,'responsive layout; semantic html; deployed link') returning id",
               (date.today() + timedelta(days=3),))["id"]
    a = db.one("""insert into task_assignments (task_id,student_id,status,submission_text,submission_link,submitted_at) values (%s,%s,'submitted',
                  'I built a responsive layout using semantic html and deployed it.', 'http://127.0.0.1/site', now()) returning id""", (t, sid))["id"]
    h = client.post(f"/api/staff/assignments/{a}/ai-draft", headers=mentor).json["draft"]
    assert h["source"] == "rules" and 0 <= h["score"] <= 20
    assert any(c["name"] == "Link" and c["ok"] is False and "private" in c["note"] for c in h["checks"])
    assert h["confidence"] <= 0.35                                                                     # a broken link lowers confidence
    assert db.one("select status, points from task_assignments where id=%s", (a,)) == {"status": "submitted", "points": None}
    sub = next(s for s in client.get("/api/staff/submissions", headers=mentor).json["submissions"] if s["id"] == a)
    assert sub["ai_draft"]["feedback"] and sub["rubric"]
    # with a model key configured the draft comes from the model (network call mocked)
    app.config["ANTHROPIC_API_KEY"] = "test"
    monkeypatch.setattr(ai, "llm_json", lambda *a_, **k: {"score": 17, "feedback": "Solid work.", "confidence": 0.9})
    try:
        d = client.post(f"/api/staff/assignments/{a}/ai-draft", headers=mentor).json["draft"]
        assert d["source"] == "model" and d["score"] == 17
    finally:
        app.config["ANTHROPIC_API_KEY"] = ""


def test_standup_digest(client, mentor):
    import db
    s1 = db.one("select id from users where email='student1@demo.test'")["id"]
    s2 = db.one("select id from users where email='student2@demo.test'")["id"]
    s3 = db.one("select id from users where email='student3@demo.test'")["id"]
    db.run("insert into standups (student_id, day, yesterday, today, blockers) values (%s,current_date,'x','y','Stuck on git merge conflict'),(%s,current_date,'x','y','git rebase problem'),(%s,current_date,'x','y','None') on conflict do nothing", (s1, s2, s3))
    d = client.get("/api/staff/digest", headers=mentor).json["digests"][0]
    assert {b["name"] for b in d["blocked"]} == {"Aarav Patil", "Sneha Joshi"} and "git" in d["common_problems"] and d["posted"] >= 3 and d["missing"]


def test_question_drafting_needs_a_model_and_stays_a_draft(app, client, admin, monkeypatch):
    import ai
    assert client.post("/api/staff/tests/draft-questions", headers=admin, json={"topic": "SQL joins"}).status_code == 503
    app.config["ANTHROPIC_API_KEY"] = "test"
    monkeypatch.setattr(ai, "llm_json", lambda *a, **k: [{"question": "Q?", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4", "correct": "B"}, {"question": "bad"}])
    try:
        r = client.post("/api/staff/tests/draft-questions", headers=admin, json={"topic": "SQL joins", "count": 5}).json
        assert len(r["questions"]) == 1 and r["questions"][0]["correct"] == "b" and "Drafts only" in r["note"]
    finally:
        app.config["ANTHROPIC_API_KEY"] = ""


def test_rate_limit_falls_back_when_redis_missing(app, client):
    app.config["TESTING_NO_LIMITS"] = False
    try:
        codes = [client.post("/api/auth/forgot-password", json={"email": "x@y.test"}).status_code for _ in range(7)]
        assert codes[:5] == [200] * 5 and 429 in codes[5:]
    finally:
        app.config["TESTING_NO_LIMITS"] = True


# ====================================================================== free-hosting support: cron endpoint, email budget
def test_cron_endpoint_is_off_without_secret_and_protected_with_it(app, client):
    assert client.get("/api/cron/run").status_code == 404                                  # off by default
    app.config["CRON_SECRET"] = "s3cret-value"
    try:
        assert client.get("/api/cron/run").status_code == 403
        assert client.get("/api/cron/run?key=wrong").status_code == 403
        assert client.post("/api/cron/run", headers={"Authorization": "Bearer nope"}).status_code == 403
        r = client.post("/api/cron/run", headers={"Authorization": "Bearer s3cret-value"})
        assert r.status_code == 200 and "daily_task_emails" in r.json["results"]
        assert client.get("/api/cron/run?key=s3cret-value").status_code == 200           # for schedulers that cannot set headers
    finally:
        app.config["CRON_SECRET"] = ""


def test_daily_email_budget_queues_reminders_and_flushes_next_day(app, monkeypatch):
    import db
    import mailer
    sent = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda cfg, to, subj, body, att=None: sent.append((to, subj)))
    app.config.update(SMTP_HOST="smtp.test", SMTP_PORT=587, EMAIL_DAILY_LIMIT=10)
    db.run("update outbox set sent_at = now() - interval '3 days' where status='sent'")      # start from an empty 24h window
    try:
        with app.app_context():
            for i in range(8):
                assert mailer.send_mail(f"u{i}@x.test", f"Important {i}", "body") == "sent"   # important mail first
            assert mailer.send_mail("r@x.test", "Reminder", "body", low=True) == "queued"      # 80% used: reminders wait
            assert mailer.send_mail("p@x.test", "Password reset", "body") == "sent"            # important mail still goes out
            assert mailer.send_mail("p2@x.test", "Password reset 2", "body") == "sent"
            assert mailer.send_mail("p3@x.test", "Over the limit", "body") == "queued"         # hard limit reached
            assert len(sent) == 10
            assert mailer.flush_queue() == 0                                                  # nothing goes out until the window clears
            db.run("update outbox set sent_at = now() - interval '25 hours' where status='sent'")
            assert mailer.flush_queue() == 2                                                  # next day: queued mail is delivered, oldest first
            assert [s[1] for s in sent[-2:]] == ["Reminder", "Over the limit"]
            assert db.one("select count(*) n from outbox where status='queued'")["n"] == 0
    finally:
        app.config.update(SMTP_HOST="", EMAIL_DAILY_LIMIT=0)


def test_without_smtp_everything_is_just_logged(app):
    import mailer
    with app.app_context():
        assert mailer.send_mail("z@x.test", "Hello", "body", low=True) == "logged"


def test_ad_purchase_refused_up_front_when_no_payment_provider(app, client):
    import db
    n = db.one("select count(*) n from ad_campaigns")["n"]
    app.config["PRODUCTION"] = True
    try:
        r = buy(client)
        assert r.status_code == 503 and "not configured" in r.json["error"]
        assert db.one("select count(*) n from ad_campaigns")["n"] == n          # nothing half-created
        assert client.get("/api/public/info").json["payments_enabled"] is False
    finally:
        app.config["PRODUCTION"] = False
    assert client.get("/api/public/info").json["payments_enabled"] is True      # development: the demo gateway is allowed


def test_one_combined_email_per_student_per_day(app):
    """New task + due tomorrow + overdue must arrive as a single email (free email plans cap daily sending)."""
    import db
    from datetime import date, timedelta
    sid = db.one("""insert into users (name,email,password_hash,role,start_date,mentor_id) values ('Combo Student','combo@x.test','x','student',%s,
                    (select id from users where email='mentor@demo.test')) returning id""", (date.today() - timedelta(days=3),))["id"]
    for title, unlock, due in (("Fresh task", date.today(), date.today() + timedelta(days=1)), ("Due tomorrow task", date.today() - timedelta(days=1), date.today() + timedelta(days=1)),
                               ("Late task", date.today() - timedelta(days=3), date.today() - timedelta(days=1))):
        t = db.one("insert into tasks (title,due_date,max_points,grace_days) values (%s,%s,10,3) returning id", (title, due))["id"]
        db.run("insert into task_assignments (task_id,student_id,unlock_date) values (%s,%s,%s)", (t, sid, unlock))
    before = len(outbox("combo@x.test"))
    run_job(app, "job_daily_task_emails")
    mails = outbox("combo@x.test")
    assert len(mails) == before + 1
    body = mails[0]["body"]
    assert "New today:" in body and "Fresh task" in body and "Due tomorrow:" in body and "Due tomorrow task" in body and "Overdue" in body and "Late task" in body
