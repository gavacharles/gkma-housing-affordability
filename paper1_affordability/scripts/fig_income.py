"""Income figures and table for the manuscript.

  17_parish_median_income   map: modelled median monthly household income by parish (2026 prices)
  18_income_calibration     chart: UNHS 2019/20 sub-region median income vs Census 2024 wealth
  tables/income_inputs.csv  sub-region medians, Gini, sigma and CPI factor used in the paper

  python paper1_affordability/scripts/fig_income.py [--out outputs]
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import _stage
from gkma.config import p
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
cpi = float(pd.read_csv(p("data/external/cpi_uplift.csv")).query("series == 'headline'")["uplift"].iloc[0])

# --- map --------------------------------------------------------------------
import geopandas as gpd  # noqa: E402
pi = gpd.read_file(p("data/external/parish_income.gpkg"))
pi["unit_id"] = pi["DName2016"].astype(str) + "/" + pi["PName2016"].astype(str)
pi["income_2026"] = pi["median_income_2019_20"] * cpi
maps.choropleth(pi, "income_2026", "Modelled median monthly household income by parish (2026 prices)",
                "17_parish_median_income", cmap=maps.SEQ_BLUE, scheme="quantiles", k=5,
                legend_title="UGX per month (quintiles)", min_n_label="Parish not matched to census",
                note=("Parish median = UNHS 2019/20 sub-region median × exp(b × (parish wealth − sub-region mean)); "
                      f"Census 2024 wealth index; uprated by headline CPI (×{cpi:.3f})."))

# --- calibration chart --------------------------------------------------------
cal = pd.read_csv(p("data/external/parish_income_calibration.csv"), index_col=0)
info = json.load(open(p("data/external/parish_income_calibration.json")))
fig, ax = plt.subplots(figsize=(maps.SINGLE * 1.25, maps.SINGLE * 0.95))
hi = {"Kampala": maps.RED[4], "Buganda South": maps.BLUE[4], "Buganda North": maps.BLUE[3]}
for sr, r in cal.iterrows():
    c = hi.get(sr, "#8c8c8c")
    ax.scatter(r["wealth_mean"], r["unhs_median"] / 1000, s=22 if sr in hi else 14, color=c, zorder=3,
               edgecolor="white", linewidth=0.4)
    off = {"Kigezi": (-24, -6), "Busoga": (4, 2)}.get(sr, (3, 2))
    ax.annotate(sr, (r["wealth_mean"], r["unhs_median"] / 1000), xytext=off, textcoords="offset points",
                fontsize=5.4, color=c if sr in hi else "#555555")
x = np.linspace(cal["wealth_mean"].min() - 0.2, cal["wealth_mean"].max() + 0.2, 50)
ax.plot(x, np.exp(info["intercept"] + info["slope_b"] * x) / 1000, color="#4d4d4d", lw=0.8, zorder=2)
ax.set_yscale("log")
ax.set_yticks([75, 100, 150, 200, 300, 500, 700])
ax.set_yticklabels(["75", "100", "150", "200", "300", "500", "700"])
ax.set_xlabel("Household-weighted mean wealth index (Census 2024)")
ax.set_ylabel("Median monthly household income,\nUNHS 2019/20 (UGX thousand, log scale)")
ax.text(0.03, 0.97, f"log(income) = {info['intercept']:.2f} + {info['slope_b']:.3f} × wealth\n"
        f"R² = {info['r2_subregions']:.2f}, n = {info['n_subregions']} sub-regions",
        transform=ax.transAxes, va="top", fontsize=5.8)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(direction="out")
maps._save(fig, "18_income_calibration",
           title="Calibration of the parish income model across the 15 UNHS sub-regions",
           note="Each point is a UNHS 2019/20 sub-region; the line is the fitted relationship used to "
                "scale sub-region medians to parishes.",
           sources="UBOS UNHS 2019/20 (Table 5.21); UBOS NPHC 2024 sub-county profile tables.")

# --- income inputs table -----------------------------------------------------
inc = pd.read_csv(p("data/external/unhs_income_by_unit.csv"))
inc["sigma"] = np.sqrt(2) * norm.ppf((inc["gini"] + 1) / 2)
inc["median_2026"] = inc["median_monthly_income_ugx"] * cpi
g = pi.dropna(subset=["income_2026"])
g = g.assign(d=g["DName2016"].str.title())
q = g.groupby("d")["income_2026"].quantile([0.1, 0.5, 0.9]).unstack()
q.columns = ["parish_p10_2026", "parish_p50_2026", "parish_p90_2026"]
tab = inc.set_index("unit")[["unhs_subregion", "median_monthly_income_ugx", "median_2026", "gini", "sigma"]] \
    .join(q).rename(columns={"median_monthly_income_ugx": "subregion_median_2019_20"})
tab.round(3).to_csv(out / "tables" / "income_inputs.csv")
print(tab.round(0).to_string())
print(f"CPI uplift {cpi:.4f}; calibration {info}")
