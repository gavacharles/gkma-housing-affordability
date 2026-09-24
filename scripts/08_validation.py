"""Validation: listing-based hedonic price index vs the UBOS RPPI.

For sale houses and apartments, a time-dummy hedonic regression per RPPI area
(Wakiso; Kampala Central & Makindye; Nakawa; Kawempe & Rubaga) gives a
quarterly listing index. Both series are rebased to the first overlapping
quarter and compared on quarter-on-quarter changes.

Caveats to state: listings are asking prices; RED post dates are estimated
from listing codes (about +/- one month), so only quarter-level movement is
compared; the overlap is short.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import _stage
from gkma.config import p
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"

AREA = {"Central": "Kampala Central & Makindye", "Makindye": "Kampala Central & Makindye",
        "Nakawa": "Nakawa", "Kawempe": "Kawempe & Rubaga", "Rubaga": "Kawempe & Rubaga"}
sub = pts["subcounty_id"].astype(str)
district, subcounty = sub.str.split("/").str[0], sub.str.split("/").str[1]
pts["rppi_area"] = np.where(district == "Wakiso", "Wakiso",
                            np.where(district == "Kampala", subcounty.map(AREA), None))

d = pts[(pts["listing_type"] == "sale") & pts["ptype"].isin(["house", "apartment"])
        & pts["rppi_area"].notna() & pts["log_price_ugx"].notna() & pts["bedrooms"].notna()].copy()
d["qstart"] = pd.PeriodIndex(pd.to_datetime(d["listing_date"]), freq="Q").start_time
fcols = [c for c in ["f_self_contained", "f_boys_quarters", "f_gated", "f_storeyed", "f_pool",
                     "f_shell_or_incomplete"] if c in d and d[c].nunique() > 1]

rows = []
for area, g in d.groupby("rppi_area"):
    qs = g["qstart"].value_counts()
    g = g[g["qstart"].isin(qs[qs >= 15].index)]           # need enough listings per quarter
    if g["qstart"].nunique() < 2:
        continue
    f = "log_price_ugx ~ bedrooms + I(bedrooms**2) + C(ptype) + C(qstart)" + "".join(f" + {c}" for c in fcols)
    if g["plot_decimals"].notna().mean() > 0.6:
        g = g[g["plot_decimals"].notna()]
        f += " + np.log(plot_decimals)"
    res = smf.ols(f, data=g).fit(cov_type="HC1")
    base_q = sorted(g["qstart"].unique())[0]
    for q in sorted(g["qstart"].unique()):
        k = f"C(qstart)[T.{pd.Timestamp(q)}]"
        coef = 0.0 if q == base_q else res.params.get(k, np.nan)
        se = 0.0 if q == base_q else res.bse.get(k, np.nan)
        rows.append({"area": area, "qstart": pd.Timestamp(q), "n": int((g["qstart"] == q).sum()),
                     "listing_index": 100 * np.exp(coef), "se": se})
idx = pd.DataFrame(rows)

rppi = pd.read_csv(p("data/external/ubos_rppi_quarterly.csv"), parse_dates=["period_start"])
m = idx.merge(rppi.rename(columns={"period_start": "qstart"})[["area", "qstart", "rppi"]],
              on=["area", "qstart"], how="left")
m["rppi_rebased"] = m.groupby("area")["rppi"].transform(lambda s: 100 * s / s.iloc[0])
m = m.sort_values(["area", "qstart"])
m["listing_qoq"] = m.groupby("area")["listing_index"].pct_change() * 100
m["rppi_qoq"] = m.groupby("area")["rppi_rebased"].pct_change() * 100
m.to_csv(T / "validation_listing_index_vs_rppi.csv", index=False)
both = m.dropna(subset=["listing_qoq", "rppi_qoq"])
summary = {"area_quarters_compared": len(both),
           "corr_qoq": both["listing_qoq"].corr(both["rppi_qoq"]) if len(both) > 2 else None,
           "mean_abs_gap_pp": (both["listing_qoq"] - both["rppi_qoq"]).abs().mean() if len(both) else None}
_stage.save_json(summary, T / "validation_summary.json")
print(m.round(2).to_string(index=False))
print(summary)

areas = list(m["area"].unique())
fig, axes = plt.subplots(1, len(areas), figsize=(maps.FULL, maps.FULL * 0.32), sharey=True, squeeze=False)
for ax, area in zip(axes[0], areas):
    s = m[m["area"] == area]
    ax.plot(s["qstart"], s["listing_index"], color=maps.BLUE[4], lw=2, marker="o", ms=4, label="Listings (hedonic)")
    ax.plot(s["qstart"], s["rppi_rebased"], color=maps.RED[4], lw=2, marker="s", ms=4, label="UBOS RPPI")
    ax.set_title(area, loc="left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", labelrotation=45, labelsize=7)
axes[0][0].set_ylabel("index, first quarter = 100")
axes[0][0].legend(frameon=False, fontsize=7)
fig.tight_layout()
maps._save(fig, "16_validation_vs_rppi", title="Listing-based hedonic price index and the UBOS Residential Property Price Index",
           note="Both series rebased to the first common quarter. RED post dates estimated from listing codes (about one month).")
