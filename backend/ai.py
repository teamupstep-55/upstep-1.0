"""Assisted review. Everything here only DRAFTS or RANKS: a mentor/admin always makes the final decision.
Works without any AI service (rule-based). If ANTHROPIC_API_KEY is set, task-review drafts and question drafting use a model."""
import io
import ipaddress
import json
import re
import socket
import zipfile
from collections import Counter
from urllib.parse import urlparse

import requests
from flask import current_app

import db
import storage
from security import bad

# ----------------------------------------------------------------------------- safe outbound link check (no SSRF)
def _public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def check_link(url, max_hops=3):
    """-> (ok, note). Only http(s) to public hosts; redirects are re-validated; short timeout; nothing is downloaded beyond headers."""
    for _ in range(max_hops + 1):
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False, "not a web link"
        if not _public_host(p.hostname):
            return False, "link points to a private or unknown address"
        try:
            r = requests.get(url, timeout=6, allow_redirects=False, stream=True, headers={"User-Agent": "UpStepLinkCheck/1.0"})
            r.close()
        except requests.RequestException:
            return False, "page did not load"
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            from urllib.parse import urljoin
            url = urljoin(url, r.headers["Location"])
            continue
        if r.status_code < 400:
            return True, f"loads (HTTP {r.status_code})"
        return False, f"returned HTTP {r.status_code}"
    return False, "too many redirects"


# ----------------------------------------------------------------------------- LLM helper (optional)
def llm_available():
    return bool(current_app.config.get("ANTHROPIC_API_KEY"))


