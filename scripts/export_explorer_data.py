"""Data for the interactive affordability explorer (docs/explorer/explorer.html).

Parish shapes (clipped to land, simplified, projected to an SVG viewBox),
modelled parish incomes, dispersion, households and minimum non-housing
budgets, plus the median listed rent/price for each area.

  python scripts/export_explorer_data.py  ->  outputs/interactive/explorer_data.json
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import norm

import _common  # noqa: F401
from gkma.analysis.affordability_index import bou_lending_rate
from gkma.config import load_config, p
from gkma.viz import pubmaps as pm

cfg = load_config()
g = cfg["geography"]
crs = cfg["project"]["crs_projected"]
cpi = float(pd.read_csv(p("data/external/cpi_uplift.csv")).query("series == 'headline'")["uplift"].iloc[0])
inc = pd.read_csv(p(cfg["income"]["table"])).set_index("unit")
sig = pd.Series(np.sqrt(2) * norm.ppf((inc["gini"] + 1) / 2), index=inc.index)
ri = cfg["affordability_index"]["residual_income"]

par = gpd.read_file(p(cfg["income"]["parish_income"])).to_crs(crs)
par = par.dropna(subset=["median_income_2019_20", "households"])
par["district"] = par[g["district_name_col"]].str.title()
par["income"] = par["median_income_2019_20"] * cpi
par["sigma"] = par["district"].map(sig)
hh = par["hh_size"].fillna(par["hh_size"].median())
par["nmin"] = ri["poverty_line_ae_2019_20"] * cpi * ri["ae_per_person"] * hh * (1 - ri["housing_share"])
par = pm.clip_land(par)

x0, y0, x1, y1 = pm._extent("main")
S = 1000 / (x1 - x0)                                       # viewBox 1000 wide


def path(geom, tol=35):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for poly in polys:
        if poly.geom_type != "Polygon" or poly.area < 2500:
            continue
        for ring in [poly.exterior, *poly.interiors]:
            xy = np.asarray(ring.coords)
            px, py = (xy[:, 0] - x0) * S, (y1 - xy[:, 1]) * S
            out.append("M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py)) + "Z")
    return "".join(out)


parishes = []
for _, r in par.iterrows():
    d = path(r.geometry)
    if d:
        parishes.append({"n": str(r[g["parish_name_col"]]).title(), "s": str(r[g["subcounty_name_col"]]).title(),
                         "d": r["district"], "hh": int(r["households"]), "inc": round(float(r["income"])),
                         "sg": round(float(r["sigma"]), 4), "nm": round(float(r["nmin"])), "p": d})

b = pm.base()
from shapely.geometry import box as sbox  # noqa: E402
frame = sbox(x0, y0, x1, y1)
lake = "".join(path(gm.intersection(frame), tol=60) for gm in b["lake"].geometry if gm.intersects(frame))
dist = "".join(path(gm.intersection(frame), tol=60) for gm in b["districts"].geometry if gm.intersects(frame))

areas = {}
for f, key in [("affordability_index_gkma.csv", None), ("affordability_index_district.csv", None)]:
    for _, r in pd.read_csv(p("outputs/tables") / f).iterrows():
        if pd.notna(r.get("median_rent")) or pd.notna(r.get("median_price")):
            areas[r["area"]] = {"rent": None if pd.isna(r["median_rent"]) else float(r["median_rent"]),
                                "price": None if pd.isna(r["median_price"]) else float(r["median_price"]),
                                "n_rent": int(r["n_rent"]), "n_sale": int(r["n_sale"])}

# tour stops: zoom box (viewBox units), outline and the stop's own index values
sc = gpd.read_file(p(g["subcounties"])).to_crs(crs)
sc["area"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
dist_poly = sc.dissolve(g["district_name_col"]).reset_index()
dist_poly["area"] = dist_poly[g["district_name_col"]].str.title()
T = p("outputs/tables")
idx = pd.concat([pd.read_csv(T / f"affordability_index_{lv}.csv") for lv in ("gkma", "district", "subcounty")])
idx = idx.set_index("area")
STOPS = [("GKMA", "Greater Kampala", "The whole metropolitan area"),
         ("Kampala", "Kampala", "The capital city"),
         ("Kampala/Central Division", "Central Division, Kampala", "The least affordable sub-county"),
         ("Wakiso", "Wakiso", "The largest district, wrapping around the city"),
         ("Wakiso/Kira Division", "Kira Division, Wakiso", "A fast-growing eastern suburb"),
         ("Mukono", "Mukono", "The eastern district"),
         ("Mukono/Goma Division", "Goma Division, Mukono", "The most affordable sub-county measured")]


def vb(geom, pad=0.18):
    a0, b0, a1, b1 = geom.bounds
    w, h = a1 - a0, b1 - b0
    side = max(w, h * 1000 / ((y1 - y0) * S)) * (1 + pad)
    cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
    bx, by = (cx - side / 2 - x0) * S, (y1 - (cy + side * ((y1 - y0) / (x1 - x0)) / 2)) * S
    if side * S >= 1000:                                   # district larger than the frame: show the whole map
        return [0, 0, 1000, round((y1 - y0) * S)]
    return [round(bx, 1), round(by, 1), round(side * S, 1), round(side * S * (y1 - y0) / (x1 - x0), 1)]


tour = []
for key, name, blurb in STOPS:
    r = idx.loc[key]
    if key == "GKMA":
        geom, box_ = None, [0, 0, 1000, round((y1 - y0) * S)]
    else:
        src = dist_poly if "/" not in key else sc
        geom = src[src["area"] == key].geometry.union_all()
        geom = geom.intersection(frame) if geom is not None else None
        box_ = vb(geom)
    tour.append({"key": key, "name": name, "blurb": blurb, "box": box_, "outline": path(geom, tol=40) if geom else "",
                 "rent": float(r["median_rent"]), "income": float(r["median_income"]), "rai": float(r["rai"]),
                 "out": float(r["agi_rent"]), "hh": float(r["households"]), "n": int(r["n_rent"])})

m = cfg["affordability_index"]["mortgage"]
data = {"parishes": parishes, "lake": lake, "districts": dist,
        "viewbox": [1000, round((y1 - y0) * S)], "areas": areas, "tour": tour,
        "mortgage": {"rate": round(bou_lending_rate(), 4), "deposit": m["deposit"], "term": m["term_years"],
                     "cap": m["cap"]},
        "meta": {"listings": 10643, "cpi": cpi}}
out = p("outputs/interactive")
out.mkdir(parents=True, exist_ok=True)
(out / "explorer_data.json").write_text(json.dumps(data, separators=(",", ":")))
print(len(parishes), "parishes;", round((out / "explorer_data.json").stat().st_size / 1024), "KB;", list(areas))
