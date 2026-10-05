"""What would it take? Policy counterfactuals for the Ownership Affordability Index.

Starts from the published index (tables/affordability_index_*.csv) and the household
income model; no listing-level data are needed.

  1. Price x interest-rate surface of the GKMA OAI (deposit and term at the base case).
  2. A cumulative policy ladder for the GKMA and districts: longer term, cheaper credit,
     free land (price less the median land share), and the cost-floor home.
  3. The price at which the median household could just buy (OAI = 100), by district,
     under base and concessional terms.
  4. The cost floor: a minimal formal home built at CAHF benchmark cost on a small titled
     plot (50 x 50 ft = 5.74 decimals) at each sub-county's median land price, with no
     developer margin. If this home is out of reach, no market price correction can fix
     affordability; only incomes, land or finance can.

Outputs
  tables/what_it_takes_surface.csv        GKMA OAI over price share x rate
  tables/what_it_takes_ladder.csv         OAI, share and households able, by scenario and area
  tables/what_it_takes_price_for_100.csv  price at OAI = 100, by area and terms
  tables/cost_floor_subcounty.csv         minimal formal home by sub-county
  maps/25_what_it_takes, 26_cost_floor
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
from gkma.analysis.affordability_index import bou_lending_rate, monthly_payment
from gkma.analysis.household import area_incomes, median_income, share_below
from gkma.config import load_config, p
from gkma.viz import pubmaps as maps

T = _paper.OUT / "tables"
cfg = load_config()["affordability_index"]["mortgage"]
BASE = {"rate": bou_lending_rate(), "deposit": cfg["deposit"], "term_years": cfg["term_years"], "cap": cfg["cap"]}
LAND_SHARE = float(pd.read_csv(T / "land_value_scenarios.csv").set_index("m2_per_bedroom").loc[32, "median_land_share"])
COST = pd.read_csv(p("data/external/replacement_cost_rates.csv")).set_index("cost_class")
PLOT_DEC = 50 * 50 / 435.6                 # 50 x 50 ft plot in decimals (1 decimal = 435.6 sq ft)
HOMES = {"1-bedroom, 30 m²": 30, "2-bedroom, 50 m²": 50}
MIN_LAND_N = 20

idx = pd.concat([pd.read_csv(T / "affordability_index_gkma.csv"), pd.read_csv(T / "affordability_index_district.csv")])
idx = idx.dropna(subset=["median_price"]).set_index("area")
inc = {**area_incomes("gkma"), **area_incomes("district")}


def qualifying(price, rate, deposit, term, cap):
    return monthly_payment(price * (1 - deposit), rate, term) / cap


def oai(price, m, **t):
    return 100 * m / qualifying(price, t["rate"], t["deposit"], t["term_years"], t["cap"])


# ------------------------------------------------------------------ 1. surface (GKMA)
m_g, P_g = median_income(inc["GKMA"]), float(idx.loc["GKMA", "median_price"])
shares = np.round(np.arange(0.02, 1.0001, 0.02), 2)
rates = np.round(np.arange(0.02, 0.2401, 0.005), 3)
surf = pd.DataFrame([{"price_share": s, "rate": r, "oai": oai(P_g * s, m_g, **{**BASE, "rate": r})}
                     for s in shares for r in rates])
surf.round(4).to_csv(T / "what_it_takes_surface.csv", index=False)

# ------------------------------------------------------------------ 2. cost floor by sub-county
land = pd.read_csv(T / "06_median_land_per_decimal.csv")
land = land[land["n"] >= MIN_LAND_N].rename(columns={"unit_id": "area", "median": "land_per_decimal"})
sub_inc = area_incomes("subcounty")
rows = []
for _, r in land.iterrows():
    if r["area"] not in sub_inc:
        continue
    i = sub_inc[r["area"]]
    m = median_income(i)
    for home, m2 in HOMES.items():
        for basis, col in [("construction cost", "rate_ugx_per_m2"), ("full development cost", "rate_full_ugx_per_m2")]:
            price = r["land_per_decimal"] * PLOT_DEC + m2 * COST.loc["bungalow_standard", col]
            q = qualifying(price, BASE["rate"], BASE["deposit"], BASE["term_years"], BASE["cap"])
            rows.append({"area": r["area"], "district": r["DName2016"], "home": home, "basis": basis,
                         "land_per_decimal": r["land_per_decimal"], "n_land": r["n"], "plot_cost": r["land_per_decimal"] * PLOT_DEC,
                         "build_cost": m2 * COST.loc["bungalow_standard", col], "price": price, "median_income": m,
                         "income_needed": q, "oai": 100 * m / q, "share_able": 1 - share_below(q, i),
                         "households_able": i["households"].sum() * (1 - share_below(q, i))})
floor = pd.DataFrame(rows)
floor.round(4).to_csv(T / "cost_floor_subcounty.csv", index=False)
cf = floor[(floor["basis"] == "construction cost")]
# GKMA cost floor: median-income household, cheapest-quartile plot among sub-counties with land data
cheap_land = float(land["land_per_decimal"].quantile(0.25))
FLOOR_PRICE = {h: cheap_land * PLOT_DEC + m2 * COST.loc["bungalow_standard", "rate_ugx_per_m2"] for h, m2 in HOMES.items()}

# ------------------------------------------------------------------ 3. ladder (cumulative)
LADDER = [
    ("Median listed home, 18.3%, 20 years", lambda P: (P, BASE)),
    ("+ 25-year term", lambda P: (P, {**BASE, "term_years": 25})),
    ("+ rate cut to 12%", lambda P: (P, {**BASE, "term_years": 25, "rate": 0.12})),
    ("+ rate cut to 8%", lambda P: (P, {**BASE, "term_years": 25, "rate": 0.08})),
    ("+ free land", lambda P: (P * (1 - LAND_SHARE), {**BASE, "term_years": 25, "rate": 0.08})),
    ("Cost-floor 2-bed home, 8%, 25 years", lambda P: (FLOOR_PRICE["2-bedroom, 50 m²"], {**BASE, "term_years": 25, "rate": 0.08})),
    ("Cost-floor 1-bed home, 8%, 25 years", lambda P: (FLOOR_PRICE["1-bedroom, 30 m²"], {**BASE, "term_years": 25, "rate": 0.08})),
]
rows = []
for area in idx.index:
    m, P, i = median_income(inc[area]), float(idx.loc[area, "median_price"]), inc[area]
    for k, (name, f) in enumerate(LADDER):
        price, t = f(P)
        q = qualifying(price, t["rate"], t["deposit"], t["term_years"], t["cap"])
        rows.append({"area": area, "step": k, "scenario": name, "price": price, "rate": t["rate"],
                     "term_years": t["term_years"], "income_needed": q, "oai": 100 * m / q,
                     "share_able": 1 - share_below(q, i), "households_able": i["households"].sum() * (1 - share_below(q, i))})
ladder = pd.DataFrame(rows)
ladder.round(4).to_csv(T / "what_it_takes_ladder.csv", index=False)

# ------------------------------------------------------------------ 4. price for OAI = 100
rows = []
for area in idx.index:
    m = median_income(inc[area])
    for terms, t in [("base (18.3%, 20 yrs, 30% deposit)", BASE),
                     ("concessional (8%, 25 yrs, 30% deposit)", {**BASE, "rate": 0.08, "term_years": 25}),
                     ("concessional, 10% deposit (8%, 25 yrs)", {**BASE, "rate": 0.08, "term_years": 25, "deposit": 0.10})]:
        unit = qualifying(1.0, t["rate"], t["deposit"], t["term_years"], t["cap"])     # qualifying income per UGX of price
        price100 = m / unit
        rows.append({"area": area, "terms": terms, "median_income": m, "median_price": float(idx.loc[area, "median_price"]),
                     "price_oai_100": price100, "price_ratio": price100 / float(idx.loc[area, "median_price"])})
p100 = pd.DataFrame(rows)
p100.round(4).to_csv(T / "what_it_takes_price_for_100.csv", index=False)

print(f"rate {BASE['rate']:.4f}; land share {LAND_SHARE:.3f}; cheapest-quartile land/decimal {cheap_land:,.0f}")
print(ladder[ladder["area"] == "GKMA"][["scenario", "price", "oai", "share_able", "households_able"]].round(3).to_string(index=False))
print(p100.round(3).to_string(index=False))
print(cf.groupby("home")[["oai", "share_able"]].describe().round(3).T.to_string())

# ------------------------------------------------------------------ figure 25
fig, (a, b) = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.5), gridspec_kw={"width_ratios": [1, 1.05], "wspace": 1.05})
bounds = [0, 5, 10, 25, 50, 100, 1e9]
cols = ["#f7fbff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
Z = surf.pivot(index="price_share", columns="rate", values="oai")
a.pcolormesh(Z.columns * 100, Z.index * 100, Z.values, cmap=ListedColormap(cols), norm=BoundaryNorm(bounds, len(cols)),
             shading="nearest", rasterized=True)
cs = a.contour(Z.columns * 100, Z.index * 100, Z.values, levels=[10, 25, 50, 100], colors=maps.INK, linewidths=0.5)
a.clabel(cs, fmt=lambda v: f"OAI {v:.0f}", fontsize=5.5, inline_spacing=2)
for x, y, lab, dx, dy, ha in [(BASE["rate"] * 100, 100, "Today", -5, -9, "right"),
                              (BASE["rate"] * 100, 100 * (1 - LAND_SHARE), "Free land", 5, 4, "left"),
                              (8, 100 * (1 - LAND_SHARE), "Free land\n+ 8% rate", -5, 4, "right")]:
    a.plot(x, y, "o", ms=4, mfc="white", mec=maps.INK, mew=0.7, zorder=5, clip_on=False)
    a.annotate(lab, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=6, color=maps.INK,
               bbox={"fc": "white", "ec": "none", "pad": 0.6, "alpha": 0.85})
a.set_xlabel("Mortgage interest rate (%)")
a.set_ylabel("Price as % of today's median listed home")
a.set_ylim(2, 101)
a.text(-0.2, 1.04, "a", transform=a.transAxes, fontsize=8, fontweight="bold")
handles = [plt.Rectangle((0, 0), 1, 1, fc=c, ec="#7a7a7a", lw=0.3) for c in cols]
a.legend(handles, ["< 5", "5–10", "10–25", "25–50", "50–100", "≥ 100"], title="GKMA OAI", loc="upper center",
         bbox_to_anchor=(0.5, -0.17), ncol=6, frameon=False, fontsize=5.5, title_fontsize=6, handlelength=1.0,
         columnspacing=0.8, handletextpad=0.3)

g = ladder[ladder["area"] == "GKMA"].sort_values("step")
y = np.arange(len(g))[::-1]
b.barh(y, g["oai"], height=0.62, color=[maps.SEQ_BLUE[3]] * 5 + [maps.OKABE_ITO[1]] * 2, edgecolor="none")
b.axvline(100, color=maps.INK, lw=0.6, ls=(0, (3, 2)))
b.text(100, len(g) - 0.35, " OAI 100:\n median household\n can just buy", fontsize=5.5, va="top", color=maps.MUTED)
for yy, (_, r) in zip(y, g.iterrows()):
    sh = r["share_able"]
    sh = "< 0.1%" if sh < 0.001 else (f"{sh:.1%}" if sh < 0.1 else f"{sh:.0%}")
    b.text(r["oai"] + 1.5, yy, f"{r['oai']:.0f}  ·  {sh} can buy", va="center", fontsize=5.8)
b.set_yticks(y)
b.set_yticklabels(g["scenario"], fontsize=6)
b.set_xlim(0, max(110, g["oai"].max() * 1.45))
b.set_xlabel("GKMA Ownership Affordability Index")
for s in ("top", "right"):
    b.spines[s].set_visible(False)
b.text(-1.0, 1.04, "b", transform=b.transAxes, fontsize=8, fontweight="bold")
maps._save(fig, "25_what_it_takes",
           title="What it would take for the median household to buy",
           note=(f"(a) GKMA Ownership Affordability Index for the median listed home (UGX {P_g/1e6:.0f} million) at "
                 f"other prices and interest rates, with a {BASE['deposit']:.0%} deposit, {BASE['term_years']}-year term and "
                 f"{BASE['cap']:.0%} repayment cap; free land removes the median land share ({LAND_SHARE:.0%}, 32 m² per bedroom). "
                 "(b) Cumulative policy ladder; each bar keeps the changes above it. Cost-floor homes are built at CAHF "
                 f"benchmark cost (UGX {COST.loc['bungalow_standard', 'rate_ugx_per_m2']/1e6:.2f} million/m²) on a 50 × 50 ft plot "
                 f"at the lower-quartile sub-county land price (UGX {cheap_land/1e6:.1f} million per decimal), with no developer margin."),
           sources="Listings (RED, Jiji, Uganda Property Centre); modelled parish incomes (UNHS 2019/20, Census 2024); "
                   "Bank of Uganda lending rate; CAHF (2020) construction costs indexed with the UBOS CIPI.")

# ------------------------------------------------------------------ figure 26
d = cf.pivot_table(index=["area", "district"], columns="home", values="share_able").reset_index()
d = d.sort_values("2-bedroom, 50 m²")
d["label"] = d["area"].str.split("/").str[1].str.replace("  ", " ") + " (" + d["district"] + ")"
fig, ax = plt.subplots(figsize=(maps.SINGLE * 1.25, maps.SINGLE * 1.45))
yy = np.arange(len(d))
ax.hlines(yy, d["2-bedroom, 50 m²"] * 100, d["1-bedroom, 30 m²"] * 100, color="#c8c8c8", lw=0.8)
ax.plot(d["2-bedroom, 50 m²"] * 100, yy, "o", ms=3.6, color=maps.OKABE_ITO[0], label="2-bedroom, 50 m²")
ax.plot(d["1-bedroom, 30 m²"] * 100, yy, "o", ms=3.6, color=maps.OKABE_ITO[1], label="1-bedroom, 30 m²")
ax.set_yticks(yy)
ax.set_yticklabels(d["label"], fontsize=5.6)
ax.set_xlabel("Households who could buy the cost-floor home (%)")
ax.set_xlim(0, max(10, float(d[["2-bedroom, 50 m²", "1-bedroom, 30 m²"]].max().max()) * 100 * 1.1))
ax.grid(axis="x", color="#ececec", lw=0.4)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, loc="lower right", fontsize=6, handletextpad=0.2)
maps._save(fig, "26_cost_floor",
           title="Share of households who could buy a minimal formal home at cost, by sub-county",
           note=(f"A home built at CAHF benchmark construction cost on a 50 × 50 ft plot ({PLOT_DEC:.2f} decimals) at the "
                 f"sub-county's median asking land price, with no developer margin, financed at {BASE['rate']:.1%} over "
                 f"{BASE['term_years']} years with a {BASE['deposit']:.0%} deposit and a {BASE['cap']:.0%} repayment cap. "
                 f"Sub-counties with at least {MIN_LAND_N} land listings."),
           sources="Land listings (RED, Jiji, Uganda Property Centre); CAHF (2020) construction costs indexed with the UBOS CIPI; "
                   "modelled parish incomes (UNHS 2019/20, Census 2024); Bank of Uganda lending rate.")
