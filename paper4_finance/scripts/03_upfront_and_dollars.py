"""Barriers before the rent: advance payments and dollar pricing (paper 4).

Needs the listing snapshot (data/processed/listings.gpkg, with title and description).

  Upfront terms   gkma.clean.payment_terms: months of rent asked in advance and any security
                  deposit, from the listing text. Upfront cash = (advance + deposit months) x
                  monthly rent, expressed in months of the GKMA median household income.
  Dollar pricing  share of listings priced in US dollars (currency field, after cleaning), by
                  market, segment (bedrooms) and district; for USD rents, the shilling cost of a
                  10% depreciation, for exchange-rate risk.

Outputs: tables/upfront_terms.csv, upfront_cash.csv, dollar_pricing.csv; maps/P4_04_upfront, P4_05_dollars
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from gkma.analysis.household import area_incomes, median_income
from gkma.clean.payment_terms import payment_terms
from gkma.config import p
from gkma.viz import pubmaps as maps

T = _paper.OUT / "tables"
LP = p("data/processed/listings.gpkg")
if not LP.exists():
    print(f"skipped: {LP} not found. Restore the paper snapshot (data/paper_snapshot_2026-09-24) to "
          "data/processed/ and re-run.")
    raise SystemExit
L = gpd.read_file(LP)
m_g = median_income(area_incomes("gkma")["GKMA"])
L["segment"] = pd.cut(L["bedrooms"].fillna(0), [-1, 1, 2, 3, 99], labels=["Single room / 1 bed", "2 beds", "3 beds", "4+ beds"])
L["district"] = L.get("district", L.get("subcounty_id", pd.Series("", index=L.index)).astype(str).str.split("/").str[0])

# ------------------------------------------------------------------ upfront terms (rentals)
R = L[L["listing_type"] == "rent"].copy()
R = R.join(payment_terms(R))
R["upfront_cash"] = R["upfront_months"] * R["rent_month_ugx"]
R["upfront_income_months"] = R["upfront_cash"] / m_g
terms = R.groupby("segment", observed=True).agg(
    n=("terms_stated", "size"), share_terms_stated=("terms_stated", "mean"),
    median_advance=("advance_months", "median"), median_deposit=("deposit_months", "median"),
    median_upfront_cash=("upfront_cash", "median"), median_upfront_income_months=("upfront_income_months", "median"))
terms.loc["All rentals"] = [len(R), R["terms_stated"].mean(), R["advance_months"].median(), R["deposit_months"].median(),
                            R["upfront_cash"].median(), R["upfront_income_months"].median()]
terms.round(4).to_csv(T / "upfront_terms.csv")
R["advance_months"].value_counts().sort_index().rename("listings").to_csv(T / "upfront_cash.csv")
print(terms.round(3).to_string())

# ------------------------------------------------------------------ dollar pricing
L["usd"] = (L["currency"] == "USD").astype(int)
dol = L.groupby(["listing_type", "segment"], observed=True)["usd"].agg(["size", "mean"]).rename(
    columns={"size": "n", "mean": "share_usd"})
dol.round(4).to_csv(T / "dollar_pricing.csv")
print(dol.round(3).to_string())

# ------------------------------------------------------------------ figures
fig, (a, b) = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.42), gridspec_kw={"wspace": 0.4})
vc = R["advance_months"].dropna().astype(int).value_counts().sort_index()
a.bar(vc.index, vc.values, color=maps.SEQ_BLUE[3], width=0.7, edgecolor="none")
a.set_xlabel("Months of rent asked in advance (where stated)")
a.set_ylabel("Rental listings")
a.set_xticks(range(1, 13))
seg = terms.drop(index="All rentals")
b.barh(seg.index.astype(str), seg["median_upfront_income_months"], color=maps.OKABE_ITO[1], height=0.6)
b.axvline(1, color=maps.INK, lw=0.6, ls=(0, (3, 2)))
b.set_xlabel("Median upfront cash, in months of GKMA median income")
for ax, l_ in [(a, "a"), (b, "b")]:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(-0.15, 1.03, l_, transform=ax.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "P4_04_upfront", title="Advance rent and the cash needed to move in",
           note="Terms read from listing text; upfront cash = (advance + deposit months) × asking rent.",
           sources="Listings (RED, Jiji, Uganda Property Centre); modelled incomes (UNHS 2019/20, Census 2024).")

fig, ax = plt.subplots(figsize=(maps.SINGLE, maps.SINGLE * 0.7))
d = dol.reset_index()
for k, (lt, g) in enumerate(d.groupby("listing_type")):
    ax.bar(np.arange(len(g)) + k * 0.4, g["share_usd"] * 100, 0.38, label=lt, color=[maps.OKABE_ITO[0], maps.OKABE_ITO[1]][k])
ax.set_xticks(np.arange(d["segment"].nunique()) + 0.2)
ax.set_xticklabels(d["segment"].unique().astype(str), fontsize=6)
ax.set_ylabel("Listings priced in US dollars (%)")
ax.legend(frameon=False, fontsize=6)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
maps._save(fig, "P4_05_dollars", title="Share of listings priced in US dollars, by market and size",
           sources="Listings (RED, Jiji, Uganda Property Centre).")
