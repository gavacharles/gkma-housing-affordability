"""The visible and the hidden market: who online listings represent (paper 3).

  1. Listing density: listings per 1,000 Census 2024 households, by sub-county.
  2. Concentration: parishes ordered from poorest to richest (modelled median income);
     cumulative share of households against cumulative share of listings, with a
     concentration index C (0 = listings spread like households, 1 = all in the richest).
  3. Visible vs hidden renters: renting households and single-room renters (Census 2024,
     UNHS 2019/20) against the online rental listings and single-room ads.

Inputs: paper-1 aggregate tables (no listing-level data), data/external/market/.
Outputs: tables/visibility_subcounty.csv, visibility_concentration.csv, visibility_renters.csv;
         maps/P3_01_visibility, P3_02_listing_density
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import trapezoid
from matplotlib.ticker import FuncFormatter

import _paper  # noqa: F401
from gkma.analysis.household import area_incomes, median_income, subcounty_polygons
from gkma.config import p
from gkma.viz import pubmaps as maps

P1 = _paper.ROOT / "paper1_affordability/outputs/tables"
T = _paper.OUT / "tables"
T.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ 1. density by sub-county
n = {k: pd.read_csv(P1 / f"{f}.csv").set_index("unit_id")["n"].fillna(0)
     for k, f in [("rent", "02_median_rent"), ("sale_dwelling", "04_median_sale_price"), ("land", "06_median_land_per_decimal")]}
sub = pd.DataFrame(n).fillna(0)
inc = area_incomes("subcounty")
sub["households"] = pd.Series({a: d["households"].sum() for a, d in inc.items()})
sub["median_income"] = pd.Series({a: median_income(d) for a, d in inc.items()})
sub["listings"] = sub[["rent", "sale_dwelling", "land"]].sum(axis=1)
sub["per_1000_hh"] = 1000 * sub["listings"] / sub["households"]
sub["rent_per_1000_hh"] = 1000 * sub["rent"] / sub["households"]
sub = sub.dropna(subset=["households"])
sub.index.name = "area"
sub.round(3).to_csv(T / "visibility_subcounty.csv")
print("listings in sub-counties:", int(sub["listings"].sum()), "| households:", int(sub["households"].sum()))
print("Spearman (density, median income):", round(sub[["per_1000_hh", "median_income"]].corr("spearman").iloc[0, 1], 3))

# ------------------------------------------------------------------ 2. concentration across parishes
par = pd.read_csv(P1 / "affordability_index_parish.csv").dropna(subset=["households", "median_income"])
par = par.sort_values("median_income").reset_index(drop=True)
curves, rows = {}, []
for col, lab in [("n_rent", "1–2 bedroom rentals"), ("n_sale", "Houses and apartments for sale")]:
    x = np.r_[0, par["households"].cumsum() / par["households"].sum()]
    y = np.r_[0, par[col].fillna(0).cumsum() / par[col].fillna(0).sum()]
    C = 1 - 2 * trapezoid(y, x)
    top20 = 1 - np.interp(0.8, x, y)
    bottom50 = np.interp(0.5, x, y)
    curves[lab] = (x, y)
    rows.append({"listings": lab, "n": int(par[col].sum()), "concentration_index": C,
                 "share_in_richest_20pct_hh": top20, "share_in_poorest_50pct_hh": bottom50})
conc = pd.DataFrame(rows)
conc.round(4).to_csv(T / "visibility_concentration.csv", index=False)
print(conc.round(3).to_string(index=False))

# ------------------------------------------------------------------ 3. visible vs hidden renters
ten = pd.read_csv(p("data/external/market/housing_tenure.csv")).set_index("area")
jiji = pd.read_csv(p("data/external/market/jiji_single_rooms_2026-10-05.csv"))
rent_by_d = sub.groupby(sub.index.str.split("/").str[0])["rent"].sum()
r = ten.copy()
r["renting_households"] = r["households"] * r["share_rented"]
r["single_room_renters"] = r["renting_households"] * r["share_renters_one_room"]
r["online_rental_listings"] = rent_by_d.reindex(r.index)
r["renters_per_listing"] = r["renting_households"] / r["online_rental_listings"]
r.round(1).to_csv(T / "visibility_renters.csv")
print(r[["renting_households", "single_room_renters", "online_rental_listings", "renters_per_listing"]].round(0).to_string())
print("Jiji single-room ads, all Uganda (5 Oct 2026):", int(jiji["ads"].sum()))

# ------------------------------------------------------------------ figure P3_01
fig, (a, b) = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.42), gridspec_kw={"wspace": 0.25})
for (lab, (x, y)), c in zip(curves.items(), [maps.OKABE_ITO[5], maps.OKABE_ITO[0]]):
    Cv = conc.set_index("listings").loc[lab, "concentration_index"]
    a.plot(x * 100, y * 100, color=c, lw=1.4, label=f"{lab} (C = {Cv:.2f})")
a.plot([0, 100], [0, 100], color="#bdbdbd", lw=0.6, ls=(0, (3, 2)))
a.text(62, 70, "Listings spread\nlike households", fontsize=5.5, color=maps.MUTED, rotation=0)
a.set_xlabel("Households, cumulative % (parishes from poorest to richest)")
a.set_ylabel("Listings, cumulative %")
a.set_xlim(0, 100)
a.set_ylim(0, 100)
a.legend(frameon=False, fontsize=5.6, loc="upper left")
a.text(-0.2, 1.04, "a", transform=a.transAxes, fontsize=8, fontweight="bold")
for s in ("top", "right"):
    a.spines[s].set_visible(False)

bars = [("Renting households, Kampala (Census 2024)", float(r.loc["Kampala", "renting_households"]), maps.SEQ_BLUE[3]),
        ("…of which in a single room (UNHS share)", float(r.loc["Kampala", "single_room_renters"]), maps.SEQ_BLUE[2]),
        ("Online rental listings, Kampala (2025–26)", float(r.loc["Kampala", "online_rental_listings"]), maps.OKABE_ITO[1]),
        ("Online single-room ads, all Uganda (5 Oct 2026)", float(jiji["ads"].sum()), maps.OKABE_ITO[5])]
y = np.arange(len(bars))[::-1]
b.barh(y, [v for _, v, _ in bars], color=[c for *_, c in bars], height=0.42, edgecolor="none")
for yy, (t, v, _) in zip(y, bars):
    b.text(v * 1.15, yy, f"{v:,.0f}", va="center", fontsize=6)
    b.text(10.5, yy + 0.3, t, va="bottom", fontsize=5.8)
b.set_xscale("log")
b.set_xlim(10, 5e6)
b.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
b.set_yticks([])
b.set_ylim(-0.5, len(bars) - 0.1)
b.set_xlabel("Number (log scale)")
for s in ("top", "right"):
    b.spines[s].set_visible(False)
b.spines["left"].set_visible(False)
b.text(-0.05, 1.04, "b", transform=b.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "P3_01_visibility",
           title="Who the online market represents",
           note=("(a) Concentration curves: GKMA parishes ordered by modelled median household income; C is the "
                 "concentration index (0 = listings distributed like households). (b) The rental market that households "
                 "use and the part of it that appears online. Single-room renters = renting households × the UNHS 2019/20 "
                 "share of Kampala renters using one sleeping room (81%)."),
           sources="Listings (RED, Jiji, Uganda Property Centre); UBOS Census 2024; UNHS 2019/20 Tables 8.1 and 8.3; "
                   "Jiji 'Single room for rent' category page (5 October 2026).")

# ------------------------------------------------------------------ figure P3_02: density map
sc = subcounty_polygons().merge(sub[["per_1000_hh", "listings"]], left_on="area_id", right_index=True, how="left")
sc.loc[sc["listings"].fillna(0) == 0, "per_1000_hh"] = np.nan
maps.choropleth(sc, "per_1000_hh", "Online listings per 1,000 households, by sub-county", "P3_02_listing_density",
                cmap=maps.SEQ_BLUE, scheme="quantiles", k=5, legend_title="Listings per 1,000 households",
                min_n_label="No listings",
                note="All deduplicated listings (rentals, dwellings and land for sale), 2025–26; Census 2024 households.")
