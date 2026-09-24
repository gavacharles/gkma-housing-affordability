"""Parish-level household income for GKMA from published UBOS data only.

See src/gkma/geo/census.py for the method. Writes
  data/external/parish_income.csv     all Ugandan parishes with wealth index and
                                      modelled median income (UGX/month, 2019/20 prices)
  data/external/parish_income.gpkg    GKMA parishes joined to the 2016 parish polygons
  data/external/parish_income_calibration.csv / .json   sub-region fit
"""
import json
import re

import _common  # noqa: F401
import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz, process

from gkma.config import load_config, p
from gkma.geo.census import UNHS_MEDIAN_2019_20, parish_income_model, parse_census

df = parse_census()                                   # every parish in Uganda
d, info = parish_income_model(df)
d.to_csv(p("data/external/parish_income.csv"), index=False)
cal = d.groupby("subregion").apply(lambda g: pd.Series({
    "households": g["households"].sum(),
    "wealth_mean": g["wealth_mean"].iloc[0],
    "unhs_median": UNHS_MEDIAN_2019_20[g.name],
    "check_hh_weighted_geomean": float((g["median_income_2019_20"].pipe(lambda s: s.clip(lower=1)).apply(lambda x: __import__("math").log(x)) * g["households"]).sum() / g["households"].sum()),
}))
cal["check_hh_weighted_geomean"] = cal["check_hh_weighted_geomean"].map(lambda x: round(__import__("math").exp(x)))
cal.to_csv(p("data/external/parish_income_calibration.csv"))
json.dump(info, open(p("data/external/parish_income_calibration.json"), "w"), indent=2)
print(json.dumps(info, indent=2))
print(cal.round(2).to_string())

# GKMA parishes -> 2016 polygons (same matching rule as 00_prepare_census.py)
g = load_config()["geography"]
par = gpd.read_file(p(g["parishes"]))
gk = d[d["district"].isin(["KAMPALA", "WAKISO", "MUKONO", "MPIGI", "BUIKWE", "LUWERO"])].copy()


def key(s):
    s = re.sub(r"\b(division|town council|municipality|ward|sub ?county)\b", "", str(s).lower())
    return re.sub(r"[^a-z0-9]", "", s)


par["_d"], par["_s"], par["_p"] = (par[g["district_name_col"]].map(key), par[g["subcounty_name_col"]].map(key),
                                   par[g["parish_name_col"]].map(key))
gk["_d"], gk["_s"], gk["_p"] = gk["district"].map(key), gk["subcounty"].map(key), gk["parish"].map(key)
idx = []
for _, r in gk.iterrows():
    cand = par[par["_d"] == r["_d"]]
    same = cand[cand["_s"].map(lambda s: fuzz.ratio(s, r["_s"]) >= 85)]
    pool = same if len(same) else cand
    hit = process.extractOne(r["_p"], pool["_p"].tolist(), scorer=fuzz.ratio) if len(pool) else None
    idx.append(pool.index[hit[2]] if hit and hit[1] >= 88 else None)
gk["poly_idx"] = idx
cols = ["subregion", "subcounty", "parish", "households", "hh_size", "wealth_nat", "median_income_2019_20"]
joined = par.join(gk.dropna(subset=["poly_idx"]).drop_duplicates("poly_idx").set_index("poly_idx")[cols])
joined.to_file(p("data/external/parish_income.gpkg"), driver="GPKG")
print(f"GKMA: {gk['poly_idx'].notna().sum()} of {len(gk)} parishes matched "
      f"({joined['households'].sum() / gk['households'].sum():.0%} of households)")
print(gk.groupby("district")["median_income_2019_20"].describe(percentiles=[.1, .5, .9]).round(-3).to_string())
