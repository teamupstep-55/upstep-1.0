"""Search-engine friendly pages. The React app is a single-page app, so Google would otherwise see an empty page.
This blueprint serves the built index.html with a real <title>, description, canonical link, JSON-LD and readable content
already inside <div id="root"> for: home, /classes, every class page, area pages, topic pages and legal pages.
React replaces that content as soon as it loads. Also serves /sitemap.xml and /robots.txt (always fresh from the database)."""
import html
import json
import os
import re

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory

import db
import services
from services import slugify

bp = Blueprint("seo", __name__)
E = html.escape

LEGAL_PATHS = {"terms": "/terms", "privacy": "/privacy", "refund": "/refund", "internship-terms": "/internship-terms"}


def dist_dir():
    return current_app.config["FRONTEND_DIST"]


def _index():
    p = os.path.join(dist_dir(), "index.html")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _page(title, desc, body_html="", path="/", jsonld=None, status=200, noindex=False):
    raw = _index()
    if raw is None:
        return jsonify(error="The website has not been built yet. Run 'npm run build' in the frontend folder."), 404
    base = services.site_url()
    head = [f"<title>{E(title)}</title>", f'<meta name="description" content="{E(desc[:300])}">', f'<link rel="canonical" href="{E(base + path)}">',
            f'<meta property="og:title" content="{E(title)}">', f'<meta property="og:description" content="{E(desc[:300])}">',
            f'<meta property="og:url" content="{E(base + path)}">', '<meta property="og:type" content="website">']
    if noindex:
        head.append('<meta name="robots" content="noindex">')
    if jsonld:
        head.append('<script type="application/ld+json">' + json.dumps(jsonld).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "</script>")
    out = re.sub(r"<title>.*?</title>", "", raw, count=1, flags=re.S).replace("</head>", "\n".join(head) + "\n</head>", 1)
    out = out.replace('<div id="root"></div>', f'<div id="root">{body_html}</div>', 1)
    return Response(out, status=status, mimetype="text/html", headers={"Cache-Control": "public, max-age=300"})


def _city():
    return services.setting("directory_city", "Pune") or "Pune"


def _fee_text(lo, hi):
    if lo is None:
        return "Fees on request"
    return f"₹{lo:,}" if lo == hi else f"₹{lo:,} to ₹{hi:,}"


def _class_list_html(rows, h1, intro=""):
    items = "".join(f'<li><a href="/classes/{E(r["slug"])}">{E(r["name"])}</a> – {E(r["category"])}, {E(r["area"])}'
                    f' ({_fee_text(r["fee_from"], r["fee_to"])}{", rated " + str(r["rating"]) + "/5" if r["rating"] else ""})</li>' for r in rows)
    return f"<main><h1>{E(h1)}</h1><p>{E(intro)}</p><ul>{items}</ul></main>"


LIST_SQL = """select c.slug, c.name, c.category, c.area, f.fee_from, f.fee_to,
         case when c.rating_count > 0 then round(c.rating_sum::numeric / c.rating_count, 1) end as rating
       from classes c left join lateral (select min(fee_min) as fee_from, max(fee_max) as fee_to from class_courses where class_id=c.id) f on true
       where c.status='live' {where} order by (c.rating_sum + 10.5)::numeric / (c.rating_count + 3) desc, c.name limit 60"""


# ------------------------------------------------------------------ crawlers
@bp.get("/robots.txt")
def robots():
    base = services.site_url()
    return Response(f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /app\nDisallow: /api/\nDisallow: /pay/\nDisallow: /status/\nDisallow: /manage/\n\nSitemap: {base}/sitemap.xml\n",
                    mimetype="text/plain", headers={"Cache-Control": "public, max-age=3600"})


@bp.get("/sitemap.xml")
def sitemap():
    base = services.site_url()
    urls = [("/", None), ("/classes", None), ("/list-your-class", None), ("/advertise", None), ("/apply", None)]
    urls += [(p, None) for p in LEGAL_PATHS.values()]
    for r in db.q("select slug, updated_at from classes where status='live' order by id"):
        urls.append((f"/classes/{r['slug']}", r["updated_at"]))
    for r in db.q("select distinct area from classes where status='live' order by area"):
        urls.append((f"/classes/in/{slugify(r['area'])}", None))
    for r in db.q("select distinct category from classes where status='live' order by category"):
        urls.append((f"/classes/topic/{slugify(r['category'])}", None))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, mod in urls:
        xml.append(f"<url><loc>{E(base + path)}</loc>" + (f"<lastmod>{mod:%Y-%m-%d}</lastmod>" if mod else "") + "</url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml", headers={"Cache-Control": "public, max-age=3600"})


