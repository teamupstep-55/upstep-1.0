"""`flask --app app demo-data` – fills a fresh database with sample people so you can click around."""
from datetime import datetime, time, timedelta

from werkzeug.security import generate_password_hash

import db
from core import today

PW = "Demo@1234"


def load():
    import seed_data
    seed_data.ensure_defaults()
    if db.one("select 1 from users where lower(email)='mentor@demo.test'"):
        return "Demo data already loaded." if db.one("select 1 from classes limit 1") else _directory() + " Directory sample data added."
    h = generate_password_hash(PW)
    tz = __import__("flask").current_app.config["TZ"]
    mentor = db.one("insert into users (name,email,phone,password_hash,role) values ('Riya Kulkarni','mentor@demo.test','9000000001',%s,'mentor') returning id", (h,))["id"]
    ids = []
    start = today() - timedelta(days=9)
    for i, (n, col) in enumerate([("Aarav Patil", "COEP Pune"), ("Sneha Joshi", "MIT-WPU"), ("Rohan Deshmukh", "VIT Pune"),
                                  ("Isha Kale", "Fergusson College"), ("Kunal More", "PICT"), ("Meera Shah", "SPPU")]):
        ids.append(db.one("""insert into users (name,email,phone,password_hash,role,college,mentor_id,start_date)
                             values (%s,%s,%s,%s,'student',%s,%s,%s) returning id""",
                          (n, f"student{i+1}@demo.test", f"90000001{i:02d}", h, col, mentor, start))["id"])
    gid = db.one("insert into student_groups (name,kind,description,mentor_id) values ('Batch 1','training','First training batch',%s) returning id", (mentor,))["id"]
    db.run("insert into channels (kind,name,group_id) values ('group','Batch 1',%s)", (gid,))
    db.run("insert into group_members (group_id, student_id) select %s, unnest(%s::bigint[])", (gid, ids[:3]))
    d = today()
    for title, due, pts in [("Set up Git and push your first repo", d - timedelta(days=6), 10),
                            ("Build a personal portfolio page (HTML/CSS)", d - timedelta(days=3), 20),
                            ("Write a 2-minute self introduction video script", d + timedelta(days=1), 10),
                            ("Python basics: 10 practice problems", d + timedelta(days=4), 20)]:
        t = db.one("insert into tasks (title,description,due_date,max_points,created_by) values (%s,%s,%s,%s,%s) returning id",
                   (title, "Follow the instructions shared in class. Submit a link or a short note.", due, pts, mentor))["id"]
        db.run("insert into task_assignments (task_id, student_id) select %s, unnest(%s::bigint[])", (t, ids))
    db.run("""update task_assignments set status='approved', points=9, submission_text='Done', submitted_at=now(), reviewed_at=now()
              where task_id=(select min(id) from tasks)""")
    db.run("""update task_assignments set status='submitted', submission_text='Here is my portfolio', submission_link='https://example.com',
              submitted_at=now() where task_id=(select min(id)+1 from tasks) and student_id = any(%s)""", (ids[:2],))
    first = datetime.combine(d - timedelta(days=9), time(10, 0), tzinfo=tz)
    for title, kind, cat, st, rec in [("Daily stand-up", "standup", None, first, "weekdays"),
                                      ("Python for beginners", "class", "Coding", first.replace(hour=11), "weekly"),
                                      ("Communication skills workshop", "workshop", "Soft skills", datetime.combine(d + timedelta(days=2), time(15, 0), tzinfo=tz), "none"),
                                      ("Resume building session", "class", "Resume", datetime.combine(d + timedelta(days=5), time(16, 0), tzinfo=tz), "none"),
                                      ("Mock interview round 1", "mock_interview", "Interview prep", datetime.combine(d + timedelta(days=8), time(11, 0), tzinfo=tz), "none")]:
        db.run("insert into events (title,kind,category,starts_at,ends_at,recurrence,created_by) values (%s,%s,%s,%s,%s,%s,%s)",
               (title, kind, cat, st, st + timedelta(minutes=45 if kind == "standup" else 90), rec, mentor))
    db.run("insert into announcements (title, body) values ('Welcome to the programme', 'Your first month is training. Check the calendar for classes and post your stand-up every morning.')")
    from services import apply_template, default_template_id
    apply_template(ids[5], default_template_id(), start)         # Meera gets the 30-day daily schedule (days 1-10 already unlocked)
    # a student who finished the programme 3 days ago with every task approved: the daily job will issue a certificate
    old = today() - timedelta(days=33)
    sid = db.one("""insert into users (name,email,phone,password_hash,role,college,mentor_id,start_date)
                    values ('Neha Iyer','student7@demo.test','9000000107',%s,'student','Symbiosis',%s,%s) returning id""", (h, mentor, old))["id"]
    for i in range(3):
        t = db.one("insert into tasks (title,description,due_date,max_points,created_by) values (%s,'Sample',%s,10,%s) returning id",
                   (f"Capstone step {i + 1}", old + timedelta(days=5 * (i + 1)), mentor))["id"]
        db.run("insert into task_assignments (task_id,student_id,status,points,submission_text,submitted_at,reviewed_at) values (%s,%s,'approved',9,'Done',now(),now())", (t, sid))
    # an applicant test so the automatic test -> shortlist -> interview flow can be tried
    tid = db.one("insert into tests (role_title,title,duration_mins,passing_score) values ('Data Analyst','Data Analyst screening',20,60) returning id")["id"]
    for i, (q, a, b, c, d, ok) in enumerate([
            ("Which SQL clause filters rows?", "WHERE", "ORDER BY", "LIMIT", "AS", "a"),
            ("Which function counts rows?", "SUM", "COUNT", "AVG", "MAX", "b"),
            ("A bar chart is best for...", "Comparing categories", "Showing a map", "Typing text", "Encrypting data", "a"),
            ("The average of 2, 4, 6 is", "3", "4", "5", "6", "b"),
            ("Which Python library is for tables of data?", "pandas", "flask", "requests", "pytest", "a")]):
        db.run("insert into test_questions (test_id,question,option_a,option_b,option_c,option_d,correct,sort_order) values (%s,%s,%s,%s,%s,%s,%s,%s)", (tid, q, a, b, c, d, ok, i))
    d0 = today()
    for k in range(1, 8):
        day = d0 + timedelta(days=k)
        if day.weekday() < 5:
            for hh in (10, 11, 15):
                db.run("insert into interview_slots (mentor_id,starts_at,duration_mins,meeting_link) values (%s,%s,30,'https://meet.example.com/interview') on conflict do nothing",
                       (mentor, datetime.combine(day, time(hh, 0), tzinfo=tz)))
    return (f"Demo data loaded. Mentor: mentor@demo.test, students: student1@demo.test … student7@demo.test, password {PW}. " + _directory())


