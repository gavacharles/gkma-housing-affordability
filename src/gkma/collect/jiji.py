"""Jiji.ug collector (public listing JSON API).

Checked 2026-09-22: robots.txt does not disallow /api_web/; terms of use
(jiji.ug/rules.html s.7.14) prohibit only software that interferes with the
platform. We therefore collect at a low rate with a contact User-Agent.

Known quirks (document in the paper's data section):
* region_name is often wrong at division level (Kisaasi/Ntinda/Kyanja are
  labelled "Central Division" but sit in Nakawa). Neighbourhood is parsed
  from the title instead and resolved through the gazetteer.
* "Property size" (sqm) is agent-entered and mixes floor and plot area.
* The same unit is frequently re-posted; see clean.dedup.
"""
from __future__ import annotations

import logging
import re

from gkma.collect.base import PoliteSession, agent_key, check_permission, now_iso, to_frame

log = logging.getLogger(__name__)

API = "https://jiji.ug/api_web/v1/listing?slug={slug}&page={page}&sort=new"
BASE = "https://jiji.ug"

# "3bdrm House in Standalone Kisaasi, Central Division for rent"
TITLE_RE = re.compile(
    r"^(?P<prefix>.*?)\s+in\s+(?P<place>.+?)(?:,\s*(?P<admin>[^,]+?))?\s+for\s+(?P<deal>rent|sale)\s*$",
    re.I,
)
SUBTYPE_WORDS = r"(?:standalone|stand alone|self[- ]contained|block of flats|estate|gated)"


def parse_title(title: str) -> dict:
    m = TITLE_RE.match(title or "")
    if not m:
        return {}
    place = re.sub(rf"^{SUBTYPE_WORDS}\s+", "", m["place"].strip(), flags=re.I)
    prop = re.sub(r"^(furnished|unfurnished|\d+\s*bdrm)\s*", "", m["prefix"], flags=re.I)
    prop = re.sub(r"\d+\s*bdrm\s*", "", prop, flags=re.I).strip()
    return {"place": place, "admin": m["admin"], "deal": m["deal"].lower(), "ptype": prop or None}


def _attr(ad: dict, name: str):
    for a in ad.get("attrs") or []:
        if a.get("name", "").lower() == name.lower():
            return a.get("value"), a.get("unit")
    return None, None


def parse_advert(ad: dict, category: str) -> dict:
    t = parse_title(ad.get("title", ""))
    price = ad.get("price_obj") or {}
    size, size_unit = _attr(ad, "Property size")
    deal = t.get("deal") or ("rent" if "rent" in category else "sale")
    return {
        "source": "jiji",
        "source_id": str(ad.get("id")),
        "url": BASE + (ad.get("url") or "").split("?")[0],
        "scraped_at": now_iso(),
        "listing_date": None,  # list API gives no post date; first_seen is derived from snapshots
        "listing_type": deal,
        "property_type": t.get("ptype") or category,
        "title": ad.get("title"),
        "description": ad.get("details") or ad.get("short_description"),
        "price_raw": price.get("value"),
        "currency_raw": "UGX" if "USh" in (price.get("view") or "USh") else price.get("view"),
        "price_period": price.get("period"),
        "location_raw": t.get("place"),
        "district_raw": ad.get("region_parent_name"),
        "region_raw": ad.get("region_name"),
        "bedrooms_raw": _attr(ad, "Bedrooms")[0],
        "bathrooms_raw": _attr(ad, "Bathrooms")[0],
        "size_raw": size,
        "size_unit_raw": size_unit,
        "tenure_raw": None,
        "furnishing_raw": _attr(ad, "Furnishing")[0],
        "listed_by": _attr(ad, "Listing by")[0],
        "agent_key": agent_key("jiji", ad.get("user_id")),
    }


def collect(max_pages: int | None = None, session: PoliteSession | None = None):
    pcfg = check_permission("jiji")
    session = session or PoliteSession()
    from gkma.config import load_config
    max_pages = max_pages or load_config()["collection"]["max_pages_per_run"]
    records = []
    for slug in pcfg["categories"]:
        url, page = API.format(slug=slug, page=1), 1
        while url and page <= max_pages:
            # Listing pages change constantly: never serve them from cache.
            data = session.get_json(url, use_cache=False)
            ads = data.get("adverts_list", {}).get("adverts", [])
            if not ads:
                break
            records += [parse_advert(a, slug) for a in ads]
            log.info("jiji %s page %d: %d ads", slug, page, len(ads))
            url, page = data.get("next_url"), page + 1
    return to_frame(records)
