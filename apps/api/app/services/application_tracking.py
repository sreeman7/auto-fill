"""Stable application keys and status groups."""

import unicodedata
import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PRE_SUBMISSION = {"saved", "in_progress", "ready_for_review"}
POST_SUBMISSION = {"applied", "assessment", "interview", "offer", "rejected", "withdrawn"}
ALL_STATUSES = PRE_SUBMISSION | POST_SUBMISSION
TRACKING_PARAMETERS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}


def search_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def canonical_job_url(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Job URL contains invalid control characters")
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Job URL must be an HTTP or HTTPS address without credentials")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    if port and port != (443 if parts.scheme.lower() == "https" else 80):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/") or "/"
    query = sorted((key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
                   if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_PARAMETERS)
    canonical = urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))
    if len(canonical) > 2000:
        raise ValueError("Job URL is too long after normalization")
    return canonical


def url_fingerprint(value: str) -> str:
    return hashlib.sha256(canonical_job_url(value).encode("utf-8")).hexdigest()
