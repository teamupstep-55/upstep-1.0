"""End-to-end API tests against a real PostgreSQL database.
Run:  TEST_DATABASE_URL=postgresql://user:pass@localhost/dbname python -m pytest -q   (the database is wiped!)"""
import io
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = os.environ.get("TEST_DATABASE_URL", "postgresql://sp:sp@localhost/sp_test")
PDF = b"%PDF-1.4 test resume"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import psycopg
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("drop schema public cascade; create schema public;")
    from app import create_app
    a = create_app({"DATABASE_URL": URL, "TESTING": True, "TESTING_NO_LIMITS": True,
                    "LOCAL_UPLOAD_DIR": str(tmp_path_factory.mktemp("up")), "SUPABASE_URL": ""})
    r = a.test_cli_runner()
    assert r.invoke(args=["init-db"]).exit_code == 0
    assert r.invoke(args=["create-admin", "--email", "admin@x.test", "--name", "Admin", "--password", "Admin@1234"]).exit_code == 0
    assert r.invoke(args=["demo-data"]).exit_code == 0
    # these original tests describe the MANUAL selection flow; the automatic flow is covered in test_v2.py
    import db
    db.run("update settings set value='0' where key='automation_enabled'")
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
def s1(client):
    return login(client, "student1@demo.test")


@pytest.fixture(scope="module")
def s5(client):
    return login(client, "student5@demo.test")


# ---------------------------------------------------------------- public + application form
def test_public_info(client):
    r = client.get("/api/public/info").json
    assert r["settings"]["company_name"] == "UpStep" and "Full Stack Developer" in r["roles"]


def apply(client, **over):
    data = {"name": "Priya Nair", "email": "priya@test.in", "phone": "+91 98765 43210", "college": "COEP",
            "role": "Data Analyst", "message": "Keen to learn", "accept_terms": "1", "resume": (io.BytesIO(PDF), "cv.pdf")}
    data.update(over)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/api/applications", data=data, content_type="multipart/form-data")


def test_application_success_and_confirmation(client):
    r = apply(client)
    assert r.status_code == 201 and "received your application" in r.json["message"]
    assert "get back to you by email" in r.json["message"]


def test_application_validation(client):
    assert apply(client, email="nope", resume=(io.BytesIO(PDF), "a.pdf")).status_code == 400
    assert apply(client, email="a@b.in", role="Astronaut", resume=(io.BytesIO(PDF), "a.pdf")).status_code == 400
    assert apply(client, email="c@b.in", resume=None).status_code == 400
    assert apply(client, email="d@b.in", resume=(io.BytesIO(b"MZ evil"), "cv.pdf")).status_code == 400
    assert apply(client, email="e@b.in", resume=(io.BytesIO(PDF), "cv.exe")).status_code == 400
    assert apply(client, resume=(io.BytesIO(PDF), "cv.pdf")).status_code == 409           # duplicate


def test_honeypot_stores_nothing(client, app):
    import db
    before = db.one("select count(*) c from applications")["c"]
    assert apply(client, email="bot@b.in", website="http://spam", resume=(io.BytesIO(PDF), "a.pdf")).status_code == 201
    assert db.one("select count(*) c from applications")["c"] == before


# ---------------------------------------------------------------- auth
def test_auth_rules(client, s1):
    assert client.post("/api/auth/login", json={"email": "student1@demo.test", "password": "bad"}).status_code == 401
    assert client.get("/api/staff/students").status_code == 401
    assert client.get("/api/staff/students", headers=s1).status_code == 403
    assert client.get("/api/student/tasks").status_code == 401
    me = client.get("/api/auth/me", headers=s1).json["user"]
    assert me["role"] == "student" and me["mentor_name"] == "Riya Kulkarni"


