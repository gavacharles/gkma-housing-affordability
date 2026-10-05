"""The Ugandan route to ownership: buy a plot, then build in stages (paper 4).

Most owner-occupiers in Greater Kampala did not use a mortgage; they bought a plot and
built over years from savings. This stage prices that route by sub-county and sets it
against saving the deposit for the median listed house.

  plot        a 50 x 100 ft plot (11.48 decimals, the common "standard plot") and a 50 x 50 ft
              plot (5.74 decimals) at the sub-county's median asking land price per decimal
              (paper 1; sub-counties with at least 20 land listings)
  build       a 2-bedroom, 50 m² house: shell at the CAHF shell rate, then finishes up to the
              standard bungalow rate (both indexed to 2026)
  self-build  illustrative owner-built starter: 30 m² at 60% of the CAHF rates (own and informal labour,
              no contractor overheads); an assumption, not a benchmark
  saving      20% of the sub-county's median household income (sensitivity: 10%, 30%), no
              interest and no cost growth; years = cost / (12 x saving)
  benchmark   years to save the 30% deposit on the district's median listed house

Outputs: tables/plot_and_build_subcounty.csv; maps/P4_02_plot_and_build, P4_03_plot_years
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from gkma.analysis.household import area_incomes, median_income, subcounty_polygons
from gkma.config import load_config, p
from gkma.viz import pubmaps as maps

P1 = _paper.ROOT / "paper1_affordability/outputs/tables"
T = _paper.OUT / "tables"
MIN_N, M2 = 20, 50
PLOTS = {"50 × 100 ft": 50 * 100 / 435.6, "50 × 50 ft": 50 * 50 / 435.6}
SAVE = [0.10, 0.20, 0.30]
cost = pd.read_csv(p("data/external/replacement_cost_rates.csv")).set_index("cost_class")
SHELL = M2 * cost.loc["shell", "rate_ugx_per_m2"]
FINISH = M2 * (cost.loc["bungalow_standard", "rate_ugx_per_m2"] - cost.loc["shell", "rate_ugx_per_m2"])
SELF = 30 * 0.60 * cost.loc["bungalow_standard", "rate_ugx_per_m2"]
DEPOSIT = load_config()["affordability_index"]["mortgage"]["deposit"]

land = pd.read_csv(P1 / "06_median_land_per_decimal.csv")
land = land[land["n"] >= MIN_N].set_index("unit_id")
inc = {a: median_income(i) for a, i in area_incomes("subcounty").items()}
dist = pd.read_csv(P1 / "affordability_index_district.csv").set_index("area")
rows = []
for area, r in land.iterrows():
    m = inc[area]
    d = area.split("/")[0]
    dep = DEPOSIT * dist.loc[d, "median_price"] if d in dist.index and pd.notna(dist.loc[d, "median_price"]) else np.nan
    for s in SAVE:
        yearly = 12 * s * m
        row = {"area": area, "district": d, "saving_rate": s, "median_income": m, "land_per_decimal": r["median"],
               "n_land": r["n"], "shell_cost": SHELL, "finish_cost": FINISH, "years_shell": SHELL / yearly,
               "years_finish": FINISH / yearly, "self_build_cost": SELF, "years_self_build": SELF / yearly,
               "deposit_median_house": dep, "years_deposit": dep / yearly}
        for k, dec in PLOTS.items():
            row[f"plot_cost_{k}"] = r["median"] * dec
            row[f"years_plot_{k}"] = r["median"] * dec / yearly
            row[f"plot_to_annual_income_{k}"] = r["median"] * dec / (12 * m)
        rows.append(row)
pb = pd.DataFrame(rows)
pb.round(4).to_csv(T / "plot_and_build_subcounty.csv", index=False)
base = pb[pb["saving_rate"] == 0.20].copy()
base["years_total_small"] = base["years_plot_50 × 50 ft"] + base["years_shell"] + base["years_finish"]
base["years_total_std"] = base["years_plot_50 × 100 ft"] + base["years_shell"] + base["years_finish"]
base["years_total_self"] = base["years_plot_50 × 50 ft"] + base["years_self_build"]
print(f"shell UGX {SHELL/1e6:.1f}m, finishes UGX {FINISH/1e6:.1f}m (50 m²)")
print(base[["area", "median_income", "land_per_decimal", "years_plot_50 × 50 ft", "years_plot_50 × 100 ft", "years_shell",
            "years_finish", "years_total_small", "years_total_self", "years_deposit"]].sort_values("years_total_small").round(1).to_string(index=False))

# ------------------------------------------------------------------ figure: years of saving, stacked
g = base.sort_values("years_total_small")
g["label"] = g["area"].str.split("/").str[1].str.replace("  ", " ") + " (" + g["district"] + ")"
fig, ax = plt.subplots(figsize=(maps.FULL, maps.FULL * 0.55))
y = np.arange(len(g))[::-1]
left = np.zeros(len(g))
for col, lab, c in [("years_plot_50 × 50 ft", "Plot, 50 × 50 ft", maps.OKABE_ITO[2]),
                    ("years_shell", "Shell, 2 bedrooms (50 m²)", maps.SEQ_BLUE[3]),
                    ("years_finish", "Finishes", maps.SEQ_BLUE[1])]:
    ax.barh(y, g[col], left=left, color=c, height=0.62, label=lab, edgecolor="white", linewidth=0.5)
    left += g[col].to_numpy()
ax.plot(g["years_plot_50 × 100 ft"] + g["years_shell"] + g["years_finish"], y, "|", ms=8, mew=1.2, color=maps.INK,
        label="Total with a 50 × 100 ft plot")
ax.plot(g["years_total_self"], y, "o", ms=3.4, color=maps.OKABE_ITO[1], label="Self-build starter: small plot + 30 m² at 60% of cost")
ax.plot(g["years_deposit"], y, "D", ms=3.2, mfc="white", mec=maps.OKABE_ITO[5], mew=0.9,
        label=f"Saving the {DEPOSIT:.0%} deposit on the district's median listed house")
ax.set_yticks(y)
ax.set_yticklabels(g["label"], fontsize=5.8)
ax.set_xlabel("Years of saving 20% of the sub-county's median household income")
ax.set_xlim(0, float(np.nanmax(g[["years_deposit", "years_total_std"]].to_numpy())) * 1.05)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#ececec", lw=0.4)
ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=5.6, loc="upper center", bbox_to_anchor=(0.42, -0.12), ncol=3)
maps._save(fig, "P4_02_plot_and_build",
           title="Years of saving to buy a plot and build in stages, against saving a mortgage deposit",
           note=(f"Plot at the sub-county's median asking price per decimal (sub-counties with at least {MIN_N} land "
                 f"listings); a 2-bedroom 50 m² house: shell UGX {SHELL/1e6:.0f} million, finishes UGX {FINISH/1e6:.0f} "
                 f"million (CAHF benchmarks indexed to 2026). Self-build starter: UGX {SELF/1e6:.0f} million (assumption). Saving 20% of median household income, without interest or "
                 "cost growth."),
           sources="Land listings (RED, Jiji, Uganda Property Centre); CAHF (2020) indexed with the UBOS CIPI; modelled "
                   "parish incomes (UNHS 2019/20, Census 2024).")

# ------------------------------------------------------------------ map: plot price in years of income
sc = subcounty_polygons().merge(base[["area", "plot_to_annual_income_50 × 100 ft"]], left_on="area_id", right_on="area",
                                how="left")
maps.choropleth(sc, "plot_to_annual_income_50 × 100 ft", "Price of a standard 50 × 100 ft plot in years of median "
                "household income, by sub-county", "P4_03_plot_years", cmap=maps.SEQ_RED, scheme="quantiles", k=5,
                legend_title="Years of median income", min_n_label=f"Fewer than {MIN_N} land listings",
                note="Median asking price per decimal × 11.48 decimals, divided by the sub-county's annual median income.")
