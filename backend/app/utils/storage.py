"""Talks to Supabase Storage for CV files.

The bucket is private. Files are only ever reached through short-lived signed links
created here, and the secret key never leaves the backend.
"""
import uuid
from pathlib import PurePosixPath

import requests
from flask import current_app
from werkzeug.utils import secure_filename

MAX_RESUME_BYTES = 8 * 1024 * 1024

RESUME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# The first bytes of each real file type, so a renamed file is caught
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
}


class StorageError(Exception):
    """The storage service failed or is not configured."""


def _base():
    url = current_app.config.get("SUPABASE_URL")
    if not url:
        raise StorageError("SUPABASE_URL is not set")
    return f"{url}/storage/v1"


def _bucket():
    return current_app.config["SUPABASE_BUCKET"]


def _headers(extra=None):
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise StorageError("SUPABASE_SERVICE_KEY is not set")
    headers = {"apikey": key}
    # Legacy service_role keys are JWTs and also go in Authorization.
    # New sb_secret_ keys go in apikey only.
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    if extra:
        headers.update(extra)
    return headers


def check_resume(filename, data):
    """Returns (extension, content_type, safe_display_name) or raises ValueError."""
    safe_name = secure_filename(filename or "")
    if not safe_name:
        raise ValueError("Please choose a file.")

    ext = PurePosixPath(safe_name).suffix.lower()
    if ext not in RESUME_TYPES:
        raise ValueError("Please upload a PDF, DOC or DOCX file.")
    if not data:
        raise ValueError("That file is empty.")
    if len(data) > MAX_RESUME_BYTES:
        raise ValueError("That file is too large. The limit is 8 MB.")
    if not data.startswith(MAGIC_BYTES[ext]):
        raise ValueError(f"That file doesn't look like a real {ext[1:].upper()} file.")

    return ext, RESUME_TYPES[ext], safe_name[:200]


def upload_resume(profile_id, filename, data):
    """Stores a CV. Returns (path_in_bucket, safe_display_name)."""
    ext, content_type, safe_name = check_resume(filename, data)

    # The stored name is random. The user's file name is never used in the path.
    path = f"candidates/{int(profile_id)}/{uuid.uuid4().hex}{ext}"

    resp = requests.post(
        f"{_base()}/object/{_bucket()}/{path}",
        headers=_headers({"Content-Type": content_type, "x-upsert": "false"}),
        data=data,
        timeout=30,
    )
    if not resp.ok:
        raise StorageError(f"Upload failed (storage returned {resp.status_code})")
    return path, safe_name


def signed_url(path, expires=300):
    """A temporary link to a stored file. It stops working after `expires` seconds."""
    resp = requests.post(
        f"{_base()}/object/sign/{_bucket()}/{path}",
        headers=_headers({"Content-Type": "application/json"}),
        json={"expiresIn": int(expires)},
        timeout=20,
    )
    if not resp.ok:
        raise StorageError(f"Could not create link (storage returned {resp.status_code})")

    body = resp.json()
    link = body.get("signedURL") or body.get("signedUrl")
    if not link:
        raise StorageError("Storage did not return a link")

    root = current_app.config["SUPABASE_URL"]
    if link.startswith("/storage/v1"):
        return root + link
    return _base() + link


def delete_file(path):
    """Removes a stored file. Missing files are not an error."""
    resp = requests.delete(
        f"{_base()}/object/{_bucket()}",
        headers=_headers({"Content-Type": "application/json"}),
        json={"prefixes": [path]},
        timeout=20,
    )
    if not resp.ok:
        raise StorageError(f"Delete failed (storage returned {resp.status_code})")