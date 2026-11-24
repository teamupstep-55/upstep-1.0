"""Resume storage. Supabase Storage (private bucket) when configured, otherwise a local folder for development."""
import os
import uuid

import requests
from flask import current_app

ALLOWED = {".pdf": b"%PDF", ".docx": b"PK", ".doc": b"\xd0\xcf\x11\xe0"}
MAX_BYTES = 3 * 1024 * 1024


def validate_resume(file_storage):
    """Returns (ext, data) or raises ValueError with a user-friendly message."""
    name = (file_storage.filename or "").lower()
    ext = os.path.splitext(name)[1]
    if ext not in ALLOWED:
        raise ValueError("Resume must be a PDF, DOC or DOCX file.")
    data = file_storage.read(MAX_BYTES + 1)
    if not data:
        raise ValueError("The resume file is empty.")
    if len(data) > MAX_BYTES:
        raise ValueError("Resume must be smaller than 3 MB.")
    if not data.startswith(ALLOWED[ext]):
        raise ValueError("That file does not look like a real " + ext[1:].upper() + ".")
    return ext, data


def _sb():
    c = current_app.config
    if c.get("SUPABASE_URL") and c.get("SUPABASE_SERVICE_KEY"):
        base = c["SUPABASE_URL"].rstrip("/") + "/storage/v1/object"
        return base, {"Authorization": f"Bearer {c['SUPABASE_SERVICE_KEY']}", "apikey": c["SUPABASE_SERVICE_KEY"]}, c["SUPABASE_BUCKET"]
    return None


def save_resume(ext, data):
    key = f"{uuid.uuid4().hex}{ext}"
    sb = _sb()
    if sb:
        base, headers, bucket = sb
        r = requests.post(f"{base}/{bucket}/{key}", data=data, timeout=30,
                          headers={**headers, "Content-Type": "application/octet-stream"})
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase Storage upload failed ({r.status_code}): {r.text[:200]}")
    else:
        folder = current_app.config["LOCAL_UPLOAD_DIR"]
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, key), "wb") as fh:
            fh.write(data)
    return key


def read_resume(key):
    sb = _sb()
    if sb:
        base, headers, bucket = sb
        r = requests.get(f"{base}/{bucket}/{key}", headers=headers, timeout=30)
        return r.content if r.status_code == 200 else None
    path = os.path.join(current_app.config["LOCAL_UPLOAD_DIR"], os.path.basename(key))
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return fh.read()
    return None