# ---------------------------------------------------------------- admin: applications -> student
def test_admin_application_flow(client, admin, s1):
    assert client.get("/api/staff/applications", headers=s1).status_code == 403
    r = client.get("/api/staff/applications?status=new", headers=admin).json
    assert r["counts"]["new"] >= 1
    a = r["applications"][0]
    assert client.get(f"/api/staff/applications/{a['id']}/resume", headers=admin).data == PDF
    assert client.patch(f"/api/staff/applications/{a['id']}", json={"status": "shortlisted"}, headers=admin).status_code == 200
    import db
    assert db.one("select count(*) c from outbox where subject like 'You are shortlisted%%'")["c"] == 1
    mid = client.get("/api/staff/mentors", headers=admin).json["mentors"][0]["id"]
    c = client.post(f"/api/staff/applications/{a['id']}/convert", json={"mentor_id": mid}, headers=admin)
    assert c.status_code == 200
    pw = c.json["temp_password"]
    assert client.post(f"/api/staff/applications/{a['id']}/convert", json={}, headers=admin).status_code == 400
    h = login(client, "priya@test.in", pw)
    u = client.get("/api/auth/me", headers=h).json["user"]
    assert u["must_change_password"] is True
    assert client.post("/api/auth/change-password", json={"current": pw, "new": "short"}, headers=h).status_code == 400
    assert client.post("/api/auth/change-password", json={"current": pw, "new": "BrandNew9"}, headers=h).status_code == 200
    login(client, "priya@test.in", "BrandNew9")


# ---------------------------------------------------------------- privacy: names only
def test_students_never_see_contact_details(client, s1, mentor, admin):
    teams = client.get("/api/student/groups", headers=s1).json["groups"]
    # newly enrolled students are auto-placed in the mentor's group, so check the originals are present (names only)
    assert {"Aarav Patil", "Sneha Joshi", "Rohan Deshmukh"} <= set(teams[0]["members"])
    assert all(isinstance(m, str) for m in teams[0]["members"])
    # chat history and dashboards must not leak contact data either
    blob = ""
    for ch in client.get("/api/chat/channels", headers=s1).json["channels"]:
        client.post(f"/api/chat/channels/{ch['id']}/messages", json={"body": "hello"}, headers=s1)
        blob += client.get(f"/api/chat/channels/{ch['id']}/messages", headers=s1).get_data(as_text=True)
    blob += client.get("/api/student/dashboard", headers=s1).get_data(as_text=True)
    blob += client.get("/api/student/groups", headers=s1).get_data(as_text=True)
    blob += client.get("/api/student/tasks", headers=s1).get_data(as_text=True)
    for leak in ("@demo.test", "9000000", "student2@", "mentor@"):
        assert leak not in blob
    # mentors see names only; admin sees contact details
    m = client.get("/api/staff/students", headers=mentor).json["students"]
    assert m and all("email" not in s and "phone" not in s for s in m)
    assert "email" in client.get("/api/staff/students", headers=admin).json["students"][0]
    assert "email" not in client.get("/api/staff/groups", headers=mentor).get_data(as_text=True)


