# UpStep: Pune class directory + internship platform

React (frontend) · Flask (backend) · PostgreSQL / Supabase (database, resume storage)

Two products in one app and one database:

1. **Class Directory** – students search Pune classes by topic, area, mode and fee, read honest reviews and contact the institute. (The original reason for the project.)
2. **Internship platform** – applications, online test, interviews, daily tasks, mentors, groups, chat, stand-ups, performance score, now with payments, certificates and automation.

```
upstep/
├─ frontend/   React + Vite website, directory, student dashboard, admin/mentor screens
├─ backend/    Flask API + automation rules + search-engine pages (seo.py)
├─ supabase/   schema.sql  ← the ONLY file a new install needs (safe to re-run to upgrade)
├─ scripts/    backup.sh (nightly database backup with rotation)
└─ run_smoke_test.sh
```

> **No budget yet?** Read **[DEPLOY_FREE.md](DEPLOY_FREE.md)**: a ₹0 launch (Render + Supabase + GitHub Actions) with the traps to avoid.

## 1. Run it on your computer (about 10 minutes)

You need Python 3.11+, Node 18+, and a PostgreSQL database (a free Supabase project, or a local PostgreSQL).

```bash
# --- backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL and SECRET_KEY; for development also set DEV_SHOW_OTP=1
flask --app app init-db         # creates all tables, the 4 legal pages and the 30-day task template
flask --app app create-admin    # asks for your admin email, name, password
flask --app app demo-data       # OPTIONAL: sample mentor, students, 12 fictional Pune listings, a test, interview slots, one sample ad
python app.py                   # API on http://localhost:5000

# --- frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173  (calls to /api are proxied to Flask)
```

**One-port mode (what production looks like):** `cd frontend && npm run build`, then open `http://localhost:5000`. Flask serves the built website itself, with real titles, descriptions, structured data and readable content on every directory page, plus `/sitemap.xml` and `/robots.txt`. This is what lets Google index each class.

Demo logins (password `Demo@1234`): `mentor@demo.test`, `student1@demo.test` … `student7@demo.test` (student7 has finished the programme, so the daily job issues a certificate), and directory members `member1@demo.test` … `member5@demo.test`.

> **Supabase:** run `supabase/schema.sql` in the SQL Editor (or use `flask --app app init-db`), create a **private** Storage bucket `resumes`, and copy the Session-pooler URI, project URL and `service_role` key into `.env`. Never put the service key in the frontend, and never commit or zip your `.env` file.
>
> `supabase/migration_pipeline.sql` is only for databases created *before* the application pipeline existed. New installs do not need it: `schema.sql` already contains those columns.

## 2. What is built

### Class Directory
| For | What |
|---|---|
| Students | `/classes` search + filters (topic, area, online/offline, fee range, verified), sort, pages · `/classes/<name>` courses and fee ranges with "last updated" date, reviews, Call / WhatsApp / Share, call-back form · area and topic landing pages (`/classes/in/kothrud`, `/classes/topic/music`) |
| Reviewers | Free account (`/register`) with email confirmation. One review per class; spam-looking reviews are held automatically; names shown as first name + initial |
| Institutes | `/list-your-class` (phone verified by OTP) · **Claim this listing** (OTP to the phone on record) · private management link to update fees, courses, and see enquiries · reminder emails when fees get older than 6 months · enquiries are forwarded instantly by email and WhatsApp/SMS gateway, with a 24-hour follow-up reminder |
| Admin | Listings, new-submission queue (approve/reject), review moderation, enquiries, **CSV import** (one row per course), reset-owner for disputes |
| Trust rules | Nothing paid can change rating or order. Ratings are smoothed so one 5-star review cannot beat many good ones. Ads are always labelled **Sponsored**. Verified = phone confirmed, nothing more |

**Getting your first 50 listings:** collect them yourself (calls, walk-ins in Shivajinagar, Kothrud, Hadapsar, Pimpri), enter them in a CSV (Admin → Class directory → CSV import → download the template) and import. Do not copy listings from other websites: it breaks their terms and gives stale data. Then let institutes claim their own listing. The 12 listings from `demo-data` are fictional samples; delete them before launch.

### Business layer
- **Legal pages and consent log** – Terms, Privacy, Refund, Internship Terms (editable, versioned). Every acceptance (apply, register, list a class, pay, buy an ad) is stored with the version and time. *The texts are drafts: have a lawyer read them before launch.*
- **Payments** – set an enrolment fee in Admin → Automation → Switches. Selecting an applicant then emails a payment link; when the payment is confirmed the account, mentor, group and daily schedule are created automatically, and an invoice is issued. Razorpay (order, signature check, webhook) when keys are set; otherwise a clearly labelled **demo gateway** with no real money, which is refused when `PRODUCTION=1`. Refunds and disputes stay with a person.
- **Certificates** – issued automatically when the programme period has ended, all work is reviewed and the performance score reaches the pass mark. Number, grade, QR code, printable page (`/certificate/<no>`) and a public verify page (`/verify/<no>`) that shows only name, grade and dates. Revocable.
- **Ads** – self-serve packages at `/advertise`, paid online, started and ended automatically, labelled Sponsored, rotated fairly, with a views/clicks report emailed at the end. Claims like "100% placement" are held for a person to check; rejecting an ad refunds it. Optional Google AdSense fallback slot (Admin → Automation → Switches).
- **Password reset by email link**, email confirmation for reviewers.

