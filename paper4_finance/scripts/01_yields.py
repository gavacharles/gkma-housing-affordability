"""Who is the formal market priced for? Rental yields against the cost of money (paper 4).

  Gross yield, by sub-county = 12 x median asking rent per bedroom / median asking price per
  bedroom (paper-1 tables; sub-counties with at least 20 listings of each). The two medians
  come from different dwellings (rentals are more often apartments, sale listings houses on
  larger plots), so this is an indicative yield; the matched version below standardises the
  dwelling and runs when the listing snapshot is present.
  Benchmarks: Bank of Uganda weighted-average lending rate, 364-day Treasury bill yield and
  headline inflation (12-month means to August 2026); UBOS Residential Property Price Index
  (RPPI) growth as the capital-gain component.

Outputs: tables/yields_subcounty.csv, yields_benchmarks.csv [, yields_matched.csv];
         maps/P4_01_yields
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from gkma.analysis.affordability_index import bou_lending_rate
from gkma.analysis.household import headline_cpi
from gkma.config import p
from gkma.viz import pubmaps as maps

P1 = _paper.ROOT / "paper1_affordability/outputs/tables"
T = _paper.OUT / "tables"
MIN_N = 20
# pooled GKMA medians reported in paper 1, Section 5.1 (all rentals; houses and apartments for sale)
GKMA_RENT_PER_BED, GKMA_PRICE_PER_BED = 700_000, 140_000_000

rb = pd.read_csv(P1 / "03_median_rent_per_bedroom.csv").set_index("unit_id")
pb = pd.read_csv(P1 / "05_median_price_per_bedroom.csv").set_index("unit_id")
y = rb[["median", "n", "DName2016"]].rename(columns={"median": "rent_per_bed", "n": "n_rent"}).join(
    pb[["median", "n"]].rename(columns={"median": "price_per_bed", "n": "n_sale"}))
y = y[(y["n_rent"] >= MIN_N) & (y["n_sale"] >= MIN_N)].copy()
y["gross_yield"] = 12 * y["rent_per_bed"] / y["price_per_bed"]
y["price_to_annual_rent"] = 1 / y["gross_yield"]
y.round(5).to_csv(T / "yields_subcounty.csv")

# ------------------------------------------------------------------ benchmarks
poe = pd.read_csv(p("data/external/mofped/datasets/MOF_POE.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
cpi = headline_cpi()
tbill = float(poe["I_TBILL_AY_364"].dropna().tail(12).mean()) / 100
infl = float(cpi.iloc[-1] / cpi.iloc[-13] - 1)
rppi = pd.read_csv(p("data/external/ubos_rppi_quarterly.csv"), parse_dates=["period_start"])
h = rppi[rppi["area"] == "Headline"].set_index("period_start")["rppi"].sort_index()
yrs = (h.index[-1] - h.index[0]).days / 365.25
rppi_cagr = float((h.iloc[-1] / h.iloc[0]) ** (1 / yrs) - 1)
rppi_1y = float(h.iloc[-1] / h.iloc[-5] - 1)
cpi_q = cpi.resample("QS").mean().reindex(h.index, method="nearest")
cpi_cagr = float((cpi_q.iloc[-1] / cpi_q.iloc[0]) ** (1 / yrs) - 1)
bench = {"lending_rate": bou_lending_rate(), "tbill_364": tbill, "inflation_12m": infl,
         "rppi_cagr": rppi_cagr, "rppi_1y": rppi_1y, "cpi_cagr_same_period": cpi_cagr,
         "rppi_period": f"{h.index[0]:%Y-%m} to {h.index[-1]:%Y-%m}",
         "gkma_gross_yield": 12 * GKMA_RENT_PER_BED / GKMA_PRICE_PER_BED,
         "median_subcounty_yield": float(y["gross_yield"].median())}
bench["gkma_total_return"] = bench["gkma_gross_yield"] + rppi_cagr
json.dump(bench, open(T / "yields_benchmarks.json", "w"), indent=2)
print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in bench.items()}, indent=2))
print(y.sort_values("gross_yield").round(4).to_string())

# ------------------------------------------------------------------ figure
fig, (a, b) = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.48), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.5})
g = y.sort_values("gross_yield")
g["label"] = g.index.str.split("/").str[1].str.replace("  ", " ") + " (" + g["DName2016"] + ")"
yy = np.arange(len(g))
a.hlines(yy, 0, g["gross_yield"] * 100, color="#dedede", lw=0.6)
a.plot(g["gross_yield"] * 100, yy, "o", ms=3.8, color=maps.OKABE_ITO[0])
refs = [(bench["lending_rate"], "Lending rate", maps.INK, "-"), (tbill, "364-day T-bill", maps.OKABE_ITO[5], (0, (3, 2))),
        (infl, "Inflation", maps.MUTED, (0, (1, 1.5)))]
for v, lab, c, ls in refs:
    a.axvline(v * 100, color=c, lw=0.7, ls=ls)
    a.text(v * 100 + 0.3, len(g) + 1.5, f"{lab}\n{v:.1%}", fontsize=5.3, color=c, va="top")
a.set_yticks(yy)
a.set_yticklabels(g["label"], fontsize=5.6)
a.set_xlabel("Gross rental yield (%), asking rent ÷ asking price, per bedroom")
a.set_xlim(0, max(20, bench["lending_rate"] * 100 + 3))
a.set_ylim(-0.7, len(g) + 1.6)
for s in ("top", "right"):
    a.spines[s].set_visible(False)
a.text(-0.62, 1.03, "a", transform=a.transAxes, fontsize=8, fontweight="bold")

base = h.iloc[0]
b.plot(h.index, 100 * h / base, color=maps.OKABE_ITO[0], lw=1.6, label="House prices (UBOS RPPI, headline)")
b.plot(cpi_q.index, 100 * cpi_q / cpi_q.iloc[0], color=maps.OKABE_ITO[5], lw=1.6, label="Consumer prices (CPI)")
b.axhline(100, color="#bdbdbd", lw=0.5)
b.set_ylabel(f"Index, {h.index[0].year} Q{(h.index[0].month - 1) // 3 + 1} = 100")
b.legend(frameon=False, fontsize=5.8, loc="upper left")
for s in ("top", "right"):
    b.spines[s].set_visible(False)
b.text(h.index[-1], 100 * h.iloc[-1] / base - 6, f"{rppi_cagr:.1%} a year", fontsize=5.6, ha="right", color=maps.OKABE_ITO[0])
b.text(cpi_q.index[-1], 100 * cpi_q.iloc[-1] / cpi_q.iloc[0] + 3, f"{cpi_cagr:.1%} a year", fontsize=5.6, ha="right",
       color=maps.OKABE_ITO[5])
b.text(-0.22, 1.03, "b", transform=b.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "P4_01_yields",
           title="Rental yields and house-price growth against the cost of money",
           note=(f"(a) Sub-counties with at least {MIN_N} rental and {MIN_N} sale listings; rents and prices are medians per "
                 "bedroom from different dwellings, so yields are indicative. Benchmarks are 12-month means to August 2026. "
                 f"(b) Quarterly, {bench['rppi_period']}."),
           sources="Listings (RED, Jiji, Uganda Property Centre); Bank of Uganda via the MoFPED Macro Data Portal; "
                   "UBOS Residential Property Price Index.")

# ------------------------------------------------------------------ matched yields (needs the snapshot)
LP = p("data/processed/listings.gpkg")
if not LP.exists():
    print(f"matched yields skipped: {LP} not found")
    raise SystemExit
import geopandas as gpd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

from gkma.analysis.household import subcounty_polygons  # noqa: E402

L = gpd.read_file(LP)
L = L[L["ptype"].isin(["house", "apartment"]) & L["bedrooms"].between(1, 5)].copy()
L = gpd.sjoin(L, subcounty_polygons().to_crs(L.crs)[["area_id", "geometry"]], predicate="within")
keep = L.groupby("area_id")["listing_type"].agg(lambda s: min((s == "rent").sum(), (s == "sale").sum()))
L = L[L["area_id"].isin(keep[keep >= MIN_N].index)]
L["log_value"] = np.log(np.where(L["listing_type"] == "rent", L["rent_month_ugx"] * 12, L["price_ugx"]))
fit = smf.ols("log_value ~ C(listing_type) * C(area_id) + bedrooms + I(bedrooms**2) + C(ptype)", data=L).fit(
    cov_type="cluster", cov_kws={"groups": L["area_id"]})
std = pd.DataFrame([{"area_id": a, "bedrooms": 2, "ptype": "house", "listing_type": t}
                    for a in L["area_id"].unique() for t in ("rent", "sale")])
std["pred"] = np.exp(fit.predict(std))
m = std.pivot(index="area_id", columns="listing_type", values="pred")
m["matched_gross_yield"] = m["rent"] / m["sale"]
m.round(5).to_csv(T / "yields_matched.csv")
print(m.round(4).to_string())