# ---------------------------------------------------------------- class directory sample data (fictional institutes)
SAMPLE = [
    ("Sahyadri Code Lab", "Coding & IT", "Kothrud", "hybrid", "Project-based web development and Python classes for beginners.",
     [("Full-stack web development", "4 months", 18000, 24000, "Weekdays 6-8 pm"), ("Python for beginners", "6 weeks", 6000, 6000, "Sat-Sun 10-12")]),
    ("Deccan Data Academy", "Data Science & AI", "Shivajinagar", "offline", "Data analysis with Excel, SQL and Python, with live projects.",
     [("Data analyst program", "5 months", 30000, 36000, "Weekdays 7-9 am"), ("SQL crash course", "3 weeks", 4500, 4500, "Evenings")]),
    ("Pimpri Spoken English Centre", "Spoken English", "Pimpri", "offline", "Confidence-building spoken English and interview practice.",
     [("Spoken English - basic", "2 months", 3500, 4500, "Mon-Fri 5-6 pm"), ("Interview and group discussion", "3 weeks", 2500, 2500, "Sat 4-6 pm")]),
    ("Hadapsar Commerce Classes", "Commerce & Accounting", "Hadapsar", "offline", "Tally, GST and accounting for working people and students.",
     [("Tally + GST", "3 months", 7000, 9000, "Evenings"), ("Advanced Excel", "1 month", 3000, 3000, "Weekends")]),
    ("Baner Design Studio", "Design & Creative", "Baner", "hybrid", "UI/UX design, Figma and graphic design with portfolio reviews.",
     [("UI/UX design", "4 months", 22000, 28000, "Weekdays 6-8 pm"), ("Graphic design basics", "2 months", 9000, 9000, "Weekends")]),
    ("Aundh IELTS Hub", "IELTS & Foreign Languages", "Aundh", "hybrid", "Small-batch IELTS and German language classes.",
     [("IELTS preparation", "2 months", 11000, 13000, "Mon-Thu 7-9 pm"), ("German A1", "3 months", 12000, 12000, "Weekends")]),
    ("Wakad Digital Marketing Institute", "Digital Marketing", "Wakad", "online", "SEO, social media and ads with real campaigns.",
     [("Digital marketing", "3 months", 15000, 20000, "Weekends 10-1")]),
    ("Kharadi Competitive Exam Point", "Competitive Exams", "Kharadi", "offline", "Foundation classes for MPSC and banking exams.",
     [("MPSC foundation", "8 months", 25000, 30000, "Mornings"), ("Banking exams", "4 months", 14000, 14000, "Evenings")]),
    ("Viman Nagar Music School", "Music", "Viman Nagar", "offline", "Guitar, keyboard and vocals for all ages.",
     [("Guitar", "Monthly", 1800, 2400, "Flexible"), ("Keyboard", "Monthly", 1800, 2400, "Flexible")]),
    ("Hinjewadi Java Institute", "Coding & IT", "Hinjewadi", "offline", "Java, Spring and interview preparation close to the IT park.",
     [("Java full stack", "5 months", 26000, 32000, "Weekdays 7-9 pm")]),
    ("Kothrud Yoga Studio", "Fitness & Yoga", "Kothrud", "offline", "Morning and evening yoga batches.",
     [("Yoga monthly batch", "Monthly", 1500, 2000, "6-7 am / 6-7 pm")]),
    ("Shivajinagar Maths Tuitions", "School Tuition", "Shivajinagar", "offline", "Maths and science tuition for classes 8 to 10.",
     [("Maths + Science, class 10", "1 year", 24000, 24000, "Evenings")]),
]
REVIEWS = [(5, "Clear teaching and the trainers were patient with beginners."), (4, "Good value for the fees. Batch timings were flexible."),
           (5, "Helped me get my first interview call. Practical sessions were the best part."), (3, "Decent classes but the batch was a bit crowded."),
           (4, "Honest about fees and the syllabus matched what was promised.")]


