"""Default legal text and task templates. `ensure_defaults()` is safe to run any number of times."""
import db

LEGAL_NOTE = ("DRAFT – written as a starting point, not legal advice. Have a lawyer read and adapt this text before you launch.")

LEGAL = {
    "terms": ("Terms of Use", """These terms apply when you use this website, the class directory and the internship platform ("the Service").

1. Who we are
The Service is run by the company named in the footer of this site ("we", "us").

2. Using the Service
You must give true information. You must not post spam, abusive or misleading content, copy listings in bulk, or try to break or overload the Service. We may remove content or suspend accounts that break these terms.

3. Class directory
Listings, fees and timings are supplied by institutes and may change. We show the date fees were last updated, but we do not guarantee them. Always confirm fees, batch timings and refund rules with the institute before paying. We do not run the classes and are not a party to your arrangement with an institute. A "Verified" badge means we confirmed the institute's phone number, nothing more.

4. Reviews
Reviews must come from your own genuine experience, must not contain personal contact details or links, and must not be abusive. Institutes cannot pay to change their rating or their position in organic results. Sponsored placements are always labelled "Sponsored".

5. Accounts
Keep your password private. You are responsible for activity on your account.

6. Limits of liability
The Service is provided "as is". To the extent the law allows, we are not liable for indirect or consequential loss, or for decisions you take based on listings or reviews.

7. Changes and contact
We may update these terms; the version you accepted and the date are recorded. Questions: use the contact email shown on the site."""),
    "privacy": ("Privacy Policy", """This policy explains what personal data we collect and why, in line with the Digital Personal Data Protection Act, 2023 and the Information Technology Act, 2000.

What we collect
- Applicants: name, email, phone, college, resume, test answers and interview notes.
- Students: the above plus task submissions, stand-ups, chat messages, attendance and performance.
- Directory users: name, email and the reviews you write. Visitors who send an enquiry: name, phone and message (shared with that institute).
- Institutes: contact details and course information you give us.
- Technical: a hashed form of your IP address for spam control. We do not store your raw IP address in review or enquiry records.

Why we use it
To run applications and training, to show and moderate the class directory, to forward enquiries to the institute you chose, to send service emails and messages, to take payments, to issue and verify certificates, and to keep the Service safe.

Who sees it
Only the people who need it: our admins and your mentor (for students); the institute (for enquiries sent to them). Payments are handled by our payment provider; we never see your card or UPI PIN. Reviewer names are shown publicly as first name and last initial. A certificate's public verify page shows only the holder's name, grade and dates.

Retention and your rights
We keep data as long as needed for these purposes or the law requires. You can ask to see, correct or delete your data, or withdraw consent, by emailing the contact address on the site. Deleting data may end your access to the Service.

Cookies and ads
We use browser storage to keep you signed in. If advertising from Google AdSense is enabled, Google may use cookies; you can manage this in your Google ad settings.

Security
Passwords are stored hashed, access is controlled on the server, and files are stored privately. No system is perfectly secure; report problems to the contact email."""),
    "refund": ("Refund and Cancellation Policy", """This policy applies to the internship enrolment fee and to advertising packages bought on this site.

Internship enrolment fee
- If you cancel before the first task unlocks, you get a full refund.
- If you cancel within 3 days of your start date, the fee is refunded after deducting a processing charge of 10%.
- After that, the fee is not refundable, except where we fail to deliver the programme or you are charged twice or in error.
- If we cancel or cannot start your batch, you get a full refund.

Advertising packages
- You can cancel before the campaign goes live for a full refund.
- If we reject your advertisement (for example because it is misleading), you get a full refund.
- Once an advertisement is live, the fee is not refundable.

How refunds work
Approved refunds are returned to the original payment method within 5 to 7 working days. Refunds of failed or double payments are handled on request. Disputes are decided by a person, not automatically. To ask for a refund, write to the contact email on the site with your payment reference."""),
    "internship-terms": ("Internship Terms", """These terms apply if you are selected for the internship / training programme.

1. Nature of the programme
This is a learning and selection programme: about one month of guided training followed by project work. It is not employment and does not by itself guarantee a job. A full-time offer depends on performance and business need.

2. Your commitments
Attend the daily stand-up, submit tasks on time, be honest about your work, respect your mentor and teammates, and keep chat and shared material professional.

3. Tasks and scoring
Tasks unlock on a daily schedule from your start date. A task not submitted by its due date plus the grace period is marked incomplete and scores zero unless your mentor reopens it. Your performance score is points earned divided by points available for the tasks released so far.

4. Certificate
A certificate is issued automatically when the programme period has ended, all submitted work is reviewed, and your performance score meets the pass mark shown on the platform. It can be revoked if it was issued by mistake or obtained through dishonest work. Anyone can verify it online.

5. Your work and our materials
You own work you create yourself. You allow us to use your project work for the programme and to show it internally. Do not share training material, test questions or other students' data outside the programme.

6. Conduct and removal
We may remove a student for repeated absence, plagiarism, harassment or breaking these terms. See the Refund Policy for fees.

7. Data
We handle your data as described in the Privacy Policy."""),
}

