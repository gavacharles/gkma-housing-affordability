"""Lightweight direct Overpass download (fallback when osmnx queries time out)."""
from __future__ import annotations

import logging

import geopandas as gpd
import requests
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

log = logging.getLogger(__name__)
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
             "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
S, W, N, E = -0.05, 32.25, 0.65, 33.05

QUERIES = {
    "taxi_stage": f"""[out:json][timeout:180];
(node["amenity"~"bus_station|taxi"]({S},{W},{N},{E});
 node["highway"="bus_stop"]({S},{W},{N},{E});
 node["public_transport"~"station|platform"]({S},{W},{N},{E}););
out;""",
    # Wetlands: flood-prone valley bottoms (Lubigi, Nakivubo, Kinawataka ...)
    "wetlands": f"""[out:json][timeout:300];
(way["natural"="wetland"]({S},{W},{N},{E});
 relation["natural"="wetland"]({S},{W},{N},{E}););
out geom tags;""",
    # Rail (paper 2): passenger stations/halts and the railway lines themselves
    "rail_stations": f"""[out:json][timeout:180];
(node["railway"~"^(station|halt|stop)$"]({S},{W},{N},{E});
 node["public_transport"="station"]["train"="yes"]({S},{W},{N},{E}););
out;""",
    "rail_lines": f"""[out:json][timeout:300];
way["railway"~"^(rail|light_rail|narrow_gauge|construction|proposed)$"]({S},{W},{N},{E});
out geom tags;""",
    "roads": f"""[out:json][timeout:300];
way["highway"~"^(motorway|trunk|primary|secondary|tertiary|motorway_link|trunk_link|primary_link)$"]({S},{W},{N},{E});
out geom tags;""",
}


def fetch(name: str) -> gpd.GeoDataFrame:
    last = None
    for url in ENDPOINTS:
        try:
            log.info("overpass %s via %s", name, url)
            r = requests.post(url, data={"data": QUERIES[name]}, timeout=360,
                              headers={"User-Agent": "GKMA-affordability-research/0.1"})
            r.raise_for_status()
            els = r.json()["elements"]
            break
        except Exception as exc:
            last = exc
            log.warning("  failed: %s", exc)
    else:
        raise RuntimeError(f"all Overpass endpoints failed: {last}")
    rows = []
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "node":
            geom = Point(e["lon"], e["lat"])
        elif name == "wetlands":
            geom = _area(e)
            if geom is None:
                continue
        elif "geometry" in e and len(e["geometry"]) > 1:
            geom = LineString([(g["lon"], g["lat"]) for g in e["geometry"]])
        else:
            continue
        rows.append({"osmid": e["id"], "element": e["type"], "name": t.get("name"),
                     "amenity": t.get("amenity"), "highway": t.get("highway"), "ref": t.get("ref"),
                     "railway": t.get("railway"), "usage": t.get("usage"), "service": t.get("service"),
                     "geometry": geom})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def _area(e: dict):
    """Polygon from a closed way, or from a multipolygon relation's outer rings."""
    if e["type"] == "way":
        pts = [(g["lon"], g["lat"]) for g in e.get("geometry", [])]
        return Polygon(pts) if len(pts) >= 4 and pts[0] == pts[-1] else None
    lines = [LineString([(g["lon"], g["lat"]) for g in m["geometry"]])
             for m in e.get("members", []) if m.get("role") == "outer" and len(m.get("geometry", [])) > 1]
    polys = list(polygonize(unary_union(lines))) if lines else []
    return unary_union(polys) if polys else None
