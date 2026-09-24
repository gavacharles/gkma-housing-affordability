"""Resolve free-text locations to GKMA neighbourhoods and coordinates.

Order of evidence, recorded in `geo_method` so precision can be reported:
  1. portal coordinates (lat/lon present)            -> "portal_coords"
  2. exact name/alias match in the lookup table      -> "lookup_exact"
  3. a lookup name contained in the text             -> "lookup_contains"
  4. fuzzy match (rapidfuzz WRatio >= 90)            -> "lookup_fuzzy"
     (a match to a sub-county row is relabelled       -> "subcounty_centroid")
  4b. portal admin field outside Kampala             -> "admin_region" (coarse)
  4c. name of an official UBOS parish                -> "ubos_parish_centroid"
  5. OpenStreetMap Nominatim (cached, 1 req/s)       -> "nominatim"   (optional)
Everything else stays unresolved and is excluded from spatial models.
"""
from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache

import numpy as np
import pandas as pd
import requests
from rapidfuzz import fuzz, process

from gkma.config import load_config, p, user_agent

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
# GKMA bounding box (lon_min, lat_min, lon_max, lat_max), generous
GKMA_BBOX = (32.25, -0.05, 33.05, 0.65)
NOISE = re.compile(r"\b(road|rd|estate|hill|area|town|village|zone|near|along|off|opp\.?|behind|kampala|wakiso|mukono|uganda|division|municipality|central|trading centre|stage)\b", re.I)


def _norm(s: str) -> str:
    s = str(s).lower().replace("-", " ")
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def lg_key(s: str) -> str:
    """Spelling-tolerant key for Luganda place names: l/r are one phoneme
    (Kulambilo = Kulambiro, Namusela = Namusera) and doubled letters vary
    (Nakweelo / Nakwelo, Nakassajja / Nakasajja). 'w' after b is dropped
    (Bwelenga ~ Bulenga is left to the fuzzy step)."""
    k = _norm(s).replace("l", "r")
    return re.sub(r"([a-z])\1+", r"\1", k)


@lru_cache(maxsize=1)
def load_lookup() -> tuple[pd.DataFrame, dict]:
    lk = pd.read_csv(p(load_config()["geography"]["neighbourhood_lookup"]))
    lk["place_id"] = lk["name"].map(_norm).str.replace(" ", "_")
    names = {}
    for _, r in lk.iterrows():
        for n in [r["name"]] + (str(r["aliases"]).split(";") if isinstance(r["aliases"], str) else []):
            if n.strip():
                names[_norm(n)] = r["place_id"]
                names.setdefault(lg_key(n), r["place_id"])
    return lk.set_index("place_id"), names


def match_place(text) -> tuple[str | None, str | None]:
    if text is None or text != text or not str(text).strip():
        return None, None
    lk, names = load_lookup()
    t = _norm(text)
    if t in names:
        return names[t], "lookup_exact"
    if lg_key(text) in names:
        return names[lg_key(text)], "lookup_exact"
    # Longest lookup name appearing as a whole word in the text
    hits = [n for n in names if re.search(rf"\b{re.escape(n)}\b", t)]
    if hits:
        return names[max(hits, key=len)], "lookup_contains"
    core = _norm(NOISE.sub(" ", t))
    if len(core) >= 4:
        best = process.extractOne(core, list(names), scorer=fuzz.WRatio)
        if best and best[1] >= 90:
            return names[best[0]], "lookup_fuzzy"
    return None, None