def llm_json(system, user, max_tokens=1200):
    c = current_app.config
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=40,
                      headers={"x-api-key": c["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": c["ANTHROPIC_MODEL"], "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]})
    if r.status_code >= 300:
        raise RuntimeError(f"model call failed ({r.status_code})")
    txt = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    return json.loads(txt)


# ----------------------------------------------------------------------------- task review draft
def _keywords(line):
    return [w for w in re.findall(r"[a-z0-9+#.]{3,}", line.lower()) if w not in {"the", "and", "with", "for", "that", "this", "from"}]


def draft_review(assignment_id):
    """Writes ai_draft on the assignment: {score, feedback, confidence, checks[], source}. Never approves anything."""
    a = db.one("""select ta.*, t.title, t.description, t.max_points, t.rubric from task_assignments ta join tasks t on t.id=ta.task_id where ta.id=%s""", (assignment_id,))
    if not a:
        bad("Submission not found.", 404)
    text_ = (a["submission_text"] or "").strip()
    checks, link_ok = [], None
    if a["submission_link"]:
        link_ok, note = check_link(a["submission_link"])
        checks.append({"name": "Link", "ok": link_ok, "note": note})
    else:
        checks.append({"name": "Link", "ok": None, "note": "no link submitted"})
    checks.append({"name": "Written note", "ok": len(text_) >= 40 if text_ else False, "note": f"{len(text_)} characters"})
    items = [i.strip() for i in re.split(r"[;\n]", a["rubric"] or "") if i.strip()]
    covered = []
    hay = (text_ + " " + (a["submission_link"] or "")).lower()
    for it in items:
        kws = _keywords(it)
        hit = bool(kws) and sum(k in hay for k in kws) / len(kws) >= 0.5
        covered.append((it, hit))
        checks.append({"name": f"Rubric: {it}", "ok": hit, "note": "mentioned" if hit else "not found in the note or link"})

    source = "rules"
    if items:
        cov = sum(h for _, h in covered) / len(items)
        base = 0.55 * cov + 0.3 * (1 if link_ok else 0 if a["submission_link"] else 0.5) + 0.15 * (1 if len(text_) >= 40 else 0)
        confidence = 0.55 if len(items) >= 3 else 0.4
    else:
        base = 0.4 * (1 if link_ok else 0) + 0.3 * (1 if len(text_) >= 40 else 0.3 if text_ else 0) + 0.2
        confidence = 0.3
    if a["submission_link"] and link_ok is False:
        confidence = min(confidence, 0.35)
    score = max(0, min(a["max_points"], round(base * a["max_points"])))
    missing = [it for it, h in covered if not h]
    fb = []
    fb.append("Your link opens correctly." if link_ok else "I could not open your link; please check it is public and correct." if a["submission_link"] else "")
    fb.append("Good, you described your work." if len(text_) >= 40 else "Add a few sentences describing what you did and what you learned.")
    if missing:
        fb.append("I could not find: " + "; ".join(missing) + ".")
    feedback = " ".join(x for x in fb if x)

    if llm_available():
        try:
            out = llm_json(
                "You help a mentor review an internship task. Return ONLY JSON: {\"score\": number, \"feedback\": string (2-4 kind, specific sentences), \"confidence\": number 0-1}. "
                "Score is out of max_points. If the evidence is thin, lower the confidence. Never invent facts about the work.",
                json.dumps({"task": a["title"], "description": a["description"], "rubric": items, "max_points": a["max_points"], "student_note": text_[:3000],
                            "link": a["submission_link"], "link_check": checks[0]["note"]}))
            score = max(0, min(a["max_points"], int(round(float(out["score"])))))
            feedback, confidence, source = str(out["feedback"])[:1500], max(0.0, min(1.0, float(out["confidence"]))), "model"
        except Exception:
            current_app.logger.exception("model review failed, keeping rule-based draft")
    draft = {"score": score, "feedback": feedback, "confidence": round(confidence, 2), "checks": checks, "source": source}
    db.run("update task_assignments set ai_draft=%s where id=%s", (json.dumps(draft), assignment_id))
    return draft


# ----------------------------------------------------------------------------- resume screening
ROLE_SKILLS = {
    "full stack": ["html", "css", "javascript", "react", "node", "python", "flask", "django", "sql", "git", "api", "mongodb", "postgres"],
    "frontend": ["html", "css", "javascript", "react", "typescript", "tailwind", "figma", "responsive", "git", "vue", "angular"],
    "backend": ["python", "flask", "django", "sql", "postgres", "api", "rest", "git", "docker", "mysql", "java", "node"],
    "data": ["python", "sql", "excel", "pandas", "numpy", "power bi", "tableau", "statistics", "machine learning", "visualization", "analysis"],
    "design": ["figma", "ux", "ui", "wireframe", "prototype", "photoshop", "illustrator", "user research", "typography", "design"],
    "marketing": ["seo", "social media", "content", "analytics", "google ads", "campaign", "email marketing", "copywriting", "canva", "facebook"],
    "hr": ["recruitment", "communication", "operations", "excel", "onboarding", "payroll", "interview", "documentation", "coordination", "people"],
}
GENERIC = ["project", "intern", "team", "certificate", "github", "leadership", "communication"]


def resume_text(key):
    data = storage.read_resume(key)
    if not data:
        return ""
    try:
        if data.startswith(b"%PDF"):
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:6])
        if data.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf8", "ignore")
            return re.sub(r"<[^>]+>", " ", xml)
    except Exception:
        return ""
    return ""


def screen_application(aid):
    """Skill match for the role. Stored on the application; used only to SORT a list for a human. Never rejects anyone."""
    a = db.one("select * from applications where id=%s", (aid,))
    if not a:
        return None
    txt = resume_text(a["resume_path"]).lower()
    role = a["role_applied"].lower()
    skills = next((v for k, v in ROLE_SKILLS.items() if k in role), sum(ROLE_SKILLS.values(), []))
    found = [s for s in skills if re.search(r"(?<![a-z])" + re.escape(s) + r"(?![a-z])", txt)]
    extra = [s for s in GENERIC if s in txt]
    if not txt.strip():
        res = {"score": None, "matched": [], "missing": [], "reasons": ["Could not read text from this resume (scanned image or unsupported file). Please read it yourself."]}
    else:
        score = round(100 * len(found) / max(1, len(skills)) * 0.8 + min(20, 5 * len(extra)))
        res = {"score": min(100, score), "matched": found, "missing": [s for s in skills if s not in found][:6],
               "reasons": [f"Mentions {len(found)} of {len(skills)} skills we look for in this role."] + ([f"Also mentions: {', '.join(extra)}."] if extra else [])}
    res["note"] = "Automatic skill match: use it to sort, not to reject."
    db.run("update applications set screening=%s where id=%s", (json.dumps(res), aid))
    return res


