from datetime import timedelta

from flask import Blueprint, g, jsonify, request

import db
from core import events_between, today, visible_events_sql
from security import auth, bad, pick_date

bp = Blueprint("common", __name__, url_prefix="/api")


@bp.get("/calendar")
@auth("student", "staff")
def calendar():
    """Events (classes, daily standup, mock interviews ...) plus task due dates, for any signed-in role."""
    start = pick_date(request.args.get("start"), "Start")
    end = pick_date(request.args.get("end"), "End")
    if end < start or (end - start).days > 62:
        bad("Choose a date range of at most two months.")
    u = g.user
    where, args = visible_events_sql(u)
    items = [{"type": "event", **e} for e in events_between(where, args, start, end)]
    if u["role"] == "student":
        rows = db.q("""select ta.id, t.title, t.due_date, ta.status from task_assignments ta join tasks t on t.id=ta.task_id
                       where ta.student_id=%s and t.due_date between %s and %s and (ta.unlock_date is null or ta.unlock_date <= %s)""",
                    (u["id"], start, end, today()))
    elif u["role"] == "mentor":
        rows = db.q("""select min(ta.id) as id, t.title, t.due_date, 'pending' as status from tasks t
                       join task_assignments ta on ta.task_id=t.id join users s on s.id=ta.student_id
                       where s.mentor_id=%s and t.due_date between %s and %s group by t.id""", (u["id"], start, end))
    else:
        rows = db.q("""select id, title, due_date, 'pending' as status from tasks where due_date between %s and %s""", (start, end))
    items += [{"type": "task", "id": r["id"], "title": r["title"], "date": r["due_date"], "status": r["status"]} for r in rows]
    return jsonify(items=items, today=today())


@bp.get("/announcements")
@auth("student", "staff")
def announcements():
    rows = db.q("""select a.id, a.title, a.body, a.created_at, u.name as author from announcements a
                   left join users u on u.id=a.created_by order by a.id desc limit 30""")
    return jsonify(announcements=rows)