# ---------------------------------------------------------------- tasks
def test_task_lifecycle(client, mentor, s1, s5):
    stu = client.get("/api/staff/students", headers=mentor).json["students"]
    sid = next(s["id"] for s in stu if s["name"] == "Aarav Patil")
    r = client.post("/api/staff/tasks", headers=mentor, json={"title": "Write README", "description": "Explain your repo", "due_date": str(date.today() + timedelta(days=2)),
                                                              "max_points": 10, "target": {"type": "students", "student_ids": [sid]}})
    assert r.status_code == 201 and r.json["assigned"] == 1
    mine = client.get("/api/student/tasks", headers=s1).json["tasks"]
    t = next(x for x in mine if x["title"] == "Write README")
    assert t["assigned_by"] == "Riya Kulkarni"
    assert client.get("/api/student/tasks", headers=s5).json["tasks"][0]["title"] != "Write README"
    assert client.post(f"/api/student/tasks/{t['id']}/submit", json={}, headers=s1).status_code == 400
    assert client.post(f"/api/student/tasks/{t['id']}/submit", json={"link": "javascript:alert(1)"}, headers=s1).status_code == 400
    assert client.post(f"/api/student/tasks/{t['id']}/submit", json={"text": "done", "link": "https://github.com/x/y"}, headers=s1).status_code == 200
    assert client.post(f"/api/student/tasks/{t['id']}/submit", json={"text": "again"}, headers=s1).status_code == 400
    # another student cannot submit someone else's task
    assert client.post(f"/api/student/tasks/{t['id']}/submit", json={"text": "hax"}, headers=s5).status_code == 404
    assert any(s["id"] == t["id"] for s in client.get("/api/staff/submissions", headers=mentor).json["submissions"])
    assert client.patch(f"/api/staff/assignments/{t['id']}", json={"action": "rework", "feedback": ""}, headers=mentor).status_code == 400
    assert client.patch(f"/api/staff/assignments/{t['id']}", json={"action": "rework", "feedback": "Add install steps"}, headers=mentor).status_code == 200
    again = next(x for x in client.get("/api/student/tasks", headers=s1).json["tasks"] if x["id"] == t["id"])
    assert again["status"] == "rework" and again["feedback"] == "Add install steps"
    client.post(f"/api/student/tasks/{t['id']}/submit", json={"text": "fixed"}, headers=s1)
    assert client.patch(f"/api/staff/assignments/{t['id']}", json={"action": "approve", "points": 11}, headers=mentor).status_code == 400
    assert client.patch(f"/api/staff/assignments/{t['id']}", json={"action": "approve", "points": 8, "feedback": "Good"}, headers=mentor).status_code == 200
    d = client.get("/api/student/dashboard", headers=s1).json
    assert d["mentor"]["name"] == "Riya Kulkarni" and d["stats"]["completed"] >= 2 and d["stats"]["performance"] is not None


def test_mentor_cannot_touch_other_mentors_students(client, admin, mentor):
    r = client.post("/api/staff/mentors", json={"name": "Other Mentor", "email": "m2@x.test"}, headers=admin)
    assert r.status_code == 201
    m2 = login(client, "m2@x.test", r.json["temp_password"])
    assert client.get("/api/staff/students", headers=m2).json["students"] == []
    stu = client.get("/api/staff/students", headers=admin).json["students"]
    sid = next(s["id"] for s in stu if s["name"] == "Aarav Patil")
    r = client.post("/api/staff/tasks", headers=m2, json={"title": "t", "due_date": str(date.today()), "target": {"type": "students", "student_ids": [sid]}})
    assert r.status_code == 400
    assert client.get("/api/staff/submissions", headers=m2).json["submissions"] == []
    assert client.post("/api/staff/groups", headers=m2, json={"name": "x"}).status_code == 403
    assert client.get(f"/api/staff/students/{sid}", headers=m2).status_code == 404


def test_task_for_group_and_all(client, admin, s1):
    gid = client.get("/api/staff/groups", headers=admin).json["groups"][0]["id"]
    r = client.post("/api/staff/tasks", headers=admin, json={"title": "Group task", "due_date": str(date.today()), "target": {"type": "group", "group_id": gid}})
    assert r.status_code == 201 and r.json["assigned"] >= 3
    r = client.post("/api/staff/tasks", headers=admin, json={"title": "Everyone", "due_date": str(date.today()), "target": {"type": "all"}})
    assert r.status_code == 201 and r.json["assigned"] >= 7
    assert client.post("/api/staff/tasks", headers=admin, json={"title": "Nobody", "due_date": "2030-01-01"}).status_code == 400