def _directory():
    from werkzeug.security import generate_password_hash as gen
    import services
    if db.one("select 1 from classes limit 1"):
        return "Directory already has data."
    h = gen(PW)
    members = []
    for i, n in enumerate(["Ananya Kulkarni", "Vikram Rao", "Pooja Mehta", "Sanjay Pawar", "Divya Nair"]):
        members.append(db.one("""insert into users (name,email,password_hash,role,email_verified) values (%s,%s,%s,'member',true)
                                 on conflict (lower(email)) do update set name=excluded.name returning id""", (n, f"member{i + 1}@demo.test", h))["id"])
    for i, (name, cat, area, mode, desc, courses) in enumerate(SAMPLE):
        phone = f"98000010{i:02d}"
        c = db.one("""insert into classes (slug,name,category,area,address,phone,whatsapp,email,website,mode,description,verified,status,source,fees_updated_at)
                      values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'live','admin', now() - make_interval(days => %s)) returning id""",
                   (services.unique_class_slug(name, area), name, cat, area, f"{area}, Pune", phone, phone, f"hello{i}@example.com", "https://example.com",
                    mode, desc + " (Sample listing for demonstration.)", i % 3 != 2, 10 if i != 3 else 240))["id"]   # one listing has stale fees
        for j, (t, dur, lo, hi, bt) in enumerate(courses):
            db.run("insert into class_courses (class_id,title,duration,fee_min,fee_max,batch_timing,sort_order) values (%s,%s,%s,%s,%s,%s,%s)", (c, t, dur, lo, hi, bt, j))
        for k in range((i % 4) + 1):
            rating, body = REVIEWS[(i + k) % len(REVIEWS)]
            db.run("insert into class_reviews (class_id,user_id,rating,body,status) values (%s,%s,%s,%s,'live') on conflict do nothing", (c, members[k], rating, body))
        services.refresh_rating(c)
    pk = db.one("select id from ad_packages where code='dir-30'")["id"]
    db.run("""insert into ad_campaigns (advertiser_name,contact_email,headline,body,link_url,package_id,starts_on,ends_on,status)
              values ('Demo Academy','ads@example.com','Learn Python in 6 weeks','Small batches, weekend classes. Sample advertisement.','https://example.com',%s,%s,%s,'active')""",
           (pk, today(), today() + timedelta(days=29)))
    return f"Directory sample data: {len(SAMPLE)} fictional Pune listings, reviews by member1@demo.test … member5@demo.test, one sample ad."
