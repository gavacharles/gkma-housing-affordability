"""Historical RED listings from the Internet Archive (Wayback Machine).

The Wayback Machine holds captures of RED listing pages from 2017 onwards (none of
substance before 2017). Older pages use a different layout from today's, with a
"PROPERTY SPECIFICATIONS" block:

    Code: 10001 District: Kampala Location: Nakasero Bedrooms: 2 Levels: 2
    Furnished: Yes Type: Town House Rent : 12,920,000/=

The capture date is an upper bound on the posting date. Contact details are
removed with the shared redact(); agent names are not stored.
"""
from __future__ import annotations

import json
import logging
import re
import time
from html import unescape
from pathlib import Path

import pandas as pd
import requests

from gkma.collect.base import redact

log = logging.getLogger(__name__)
CDX = "https://web.archive.org/cdx/search/cdx"
UA = {"User-Agent": "GKMA-housing-research/0.1 (University of Johannesburg; historical listings via Wayback)"}
FIELDS = ["Code", "District", "Location", "Bedrooms", "Bathrooms", "Levels", "Furnished", "Type", "Size",
          "Plot Size", "Rent", "Price", "Title"]
COLUMNS = ["code", "capture_timestamp", "capture_year", "url"] + \
    [f.lower().replace(" ", "_") for f in FIELDS if f != "Code"] + ["tenure", "status", "description", "headline",
                                                                    "layout", "spec_text"]
WORDS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}


def cdx_index(year: int) -> pd.DataFrame:
    """Earliest successful capture of each listing page captured in `year`."""
    q = {"url": "realestatedatabase.net/FindAHouse/HouseDetails.aspx*", "from": f"{year}0101",
         "to": f"{year}1231", "output": "json", "fl": "timestamp,original", "filter": "statuscode:200",
         "limit": "200000"}
    for attempt in range(5):
        try:
            r = requests.get(CDX, params=q, headers=UA, timeout=300)
            r.raise_for_status()
            rows = r.json()[1:]
            break
        except Exception as exc:  # noqa: BLE001
            log.warning("cdx %s attempt %d: %s", year, attempt + 1, exc)
            time.sleep(30 * (attempt + 1))
    else:
        raise RuntimeError(f"CDX index for {year} failed")
    df = pd.DataFrame(rows, columns=["timestamp", "url"])
    df["code"] = df["url"].str.extract(r"HouseCode=(\d+)", flags=re.I)[0]
    df = df.dropna(subset=["code"]).sort_values("timestamp").drop_duplicates("code")
    return df.reset_index(drop=True)


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _num(v):
    v = (v or "").strip().lower()
    return WORDS.get(v, v) if v else None


def parse_quick_summary(t: str) -> dict | None:
    """2020-21 layout: 'QUICK SUMMARY Code: .. Location: .. District: .. Price: .. Category: ..
    BedRooms: five Bathrooms: one Size 25 Decimals Tenure .. Status For sale Agent .. DESCRIPTION ..'.
    The agent's name is not kept."""
    m = re.search(r"QUICK SUMMARY(.*?)DESCRIPTION(.*?)(Send this property|Tell a friend|Email this|Related|$)", t,
                  flags=re.I)
    if not m:
        return None
    q, desc = m.group(1), m.group(2)
    g = lambda pat: (re.search(pat, q, flags=re.I) or [None, None])[1]  # noqa: E731
    status = g(r"Status\s+(For\s+\w+)")
    price = g(r"Price:\s*(.*?)\s+Category:")
    cat = g(r"Category:\s*(.*?)\s+(?:BedRooms:|Bathrooms:|Size\b|Tenure\b|Status\b)")
    is_sale = bool(status and "sale" in status.lower())
    return {"location": g(r"Location:\s*(.*?)\s+District:"), "district": g(r"District:\s*(.*?)\s+Price:"),
            "type": (cat or "") + (" Sale" if is_sale else ""),
            "bedrooms": _num(g(r"BedRooms:\s*(\w+)")), "bathrooms": _num(g(r"Bathrooms:\s*(\w+)")),
            "size": g(r"Size\s+(.*?)\s+Tenure"), "tenure": g(r"Tenure\s+(.*?)\s+Status"), "status": status,
            "price": price if is_sale else None, "rent": None if is_sale else price,
            "description": redact(desc.strip()[:3000]), "layout": "quick_summary_2020",
            "spec_text": redact(q.strip()[:1500])}


def parse_archived(html: str) -> dict:
    """Parse an archived RED page: 2017 'PROPERTY SPECIFICATIONS' or 2020-21 'QUICK SUMMARY' layout."""
    t = _text(html)
    qs = parse_quick_summary(t)
    if qs is not None:
        qs["spec_text"] = re.sub(r"Agent\s+\S+", "Agent [removed]", qs["spec_text"])
        return qs
    m = re.search(r"PROPERTY SPECIFICATIONS(.*?)(PROPERTY DETAILS|$)", t, flags=re.I)
    spec = m.group(1) if m else ""
    out = {}
    keys = "|".join(re.escape(k) for k in FIELDS)
    for k, v in re.findall(rf"({keys})\s*:\s*(.*?)(?=\s(?:{keys})\s*:|$)", spec):
        out[k.lower().replace(" ", "_")] = v.strip()
    d = re.search(r"PROPERTY DETAILS(.*?)(Send this property|Tell a friend|Email this|Related Properties|$)", t,
                  flags=re.I)
    out["description"] = redact(d.group(1).strip()[:3000]) if d else None
    h = re.search(r"(\d+\s*bedroom[^.>]{0,80}?(?:for rent|for sale)[^,>]{0,60})", t, flags=re.I)
    out["headline"] = h.group(1).strip() if h else None
    out["layout"] = "specifications_2017" if spec else None
    out["spec_text"] = redact(spec.strip()[:1500]) if spec else None
    return out


def fetch(timestamp: str, url: str, session: requests.Session, tries: int = 4) -> str | None:
    raw = f"https://web.archive.org/web/{timestamp}id_/{url}"
    for attempt in range(tries):
        try:
            r = session.get(raw, headers=UA, timeout=120)
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 503):
                time.sleep(60 * (attempt + 1))
                continue
            return None
        except requests.RequestException as exc:
            log.warning("fetch %s attempt %d: %s", url, attempt + 1, exc)
            time.sleep(20 * (attempt + 1))
    return None


def collect(year: int, out_csv: Path, delay: float = 1.5, max_pages: int | None = None) -> pd.DataFrame:
    """Download and parse the archived listings of `year`; resumable (skips codes already in out_csv)."""
    idx = cdx_index(year)
    done = set(pd.read_csv(out_csv, dtype=str)["code"]) if out_csv.exists() else set()
    todo = idx[~idx["code"].isin(done)]
    if max_pages:
        todo = todo.head(max_pages)
    log.info("archive %s: %d captured listings, %d already done, %d to fetch", year, len(idx), len(done), len(todo))
    s = requests.Session()
    header = not out_csv.exists()
    for i, r in enumerate(todo.itertuples(), 1):
        html = fetch(r.timestamp, r.url, s)
        rec = {"code": r.code, "capture_timestamp": r.timestamp, "capture_year": year, "url": r.url}
        if html:
            rec.update(parse_archived(html))
        row = pd.DataFrame([rec]).reindex(columns=COLUMNS)      # fixed columns: rows stay aligned
        row.to_csv(out_csv, mode="a", header=header, index=False)
        header = False
        if i % 200 == 0:
            log.info("archive %s: %d / %d", year, i, len(todo))
        time.sleep(delay)
    return pd.read_csv(out_csv, dtype=str)
