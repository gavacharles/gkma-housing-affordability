"""Common CLI for analysis stages: --data (processed dir) and --out (outputs dir)."""
import argparse
import json

import _common  # noqa: F401
import geopandas as gpd
import numpy as np
import pandas as pd

from gkma.config import p
from gkma.geo.boundaries import analysis_units, study_units
from gkma.viz import pubmaps as maps


def setup(description: str):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--data", default="data/processed")
    ap.add_argument("--out", default="outputs")
    a, _ = ap.parse_known_args()
    out = p(a.out)
    for sub in ("maps", "tables", "models"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    maps.OUT_DIR = str(out / "maps")
    pts = gpd.read_file(p(a.data) / "listings.gpkg")
    for c in pts.columns:  # GeoPackage round-trip: restore numerics
        if pts[c].dtype == object and c != "geometry":
            conv = pd.to_numeric(pts[c], errors="coerce")
            if conv.notna().sum() == pts[c].notna().sum() and pts[c].notna().any():
                pts[c] = conv
    bg = study_units()
    if bg["unit_id"].astype(str).str.startswith("hex").all():  # fallback grid: keep hexes near data
        hull = pts.unary_union.convex_hull.buffer(3000)
        bg = bg[bg.intersects(hull)].reset_index(drop=True)
    return a, out, pts, analysis_units(pts), bg


def save_json(obj, path):
    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        return str(o)
    path.write_text(json.dumps(obj, indent=2, default=conv))
