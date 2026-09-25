"""Is the Expressway premium the Entebbe Road corridor's affluence? (paper 2)

Hedonic models of log rent and log sale price with travel time to the Expressway and
Northern Bypass access points and to the CBD, the parish wealth index and structural
controls; standard errors clustered by neighbourhood point. The Expressway term is
re-estimated
  S1  base
  S2  + distance to the old Entebbe Road
  S3  + sector fixed effects (8 wedges of 45 degrees around the CBD)
  S4  + sector fixed effects + CBD travel-time quintile fixed effects
and, as placebos, the straight-line distance to each other radial trunk road is
estimated alongside distance to the Expressway.

  python paper2_transit/scripts/03_corridor.py [--acc neighbourhood_accessibility.csv]
  -> paper2_transit/outputs/tables/corridor_models.csv, corridor_placebo.csv
"""
import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from shapely.geometry import Point

import _paper  # noqa: F401
from gkma.config import load_config, p

ap = argparse.ArgumentParser()
ap.add_argument("--acc", default="neighbourhood_accessibility.csv")
ap.add_argument("--tag", default="")
a = ap.parse_args()

cfg = load_config()
crs = cfg["project"]["crs_projected"]
L = gpd.read_file(p("data/processed/listings.gpkg"))
L["pt"] = L.geometry.to_wkt()                      # same neighbourhood-point key as 01_accessibility
L = L.to_crs(crs)
A = pd.read_csv(_paper.OUT / "tables" / a.acc)
d = L.merge(A.drop(columns=["n_listings", "n_rent", "n_sale", "lon", "lat"]), on="pt", how="left")
for c in ["tt_cbd_min", "tt_expressway_min", "tt_bypass_min"]:
    d[f"ln_{c}"] = np.log1p(d[c])

# radial trunk roads (OSM names)
roads = gpd.read_file(p("data/external/osm/roads.gpkg")).to_crs(crs)
RADIALS = {"entebbe_road": ["Entebbe Road", "Entebbe - Kampala Road"],
           "jinja_road": ["Jinja Road", "Jinja - Kampala Road"],
           "bombo_road": ["Bombo Road", "Gulu - Kampala Road"],
           "gayaza_road": ["Gayaza Road"],
           "hoima_road": ["Hoima Road"],
           "masaka_road": ["Kampala - Masaka Road", "Masaka Road"],
           "fortportal_road": ["Fort Portal - Kampala Road"]}
for k, names in RADIALS.items():
    geom = roads[roads["name"].isin(names)].union_all()
    d[f"ln_dist_{k}"] = np.log1p(d.geometry.distance(geom) / 1000)
d["ln_dist_expressway"] = np.log1p(d["dist_entebbe_expressway_km"])

# sectors around the CBD
cbd = gpd.GeoSeries([Point(cfg["geography"]["points_of_interest"]["cbd"])], crs="EPSG:4326").to_crs(crs).iloc[0]
ang = np.degrees(np.arctan2(d.geometry.y - cbd.y, d.geometry.x - cbd.x)) % 360
d["sector"] = (ang // 45).astype(int)
d["cbd_band"] = pd.qcut(d["tt_cbd_min"], 5, labels=False, duplicates="drop")

CTRL = {"rent": "bedrooms + I(bedrooms**2) + bathrooms + f_furnished + f_self_contained + C(ptype) + C(source)",
        "sale": "bedrooms + bathrooms + np.log(plot_decimals) + f_storeyed + C(ptype) + C(source)"}
Y = {"rent": "np.log(rent_month_ugx)", "sale": "np.log(price_ugx)"}
BASE = "ln_tt_expressway_min + ln_tt_bypass_min + ln_tt_cbd_min + wealth_index"
SPECS = {"S1 base": BASE,
         "S2 + old Entebbe Road": BASE + " + ln_dist_entebbe_road",
         "S3 + sector FE": BASE + " + C(sector)",
         "S4 + sector FE + CBD-time bands": BASE + " + C(sector) + C(cbd_band)"}


def fit(sub, rhs, market):
    m0 = smf.ols(f"{Y[market]} ~ {rhs} + {CTRL[market]}", data=sub)
    idx = m0.data.row_labels
    return m0.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(sub.loc[idx, "pt"])[0]}), sub.loc[idx]


rows, prow = [], []
for market in ("rent", "sale"):
    sub = d[(d["listing_type"] == market) & (d["ptype"] != "land")]
    if market == "sale":
        sub = sub[sub["plot_decimals"] > 0]
    for name, rhs in SPECS.items():
        m, used = fit(sub, rhs, market)
        for k in ["ln_tt_expressway_min", "ln_tt_bypass_min", "ln_tt_cbd_min", "ln_dist_entebbe_road"]:
            if k in m.params:
                rows.append({"market": market, "spec": name, "term": k, "coef": m.params[k], "se": m.bse[k],
                             "p": m.pvalues[k], "n": int(m.nobs), "points": used["pt"].nunique(),
                             "r2_adj": m.rsquared_adj})
    # placebo corridors: distance to the Expressway vs distance to each radial, same model
    for k in RADIALS:
        rhs = f"ln_dist_expressway + ln_dist_{k} + ln_tt_cbd_min + wealth_index"
        m, used = fit(sub, rhs, market)
        prow.append({"market": market, "radial": k, "coef_radial": m.params[f"ln_dist_{k}"],
                     "p_radial": m.pvalues[f"ln_dist_{k}"], "coef_expressway": m.params["ln_dist_expressway"],
                     "p_expressway": m.pvalues["ln_dist_expressway"], "n": int(m.nobs)})
res, plc = pd.DataFrame(rows), pd.DataFrame(prow)
T = _paper.OUT / "tables"
res.round(4).to_csv(T / f"corridor_models{a.tag}.csv", index=False)
plc.round(4).to_csv(T / f"corridor_placebo{a.tag}.csv", index=False)
star = lambda p_: "**" if p_ < .01 else "*" if p_ < .05 else ""  # noqa: E731
pd.set_option("display.width", 200)
show = res.assign(est=[f"{c:+.3f}{star(p_)} ({s:.3f})" for c, s, p_ in zip(res.coef, res.se, res.p)])
print(show.pivot_table(index=["market", "term"], columns="spec", values="est", aggfunc="first").to_string())
print(plc.assign(radial=plc.radial, rad=[f"{c:+.3f}{star(p_)}" for c, p_ in zip(plc.coef_radial, plc.p_radial)],
                 exp=[f"{c:+.3f}{star(p_)}" for c, p_ in zip(plc.coef_expressway, plc.p_expressway)])
      [["market", "radial", "rad", "exp", "n"]].to_string(index=False))