# ----------------------------------------------------------------------------- stand-up digest
_NONE = {"", "none", "no", "nil", "nothing", "na", "n/a", "-", "no blockers", "nope", "nahi", "none."}
STOP = set("the a an and or to of in on for with is are was am i my it me we this that have has had not no be but can cant cannot get got so do does did when how what why will would should".split())


def standup_digest(mentor_id, day):
    students = db.q("""select u.id, u.name from users u where u.role='student' and u.is_active and u.mentor_id=%s and u.start_date <= %s
                       and u.outcome='in_progress' order by u.name""", (mentor_id, day))
    ids = [s["id"] for s in students]
    posted = {r["student_id"]: r for r in db.q("select * from standups where student_id = any(%s) and day=%s", (ids, day))} if ids else {}
    blocked, missing, words = [], [], Counter()
    for s in students:
        sp = posted.get(s["id"])
        if not sp:
            missing.append(s["name"])
            continue
        b = (sp["blockers"] or "").strip()
        if b.lower() not in _NONE:
            blocked.append({"name": s["name"], "blocker": b})
            words.update(set(w for w in re.findall(r"[a-z][a-z+#.]{2,}", b.lower()) if w not in STOP))
    common = [w for w, n in words.most_common(6) if n >= 2]
    return {"day": day, "students": len(students), "posted": len(posted), "blocked": blocked, "missing": missing, "common_problems": common}


def digest_text(d):
    lines = [f"Stand-up digest for {d['day']}: {d['posted']} of {d['students']} posted.", ""]
    if d["blocked"]:
        lines.append("Blocked:")
        lines += [f"  - {b['name']}: {b['blocker']}" for b in d["blocked"]]
    if d["missing"]:
        lines += ["", "Did not post: " + ", ".join(d["missing"])]
    if d["common_problems"]:
        lines += ["", "Common words in blockers: " + ", ".join(d["common_problems"])]
    if not d["blocked"] and not d["missing"]:
        lines.append("Nobody is blocked and everyone posted.")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- draft MCQs (needs a model)
def draft_questions(topic, count, level):
    if not llm_available():
        bad("Drafting questions needs an AI key. Set ANTHROPIC_API_KEY in the backend settings, or add questions by hand.", 503)
    out = llm_json("You write multiple-choice questions for an internship screening test. Return ONLY a JSON array of objects "
                   "{\"question\",\"option_a\",\"option_b\",\"option_c\",\"option_d\",\"correct\" (one of a,b,c,d)}. One clearly correct answer, plausible distractors, no trick questions.",
                   f"Topic: {topic}\nLevel: {level}\nNumber of questions: {count}", max_tokens=3000)
    qs = []
    for q in out if isinstance(out, list) else []:
        if all(isinstance(q.get(k), str) and q.get(k).strip() for k in ("question", "option_a", "option_b", "option_c", "option_d")) and str(q.get("correct", "")).lower() in "abcd" and q.get("correct"):
            qs.append({k: q[k].strip() for k in ("question", "option_a", "option_b", "option_c", "option_d")} | {"correct": q["correct"].lower(), "marks": 1})
    if not qs:
        bad("The AI did not return usable questions. Please try again.", 502)
    return qs[:count]
