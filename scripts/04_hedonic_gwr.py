"""Stage 2 — RQ2: which attributes drive prices and how does that vary in space?

Hedonic OLS (clustered SEs, portal + quarter FE), tenure/title premium,
residual Moran's I, then GWR (or MGWR with --mgwr) with coefficient maps.
"""
import sys

import numpy as np
import pandas as pd

import _stage
from gkma.analysis.hedonic import gwr_fit, hedonic_ols, premium_table, residual_moran, tenure_models
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
summary = {}
for market in ("rent", "sale"):
    res, used = hedonic_ols(pts, market)
    (T / f"hedonic_{market}.txt").write_text(res.summary().as_text())
    pd.DataFrame({"coef": res.params, "se": res.bse, "p": res.pvalues}).to_csv(T / f"hedonic_{market}.csv")
    summary[market] = {"n": int(res.nobs), "r2_adj": res.rsquared_adj, **residual_moran(res, used)}
    if market == "sale":
        prem = premium_table(res, "C(title_status")
        prem.to_csv(T / "title_premium_houses.csv")
        print("Title premium (houses):\n", prem.round(3).to_string())

    # GWR on core continuous drivers
    y = "log_rent_month_ugx" if market == "rent" else "log_price_ugx"
    xs = [c for c in ["bedrooms", "bathrooms", "dist_cbd_km", "dist_major_road_km", "f_self_contained", "f_gated"]
          if c in used and used[c].notna().mean() > 0.9 and used[c].std() > 0]
    _, local, gsum = gwr_fit(used, y, xs, multiscale="--mgwr" in sys.argv)
    local.to_file(out / "models" / f"gwr_{market}.gpkg", driver="GPKG")
    summary[market]["gwr"] = gsum
    maps.coef_points(local, [f"b_{c}" for c in xs], [maps.label(c) for c in xs],
                     f"07_gwr_coefficients_{market}", units=bg,
                     note=f"{'MGWR' if '--mgwr' in sys.argv else 'GWR'} local coefficients on standardised variables; "
                          "hollow grey = not significant after multiple-testing correction.")

land_counts = pts[(pts["listing_type"] == "sale") & (pts["ptype"] == "land")]["tenure_class"].value_counts()
land_counts.to_csv(T / "tenure_counts_land.csv", header=["listings"])
house_counts = pts[(pts["listing_type"] == "sale") & (pts["ptype"] != "land")]["title_status"].value_counts()
house_counts.to_csv(T / "title_status_counts_houses.csv", header=["listings"])
print("Land listings by tenure:", land_counts.to_dict(), "| houses by title status:", house_counts.to_dict())
try:
    ten = tenure_models(pts)
    tp = premium_table(ten, "C(tenure_class")
    tp.to_csv(T / "tenure_premium_land.csv")
    (T / "tenure_model_land.txt").write_text(ten.summary().as_text())
    print("Tenure premium (land, per decimal):\n", tp.round(3).to_string())
except Exception as exc:
    print("Land tenure model skipped:", exc)
_stage.save_json(summary, T / "hedonic_summary.json")
print(pd.json_normalize(summary).T.to_string())
