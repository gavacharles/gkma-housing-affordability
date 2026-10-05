"""What can the median household rent, and where? (paper 3)

Budget = 30% of median household income: the GKMA median (UGX ~164,000 a month) and each
sub-county's own median.

  Aggregate (runs now, from paper-1 tables): the lower quartile, median and upper quartile
  of listed rents in each sub-county against the local budget; the price bands of the
  online single-room market (Jiji, 5 October 2026) against the GKMA budget.
  Listing level (runs when data/processed/listings.gpkg is present): the share of rental
  listings within budget by sub-county and by travel time to the CBD, and the distance from
  every parish to the nearest listing within its own households' budget.

Outputs: tables/affordable_supply_subcounty.csv, affordable_supply_bands.csv
         [listing level] affordable_supply_listings.csv, affordable_supply_parish_distance.csv
         maps/P3_04_affordable_supply [, P3_05_nearest_affordable]
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

import _paper  # noqa: F401
from gkma.analysis.affordability_index import parish_incomes
from gkma.analysis.household import area_incomes, median_income, subcounty_polygons
from gkma.analysis.supply import budget_share, nearest_within_budget
from gkma.config import p
from gkma.viz import pubmaps as maps

P1 = _paper.ROOT / "paper1_affordability/outputs/tables"
T = _paper.OUT / "tables"
SHARE, MIN_N = 0.30, 20
m_g = median_income(area_incomes("gkma")["GKMA"])
B_G = SHARE * m_g
loc = {a: SHARE * median_income(i) for a, i in area_incomes("subcounty").items()}

# ------------------------------------------------------------------ aggregate
r = pd.read_csv(P1 / "02_median_rent.csv").set_index("unit_id")
r = r[r["n"] >= MIN_N].copy()
r["budget_local"] = r.index.map(loc)
r["budget_gkma"] = B_G
r["median_over_budget"] = r["median"] / r["budget_local"]
r["q25_over_budget"] = r["q25"] / r["budget_local"]
r.round(3).to_csv(T / "affordable_supply_subcounty.csv")
bands = pd.read_csv(p("data/external/market/jiji_single_rooms_2026-10-05.csv"))
bands.to_csv(T / "affordable_supply_bands.csv", index=False)
print(f"GKMA budget UGX {B_G:,.0f}; sub-counties where the lower-quartile rent is within the local budget: "
      f"{int((r['q25_over_budget'] <= 1).sum())} of {len(r)}")
print(r[["n", "q25", "median", "budget_local", "q25_over_budget"]].sort_values("q25_over_budget").round(2).to_string())

fig, (a, b) = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.5), gridspec_kw={"width_ratios": [1.6, 1], "wspace": 0.35})
g = r.sort_values("median")
g["label"] = g.index.str.split("/").str[1].str.replace("  ", " ") + " (" + g["DName2016"] + ")"
y = np.arange(len(g))
a.hlines(y, g["q25"], g["q75"], color=maps.SEQ_BLUE[2], lw=3.2, label="Middle half of listed rents")
a.plot(g["median"], y, "o", ms=3.5, color=maps.SEQ_BLUE[4], label="Median listed rent")
a.plot(g["budget_local"], y, "|", ms=9, mew=1.4, color=maps.OKABE_ITO[5], label="30% of the sub-county's median income")
a.axvline(B_G, color=maps.INK, lw=0.6, ls=(0, (3, 2)))
a.text(B_G * 0.96, -0.9, f"30% of GKMA median income\n(UGX {B_G/1e3:,.0f}k)", fontsize=5.3, color=maps.MUTED, va="top", ha="right")
a.set_xscale("log")
a.set_xlim(8e4, 1.5e7)
a.set_ylim(-2.2, len(g) - 0.4)
a.set_xticks([1e5, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7])
a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1e6:g}m"))
a.set_yticks(y)
a.set_yticklabels(g["label"], fontsize=5.6)
a.set_xlabel("Monthly rent, UGX (log scale), all rental listings")
a.legend(frameon=False, fontsize=5.5, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, handlelength=1.4)
for s in ("top", "right"):
    a.spines[s].set_visible(False)
a.text(-0.55, 1.03, "a", transform=a.transAxes, fontsize=8, fontweight="bold")

lo = [0, 130e3, 200e3, 310e3, 1e6]
cols = [maps.OKABE_ITO[2] if l_ < B_G else maps.SEQ_BLUE[3] for l_ in lo]
b.bar(range(len(bands)), bands["ads"], color=cols, edgecolor="none", width=0.7)
for i, v in enumerate(bands["ads"]):
    b.text(i, v + 0.6, str(v), ha="center", fontsize=6)
b.set_xticks(range(len(bands)))
b.set_xticklabels(["< 130k", "130–\n200k", "200–\n310k", "310k–\n1m", "> 1m"], fontsize=5.6)
b.set_ylim(0, 50)
b.set_xlabel("Asking rent, UGX a month")
b.set_ylabel("Single-room ads, all Uganda")
b.text(0.03, 0.98, f"Green: bands reaching below the GKMA\nmedian budget (UGX {B_G/1e3:,.0f}k a month)",
       transform=b.transAxes, fontsize=5.6, va="top", color=maps.MUTED)
for s in ("top", "right"):
    b.spines[s].set_visible(False)
b.text(-0.3, 1.03, "b", transform=b.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "P3_04_affordable_supply",
           title="Listed rents against what the median household can pay",
           note=(f"(a) Sub-counties with at least {MIN_N} rental listings (all sizes); budget = 30% of median household "
                 "income. (b) Price-band counts on Jiji's public 'Single room for rent' page, all of Uganda, 5 October 2026 "
                 "(the 130–200k band straddles the budget)."),
           sources="Listings (RED, Jiji, Uganda Property Centre); jiji.ug; modelled incomes (UNHS 2019/20, Census 2024).")

# ------------------------------------------------------------------ listing level (needs the snapshot)
LP = p("data/processed/listings.gpkg")
if not LP.exists():
    print(f"listing-level analysis skipped: {LP} not found (restore data/paper_snapshot_2026-09-24 and re-run)")
    raise SystemExit
L = gpd.read_file(LP)
L = L[L["listing_type"] == "rent"].copy()
sc = subcounty_polygons().to_crs(L.crs)
L = gpd.sjoin(L, sc[["area_id", "geometry"]], predicate="within").drop(columns="index_right")
acc = pd.read_csv(_paper.ROOT / "paper2_transit/outputs/tables/neighbourhood_accessibility.csv")[["pt", "tt_cbd_min"]]
L["pt"] = L.geometry.to_wkt()
L = L.merge(acc, on="pt", how="left")
L["tt_band"] = pd.cut(L["tt_cbd_min"], [0, 20, 30, 45, 60, 1e3], labels=["<20", "20-30", "30-45", "45-60", "60+"])
rows = []
for key, grp in list(L.groupby("area_id")) + list(L.groupby("tt_band")) + [("GKMA", L)]:
    if len(grp) < MIN_N:
        continue
    rows.append({"group": str(key), "n": len(grp), "share_within_gkma_budget": budget_share(grp["rent_month_ugx"], B_G),
                 "share_within_local_budget": budget_share(grp["rent_month_ugx"], loc.get(key, B_G)),
                 "share_single_rooms": float((grp["bedrooms"] <= 1).mean())})
pd.DataFrame(rows).round(4).to_csv(T / "affordable_supply_listings.csv", index=False)

par = parish_incomes(L.crs).dropna(subset=["households", "income"])
par["budget"] = (SHARE * par["income"]).round(-3)
dist = nearest_within_budget(par, L)
out = par.drop(columns="geometry").join(dist)
out[[c for c in out.columns if c in ("PName2016", "SName2016", "DName2016", "households", "income", "budget",
                                       "nearest_m", "n_within_budget")]].to_csv(T / "affordable_supply_parish_distance.csv", index=False)
par = par.join(dist)
par["nearest_km"] = (par["nearest_m"] / 1000).replace(np.inf, np.nan)
maps.choropleth(par.assign(unit_id=par.index.astype(str)), "nearest_km",
                "Distance to the nearest listing within the parish's budget", "P3_05_nearest_affordable",
                cmap=maps.SEQ_RED, scheme="quantiles", k=5, legend_title="km to nearest affordable listing",
                min_n_label="None within budget",
                note="Budget = 30% of the parish's modelled median household income; straight-line distance.")
