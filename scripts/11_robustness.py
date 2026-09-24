"""Robustness: key hedonic coefficients and headline index values re-estimated on
alternative samples.

  full               all listings
  neighbourhood_only listings located by exact or contained gazetteer match
  drop_<portal>      each portal left out in turn

Outputs  tables/robustness.csv
"""
import numpy as np
import pandas as pd

import _stage
from gkma.analysis.affordability_index import bou_lending_rate, compute_index
from gkma.analysis.hedonic import hedonic_ols
from gkma.config import load_config

a, out, pts, units, bg = _stage.setup(__doc__)
ai = load_config().get("affordability_index", {})
m = ai.get("mortgage", {})
base = {"rate": bou_lending_rate() if m.get("rate", "bou") == "bou" else float(m["rate"]),
        "deposit": m.get("deposit", 0.30), "term_years": m.get("term_years", 20), "cap": m.get("cap", 0.35)}
min_n = ai.get("min_listings", 20)

KEY = {"rent": ["wealth_index", "np.log1p(dist_cbd_km)", "f_furnished"],
       "sale": ["wealth_index", "np.log(plot_decimals)", "np.log1p(dist_entebbe_expressway_km)",
                'C(title_status, Treatment("unknown"))[T.titled]']}
variants = {"full": pts,
            "neighbourhood_only": pts[pts["geo_method"].isin(["lookup_exact", "lookup_contains"])]}
for src in sorted(pts["source"].unique()):
    variants[f"drop_{src}"] = pts[pts["source"] != src]

rows = []
for name, d in variants.items():
    row = {"variant": name, "n": len(d)}
    for market, keys in KEY.items():
        try:
            res, _ = hedonic_ols(d, market)
            row[f"{market}_n"] = int(res.nobs)
            row[f"{market}_r2_adj"] = res.rsquared_adj
            for k in keys:
                if k in res.params:
                    row[f"{market}:{k}"] = res.params[k]
                    row[f"{market}:{k}:p"] = res.pvalues[k]
        except Exception as e:  # noqa: BLE001  (e.g. a portal holds all of one category)
            print(f"{name} {market}: {e}")
    idx = pd.concat([compute_index(d, "gkma", base, min_n=min_n), compute_index(d, "district", base, min_n=min_n)])
    for area in ("GKMA", "Kampala", "Wakiso", "Mukono"):
        r = idx[idx["area"] == area]
        for k in ("rai", "oai", "agi_rent"):
            row[f"{area}:{k}"] = float(r[k].iloc[0]) if len(r) and k in r and r[k].notna().any() else np.nan
    rows.append(row)
    print(name, len(d))

rob = pd.DataFrame(rows).set_index("variant")
rob.round(4).to_csv(out / "tables" / "robustness.csv")
print(rob.T.round(3).to_string())
