"""Building footprint area on the night-light grid (paper 2).

Streams the Microsoft Global Building Footprints tiles covering Greater Kampala and
sums, for each cell of the NASA Black Marble night-light grid (15 arc-seconds,
about 460 m), the number of buildings and their total footprint area (m², from the
polygon area in a local equal-area approximation). Buildings are assigned to the
cell containing their centroid.

  python paper2_transit/scripts/00_buildings_grid.py
  -> data/external/buildings/building_grid.tif   (band 1: footprint area m², band 2: count)
"""
import glob
import gzip
import json
import math

import numpy as np
import rasterio

import _paper  # noqa: F401
from gkma.config import load_config, p

cfg = load_config()
nl = p(cfg["covariates"]["night_lights"]) if "night_lights" in cfg.get("covariates", {}) else \
    p("data/external/viirs_annual_2024_uganda.tif")
with rasterio.open(nl) as src:
    prof, T, H, W = src.profile.copy(), src.transform, src.height, src.width
area = np.zeros((H, W), dtype="float64")
count = np.zeros((H, W), dtype="float64")
inv = ~T
M_PER_DEG = 111_320.0

n_in = n_all = 0
for f in sorted(glob.glob(str(p("data/external/buildings/ms/*.csv.gz")))):
    with gzip.open(f, "rt") as fh:
        for line in fh:
            n_all += 1
            ring = json.loads(line)["geometry"]["coordinates"][0]
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            cx, cy = sum(xs[:-1]) / (len(xs) - 1), sum(ys[:-1]) / (len(ys) - 1)
            col, row = inv * (cx, cy)
            col, row = int(math.floor(col)), int(math.floor(row))
            if not (0 <= row < H and 0 <= col < W):
                continue
            kx = M_PER_DEG * math.cos(math.radians(cy))
            a = 0.0
            for i in range(len(xs) - 1):                       # shoelace, metres
                a += (xs[i] * kx) * (ys[i + 1] * M_PER_DEG) - (xs[i + 1] * kx) * (ys[i] * M_PER_DEG)
            area[row, col] += abs(a) / 2
            count[row, col] += 1
            n_in += 1
    print(f"{f.split('/')[-1]}: running total {n_in:,} buildings in the grid (of {n_all:,} read)")

prof.update(count=2, dtype="float32", nodata=0, compress="lzw")
dest = p("data/external/buildings/building_grid.tif")
with rasterio.open(dest, "w", **prof) as dst:
    dst.write(area.astype("float32"), 1)
    dst.write(count.astype("float32"), 2)
    dst.set_band_description(1, "building footprint area (m2)")
    dst.set_band_description(2, "building count")
print(f"wrote {dest}: {n_in:,} buildings, {area.sum() / 1e6:,.1f} km² of footprint")