# ---------------------------------------------------------------- groups
def test_group_generation_and_save(client, admin, s1):
    r = client.post("/api/staff/groups/generate", headers=admin, json={"size": 3, "kind": "project", "prefix": "Team", "assign_mentors": True})
    assert r.status_code == 200
    gs = r.json["groups"]
    sizes = [len(x["members"]) for x in gs]
    assert max(sizes) - min(sizes) <= 1 and sum(sizes) >= 7
    assert len({m["id"] for x in gs for m in x["members"]}) == sum(sizes)       # nobody twice
    assert client.post("/api/staff/groups/bulk", headers=admin, json={"groups": gs}).status_code == 201
    mine = client.get("/api/student/groups", headers=s1).json["groups"]
    assert {g["kind"] for g in mine} == {"training", "project"}
    assert client.post("/api/staff/groups/generate", headers=admin, json={"size": 3, "kind": "project"}).status_code == 400   # nobody left ungrouped
    assert client.post("/api/staff/groups/generate", headers=admin, json={"size": 1}).status_code == 400


def test_manual_group_edit(client, admin):
    stu = client.get("/api/staff/students", headers=admin).json["students"]
    ids = [s["id"] for s in stu[:2]]
    gid = client.post("/api/staff/groups", headers=admin, json={"name": "Hand-picked", "kind": "training", "student_ids": ids}).json["group_id"]
    assert client.put(f"/api/staff/groups/{gid}", headers=admin, json={"name": "Renamed", "kind": "training", "student_ids": ids[:1]}).status_code == 200
    g = next(x for x in client.get("/api/staff/groups", headers=admin).json["groups"] if x["id"] == gid)
    assert g["name"] == "Renamed" and len(g["members"]) == 1
    assert client.delete(f"/api/staff/groups/{gid}", headers=admin).status_code == 200


# ---------------------------------------------------------------- calendar, chat, standup
def test_calendar_expands_repeats(client, s1):
    start = date.today() - timedelta(days=date.today().weekday())      # this Monday
    r = client.get(f"/api/calendar?start={start}&end={start + timedelta(days=6)}", headers=s1).json["items"]
    stand = [i for i in r if i["type"] == "event" and i["title"] == "Daily stand-up"]
    assert len(stand) == 5 and all(date.fromisoformat(i["occurrence_date"]).weekday() < 5 for i in stand)
    assert any(i["type"] == "task" for i in client.get(f"/api/calendar?start={start - timedelta(days=30)}&end={start + timedelta(days=30)}", headers=s1).json["items"])
    assert client.get(f"/api/calendar?start={start}&end={start + timedelta(days=200)}", headers=s1).status_code == 400


def test_event_audience_rules(client, admin, mentor, s5):
    when = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
    assert client.post("/api/staff/events", headers=mentor, json={"title": "For all", "starts_at": when}).status_code == 400     # mentor cannot broadcast
    stu = client.get("/api/staff/students", headers=admin).json["students"]
    sid = next(s["id"] for s in stu if s["name"] == "Aarav Patil")
    r = client.post("/api/staff/events", headers=admin, json={"title": "1:1 mock interview", "kind": "mock_interview", "starts_at": when,
                                                              "audience": {"type": "student", "student_id": sid}})
    assert r.status_code == 201
    today = date.today()
    far = f"/api/calendar?start={today}&end={today + timedelta(days=3)}"
    assert not any(i.get("title") == "1:1 mock interview" for i in client.get(far, headers=s5).json["items"])
    assert client.post("/api/staff/events", headers=admin, json={"title": "Bad", "starts_at": when, "ends_at": "2000-01-01T00:00:00"}).status_code == 400


