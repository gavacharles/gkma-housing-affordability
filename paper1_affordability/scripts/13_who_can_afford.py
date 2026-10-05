"""Who can afford the listed home? Two readings of the index that do not saturate.

The share of households priced out sits at 87-100% in every district, so it cannot rank
areas or show how far out of reach the listed home is. This stage adds:

  1. Position in the income distribution: the share of households who could afford the
     median listed home (log scale, so 0.1% and 2% are distinguishable), the income
     percentile that the qualifying income corresponds to, and the qualifying income in
     household-weighted standard deviations of log income above the area's median
     (z-distance).
  2. Key workers: published earnings of named occupations (NLFS 2021 medians uprated by
     the headline CPI, and the public-service salary scales) set against the qualifying
     incomes, for one and two earners.

Outputs
  tables/income_position.csv      GKMA, districts and sub-counties
  tables/key_workers.csv          occupations x qualifying incomes
  maps/27_income_position, 28_key_workers
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
from gkma.analysis.household import area_incomes, cpi_uplift, income_quantile, share_below, z_distance
from gkma.config import p
from gkma.viz import pubmaps as maps

T = _paper.OUT / "tables"
MIN_N = 20

# ------------------------------------------------------------------ 1. position in the distribution
rows = []
for level, f in [("gkma", "affordability_index_gkma"), ("district", "affordability_index_district"),
                 ("subcounty", "affordability_index_subcounty")]:
    idx = pd.read_csv(T / f"{f}.csv").set_index("area")
    for area, inc in area_incomes(level).items():
        r = idx.loc[area]
        p90 = income_quantile(0.90, inc)
        for tenure, q, n in [("rent", r["rent_income_needed"], r["n_rent"]), ("own", r["own_income_needed"], r["n_sale"])]:
            if pd.isna(q) or n < MIN_N:
                continue
            s = 1 - share_below(q, inc)
            rows.append({"level": level, "area": area, "tenure": tenure, "n": n, "income_needed": q,
                         "median_income": r["median_income"], "share_able": s, "households_able": s * inc["households"].sum(),
                         "percentile_needed": 100 * (1 - s), "z_distance": z_distance(q, inc), "multiple_of_p90": q / p90})
pos = pd.DataFrame(rows)
pos.round(5).to_csv(T / "income_position.csv", index=False)
print(pos[pos["level"] != "subcounty"].round(4).to_string(index=False))

# ------------------------------------------------------------------ 2. key workers
UPRATE_2021 = cpi_uplift("2021-01", "2021-12")
kw = pd.read_csv(p("data/external/key_worker_earnings.csv"))
kw["earnings_2026"] = kw["monthly_gross_ugx"] * np.where(kw["uprate_to_2026"] == "cpi", UPRATE_2021, 1.0)
gk = pd.read_csv(T / "affordability_index_gkma.csv").iloc[0]
dist = pd.read_csv(T / "affordability_index_district.csv").set_index("area")
sub = pos[(pos["level"] == "subcounty") & (pos["tenure"] == "rent")]
floor = pd.read_csv(T / "what_it_takes_ladder.csv").query("area == 'GKMA'").set_index("step")
BARS = {
    "Rent: cheapest sub-county": float(sub["income_needed"].min()),
    "Rent: Wakiso": float(dist.loc["Wakiso", "rent_income_needed"]),
    "Rent: GKMA": float(gk["rent_income_needed"]),
    "Rent: Kampala": float(dist.loc["Kampala", "rent_income_needed"]),
    "Buy: cost-floor 2-bed home, 8%": float(floor.loc[5, "income_needed"]),
    "Buy: GKMA median home": float(gk["own_income_needed"]),
}
rows = []
for _, r in kw.iterrows():
    for earners in (1, 2):
        e = r["earnings_2026"] * earners
        rows.append({"occupation": r["occupation"], "group": r["group"], "earners": earners, "household_income": e,
                     **{f"ratio_{k}": e / v for k, v in BARS.items()}, "verify": r["verify"], "source": r["source"]})
kwt = pd.DataFrame(rows)
kwt.round(4).to_csv(T / "key_workers.csv", index=False)
print(f"CPI uplift 2021 -> Aug 2026: {UPRATE_2021:.4f}")
print({k: round(v) for k, v in BARS.items()})
print(kwt[["occupation", "earners", "household_income"] + [c for c in kwt if c.startswith("ratio_")]].round(2).to_string(index=False))

# ------------------------------------------------------------------ figure 27: position
d = pos.copy()
d["label"] = np.where(d["level"] == "subcounty", d["area"].str.split("/").str[1].str.replace("  ", " ") + " (" +
                      d["area"].str.split("/").str[0] + ")", d["area"])
fig, axes = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.62), gridspec_kw={"wspace": 1.0})
for ax, tenure, title, letter in [(axes[0], "rent", "Rent the median listed 1–2 bedroom home", "a"),
                                  (axes[1], "own", "Buy the median listed house with a mortgage", "b")]:
    g = d[d["tenure"] == tenure].copy()
    g["order"] = g["level"].map({"gkma": 0, "district": 1, "subcounty": 2})
    top = g[g["order"] < 2].sort_values(["order", "share_able"], ascending=[True, False])
    rest = g[g["order"] == 2].sort_values("share_able", ascending=False)
    g = pd.concat([top, rest])
    y = np.arange(len(g))[::-1].astype(float)
    y[len(top):] -= 0.8                                       # gap between summary rows and sub-counties
    x = np.clip(g["share_able"] * 100, 1e-3, None)
    colors = np.where(g["order"] < 2, maps.INK, maps.OKABE_ITO[0])
    ax.hlines(y, 1e-3, x, color="#dedede", lw=0.6)
    ax.scatter(x, y, s=12, c=colors, zorder=3, linewidths=0)
    ax.set_xscale("log")
    ax.set_xlim(1e-3, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.set_yticks(y)
    ax.set_yticklabels(g["label"], fontsize=5.4)
    for t, w in zip(ax.get_yticklabels(), g["order"] < 2):
        t.set_fontweight("bold" if w else "normal")
    ax.set_xlabel("Households who could afford it (log scale)")
    ax.set_title(title, fontsize=6.8, loc="left", pad=8)
    ax.grid(axis="x", color="#ececec", lw=0.4)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(-0.95, 1.06, letter, transform=ax.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "27_income_position",
           title="Share of households who could afford the median listed home",
           note=("Rent at 30% of income (1–2 bedroom homes); ownership on the base mortgage terms (18.3%, 30% deposit, "
                 "20 years, 35% repayment cap). Household incomes are the household-weighted mixture of parish lognormal "
                 f"distributions. Areas with at least {MIN_N} qualifying listings; values below 0.001% are drawn at 0.001%."),
           sources="Listings (RED, Jiji, Uganda Property Centre); modelled parish incomes (UNHS 2019/20, Census 2024).")

# ------------------------------------------------------------------ figure 28: key workers
k = kw.sort_values("earnings_2026").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(maps.FULL, maps.FULL * 0.6))
y = np.arange(len(k))
ax.hlines(y, k["earnings_2026"], 2 * k["earnings_2026"], color="#bdbdbd", lw=0.9)
ax.plot(k["earnings_2026"], y, "o", ms=4, color=maps.OKABE_ITO[0], label="One earner")
ax.plot(2 * k["earnings_2026"], y, "o", ms=4, mfc="white", mec=maps.OKABE_ITO[0], mew=0.9, label="Two earners")
ref_colors = {"Rent": maps.OKABE_ITO[5], "Buy": maps.INK}
for i, (name, v) in enumerate(BARS.items()):
    kind = name.split(":")[0]
    ax.axvline(v, color=ref_colors[kind], lw=0.6, ls=(0, (3, 2)) if kind == "Rent" else "-", zorder=1)
    ax.text(v * 1.025, len(k) + 1.3, name, rotation=90, fontsize=5.2, ha="left", va="top", color=ref_colors[kind],
            bbox={"fc": "white", "ec": "none", "pad": 0.4, "alpha": 0.9})
ax.set_xscale("log")
ax.set_xlim(1e5, 4e7)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1e6:g}m"))
ax.set_yticks(y)
ax.set_yticklabels([o + (" *" if v == "yes" else "") for o, v in zip(k["occupation"], k["verify"])], fontsize=5.8)
ax.set_xlabel("Gross monthly household income, UGX (log scale)")
ax.set_ylim(-0.7, len(k) + 1.5)
ax.grid(axis="x", color="#ececec", lw=0.4, which="both")
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=True, framealpha=0.95, edgecolor="none", loc="lower right", fontsize=6)
maps._save(fig, "28_key_workers",
           title="Key workers' earnings against the incomes needed to rent or buy the median listed home",
           note=("Dashed lines: income needed to rent the median listed 1–2 bedroom home at 30% of income (cheapest "
                 "sub-county with at least 20 listings, Wakiso, GKMA, Kampala). Solid lines: income needed to buy the "
                 "cost-floor 2-bedroom home at 8% over 25 years, and the GKMA median listed house on base mortgage terms. "
                 f"Survey medians (NLFS 2021) uprated by the headline CPI (×{UPRATE_2021:.3f}). * Public-service scales "
                 "reported in the press; to be checked against the Ministry of Public Service circulars."),
           sources="UBOS National Labour Force Survey 2021; Ministry of Public Service salary structures FY2025/26–2026/27 "
                   "(as reported); listings (RED, Jiji, Uganda Property Centre); modelled parish incomes.")
