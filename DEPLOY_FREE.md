# Launch for ₹0 (what is free, what is not, and the traps)

Prices and limits below were checked in November 2026 and **change often**: confirm on each provider's pricing page before you rely on them.

## Will it handle 50 users? Yes for a pilot. What I measured, and what I could not

I started the app exactly as the free host will (one gunicorn worker, 8 threads) and had **30 visitors and 20 signed-in students use it at the same moment** (search, class pages, enquiries, login, dashboards, tasks):

- 470 requests in about 6 seconds, **0 errors**.
- Typical page or API call: **40–60 ms**. Login: **about 0.8–1 s** when 20 people log in at once (password hashing is deliberately slow).
- Memory: about 67 MB idle. 50 people logging in at the same instant used to push it to **323 MB** (dangerous on a 512 MB instance); I now limit concurrent password hashing, which cut that peak to **133 MB** with the same total time.
- Email: tasks, due-tomorrow and overdue notices are now **one email per student per day**, so 50 students is about 50 emails a day, inside a 100-a-day free plan.

**What this does not prove:** I ran it on my own machine with a local database and a full CPU core. A free Render instance has a smaller CPU share (I could not confirm how small) and your database is a network hop away, so expect it to be slower than these numbers, especially for logins and the first visit after a sleep. 50 *registered* users are almost never online at once: a few at a time is the normal case. If you ever see it struggling, the first paid upgrade is the always-on instance.

## The free stack

| Job | Use | Free limits that matter |
|---|---|---|
| App + website (Flask, serves the built React site) | **Render**, free web service (Docker) | Sleeps after 15 min without visitors; the next visitor waits about a minute. 750 free hours a month (enough for one always-on service). Its disk is wiped on every restart, so files must not live there |
| Database | **Supabase** (free) or **Neon** (free) | Supabase is already what the app is set up for. Neon's free database scales to zero after 5 idle minutes and is about 0.5–1 GB per project. The app reconnects automatically if the database was asleep |
| Resume files | **Supabase Storage** (free), private bucket `resumes` | Small free quota; resumes are tiny |
| Email | Any free SMTP plan (Resend, Brevo, Gmail app password …) | Free plans cap sending (Resend: 100 a day). Set `EMAIL_DAILY_LIMIT`; reminders wait in a queue when 80% is used and important mail (password reset, test links, payments) always goes first |
| Automation + keep-awake | **GitHub Actions** (free schedules in this repo) | GitHub may delay a run by minutes, and can pause schedules in repositories with no activity: keep an eye on the Actions tab |

**Do not use:** Vercel Hobby (not allowed for commercial use: you take payments and show ads) · Render's free Postgres (it expires) · the free tier of uptime monitors that ban commercial use (UptimeRobot did from late 2024). GitHub Actions already pings your site.

## What is NOT free, and what the app does about it

- **A domain name** (a `.in` costs a few hundred rupees a year). Until you have one, your site lives at `https://yourname.onrender.com`. Most email services only let you send from a domain you own and verify; with no domain, use a Gmail/Brevo account's SMTP details for now and expect some mail to land in spam. This is the one purchase worth making early.
- **Taking money.** Razorpay needs a business KYC and charges per transaction. So for now: keep the internship free (Admin → Automation → Switches → Enrolment fee = 0) and leave the Razorpay keys empty. The app then automatically **hides "Advertise" and refuses ad purchases** instead of failing at payment time. Directory listings, reviews, tests, interviews, certificates, reminders and the weekly report all work without payments.
- **Always-on hosting** (Render Starter is about $7 a month) and a bigger email plan (Resend Pro about $20 a month): upgrade when real users complain about the one-minute wake-up or the email cap.

## Step by step (about an hour)

0. **Name:** the product is called **UpStep**. New databases start with that name. If you reuse an older database, change it in Admin → Settings → Company name.
1. **GitHub:** create a *private* repository and push this folder. (`.env` is ignored, so your secrets stay out. Never upload a `.env` file.)
2. **Supabase:** new project (choose the region closest to where you will run Render; a database in the same region as the app is faster. I did not verify the current region lists, so check both) → Project Settings → Database → copy the **Session pooler** connection string. Storage → create a **private** bucket named `resumes`. Project Settings → API → copy the project URL and the `service_role` key (server only, never in the website).
3. **Create the tables, from your own computer** (needs Python): 
   ```bash
   cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   DATABASE_URL='postgresql://…' flask --app app init-db
   DATABASE_URL='postgresql://…' flask --app app create-admin
   ```
   Do **not** run `demo-data` on the real database.
4. **Render:** New → Blueprint → choose the repository (it reads `render.yaml`). Fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, the SMTP values, and `SITE_URL` (you can fill it after the first deploy, once Render shows your address; then redeploy). `SECRET_KEY` and `CRON_SECRET` are generated for you: copy the `CRON_SECRET` value.
5. **GitHub → Settings → Secrets and variables → Actions:** add `SITE_URL` (your Render address, no trailing slash) and `CRON_SECRET` (the same value as on Render). Open the Actions tab and run both workflows once with "Run workflow" to confirm they turn green.
6. **First login:** open your site, sign in with the admin you created, then Admin → Settings (company name, contact email), Admin → Legal pages (have a lawyer read them), Admin → Class directory → CSV import (your first real listings).
7. **Check Admin → Automation → Switches:** "What is connected" should show your email; the decision log fills up as the rules run.

## Updating later

Pull the new code, then run `flask --app app init-db` once against your database (it only adds what is missing and is safe to repeat), then redeploy.

## Known free-tier behaviour to expect

- The first visit after a quiet spell can take about a minute (the keep-alive workflow makes this rare, not impossible). Search engines may time out on a cold start, so a paid always-on instance is the first upgrade to consider once you want Google traffic.
- Emails above the daily cap are delayed to the next day (reminders) rather than lost.
- If the Actions schedules stop, nothing breaks but reminders, task unlocking messages, certificates and the weekly report stop until you run the **Run all automations now** button in Admin → Automation (tasks still unlock by date on their own).
