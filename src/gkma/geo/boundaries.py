"""Administrative units for aggregation, with a hex-grid fallback.

Boundaries: OCHA/UBOS common operational datasets for Uganda on HDX
("cod-ab-uga"). Save the parish (admin 4, if published) and sub-county
(admin 3) layers to the paths in config.yaml. Until they exist, a 1.5 km
hexagon grid over the GKMA extent is used so the workflow still runs.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box

from gkma.config import load_config, p

log = logging.getLogger(__name__)
GKMA_BBOX = (32.25, -0.05, 33.05, 0.65)


def points_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    cfg = load_config()["project"]
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=cfg["crs_geographic"])
    return g.to_crs(cfg["crs_projected"])


def _read_units(path_key: str, name_col_key: str) -> gpd.GeoDataFrame | None:
    g = load_config()["geography"]
    path = p(g[path_key])
    if not path.exists():
        return None
    units = gpd.read_file(path).to_crs(load_config()["project"]["crs_projected"])
    districts = g["gkma_districts"] + g["gkma_fringe_districts"]
    dcol = g["district_name_col"]
    if dcol in units:
        units = units[units[dcol].str.title().isin(districts)]
    scol = g.get("subcounty_name_col")
    if scol in units and g.get("exclude_subcounties"):
        units = units[~units[scol].str.title().isin([x.title() for x in g["exclude_subcounties"]])]
    units = units.rename(columns={g[name_col_key]: "unit_name"})
    units["unit_id"] = units.get(dcol, "").astype(str) + "/" + units["unit_name"].astype(str)
    return units[["unit_id", "unit_name", "geometry"] + ([dcol] if dcol in units else [])]


def hex_grid(size_m: float = 1500) -> gpd.GeoDataFrame:
    crs = load_config()["project"]["crs_projected"]
    ext = gpd.GeoSeries([box(*GKMA_BBOX)], crs="EPSG:4326").to_crs(crs).total_bounds
    w, h = np.sqrt(3) * size_m, 1.5 * size_m
    hexes, ids = [], []
    for row, y in enumerate(np.arange(ext[1], ext[3] + h, h)):
        for x in np.arange(ext[0] + (w / 2 if row % 2 else 0), ext[2] + w, w):
            hexes.append(Polygon([(x + size_m * np.cos(a), y + size_m * np.sin(a))
                                  for a in np.radians(np.arange(30, 390, 60))]))
            ids.append(f"hex_{len(ids)}")
    return gpd.GeoDataFrame({"unit_id": ids, "unit_name": ids}, geometry=hexes, crs=crs)


def load_units(level: str = "parish") -> tuple[gpd.GeoDataFrame, str]:
    key = {"parish": ("parishes", "parish_name_col"),
           "subcounty": ("subcounties", "subcounty_name_col")}[level]
    units = _read_units(*key)
    if units is None:
        log.warning("%s boundaries not found; using 1.5 km hex grid", level)
        return hex_grid(), "hex"
    return units, level


def assign_units(pts: gpd.GeoDataFrame, units: gpd.GeoDataFrame, prefix: str) -> gpd.GeoDataFrame:
    j = gpd.sjoin(pts, units[["unit_id", "unit_name", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()].drop(columns="index_right")
    return j.rename(columns={"unit_id": f"{prefix}_id", "unit_name": f"{prefix}_name"})


def attach_units(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add parish_* and subcounty_* ids, plus analysis_unit (parish, or
    sub-county where the parish has too few listings)."""
    par, _ = load_units("parish")
    sub, _ = load_units("subcounty")
    pts = assign_units(pts, par, "parish")
    pts = assign_units(pts, sub, "subcounty")
    g = load_config()["geography"]
    if g.get("map_level", "parish") == "subcounty":
        pts["analysis_unit"] = pts["subcounty_id"]
    else:
        k = g["min_listings_per_unit"]
        n = pts.groupby("parish_id")["parish_id"].transform("size")
        pts["analysis_unit"] = np.where(n >= k, pts["parish_id"], pts["subcounty_id"])
    return pts


def in_study_area(pts: gpd.GeoDataFrame) -> pd.Series:
    """True for points inside the GKMA districts (or the bbox if no boundaries)."""
    sub = _read_units("subcounties", "subcounty_name_col")
    if sub is None:
        area = gpd.GeoSeries([box(*GKMA_BBOX)], crs="EPSG:4326").to_crs(pts.crs).iloc[0]
        return pts.geometry.within(area)
    return pts.geometry.within(sub.unary_union)


def analysis_units(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Polygons for the mixed parish/sub-county analysis units used by pts."""
    par, _ = load_units("parish")
    sub, _ = load_units("subcounty")
    both = pd.concat([par, sub]).drop_duplicates("unit_id")
    used = set(pts["analysis_unit"].dropna())
    return gpd.GeoDataFrame(both[both["unit_id"].isin(used)], crs=par.crs).reset_index(drop=True)


def study_units() -> gpd.GeoDataFrame:
    """All mapping units (sub-counties or parishes, per geography.map_level)."""
    level = load_config()["geography"].get("map_level", "parish")
    units, _ = load_units("subcounty" if level == "subcounty" else "parish")
    return units
