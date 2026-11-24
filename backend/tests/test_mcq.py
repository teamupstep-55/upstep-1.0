"""Software-engineer internship journey: MCQ test (30 q, 30 s, pass 21, 3 attempts, 2-day wait), offer letter, repo per timeline, GitHub link.
Run like the other tests:  TEST_DATABASE_URL=postgresql://user:pass@localhost/dbname python -m pytest -q tests/test_mcq.py   (the database is wiped!)"""
import io
from datetime import timedelta

import pytest

from test_v2 import PDF, app, client, login  # noqa: F401  (reuse the fixtures)

SWE, COMMERCE = "Software Engineer Intern", "Commerce Intern"


def apply(client, email, role=SWE, months="3"):
    data = {"name": "Test Intern", "email": email, "phone": "9876500123", "college": "COEP", "role": role, "accept_terms": "1",
            "resume": (io.BytesIO(PDF), "cv.pdf")}
    if months:
        data["timeline_months"] = months
    r = client.post("/api/applications", data=data, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    return r.json["status_url"].rsplit("/", 1)[-1]


def correct_for(qid):
    import db
    return db.one("select correct from mcq_questions where id=%s", (qid,))["correct"]


def run_attempt(client, token, right):
    """Answer every question; the first `right` correctly, the rest wrongly. Returns the final result."""
    d = client.post(f"/api/applicant/{token}/mcq/start").json
    n = 0
    while not d.get("finished"):
        q = d["question"]
        assert "correct" not in q                              # answers are never sent to the browser
        good = correct_for(q["id"])
        ans = good if n < right else next(k for k in "abcd" if k != good)
        d = client.post(f"/api/applicant/{token}/mcq/answer", json={"question_id": q["id"], "answer": ans}).json
        n += 1
    assert n == 30
    return d


def test_roles_and_apply_rules(client):
    info = client.get("/api/public/info").json
    tracks = {r["title"]: (r["track"], r["requires_test"]) for r in info["role_tracks"]}
    assert tracks[SWE] == ("cs", True) and tracks[COMMERCE] == ("commerce", False)
    # the software-engineer role needs a valid timeline
    r = client.post("/api/applications", data={"name": "A B", "email": "nt@x.test", "phone": "9876500124", "college": "X", "role": SWE, "accept_terms": "1",
                                               "timeline_months": "2", "resume": (io.BytesIO(PDF), "cv.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 400
    tok = apply(client, "commerce@x.test", COMMERCE, "1")
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["enabled"] is False                                # commerce has no test


def test_pass_flow_offer_repo_submit(client):
    import db
    tok = apply(client, "pass@x.test", SWE, "3")
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "test_open" and p["test"]["can_start"] and p["test"]["attempts_left"] == 3
    res = run_attempt(client, tok, right=21)
    assert res["passed"] and res["score"] == 21
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "passed" and "offer" not in p          # the offer arrives the NEXT day
    assert client.post(f"/api/applicant/{tok}/internship/start").status_code == 409
    db.run("update applications set offer_due_at = now() - interval '1 minute' where access_token=%s", (tok,))
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "offer_sent" and p["offer"]["months"] == 3
    assert "repo" not in p                                      # repo only after accepting
    db.run("insert into internship_repos (track,timeline_months,title,github_url) values ('cs',1,'One month','https://github.com/o/one'),('cs',3,'Three months','https://github.com/o/three')")
    assert client.post(f"/api/applicant/{tok}/internship/start").status_code == 200
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "working" and p["repo"]["title"] == "Three months"   # only THEIR timeline
    assert client.post(f"/api/applicant/{tok}/internship/submit", json={"github_url": "http://evil.example/x"}).status_code == 400
    assert client.post(f"/api/applicant/{tok}/internship/submit", json={"github_url": "https://github.com/me/proj"}).status_code == 200
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "submitted" and p["submission"]["github_url"] == "https://github.com/me/proj"


def test_three_attempts_then_two_day_wait(client):
    import db
    tok = apply(client, "fail@x.test", SWE, "1")
    for i in range(3):
        res = run_attempt(client, tok, right=20)                # one short of the pass mark
        assert res["passed"] is False and res["score"] == 20
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["stage"] == "cooldown" and p["test"]["attempts_left"] == 0 and p["test"]["retry_after"]
    assert client.post(f"/api/applicant/{tok}/mcq/start").status_code == 409
    db.run("update applications set mcq_retry_after = now() - interval '1 minute' where access_token=%s", (tok,))
    p = client.get(f"/api/applicant/{tok}/program").json
    assert p["test"]["can_start"] and p["test"]["attempts_left"] == 3     # a fresh set of 3 attempts
    assert run_attempt(client, tok, right=30)["passed"]


def test_server_enforces_30_seconds(client):
    import db
    tok = apply(client, "slow@x.test", SWE, "4")
    d = client.post(f"/api/applicant/{tok}/mcq/start").json
    first = d["question"]["id"]
    db.run("""update mcq_attempts set question_shown_at = now() - interval '45 seconds'
              where application_id=(select id from applications where access_token=%s) and finished_at is null""", (tok,))
    r = client.post(f"/api/applicant/{tok}/mcq/answer", json={"question_id": first, "answer": correct_for(first)}).json
    assert r.get("resync") and r["question"]["id"] != first       # too late: recorded as unanswered, next question served
    row = db.one("select answer, is_correct from mcq_answers where question_id=%s", (first,))
    assert row["answer"] is None and row["is_correct"] is False
    # closing the tab does not pause the clock: reopening resumes the SAME attempt and does not use another attempt
    again = client.post(f"/api/applicant/{tok}/mcq/start").json
    assert again["question"]["id"] == r["question"]["id"]
    assert client.get(f"/api/applicant/{tok}/program").json["test"]["attempts_used"] == 1


def test_test_is_balanced(client):
    import db
    from mcq_bank import QUOTAS
    tok = apply(client, "bal@x.test", SWE, "6")
    client.post(f"/api/applicant/{tok}/mcq/start")
    ids = db.one("select question_ids from mcq_attempts where application_id=(select id from applications where access_token=%s)", (tok,))["question_ids"]
    rows = db.q("select topic, count(*) n from mcq_questions where id = any(%s) group by topic", (ids,))
    assert {r["topic"]: r["n"] for r in rows} == QUOTAS