class Nominatim:
    """Cached OSM geocoder. Respects the 1 request/second usage policy."""

    def __init__(self) -> None:
        ccfg = load_config()["collection"]
        self.cache_path = p("data/interim/nominatim_cache.json")
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self.ua = user_agent()
        self._last = 0.0

    def geocode(self, query: str, district: str | None = None):
        district = district if isinstance(district, str) else None   # NaN -> None
        key = f"{query}|{district or ''}"
        if key in self.cache:
            return self.cache[key]
        time.sleep(max(0.0, 1.1 - (time.monotonic() - self._last)))
        q = ", ".join(x for x in [query, district, "Uganda"] if isinstance(x, str) and x)
        lon0, lat0, lon1, lat1 = GKMA_BBOX
        res = None
        for attempt in range(3):   # the public server is sometimes slow; never fail the pipeline
            try:
                r = requests.get(NOMINATIM, params={
                    "q": q, "format": "jsonv2", "limit": 1, "countrycodes": "ug",
                    "viewbox": f"{lon0},{lat1},{lon1},{lat0}", "bounded": 1,
                }, headers={"User-Agent": self.ua}, timeout=30)
                res = r.json()
                break
            except (requests.RequestException, ValueError) as exc:
                log.warning("nominatim %r attempt %d: %s", q, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
        self._last = time.monotonic()
        if res is None:
            return None            # not cached: retried on the next run
        out = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"]),
               "osm_name": res[0].get("display_name")} if res else None
        self.cache[key] = out
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=1))
        return out


def resolve_locations(df: pd.DataFrame, use_nominatim: bool = False) -> pd.DataFrame:
    out = df.copy()
    lk, _ = load_lookup()
    lat = pd.to_numeric(out["lat"], errors="coerce")
    lon = pd.to_numeric(out["lon"], errors="coerce")
    method = np.where(lat.notna() & lon.notna(), "portal_coords", None).astype(object)
    place_ids = []
    rows = zip(out["location_raw"], out["title"], out["region_raw"], out["district_raw"])
    for i, (loc, title, region, district) in enumerate(rows):
        pid, m = match_place(loc)
        if pid is None:  # fall back to the title ("... in Kisaasi, ...")
            pid, m = match_place(title)
        if pid is not None and lk.at[pid, "level"] == "subcounty":
            m = "subcounty_centroid"
        if pid is None and district != "Kampala":
            # Portal admin field (sub-county) as a coarse fallback. Not used in
            # Kampala, where Jiji's division labels are unreliable.
            pid, _ = match_place(region)
            m = "admin_region" if pid else None
        place_ids.append(pid)
        if method[i] is None and pid is not None:
            method[i] = m
    out["place_id"] = place_ids
    has = out["place_id"].notna()
    out.loc[has & lat.isna(), "lat"] = out.loc[has & lat.isna(), "place_id"].map(lk["lat"])
    out.loc[has & lon.isna(), "lon"] = out.loc[has & lon.isna(), "place_id"].map(lk["lon"])
    out["place_name"] = out["place_id"].map(lk["name"])
    out["place_district"] = out["place_id"].map(lk["district"])

    # Fallback: the place is an official UBOS parish name -> parish centroid
    idx = parish_index()
    if idx is not None:
        todo = out["lat"].isna()
        for i in out.index[todo]:
            hit = match_parish(out.at[i, "location_raw"], out.at[i, "district_raw"], idx)
            if hit is None:
                continue
            out.at[i, "lat"], out.at[i, "lon"] = hit["lat"], hit["lon"]
            out.at[i, "place_name"], out.at[i, "place_district"] = hit["parish"], hit["district"]
            method[out.index.get_loc(i)] = "ubos_parish_centroid"

    if use_nominatim:
        geo = Nominatim()
        todo = out["lat"].isna() & out["location_raw"].notna()
        for i in out.index[todo]:
            hit = geo.geocode(str(out.at[i, "location_raw"]), out.at[i, "district_raw"])
            if hit:
                out.at[i, "lat"], out.at[i, "lon"] = hit["lat"], hit["lon"]
                method[out.index.get_loc(i)] = "nominatim"
    out["geo_method"] = method
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out


def verify_lookup_against_osm(threshold_km: float = 2.0) -> pd.DataFrame:
    """Geocode each lookup row via Nominatim; flag rows > threshold_km apart."""
    lk, _ = load_lookup()
    geo = Nominatim()
    rows = []
    for pid, r in lk.iterrows():
        hit = geo.geocode(r["name"], r["district"])
        d = np.nan
        if hit:
            dlat = np.radians(hit["lat"] - r["lat"])
            dlon = np.radians(hit["lon"] - r["lon"]) * np.cos(np.radians(r["lat"]))
            d = 6371 * np.hypot(dlat, dlon)
        rows.append({"name": r["name"], "district": r["district"], "lat": r["lat"], "lon": r["lon"],
                     "osm_lat": hit and hit["lat"], "osm_lon": hit and hit["lon"],
                     "osm_name": hit and hit["osm_name"], "distance_km": d,
                     "check": "OSM not found" if not hit else ("CHECK" if d > threshold_km else "ok")})
    return pd.DataFrame(rows)