DAILY_30 = [
    ("Set up your tools", "Install Git, a code editor and create a GitHub account. Share your GitHub profile link.", "github profile; git installed; editor"),
    ("Git basics", "Create a repository, make 3 commits and push. Share the repo link.", "repository; commit; push"),
    ("HTML structure", "Build a one-page 'About me' in plain HTML with headings, a list and an image.", "heading; list; image; html"),
    ("CSS styling", "Style yesterday's page: colours, spacing and a readable font.", "css; colour; spacing; font"),
    ("Responsive layout", "Make the page work on a phone using flexbox or grid. Describe what you changed.", "responsive; flexbox; grid; mobile"),
    ("Rest and review", "Re-read your work from days 1-5. List three things you would improve.", "improve; review"),
    ("Weekend practice", "Pick any small web page you like and rebuild a section of it. Share a screenshot.", "screenshot; rebuild"),
    ("JavaScript variables", "Write 10 small programs using variables and conditions. Share the file or link.", "variable; condition; function"),
    ("Functions and arrays", "Solve 8 practice problems with functions and arrays.", "function; array; loop"),
    ("The DOM", "Add a button to your page that changes text or colour when clicked.", "dom; click; event"),
    ("Mini project: to-do list", "Build a to-do list (add, tick, delete) in plain JavaScript.", "add; delete; list; javascript"),
    ("Fetching data", "Fetch data from a public API and show it on a page.", "fetch; api; json"),
    ("Rest and review", "Write a short note on what you learned this week and where you are stuck.", "learned; stuck"),
    ("Weekend practice", "Improve your to-do list: save items so they stay after refresh.", "storage; persist"),
    ("Python basics", "Solve 10 beginner Python problems (strings, lists, loops).", "python; string; list; loop"),
    ("Python functions and files", "Write a script that reads a text file and counts the words.", "file; count; function"),
    ("Intro to databases", "Design two related tables on paper and write them as SQL CREATE TABLE statements.", "table; primary key; foreign key; sql"),
    ("SQL queries", "Write 8 queries: select, filter, sort, join and group.", "select; where; join; group"),
    ("Flask hello world", "Create a Flask app with two routes that return JSON.", "flask; route; json"),
    ("Flask + database", "Connect your Flask app to a database table and return its rows.", "database; query; endpoint"),
    ("Rest and review", "Draw a simple diagram showing how browser, server and database talk to each other.", "diagram; server; database"),
    ("Weekend practice", "Add one more endpoint to your Flask app and test it with a browser or curl.", "endpoint; test"),
    ("Clear communication", "Record a 2-minute video or voice note introducing yourself. Share the link.", "introduction; clear"),
    ("Write a professional email", "Write an email to a mentor asking for feedback on your project. Paste it.", "subject; greeting; request; thanks"),
    ("Resume draft", "Write your first resume draft (one page). Share the file link.", "education; projects; skills"),
    ("LinkedIn profile", "Complete your LinkedIn profile and share the link.", "headline; summary; skills"),
    ("Mock interview prep", "Write answers to 5 common HR questions (tell me about yourself, strengths, etc.).", "strengths; example; yourself"),
    ("Mock interview", "Practice a 10-minute mock interview with a friend or mentor. Write 3 things to improve.", "improve; feedback"),
    ("Portfolio", "Put your best 3 projects on one portfolio page. Share the link.", "portfolio; project; link"),
    ("Final reflection", "Write a short reflection: what you built, what you learned, what you will do next.", "built; learned; next"),
]


def ensure_defaults():
    for slug, (title, body) in LEGAL.items():
        if not db.one("select 1 from legal_documents where slug=%s", (slug,)):
            db.run("insert into legal_documents (slug, version, title, body) values (%s,1,%s,%s)", (slug, title, body))
    if not db.one("select 1 from task_templates limit 1"):
        tid = db.one("insert into task_templates (name, description, is_default) values (%s,%s,true) returning id",
                     ("30-day training", "One small task every day for 30 days. Day N unlocks on start date + N - 1."))["id"]
        for i, (title, desc, rubric) in enumerate(DAILY_30, start=1):
            db.run("""insert into task_template_items (template_id, day_no, title, description, max_points, due_in_days, grace_days, rubric)
                      values (%s,%s,%s,%s,%s,%s,%s,%s)""", (tid, i, title, desc, 10, 1, 1, rubric))
        tid2 = db.one("insert into task_templates (name, description) values (%s,%s) returning id",
                      ("7-day starter", "A short week-long warm-up."))["id"]
        for i, (title, desc, rubric) in enumerate(DAILY_30[:7], start=1):
            db.run("""insert into task_template_items (template_id, day_no, title, description, max_points, due_in_days, grace_days, rubric)
                      values (%s,%s,%s,%s,%s,%s,%s,%s)""", (tid2, i, title, desc, 10, 1, 1, rubric))
