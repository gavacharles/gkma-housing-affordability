"""Shared collection machinery: permission gate, polite HTTP, raw schema.

Every portal collector returns records in RAW_COLUMNS. Values stay as the
portal shows them ("Ugx 160,000,000/=", "12 Decimals", "Private Mailo");
all interpretation happens in gkma.clean so the raw layer is auditable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from gkma.config import load_config, p, user_agent

log = logging.getLogger(__name__)

RAW_COLUMNS = [
    "source", "source_id", "url", "scraped_at", "listing_date",
    "listing_date_source",  # portal | estimated_from_code | None
    "listing_type",        # rent | sale
    "property_type", "title", "description",
    "price_raw", "currency_raw", "price_period",
    "location_raw", "district_raw", "region_raw",
    "bedrooms_raw", "bathrooms_raw", "size_raw", "size_unit_raw",
    "tenure_raw", "furnishing_raw", "listed_by",
    "agent_key",           # SHA-256 of agent phone/name: dedup without storing personal data
    "lat", "lon",
]

# terms_permit: terms/robots checked and do not prohibit collection
# written_consent: the portal agreed (record the reference)
# researcher_authorised: the researcher has decided to proceed while consent is
#   being sought; recorded with a dated note for the ethics file
ALLOWED_PERMISSIONS = {"terms_permit", "written_consent", "researcher_authorised"}


class PermissionNotGranted(RuntimeError):
    pass


def check_permission(portal: str) -> dict:
    """Stop unless config.yaml records a permission basis for this portal."""
    pcfg = load_config()["collection"]["portals"][portal]
    status = pcfg.get("permission", "not_granted")
    if status not in ALLOWED_PERMISSIONS:
        raise PermissionNotGranted(
            f"{portal}: permission is '{status}'. The portal's terms restrict "
            "automated copying. Request a research extract (docs/letter_template.md), "
            "then set permission: written_consent and consent_reference in config.yaml. "
            "Until then use the manual-entry route (scripts/01_collect.py --manual)."
        )
    if status in ("written_consent", "researcher_authorised") and not pcfg.get("consent_reference"):
        raise PermissionNotGranted(f"{portal}: '{status}' needs a consent_reference note in config.yaml.")
    return pcfg


def agent_key(*parts: str | None) -> str | None:
    text = "|".join(str(x).strip().lower() for x in parts if x)
    return hashlib.sha256(text.encode()).hexdigest()[:16] if text else None


PHONE_RE = re.compile(r"(?:\+?256|\b0)[\s-]?[37]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text):
    """Remove phone numbers and email addresses from free text."""
    if not isinstance(text, str):
        return text
    return EMAIL_RE.sub("[email]", PHONE_RE.sub("[phone]", text))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PoliteSession:
    """requests wrapper: robots.txt check, per-host delay, on-disk cache."""

    def __init__(self) -> None:
        ccfg = load_config()["collection"]
        self.delay = float(ccfg["min_delay_seconds"])
        self.cache_dir = p(ccfg["cache_dir"])
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent()
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
            # Fetch with our own User-Agent: some hosts 403 the urllib default,
            # which robotparser would misread as "disallow everything".
            # A network failure fetching robots.txt is a transient error (the
            # caller pauses and retries), not a ban: nothing is cached, so the
            # file is fetched again on the next attempt.
            r = self.s.get(host + "/robots.txt", timeout=30)
            if r.status_code in (401, 403):
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True       # no robots.txt: standard says allowed
            else:
                rp.parse(r.text.splitlines())
            self._robots[host] = rp
        return self._robots[host].can_fetch(self.s.headers["User-Agent"], url)

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".cache")

    def get(self, url: str, use_cache: bool = True) -> str:
        cache = self._cache_path(url)
        if use_cache and cache.exists():
            return cache.read_text(encoding="utf-8")
        if not self._allowed(url):
            raise PermissionNotGranted(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        wait = self.delay - (time.monotonic() - self._last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        resp = self.s.get(url, timeout=40)
        self._last[host] = time.monotonic()
        resp.raise_for_status()
        cache.write_text(resp.text, encoding="utf-8")
        return resp.text

    def get_json(self, url: str, use_cache: bool = True) -> dict:
        return json.loads(self.get(url, use_cache=use_cache))


def to_frame(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    for col in RAW_COLUMNS:
        if col not in df:
            df[col] = None
    for col in ("title", "description"):
        df[col] = df[col].map(redact)
    return df[RAW_COLUMNS]


def save_raw(df: pd.DataFrame, source: str) -> Path:
    """Append-only snapshots: one file per source per collection day."""
    out = p("data/raw") / source
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{source}_{datetime.now():%Y%m%d}.csv"
    if path.exists():
        df = pd.concat([pd.read_csv(path, dtype=str), df.astype(str)], ignore_index=True)
        df = df.drop_duplicates(subset=["source", "source_id"], keep="last")
    df.to_csv(path, index=False)
    log.info("saved %d rows -> %s", len(df), path)
    return path
