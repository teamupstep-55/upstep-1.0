import os
import secrets
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.security import generate_password_hash

import alerts
import db
from security import ApiError, password_problem

load_dotenv()
HERE = os.path.dirname(os.path.abspath(__file__))


class Provider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, time):
            return o.isoformat(timespec="minutes")          # interview times: "10:30"
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app(test_config=None):
    app = Flask(__name__)
    app.json = Provider(app)
    env = os.environ.get
    secret = env("SECRET_KEY")
    if not secret:
        if env("PRODUCTION") == "1":
            raise RuntimeError("Set SECRET_KEY in the environment for production.")
        secret = secrets.token_hex(32)  # dev only: sessions reset on every restart
    app.config.update(
        SECRET_KEY=secret,
        DATABASE_URL=env("DATABASE_URL", ""),
        TZ=ZoneInfo(env("APP_TIMEZONE", "Asia/Kolkata")),
        TOKEN_HOURS=int(env("TOKEN_HOURS", "12")),
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        SUPABASE_URL=env("SUPABASE_URL", ""),
        SUPABASE_SERVICE_KEY=env("SUPABASE_SERVICE_KEY", ""),
        SUPABASE_BUCKET=env("SUPABASE_BUCKET", "resumes"),
        LOCAL_UPLOAD_DIR=os.path.join(HERE, "uploads"),
        BREVO_API_KEY=env("BREVO_API_KEY", ""),
        SMTP_HOST=env("SMTP_HOST", ""), SMTP_PORT=int(env("SMTP_PORT", "587")),
        SMTP_USER=env("SMTP_USER", ""), SMTP_PASSWORD=env("SMTP_PASSWORD", ""), SMTP_FROM=env("SMTP_FROM", ""),
        SITE_URL=env("SITE_URL") or env("RENDER_EXTERNAL_URL") or "http://localhost:5173",   # Render sets RENDER_EXTERNAL_URL itself
        TESTING_NO_LIMITS=env("DISABLE_RATE_LIMITS") == "1",   # for automated tests only
        PRODUCTION=env("PRODUCTION") == "1",
        TRUST_PROXY=env("TRUST_PROXY") == "1",                 # only behind a proxy you control (Render, Nginx ...)
        FRONTEND_DIST=env("FRONTEND_DIST", os.path.join(HERE, "..", "frontend", "dist")),
        RAZORPAY_KEY_ID=env("RAZORPAY_KEY_ID", ""), RAZORPAY_KEY_SECRET=env("RAZORPAY_KEY_SECRET", ""),
        RAZORPAY_WEBHOOK_SECRET=env("RAZORPAY_WEBHOOK_SECRET", ""),
        ANTHROPIC_API_KEY=env("ANTHROPIC_API_KEY", ""), ANTHROPIC_MODEL=env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        SMS_WEBHOOK_URL=env("SMS_WEBHOOK_URL", ""), WHATSAPP_WEBHOOK_URL=env("WHATSAPP_WEBHOOK_URL", ""),
        ALERT_WEBHOOK_URL=env("ALERT_WEBHOOK_URL", ""),
        DEV_SHOW_OTP=env("DEV_SHOW_OTP") == "1",               # development only: shows OTP codes on screen
        AUTO_SCHEDULER=env("AUTO_SCHEDULER") == "1",
        REDIS=None,
        CRON_SECRET=env("CRON_SECRET", ""),                    # lets an outside scheduler wake the app and run the automations
        EMAIL_DAILY_LIMIT=int(env("EMAIL_DAILY_LIMIT", "0") or 0),   # e.g. 100 on a free email plan; 0 = no limit
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("DATABASE_URL is empty. Copy .env.example to .env and paste your Supabase connection string.")
    db.init_pool(app.config["DATABASE_URL"], int(env("DB_POOL_MAX", "5")))

    if env("REDIS_URL"):
        try:
            import redis
            r = redis.Redis.from_url(env("REDIS_URL"), socket_timeout=2, decode_responses=True)
            r.ping()
            app.config["REDIS"] = r
        except Exception as e:                                  # noqa: BLE001
            app.logger.warning("REDIS_URL set but Redis is not reachable (%s): using in-memory rate limits", e)
    alerts.init_sentry(env("SENTRY_DSN"))
    if app.config["PRODUCTION"] and not app.config.get("SUPABASE_URL"):
        app.logger.error("PRODUCTION=1 but Supabase Storage is not configured: uploaded resumes would be saved on the server's disk, "
                         "which most free hosts wipe on every restart. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")

    origins = [o.strip() for o in (env("CORS_ORIGINS") or app.config["SITE_URL"] or "http://localhost:5173").split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}}, allow_headers=["Authorization", "Content-Type"])

    from routes import (ads, applicant, auth_routes, automation_routes, certs, chat, classes, classes_admin, common, cron, legal, payments, public,
                        staff, student)
    for mod in (auth_routes, public, student, staff, chat, common, legal, classes, classes_admin, applicant, payments, certs, ads, automation_routes, cron):
        app.register_blueprint(mod.bp)
    import seo
    app.register_blueprint(seo.bp)                              # last: its catch-all serves the React app

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(404)
    def nf(_):
        return jsonify(error="Not found."), 404

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error="That upload is too large (limit 3 MB)."), 413

    @app.errorhandler(405)
    def na(_):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(Exception)
    def boom(e):
        app.logger.exception(e)
        alerts.notify(f"500 error: {type(e).__name__}: {e}")
        return jsonify(error="Something went wrong on our side. Please try again."), 500

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.get("/api/health")
    def health():
        """Point an uptime monitor (UptimeRobot, Better Stack ...) at this URL."""
        db.one("select 1 as ok")
        return jsonify(ok=True)

    # ---------------- CLI
    @app.cli.command("init-db")
    def init_db_cmd():
        """Create all tables (same as running supabase/schema.sql)."""
        db.apply_sql_file(os.path.join(HERE, "..", "supabase", "schema.sql"))
        import seed_data
        seed_data.ensure_defaults()
        click.echo("Database ready.")

    @app.cli.command("run-automations")
    @click.option("--force", is_flag=True, help="Also send the weekly report and stand-up digests now.")
    def run_automations_cmd(force):
        """Run every scheduled job once (reminders, task unlock, certificates ...). Put this in cron, e.g. every 30 minutes."""
        import automation
        for k, v in automation.run_all(force=force).items():
            click.echo(f"{k}: {v}")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_admin_cmd(email, name, password):
        """Create (or reset) an admin account."""
        email = email.strip().lower()
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        db.run("""insert into users (name,email,password_hash,role) values (%s,%s,%s,'admin')
                  on conflict (lower(email)) do update set role='admin', password_hash=excluded.password_hash, is_active=true""",
               (name.strip(), email, generate_password_hash(password)))
        click.echo(f"Admin ready: {email}")

    @app.cli.command("demo-data")
    def demo_cmd():
        """Add a demo mentor, 6 students, tasks, classes and a standup (password for all: Demo@1234)."""
        from demo import load
        click.echo(load())

    if app.config["AUTO_SCHEDULER"] and not app.config.get("TESTING"):
        import automation
        automation.start_scheduler(app, int(env("AUTO_INTERVAL_MIN", "30")))
    if env("KEEP_AWAKE") == "1" and not app.config.get("TESTING"):
        _start_keep_awake(app)
    return app


def _start_keep_awake(app):
    """Free hosts sleep after ~15 idle minutes. While the app is awake, it calls its own public address every 4 minutes
    so it stays awake. (Outside pingers wake it again after a restart.)"""
    import threading, time
    import requests as _rq

    def loop():
        time.sleep(60)
        url = (os.environ.get("RENDER_EXTERNAL_URL") or app.config["SITE_URL"]).rstrip("/") + "/api/health"
        while True:
            try:
                _rq.get(url, timeout=30)
            except Exception:
                pass
            time.sleep(240)
    threading.Thread(target=loop, daemon=True, name="upstep-keep-awake").start()


app = None
if os.environ.get("DATABASE_URL"):
    app = create_app()

if __name__ == "__main__":
    (app or create_app()).run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")),
                             debug=os.environ.get("FLASK_DEBUG") == "1")
