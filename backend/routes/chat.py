from flask import Blueprint, g, jsonify, request

import db
from core import can_use_channel, ensure_mentor_channel
from security import allow, auth, bad, text

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@bp.get("/channels")
@auth("student", "staff")
def channels():
    u = g.user
    if u["role"] == "student":
        if u["mentor_id"]:
            ensure_mentor_channel(u["id"])
        rows = db.q("""select c.id, c.kind, case when c.kind='general' then 'Everyone'
                               when c.kind='group' then gr.name else 'Mentor: ' || coalesce(mu.name,'not assigned yet') end as name
                       from channels c
                       left join student_groups gr on gr.id=c.group_id
                       left join users s on s.id=c.student_id left join users mu on mu.id=s.mentor_id
                       where c.kind='general'
                          or (c.kind='group' and c.group_id in (select group_id from group_members where student_id=%s))
                          or (c.kind='mentor' and c.student_id=%s and s.mentor_id is not null)
                       order by c.kind, c.id""", (u["id"], u["id"]))
    else:
        if u["role"] == "mentor":
            db.run("""insert into channels (kind,name,student_id) select 'mentor','Mentor chat',id from users
                      where role='student' and mentor_id=%s on conflict do nothing""", (u["id"],))
        else:
            db.run("""insert into channels (kind,name,student_id) select 'mentor','Mentor chat',id from users
                      where role='student' and mentor_id is not null on conflict do nothing""")
        rows = db.q("""select c.id, c.kind, case when c.kind='general' then 'Everyone'
                               when c.kind='group' then 'Group: ' || gr.name
                               else s.name || case when %s then ' (mentor: ' || coalesce(mu.name,'none') || ')' else '' end end as name
                       from channels c
                       left join student_groups gr on gr.id=c.group_id
                       left join users s on s.id=c.student_id left join users mu on mu.id=s.mentor_id
                       where %s or c.kind='general'
                          or (c.kind='group' and gr.mentor_id=%s)
                          or (c.kind='mentor' and s.mentor_id=%s)
                       order by c.kind, name""", (u["role"] == "admin", u["role"] == "admin", u["id"], u["id"]))
    return jsonify(channels=rows)


def _channel(cid):
    ch = db.one("select * from channels where id=%s", (cid,))
    if not ch or not can_use_channel(g.user, ch):
        bad("Chat not found.", 404)
    return ch


@bp.get("/channels/<int:cid>/messages")
@auth("student", "staff")
def messages(cid):
    _channel(cid)
    after = request.args.get("after", type=int)
    if after:
        rows = db.q("""select m.id, m.body, m.created_at, m.sender_id, coalesce(u.name,'Former member') as sender_name,
                              u.role as sender_role from messages m left join users u on u.id=m.sender_id
                       where m.channel_id=%s and m.id > %s order by m.id limit 200""", (cid, after))
    else:
        rows = db.q("""select * from (select m.id, m.body, m.created_at, m.sender_id, coalesce(u.name,'Former member') as sender_name,
                              u.role as sender_role from messages m left join users u on u.id=m.sender_id
                       where m.channel_id=%s order by m.id desc limit 80) x order by id""", (cid,))
    return jsonify(messages=rows, me=g.user["id"])      # names and roles only – no email or phone


@bp.post("/channels/<int:cid>/messages")
@auth("student", "staff")
def send(cid):
    _channel(cid)
    if not allow(f"chat:{g.user['id']}", 30, 60):
        bad("You are sending messages too fast. Wait a moment.", 429)
    body = text(request.get_json(silent=True) or {}, "body", 2000, True, "Message")
    row = db.one("insert into messages (channel_id, sender_id, body) values (%s,%s,%s) returning id, created_at",
                 (cid, g.user["id"], body))
    return jsonify(message={"id": row["id"], "body": body, "created_at": row["created_at"], "sender_id": g.user["id"],
                            "sender_name": g.user["name"], "sender_role": g.user["role"]}), 201
