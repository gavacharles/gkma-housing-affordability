"""Uganda Property Centre (ugandapropertycentre.com).

Terms of use (Dilmak Solutions Ventures Ltd): "You agree not to use any
automated software to view the Services without consent" and "not to attempt
to copy our data ... without our consent." Runs only with written consent.

Each detail page embeds schema.org RealEstateListing JSON-LD (price,
currency, datePosted) and the URL encodes deal/type/region/district/area:
/for-rent/houses/central-region/wakiso/entebbe-municipality/11182-3-bedroom-house
UPC also publishes quarterly market reports and area price averages, which
are useful as an external validation series (cite them, don't copy them).
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from gkma.collect.base import PoliteSession, check_permission, now_iso, to_frame

log = logging.getLogger(__name__)


def parse_url(url: str) -> dict:
    parts = [x for x in urlparse(url).path.split("/") if x]
    out = {"deal": None, "ptype": None, "region": None, "district": None, "area": None, "id": None}
    if not parts:
        return out
    out["deal"] = "rent" if parts[0] == "for-rent" else "sale" if parts[0] == "for-sale" else None
    slug = parts[-1]
    m = re.match(r"(\d+)-", slug)
    out["id"] = m.group(1) if m else None
    geo = [x for x in parts[1:-1] if x != "showtype"]
    regions = [i for i, x in enumerate(geo) if x.endswith("-region")]
    if regions:
        r = regions[0]
        out["ptype"] = "/".join(geo[:r])
        out["region"] = geo[r]
        out["district"] = geo[r + 1] if len(geo) > r + 1 else None
        out["area"] = geo[r + 2] if len(geo) > r + 2 else None
    return out


def parse_detail(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    ld = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        if obj.get("@type") == "RealEstateListing":
            ld = obj
    offer = ld.get("offers") or {}
    u = parse_url(url)
    title_tag = soup.title.string if soup.title else ""
    beds = re.search(r"(\d+)\s*Beds?", title_tag or "")
    baths = re.search(r"(\d+)\s*Baths?", title_tag or "")
    body = soup.get_text(" ", strip=True)
    size = re.search(r"(\d[\d,.]*\s*(?:decimals?|acres?|sq\.?\s*m|sqm|m²|sq\.?\s*ft|ft))", body, re.I)
    tenure = re.search(r"\b(freehold|leasehold|mailo|kibanja|customary)\b", body, re.I)
    return {
        "source": "upc",
        "source_id": u["id"],
        "url": url,
        "scraped_at": now_iso(),
        "listing_date": (ld.get("datePosted") or "")[:10] or None,
        "listing_type": u["deal"],
        "property_type": u["ptype"],
        "title": ld.get("name"),
        "description": ld.get("description"),
        "price_raw": offer.get("price"),
        "currency_raw": offer.get("priceCurrency"),
        "price_period": "per month" if u["deal"] == "rent" else None,
        "location_raw": (u["area"] or u["district"] or "").replace("-", " ").title() or None,
        "district_raw": (u["district"] or "").replace("-", " ").title() or None,
        "region_raw": u["region"],
        "bedrooms_raw": beds.group(1) if beds else None,
        "bathrooms_raw": baths.group(1) if baths else None,
        "size_raw": size.group(1) if size else None,
        "size_unit_raw": None,
        "tenure_raw": tenure.group(1) if tenure else None,
        "furnishing_raw": None,
        "listed_by": None,
        "agent_key": None,
    }


def collect(limit: int | None = None, session: PoliteSession | None = None):
    pcfg = check_permission("upc")
    session = session or PoliteSession()
    urls = session.get(pcfg["sitemap"], use_cache=False).split()
    urls = [u for u in urls if "/for-rent/" in u or "/for-sale/" in u]
    # GKMA pre-filter on URL; the spatial filter later is authoritative.
    keep = ("kampala", "wakiso", "mukono", "mpigi", "buikwe", "luweero", "entebbe")
    urls = [u for u in urls if any(k in u for k in keep)][:limit]
    records = []
    for u in urls:
        try:
            records.append(parse_detail(session.get(u), u))
        except Exception as exc:
            log.warning("upc %s: %s", u, exc)
    return to_frame(records)