def check_against_parishes() -> pd.DataFrame:
    """For lookup names that are also UBOS parish names, test whether the
    lookup point falls inside that parish. Returns one row per mismatch."""
    import geopandas as gpd
    g = load_config()["geography"]
    par = gpd.read_file(p(g["parishes"]))
    pcol = g["parish_name_col"]
    lk, _ = load_lookup()
    lk = lk[lk.get("level", "neighbourhood") != "subcounty"].reset_index()
    pts = gpd.GeoDataFrame(lk, geometry=gpd.points_from_xy(lk["lon"], lk["lat"]), crs="EPSG:4326").to_crs(par.crs)
    j = gpd.sjoin(pts, par[[pcol, "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]

    def key(s):  # "Kamwokya II" / "Seeta Ward" -> "kamwokya" / "seeta"
        s = re.sub(r"\s+(i{1,3}|iv|v|ward|central|a|b)$", "", str(s).lower().strip())
        return re.sub(r"[^a-z]", "", s)
    par["_k"] = par[pcol].map(key)
    rows = []
    for i, r in j.iterrows():
        k = key(r["name"])
        same = par[par["_k"] == k]
        if same.empty or (isinstance(r[pcol], str) and key(r[pcol]) == k):
            continue
        d = pts.geometry[i].distance(same.geometry.unary_union) / 1000
        rows.append({"name": r["name"], "falls_in_parish": r[pcol],
                     "namesake_parish": ", ".join(same[pcol].unique()), "km_to_namesake": round(d, 2)})
    return pd.DataFrame(rows)


def _parish_key(s) -> str:
    """'Kamwokya II' / 'Seeta Ward' / 'Kansanga-Muyenga' -> 'kamwokya' / 'seeta' / 'kansangamuyenga'."""
    s = re.sub(r"\s+(i{1,3}|iv|v|vi|ward|central|a|b)$", "", str(s).lower().strip())
    return lg_key(s).replace(" ", "")


@lru_cache(maxsize=1)
def parish_index():
    """name key -> list of (parish, district, lat, lon) for study-area parishes."""
    import geopandas as gpd
    g = load_config()["geography"]
    path = p(g["parishes"])
    if not path.exists():
        return None
    par = gpd.read_file(path)
    pts = par.geometry.representative_point().to_crs("EPSG:4326")
    idx: dict[str, list[dict]] = {}
    for (_, r), pt in zip(par.iterrows(), pts):
        idx.setdefault(_parish_key(r[g["parish_name_col"]]), []).append(
            {"parish": r[g["parish_name_col"]], "district": r[g["district_name_col"]],
             "lat": pt.y, "lon": pt.x})
    return idx


def match_parish(text, district, idx) -> dict | None:
    """Exact parish-name match (after normalising); a name found in several
    districts is resolved with the listing's district, else left unresolved."""
    if not isinstance(text, str) or not text.strip():
        return None
    hits = []
    for part in re.split(r"[,/]| - ", text):
        k = _parish_key(part)
        if len(k) >= 4 and k in idx:
            hits = idx[k]
            break
    if not hits:
        return None
    if isinstance(district, str):
        same = [h for h in hits if h["district"].lower() == district.strip().lower()]
        if same:
            hits = same
    uniq = {(h["parish"], h["district"]) for h in hits}
    if len(uniq) == 1:
        return hits[0]
    # Several same-named parishes: accept only if they are neighbours (< 3 km apart)
    lats, lons = [h["lat"] for h in hits], [h["lon"] for h in hits]
    if (max(lats) - min(lats)) * 111 < 3 and (max(lons) - min(lons)) * 111 < 3:
        return {**hits[0], "lat": float(np.mean(lats)), "lon": float(np.mean(lons))}
    return None