### Automation ("auto mode")
Rules do the routine work; **every automatic decision is logged in Admin → Automation and the reversible ones have an Undo button.** Turn it all off with one switch.

| Area | Automatic | A person still does |
|---|---|---|
| Applying | Test link emailed at once (no account needed) | |
| Test | At/above pass mark → shortlisted + interview link; clearly below → polite decline | Borderline scores; undo any decision |
| Interviews | Applicant picks a slot from open mentor times; confirmation with calendar file, entry in the mentor's calendar, reminders 24 h and 1 h before | Interview; opening slots |
| Selecting | Account, welcome email, mentor, group, daily schedule (after payment if a fee is set) | The final selection click |
| Daily tasks | Task templates: Day N unlocks on start date + N − 1; email when unlocked, 24 h before due, when overdue; past due + grace → marked incomplete (mentor can reopen) | Editing templates |
| Inactive students | 2 days quiet → nudge; 4 days → flag to the mentor | The call |
| Certificates | See above | Revoking a wrong one |
| Reviews / listings | Auto-approve normal reviews, hold spam patterns (links, phone numbers, abuse, duplicates, bursts); OTP verification; stale-fee and 24 h enquiry reminders | Held reviews, ownership disputes |
| Reports | Weekly report emailed to admins every Monday; daily stand-up digest per mentor | Reading them |
| AI-assisted | Task review **draft** (link check + rubric check, optional model), resume skill **ranking**, question drafting (needs a key) | Every final decision. AI never approves, rejects or shortlists |

**Scheduling:** on a host that sleeps when idle, let GitHub Actions call `POST /api/cron/run` (set `CRON_SECRET`; workflows are in `.github/workflows`). Otherwise set `AUTO_SCHEDULER=1` (runs inside the web process every `AUTO_INTERVAL_MIN` minutes; a database lock makes sure only one instance runs a tick), or run `flask --app app run-automations` from cron. The same button exists in Admin → Automation. Every job is safe to run repeatedly; nothing is sent twice.

### Operations
- **Backups:** `scripts/backup.sh` (compressed `pg_dump`, keeps the newest 14). Put it in cron. Restore line is at the bottom of the script.
- **Health:** point an uptime monitor at `GET /api/health`.
- **Error alerts to your phone:** set `ALERT_WEBHOOK_URL` (Slack, Discord, ntfy.sh …) and optionally `SENTRY_DSN`.
- **Rate limits:** per process by default; set `REDIS_URL` to share them across instances.
- **Free email plans:** set `EMAIL_DAILY_LIMIT` (for example 100). Reminders and digests wait in a queue when 80% of the budget is used; password resets, test links and payment mails always go first.
- **Email / SMS / WhatsApp:** without SMTP or a gateway webhook, messages are only saved in the `outbox` table (so nothing is lost, and you can see exactly what would be sent).

## 3. Settings you must change before real users

1. `SECRET_KEY` (long random), `PRODUCTION=1`, `CORS_ORIGINS`, `SITE_URL` (public https address), `TRUST_PROXY=1` if behind a proxy.
2. SMTP settings, and an SMS/WhatsApp webhook if you want OTPs and instant alerts by phone. Without an SMS gateway, institute OTP verification cannot reach phones.
3. Razorpay keys and webhook (`/api/webhooks/razorpay`) if the internship is paid.
4. Lawyer review of the four legal texts; your company name and contact email (Admin → Settings).
5. Delete the demo data and demo users.

## 4. Privacy

Enforced in the API, not just the UI. Students never receive another person's email or phone from any endpoint; mentors see names and progress; only admins see contact details. Directory members have their own role and cannot reach any internship data (covered by tests). Raw IP addresses are not stored in reviews or enquiries (a keyed hash is used for spam control). Certificates' public page shows name, grade and dates only.

## 5. Tests

```bash
cd backend && TEST_DATABASE_URL=postgresql://user:pass@localhost/testdb python -m pytest -q   # 65 API tests (wipes that DB!)
TEST_DATABASE_URL=postgresql://user:pass@localhost/testdb ./run_smoke_test.sh                  # 40 React screen tests against a live API
```
Use a throw-away local PostgreSQL for these, never your Supabase project.

## 6. Deploying

- **Free launch:** `DEPLOY_FREE.md` (Dockerfile + `render.yaml` + GitHub Actions are included; the Dockerfile could not be built in my test environment, so the first Render build is its first real test).
- **Single service (simplest):** build the frontend (`npm run build`), run `gunicorn -w 2 --threads 8 "app:create_app()"` from `backend/` on Render, Railway or a VPS, with the environment variables above. Flask serves the API and the website.
- **Split hosting:** host `frontend/dist` on Vercel/Netlify/Cloudflare Pages with `VITE_API_URL` set and an all-paths-to-`index.html` rewrite. You then lose the server-rendered directory pages (bad for Google), so prefer single service.

## 7. Known limits

- Chat still refreshes every 4 seconds (Supabase Realtime can replace it later).
- The AI model path (`ANTHROPIC_API_KEY`) is built but has only been tested with a mocked model; the rule-based fallback is what is verified.
- Razorpay was tested with simulated responses and signatures, not against Razorpay's servers: do a live test-mode payment before launch.
- The WhatsApp/SMS hook posts JSON to a URL you provide; no specific provider is built in.
- Task templates are copied to each student when they enrol; editing a template does not change tasks already created for current students.
