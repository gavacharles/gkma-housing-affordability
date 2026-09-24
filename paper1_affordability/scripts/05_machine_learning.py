"""Stage 3 — RQ3: do ML models beat hedonic models, and what do they reveal?

Spatial-block vs random CV for OLS, RF, XGBoost, LightGBM (+GWR with --gwr),
then SHAP on the best spatial-CV model: global importance and a map of the
dominant driver by unit.
"""
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import _stage
from gkma.analysis.ml import cross_validate, fit_and_explain, shap_by_unit, shap_importance, summarise_cv
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
for market, y in (("rent", "log_rent_month_ugx"), ("sale", "log_price_ugx")):
    d = pts[(pts["listing_type"] == market) & (pts["ptype"] != "land")]
    res, oof = cross_validate(d, y, include_gwr="--gwr" in sys.argv)
    res.to_csv(T / f"cv_folds_{market}.csv", index=False)
    s = summarise_cv(res)
    s.to_csv(T / f"cv_summary_{market}.csv")
    print(f"\n{market.upper()} cross-validation\n", s.to_string())

    sp = res[res["scheme"] == "spatial_block"].groupby("model")["rmse_log"].mean()
    best = sp.drop(["HedonicOLS", "GWR"], errors="ignore").idxmin()
    model, shap_df, meta = fit_and_explain(d, y, best)
    imp = shap_importance(shap_df)
    imp.to_csv(T / f"shap_importance_{market}.csv", header=["mean_abs_shap"])

    fig, ax = plt.subplots(figsize=(maps.FULL * 0.75, maps.FULL * 0.5))
    top = imp.head(15)[::-1]
    ax.barh([maps.label(v) for v in top.index], top.values, color=maps.BLUE[4], height=0.6)
    ax.set_xlabel("mean |SHAP| (log price units)")
    ax.spines[["top", "right"]].set_visible(False)
    maps._save(fig, f"08_shap_importance_{market}",
               title=f"Global feature importance for asking {'rents' if market == 'rent' else 'sale prices'} ({best}, mean |SHAP|)",
               note="Mean absolute SHAP value on the log scale; one-hot categories summed to their parent variable.")

    by_unit = shap_by_unit(shap_df, meta)
    by_unit.to_csv(T / f"shap_by_unit_{market}.csv")
    g = bg.merge(by_unit, left_on="unit_id", right_index=True, how="left")
    g["dominant_feature"] = g["dominant_feature"].map(lambda v: maps.label(v) if isinstance(v, str) else v)
    maps.dominant_feature_map(g, f"09_shap_dominant_{market}", f"Dominant price driver by area ({market})",
                              note=f"{best}; feature with largest mean |SHAP| among listings in each unit.")
    maps.choropleth(g, "location_effect", f"Location premium from SHAP ({market}, log points)",
                    f"10_shap_location_effect_{market}", cmap=maps.DIVERGING, scheme="quantiles",
                    fmt="{:.2f}", legend_title="sum of location SHAP")