# ------------------------------------------------------------------ pages
def render_for(path):
    city, co = _city(), services.company()
    if path == "/classes":
        rows = db.q(LIST_SQL.format(where=""))
        return _page(f"Find classes in {city} – compare fees, timings and reviews | {co}",
                     f"Search {len(rows)}+ classes and institutes in {city} by topic, area, mode and fee. Read honest reviews and contact the institute directly.",
                     _class_list_html(rows, f"Classes and institutes in {city}", "Compare fees and read reviews from students."), path)
    m = re.fullmatch(r"/classes/in/([a-z0-9-]+)", path)
    if m:
        row = next((r for r in db.q("select distinct area from classes where status='live'") if slugify(r["area"]) == m.group(1)), None)
        if not row:
            return _page("Page not found", "", "<h1>No classes found here yet</h1>", path, status=404, noindex=True)
        rows = db.q(LIST_SQL.format(where="and c.area = %s"), (row["area"],))
        return _page(f"Classes in {row['area']}, {city} – fees and reviews | {co}",
                     f"{len(rows)} classes and institutes in {row['area']}, {city}. Compare fees and timings and read student reviews.",
                     _class_list_html(rows, f"Classes in {row['area']}, {city}"), path)
    m = re.fullmatch(r"/classes/topic/([a-z0-9-]+)", path)
    if m:
        row = next((r for r in db.q("select distinct category from classes where status='live'") if slugify(r["category"]) == m.group(1)), None)
        if not row:
            return _page("Page not found", "", "<h1>No classes found here yet</h1>", path, status=404, noindex=True)
        rows = db.q(LIST_SQL.format(where="and c.category = %s"), (row["category"],))
        return _page(f"{row['category']} classes in {city} – fees and reviews | {co}",
                     f"{len(rows)} {row['category']} classes in {city}. Compare fees, batch timings and reviews.",
                     _class_list_html(rows, f"{row['category']} classes in {city}"), path)
    m = re.fullmatch(r"/classes/([a-z0-9-]+)", path)
    if m:
        c = db.one("select * from classes where slug=%s and status='live'", (m.group(1),))
        if not c:
            return _page("Class not found", "", "<h1>This class is not listed</h1>", path, status=404, noindex=True)
        courses = db.q("select title, duration, fee_min, fee_max, batch_timing from class_courses where class_id=%s order by sort_order, id", (c["id"],))
        lo = min((x["fee_min"] for x in courses if x["fee_min"] is not None), default=None)
        hi = max((x["fee_max"] for x in courses if x["fee_max"] is not None), default=None)
        rating = round(c["rating_sum"] / c["rating_count"], 1) if c["rating_count"] else None
        title = f"{c['name']} – {c['category']} in {c['area']}, {city} | Fees & reviews"
        desc = (f"{c['name']} in {c['area']}, {city}. {_fee_text(lo, hi)}. " + (c["description"] or f"{c['category']} classes."))[:290]
        ld = {"@context": "https://schema.org", "@type": "EducationalOrganization", "name": c["name"], "url": services.site_url() + path,
              "description": c["description"] or desc, "telephone": c["phone"],
              "address": {"@type": "PostalAddress", "streetAddress": c["address"] or "", "addressLocality": c["area"] + ", " + city, "addressCountry": "IN"}}
        if c["rating_count"] >= 1:
            ld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating, "reviewCount": c["rating_count"]}
        rows = "".join(f"<li>{E(x['title'])} – {_fee_text(x['fee_min'], x['fee_max'])}"
                       f"{' · ' + E(x['duration']) if x['duration'] else ''}{' · ' + E(x['batch_timing']) if x['batch_timing'] else ''}</li>" for x in courses)
        body = (f"<main><h1>{E(c['name'])}</h1><p>{E(c['category'])} · {E(c['area'])}, {E(city)} · {E(c['mode'])}"
                f"{' · Verified' if c['verified'] else ''}{' · rated ' + str(rating) + '/5 by ' + str(c['rating_count']) + ' students' if rating else ''}</p>"
                f"<p>{E(c['description'] or '')}</p><h2>Courses and fees</h2><ul>{rows}</ul></main>")
        return _page(title, desc, body, path, ld)
    static = {"/": (services.setting("tagline") or co, f"{co}: {services.setting('tagline')}"),
              "/list-your-class": (f"List your class for free in {city} | {co}", f"Add your institute to the {city} class directory. Free listing, verified by phone."),
              "/advertise": (f"Advertise your institute | {co}", f"Reach students searching for classes in {city}. Clearly labelled sponsored placements."),
              "/apply": (f"Apply for the internship | {co}", "Apply for a 30-day guided internship with a mentor, daily tasks and a certificate.")}
    if path in static:
        t, d = static[path]
        return _page(t if path != "/" else co, d, "", path)
    for slug, p in LEGAL_PATHS.items():
        if path == p:
            doc = services.latest_legal(slug)
            if doc:
                body = "<main><h1>" + E(doc["title"]) + "</h1>" + "".join(f"<p>{E(x)}</p>" for x in doc["body"].split("\n\n")) + "</main>"
                return _page(f"{doc['title']} | {co}", f"{doc['title']} for {co}.", body, path)
    return None


@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def spa(path):
    if path.startswith("api/"):
        return jsonify(error="Not found."), 404
    root = dist_dir()
    full = os.path.normpath(os.path.join(root, path))
    if path and full.startswith(os.path.normpath(root) + os.sep) and os.path.isfile(full):
        resp = send_from_directory(root, path)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable" if path.startswith("assets/") else "public, max-age=3600"
        return resp
    page = render_for("/" + path.rstrip("/") if path else "/")
    if page is not None:
        return page
    # any other client-side route (login, dashboards...): plain app shell, not for indexing
    return _page(services.company(), "", "", "/" + path, noindex=True) if _index() else (jsonify(error="The website has not been built yet."), 404)
