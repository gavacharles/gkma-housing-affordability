"""First look (paper 2): do road-network travel times carry a price signal?

Hedonic models of log rent and log sale price on travel time to the CBD and to the
Expressway and Northern Bypass access points, with the paper-1 structural controls,
portal fixed effects and the parish wealth index; standard errors clustered by
neighbourhood point (the level at which access varies). Compared with the same
models using straight-line distances.

  python paper2_transit/scripts/02_first_look.py -> paper2_transit/outputs/tables/first_look.csv
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import _paper  # noqa: F401
from gkma.config import p

L = gpd.read_file(p("data/processed/listings.gpkg"))
L["pt"] = L.geometry.to_wkt()
A = pd.read_csv(_paper.OUT / "tables" / "neighbourhood_accessibility.csv")
d = L.merge(A.drop(columns=["n_listings", "n_rent", "n_sale", "lon", "lat"]), on="pt", how="left")
for c in ["tt_cbd_min", "tt_expressway_min", "tt_bypass_min", "tt_rail_min"]:
    d[f"ln_{c}"] = np.log1p(d[c])
d["ln_acc60"] = np.log1p(d["acc_ntl_60"])

CTRL = {"rent": "bedrooms + I(bedrooms**2) + bathrooms + f_furnished + f_self_contained + C(ptype) + C(source)",
        "sale": "bedrooms + bathrooms + np.log(plot_decimals) + f_storeyed + C(ptype) + C(source)"}
Y = {"rent": "np.log(rent_month_ugx)", "sale": "np.log(price_ugx)"}
SPECS = {"distance (paper 1)": "np.log1p(dist_cbd_km) + np.log1p(dist_entebbe_expressway_km) + np.log1p(dist_northern_bypass_km)",
         "travel time": "ln_tt_cbd_min + ln_tt_expressway_min + ln_tt_bypass_min",
         "travel time + activity access": "ln_tt_cbd_min + ln_tt_expressway_min + ln_tt_bypass_min + ln_acc60"}
rows = []
for market in ("rent", "sale"):
    sub = d[(d["listing_type"] == market) & (d["ptype"] != "land")]
    if market == "sale":
        sub = sub[sub["plot_decimals"] > 0]
    for name, rhs in SPECS.items():
        for wealth in (False, True):
            f = f"{Y[market]} ~ {rhs} + {CTRL[market]}" + (" + wealth_index" if wealth else "")
            dd = sub.dropna(subset=[c for c in sub.columns if c in f] + ["pt"])
            m = smf.ols(f, data=dd).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(dd["pt"])[0]})
            for k_, v in m.params.items():
                if any(s in k_ for s in ("tt_", "dist_", "acc60", "wealth")):
                    rows.append({"market": market, "spec": name, "wealth_control": wealth, "term": k_,
                                 "coef": v, "se": m.bse[k_], "p": m.pvalues[k_], "n": int(m.nobs),
                                 "points": dd["pt"].nunique(), "r2_adj": m.rsquared_adj})
res = pd.DataFrame(rows)
res.round(4).to_csv(_paper.OUT / "tables" / "first_look.csv", index=False)
pd.set_option("display.width", 200)
print(res.assign(sig=np.where(res.p < .01, "**", np.where(res.p < .05, "*", "")))
      [["market", "spec", "wealth_control", "term", "coef", "se", "sig", "n", "points", "r2_adj"]].round(3).to_string(index=False))
