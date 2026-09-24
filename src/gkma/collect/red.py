"""Real Estate Database (realestatedatabase.net) — also serves lamudi.co.ug.

Both domains run the same ASP.NET backend (identical robots.txt, shared
HouseCode ids), so treat them as ONE source and never collect both.

RED's terms (Zillion Technologies Ltd) prohibit copying or publishing its
content without consent, and its XML/CSV feed sits under /FindAHouseOld/,
which robots.txt disallows (never used here). The collector runs when
config.yaml records a permission basis: "written_consent", or
"researcher_authorised" (the researcher proceeds while consent is sought).
Two routes:

1. load_extract(): read a CSV/XML extract from RED (preferred once agreed).
2. collect(): newest-first crawl of public detail pages listed in the sitemap
   (robots.txt allows /FindAHouse/), low rate, phone numbers and emails
   redacted, agent names hashed.

Detail pages carry a structured QUICK SUMMARY block:
Code / Location / District / Price / Category / BedRooms / Bathrooms /
Size / Tenure / Status / Agent — the only portal with tenure as a field.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote_plus

import pandas as pd
from bs4 import BeautifulSoup

from gkma.collect.base import PoliteSession, agent_key, check_permission, now_iso, to_frame
from gkma.config import load_config, p

log = logging.getLogger(__name__)

SUMMARY_KEYS = ["Code", "Location", "District", "Price", "Category", "BedRooms",
                "Bathrooms", "Size", "Tenure", "Status", "Agent", "Inspection fee"]
WORD_NUM = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def _text_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]


def parse_detail(html: str, url: str = "") -> dict:
    lines = _text_lines(html)
    try:
        start = lines.index("QUICK SUMMARY")
    except ValueError:
        return {}
    block = lines[start: start + 60]
    fields = {}
    for i, ln in enumerate(block[:-1]):
        key = ln.rstrip(":").strip()
        if key in SUMMARY_KEYS and key not in fields:
            fields[key] = block[i + 1]
    # Description: text between "DESCRIPTION" and the standard disclaimer
    desc = ""
    if "DESCRIPTION" in lines:
        j = lines.index("DESCRIPTION")
        chunk = []
        for ln in lines[j + 1: j + 80]:
            if ln.startswith("●") or ln.upper().startswith("REVIEWS"):
                break
            chunk.append(ln)
        desc = " ".join(chunk)
    # Heading: "🏠 4 bedroom ... in Sonde Mukono Uganda, code: 233811, 🕗 22/09/2026".
    # The date there is the day the page is served, NOT the post date (an old
    # listing shows today's date too), so it is ignored; see code_date_model().
    date, title = None, None
    for ln in lines[:400]:
        if re.search(r"code:\s*\d+", ln):
            title = ln.split(", code:")[0].lstrip("🏠 ").strip()
            break
    price = fields.get("Price", "")
    status = fields.get("Status", "").lower()
    return {
        "source": "red",
        "source_id": fields.get("Code"),
        "url": url,
        "scraped_at": now_iso(),
        "listing_date": date,
        "listing_type": "rent" if "rent" in status else "sale" if "sale" in status else None,
        "property_type": fields.get("Category"),
        "title": title,
        "description": desc,
        "price_raw": price,
        "currency_raw": "USD" if re.search(r"\$|usd", price, re.I) else "UGX",
        "price_period": "per month" if re.search(r"month|/m\b|pm\b", price, re.I) or "rent" in status else None,
        "location_raw": fields.get("Location"),
        "district_raw": fields.get("District"),
        "region_raw": None,
        "bedrooms_raw": WORD_NUM.get(fields.get("BedRooms", "").lower(), fields.get("BedRooms")),
        "bathrooms_raw": WORD_NUM.get(fields.get("Bathrooms", "").lower(), fields.get("Bathrooms")),
        "size_raw": fields.get("Size"),
        "size_unit_raw": None,
        "tenure_raw": fields.get("Tenure"),
        "furnishing_raw": None,
        "listed_by": "Agent",
        "agent_key": agent_key("red", fields.get("Agent")),
    }


def sitemap_urls(session: PoliteSession, sitemap: str) -> list[str]:
    xml = session.get(sitemap, use_cache=False)
    urls = re.findall(r"<loc>(.*?)</loc>", xml)
    return [u.replace("&amp;", "&").split("#")[0] for u in urls if "HouseDetails" in u]


def sitemap_frame(urls: list[str]) -> pd.DataFrame:
    """code, url, title and the place named in the title ("... for sale in Sonde")."""
    rows = []
    for u in urls:
        m = re.search(r"HouseCode=(\d+)", u)
        if not m:
            continue
        t = re.search(r"Title=([^&#]*)", u)
        title = unquote_plus(t.group(1)) if t else ""
        pl = re.search(r"\b(?:sale|rent)\s+in\s+(.+)$", title, re.I)
        rows.append({"code": int(m.group(1)), "url": u, "title": title,
                     "place": pl.group(1).strip() if pl else None})
    return pd.DataFrame(rows).drop_duplicates("code").sort_values("code", ascending=False)


def outside_gkma_names() -> set[str]:
    """District and sub-county names outside the study area (UBOS boundaries)."""
    import geopandas as gpd
    raw = p("data/external/boundaries/ubos_2018/UGANDA BOUNDARIES SHAPEFILES AS OF 17 08 2018/"
            "PARISHES_2016_UTM_36N.shp")
    if not raw.exists():
        return set()
    par = gpd.read_file(raw, ignore_geometry=True)
    g = load_config()["geography"]
    study = {d.upper() for d in g["gkma_districts"] + g["gkma_fringe_districts"]}
    inside = set(par[par["DName2016"].isin(study)][["SName2016", "PName2016"]].stack().str.lower())
    inside |= {d.lower() for d in study}
    out = set(par[~par["DName2016"].isin(study)][["DName2016", "SName2016"]].stack().str.lower())
    return {x for x in out - inside if len(x) > 3}


def code_date_model():
    """Estimated post date from RED's sequential HouseCode.

    RED pages show no post date (the date beside the code is the day the page
    is served). Anchors: the earliest Internet Archive capture of each listing
    URL (data/interim/red_wayback_first_capture.csv), summarised as the 5th
    percentile per 2,000-code bin (a capture can only come after posting), made
    monotone, plus the latest live code observed today. Returns a function
    code -> Timestamp. Accuracy is roughly +/- one month: use it for windowing
    and quarter fixed effects, not for month-level timing.
    """
    import numpy as np
    pcfg = load_config()["collection"]["portals"]["red"]
    wb = pd.read_csv(p("data/interim/red_wayback_first_capture.csv"), parse_dates=["first"])
    wb["bin"] = (wb["code"] // 2000) * 2000 + 1000
    env = wb.groupby("bin")["first"].quantile(0.05)
    env = env[wb.groupby("bin").size() >= 10]
    x = env.index.to_numpy(dtype=float)
    y = np.maximum.accumulate(env.to_numpy().astype("datetime64[D]").astype(float))
    x = np.append(x, float(pcfg["latest_code"]))
    y = np.append(y, float(pd.Timestamp(pcfg["latest_code_date"]).to_datetime64().astype("datetime64[D]").astype(float)))

    def estimate(code) -> pd.Timestamp:
        return pd.Timestamp(np.datetime64(int(round(np.interp(float(code), x, y))), "D"))
    return estimate


def collect(limit: int | None = None, session: PoliteSession | None = None,
            out_path: str | Path = "data/raw/red/red_crawl.csv"):
    """Crawl RED detail pages by HouseCode, newest first, with resume.

    RED's sitemap is stale (it stops at code 233811, about October 2025), so
    the crawl walks codes from `latest_code` down to `min_code` (config.yaml).
    Codes that return no listing (deleted, or never used) are recorded as done.
    Each listing is appended to `out_path` immediately; an interrupted run
    resumes where it stopped. No cookies are kept between requests (a growing
    ASP.NET session cookie made RED answer 400 after ~3 hours). After repeated
    errors the crawl pauses and retries with a fresh connection.
    """
    import time

    import requests

    pcfg = check_permission("red")
    session = session or PoliteSession()
    out_path = p(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done_path = out_path.with_suffix(".done.txt")      # codes attempted (incl. empty codes)
    done = set(done_path.read_text().split()) if done_path.exists() else set()
    codes = [c for c in range(int(pcfg["latest_code"]), int(pcfg["min_code"]) - 1, -1) if str(c) not in done]
    if limit:
        codes = codes[:limit]
    est = code_date_model()
    log.info("red: codes %s..%s, %d already done, %d to fetch (est. %s to %s)",
             pcfg["min_code"], pcfg["latest_code"], len(done), len(codes),
             est(pcfg["min_code"]).date(), est(pcfg["latest_code"]).date())

    base = "https://www.realestatedatabase.net/FindAHouse/HouseDetails.aspx?HouseCode={}"
    n_new, errors = 0, 0
    with open(done_path, "a") as done_fh:
        for i, code in enumerate(codes):
            url = base.format(code)
            session.s.cookies.clear()
            try:
                html = session.get(url, use_cache=False)
                errors = 0
            except (requests.RequestException, OSError) as exc:
                errors += 1
                log.warning("red %s: %s", code, exc)
                if errors >= 5:
                    log.warning("red: %d errors in a row - pausing 10 min, fresh connection", errors)
                    time.sleep(600)
                    session = PoliteSession()
                if errors >= 25:
                    log.error("red: persistent errors - stopping; re-run to resume")
                    break
                continue
            rec = parse_detail(html, url=url)
            done_fh.write(f"{code}\n")
            done_fh.flush()
            if not rec:
                continue
            rec["listing_date"] = est(code).date().isoformat()
            rec["listing_date_source"] = "estimated_from_code"
            row_df = to_frame([rec])
            if out_path.exists():   # always append in the file's own column order
                cols = pd.read_csv(out_path, nrows=0).columns
                row_df = row_df.reindex(columns=cols)
            row_df.to_csv(out_path, mode="a", header=not out_path.exists(), index=False)
            n_new += 1
            if n_new % 50 == 0:
                log.info("red %d/%d codes, %d listings (code %s, est. %s, %s)",
                         i + 1, len(codes), n_new, code, rec["listing_date"], rec.get("district_raw"))
    log.info("red: %d listings written to %s", n_new, out_path)
    return out_path


# Column names RED is likely to use in a member CSV extract -> RAW_COLUMNS.
# Adjust once the real extract arrives.
EXTRACT_MAP = {
    "HouseCode": "source_id", "Title": "title", "Description": "description",
    "Price": "price_raw", "Currency": "currency_raw", "Location": "location_raw",
    "District": "district_raw", "Category": "property_type", "Bedrooms": "bedrooms_raw",
    "Bathrooms": "bathrooms_raw", "Size": "size_raw", "Tenure": "tenure_raw",
    "Status": "listing_type", "DateUploaded": "listing_date",
    "Latitude": "lat", "Longitude": "lon",
}


def load_extract(path: str | Path):
    check_permission("red")
    path = Path(path)
    df = pd.read_xml(path) if path.suffix == ".xml" else pd.read_csv(path, dtype=str)
    df = df.rename(columns={k: v for k, v in EXTRACT_MAP.items() if k in df})
    df["source"] = "red"
    df["scraped_at"] = now_iso()
    if "listing_type" in df:
        df["listing_type"] = df["listing_type"].str.lower().str.extract(r"(rent|sale)")[0]
    return to_frame(df.to_dict("records"))
