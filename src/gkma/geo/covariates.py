"""Location covariates for each listing.

OSM layers are downloaded once with osmnx and cached as GeoPackages in
data/external/osm/. Night-time lights (VIIRS annual composite, e.g. from
the Earth Observation Group) and a flood hazard layer are optional rasters/
polygons you place in data/external/ (paths in config.yaml).
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from sklearn.neighbors import BallTree

from gkma.config import load_config, p

log = logging.getLogger(__name__)
OSM_DIR = "data/external/osm"
BBOX = (32.25, -0.05, 33.05, 0.65)  # left, bottom, right, top

POI_TAGS = {
    "school": {"amenity": ["school", "college", "university", "kindergarten"]},
    "health": {"amenity": ["hospital", "clinic", "doctors"], "healthcare": True},
    "market": {"amenity": ["marketplace"], "shop": ["supermarket", "mall"]},
    "taxi_stage": {"amenity": ["bus_station", "taxi"], "highway": ["bus_stop"],
                   "public_transport": ["station", "platform"]},
}
ROAD_TAGS = {"highway": ["motorway", "trunk", "primary", "secondary", "tertiary",
                         "motorway_link", "trunk_link", "primary_link"]}


def _osm_layer(name: str, tags: dict) -> gpd.GeoDataFrame:
    path = p(OSM_DIR) / f"{name}.gpkg"
    crs = load_config()["project"]["crs_projected"]
    if path.exists():
        return gpd.read_file(path).to_crs(crs)
    import osmnx as ox
    ox.settings.overpass_url = load_config()["geography"].get("overpass_url", ox.settings.overpass_url)
    ox.settings.requests_timeout = 600
    log.info("downloading OSM %s from %s ...", name, ox.settings.overpass_url)
    try:
        from gkma.geo.osm_direct import QUERIES, fetch
        # Lighter hand-written queries first; osmnx for anything else
        gdf = fetch(name) if name in QUERIES else ox.features_from_bbox(bbox=BBOX, tags=tags).reset_index()
    except Exception:
        gdf = ox.features_from_bbox(bbox=BBOX, tags=tags).reset_index()
    keep = [c for c in ["osmid", "element", "name", "amenity", "highway", "shop", "ref", "geometry"] if c in gdf]
    gdf = gdf[keep]
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GPKG")
    return gdf.to_crs(crs)


def _dist_and_count(pts: gpd.GeoDataFrame, targets: gpd.GeoDataFrame, radius_m: float = 1000):
    """Distance to the nearest target point and count within radius (metres)."""
    tp = targets.geometry.representative_point()
    tree = BallTree(np.c_[tp.x, tp.y])
    xy = np.c_[pts.geometry.x, pts.geometry.y]
    dist, _ = tree.query(xy, k=1)
    counts = tree.query_radius(xy, r=radius_m, count_only=True)
    return dist[:, 0], counts


def _dist_to_lines(pts: gpd.GeoDataFrame, lines: gpd.GeoDataFrame) -> np.ndarray:
    if lines.empty:
        return np.full(len(pts), np.nan)
    j = gpd.sjoin_nearest(pts[["geometry"]], lines[["geometry"]], distance_col="d")
    return j[~j.index.duplicated()]["d"].reindex(pts.index).to_numpy()


def add_covariates(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cfg = load_config()
    out = pts.copy()
    crs = cfg["project"]["crs_projected"]

    cbd = gpd.GeoSeries([Point(cfg["geography"]["points_of_interest"]["cbd"])], crs="EPSG:4326").to_crs(crs).iloc[0]
    out["dist_cbd_km"] = out.geometry.distance(cbd) / 1000

    for name, tags in POI_TAGS.items():
        try:
            layer = _osm_layer(name, tags)
            d, n = _dist_and_count(out, layer)
            out[f"dist_{name}_km"], out[f"n_{name}_1km"] = d / 1000, n
        except Exception as exc:
            log.warning("OSM %s unavailable: %s", name, exc)

    try:
        roads = _osm_layer("roads", ROAD_TAGS)
        roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])]
        major = roads[roads["highway"].isin(["motorway", "trunk", "primary"])]
        out["dist_major_road_km"] = _dist_to_lines(out, major) / 1000
        for key, label in cfg["geography"]["corridors"].items():
            words = [w for w in label.lower().replace("-", " ").split() if len(w) > 3]
            nm = roads["name"].fillna("").str.lower()
            sel = roads[np.logical_and.reduce([nm.str.contains(w) for w in words])]
            if sel.empty and key == "entebbe_expressway":
                sel = roads[(roads["highway"] == "motorway")]
            out[f"dist_{key}_km"] = _dist_to_lines(out, sel) / 1000
            log.info("corridor %s: %d segments", key, len(sel))
    except Exception as exc:
        log.warning("OSM roads unavailable: %s", exc)

    # Flood proxy from open data: OSM wetlands. Kampala's floods are mostly
    # pluvial flash floods in the wetland valleys; a modelled hazard layer
    # (config geography.flood) replaces this when available.
    try:
        wet = _osm_layer("wetlands", {"natural": "wetland"})
        wet = wet[wet.geom_type.isin(["Polygon", "MultiPolygon"])]
        out["dist_wetland_km"] = _dist_to_lines(out, wet) / 1000   # 0 inside a wetland
        out["near_wetland_200m"] = (out["dist_wetland_km"] <= 0.2).astype(int)
    except Exception as exc:
        log.warning("OSM wetlands unavailable: %s", exc)

    # Census 2024 parish profile (scripts/00_prepare_census.py): neighbourhood
    # socio-economic status from household asset/service shares.
    census = p("data/external/census2024_parish.gpkg")
    if census.exists():
        cz = gpd.read_file(census).to_crs(crs)
        keep = [c for c in ["wealth_index", "sh_grid", "sh_computer", "hh_size", "households"] if c in cz]
        j = gpd.sjoin(out[["geometry"]], cz[keep + ["geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated()]
        for c in keep:
            out["census_" + c if c == "households" else c] = j[c].reindex(out.index)

    ntl = p(cfg["geography"]["night_lights"])
    if ntl.exists():
        from rasterstats import zonal_stats
        buf = out.geometry.buffer(500).to_crs("EPSG:4326")
        zs = zonal_stats(buf, str(ntl), stats=["mean"])
        out["ntl_500m"] = [z["mean"] for z in zs]
    flood = p(cfg["geography"]["flood"])
    if flood.exists():
        fz = gpd.read_file(flood).to_crs(crs)
        out["in_flood_zone"] = out.geometry.within(fz.unary_union).astype(int)
    return out
