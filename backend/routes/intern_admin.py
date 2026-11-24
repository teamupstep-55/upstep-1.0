"""Admin screens for the internship programme: repos per track + timeline, MCQ results, submitted GitHub links."""
from flask import Blueprint, jsonify, request

import db
from security import auth, bad, text

bp = Blueprint("intern_admin", __name__, url_prefix="/api/staff/internship")


@bp.get("")
@auth("admin")
def overview():
    repos = db.q("select * from internship_repos order by track, timeline_months")
    submissions = db.q("""select s.id, s.github_url, s.submitted_at, s.review_status, s.review_note, a.name, a.email, a.role_applied, a.timeline_months
                          from repo_submissions s join applications a on a.id=s.application_id order by s.submitted_at desc limit 200""")
    candidates = db.q("""select a.id, a.name, a.email, a.role_applied, a.timeline_months, a.mcq_stage, a.mcq_attempts_used, a.mcq_retry_after,
                                a.offer_due_at, a.offer_sent_at, a.internship_started_at,
                                (select max(score) from mcq_attempts m where m.application_id=a.id and m.finished_at is not null) as best_score,
                                (select count(*) from repo_submissions s where s.application_id=a.id) as submitted
                         from applications a where a.mcq_stage is not null order by a.created_at desc limit 300""")
    topics = db.q("select topic, count(*) n from mcq_questions where active group by topic order by topic")
    return jsonify(repos=repos, submissions=submissions, candidates=candidates, question_bank=topics)


@bp.post("/repos")
@auth("admin")
def save_repo():
    b = request.get_json(silent=True) or {}
    track = b.get("track")
    try:
        months = int(b.get("timeline_months"))
    except (TypeError, ValueError):
        months = 0
    if track not in ("cs", "commerce") or months not in (1, 3, 4, 6):
        bad("Choose a track and a timeline of 1, 3, 4 or 6 months.")
    title = text(b, "title", 120, True, "Title")
    url = text(b, "github_url", 300, True, "GitHub link")
    if not url.startswith("https://github.com/"):
        bad("The repo link must start with https://github.com/")
    db.run("""insert into internship_repos (track, timeline_months, title, github_url, instructions, active) values (%s,%s,%s,%s,%s,%s)
              on conflict (track, timeline_months) do update set title=excluded.title, github_url=excluded.github_url,
              instructions=excluded.instructions, active=excluded.active""",
           (track, months, title, url, text(b, "instructions", 4000), bool(b.get("active", True))))
    return jsonify(ok=True), 201


@bp.delete("/repos/<int:rid>")
@auth("admin")
def delete_repo(rid):
    db.run("delete from internship_repos where id=%s", (rid,))
    return jsonify(ok=True)


@bp.post("/submissions/<int:sid>/review")
@auth("admin")
def review(sid):
    b = request.get_json(silent=True) or {}
    status = b.get("status")
    if status not in ("approved", "changes_requested"):
        bad("Choose approved or changes requested.")
    db.run("update repo_submissions set review_status=%s, review_note=%s where id=%s", (status, text(b, "note", 1000) or None, sid))
    return jsonify(ok=True)