def test_chat_access(client, s1, s5, mentor, admin):
    ch1 = {c["name"]: c for c in client.get("/api/chat/channels", headers=s1).json["channels"]}
    assert "Everyone" in ch1 and "Mentor: Riya Kulkarni" in ch1 and "Batch 1" in ch1
    ch5 = {c["name"]: c for c in client.get("/api/chat/channels", headers=s5).json["channels"]}
    assert "Batch 1" not in ch5                                            # not a member
    assert client.get(f"/api/chat/channels/{ch1['Batch 1']['id']}/messages", headers=s5).status_code == 404
    assert client.get(f"/api/chat/channels/{ch1['Mentor: Riya Kulkarni']['id']}/messages", headers=s5).status_code == 404
    mid = ch1["Mentor: Riya Kulkarni"]["id"]
    r = client.post(f"/api/chat/channels/{mid}/messages", json={"body": "Hi mentor"}, headers=s1)
    assert r.status_code == 201
    got = client.get(f"/api/chat/channels/{mid}/messages", headers=mentor).json["messages"]
    assert got[-1]["body"] == "Hi mentor" and got[-1]["sender_name"] == "Aarav Patil"
    assert client.post(f"/api/chat/channels/{mid}/messages", json={"body": "  "}, headers=mentor).status_code == 400
    new = client.get(f"/api/chat/channels/{mid}/messages?after={got[-1]['id']}", headers=s1).json["messages"]
    assert new == []
    assert any(c["kind"] == "mentor" for c in client.get("/api/chat/channels", headers=mentor).json["channels"])
    everyone = ch1["Everyone"]["id"]
    assert client.post(f"/api/chat/channels/{everyone}/messages", json={"body": "hi all"}, headers=s5).status_code == 201
    assert len(client.get("/api/chat/channels", headers=admin).json["channels"]) >= 5


def test_standup(client, s1, mentor):
    assert client.post("/api/student/standup", json={}, headers=s1).status_code == 400
    assert client.post("/api/student/standup", json={"yesterday": "Git", "today": "HTML", "blockers": ""}, headers=s1).status_code == 200
    assert client.post("/api/student/standup", json={"yesterday": "Git", "today": "CSS"}, headers=s1).status_code == 200   # update, not duplicate
    rows = client.get("/api/staff/standups", headers=mentor).json["standups"]
    mine = next(r for r in rows if r["name"] == "Aarav Patil")
    assert mine["posted"] and mine["today"] == "CSS" and sum(r["posted"] for r in rows) == 1
    assert client.get("/api/student/dashboard", headers=s1).json["standup_done"] is True


def test_admin_student_management(client, admin, s1):
    stu = client.get("/api/staff/students", headers=admin).json["students"]
    sid = next(s["id"] for s in stu if s["name"] == "Meera Shah")
    assert client.patch(f"/api/staff/students/{sid}", json={"phase": "project", "outcome": "offered"}, headers=admin).status_code == 200
    assert client.patch(f"/api/staff/students/{sid}", json={"phase": "bogus"}, headers=admin).status_code == 400
    assert client.patch(f"/api/staff/students/{sid}", json={"outcome": "offered"}, headers=s1).status_code == 403
    d = client.get(f"/api/staff/students/{sid}", headers=admin).json
    assert d["student"]["phase"] == "project" and d["student"]["outcome"] == "offered"
    r = client.post(f"/api/staff/students/{sid}/reset-password", headers=admin)
    assert r.status_code == 200 and login(client, "student6@demo.test", r.json["temp_password"])
    r = client.post("/api/staff/students", headers=admin, json={"name": "Walk In", "email": "walk@in.test"})
    assert r.status_code == 201
    assert client.post("/api/staff/students", headers=admin, json={"name": "Dup", "email": "WALK@in.test"}).status_code == 409
    ov = client.get("/api/staff/overview", headers=admin).json
    assert ov["students"] >= 8 and ov["mentors"] >= 2


def test_announcements_and_settings(client, admin, s1):
    assert client.post("/api/staff/announcements", json={"title": "Hello"}, headers=s1).status_code == 403
    assert client.post("/api/staff/announcements", json={"title": "Holiday on Friday", "body": "No class"}, headers=admin).status_code == 201
    assert client.get("/api/announcements", headers=s1).json["announcements"][0]["title"] == "Holiday on Friday"
    assert client.put("/api/staff/settings", json={"company_name": "Acme Learning"}, headers=admin).status_code == 200
    assert client.get("/api/public/info").json["settings"]["company_name"] == "Acme Learning"
    assert client.post("/api/staff/roles", json={"title": "QA Tester"}, headers=admin).status_code == 201
    assert "QA Tester" in client.get("/api/public/info").json["roles"]
