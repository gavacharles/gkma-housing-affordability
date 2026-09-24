"""GKMA Housing Affordability Index: RAI, OAI and AGI at GKMA, district and
sub-county level (parish in the supplement), with mortgage sensitivity.

Outputs
  tables/affordability_index_{gkma,district,subcounty,parish}.csv   base case
  tables/affordability_index_sensitivity.csv                        GKMA & districts x scenarios
  maps/19_rai_subcounty, 20_oai_subcounty, 21_agi_rent_subcounty
  maps/22_affordability_index_districts                            chart with 95% CIs
  tables/affordability_burden_gradient.csv, maps/23_burden_gradient   burden thresholds 10-80%
  maps/24_residual_income                                          residual-income test
  maps/S1_listings_parish, S2_rai_parish, S3_oai_parish            supplementary parish maps
                                                                    (index only where >= min_listings)
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _stage
from gkma.analysis.affordability_index import bou_lending_rate, burden_gradient, compute_index
from gkma.config import load_config, p
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
cfg = load_config().get("affordability_index", {})
m = cfg.get("mortgage", {})
rate = bou_lending_rate() if m.get("rate", "bou") == "bou" else float(m["rate"])
base = {"rate": rate, "deposit": m.get("deposit", 0.30), "term_years": m.get("term_years", 20), "cap": m.get("cap", 0.35)}
min_n = cfg.get("min_listings", 20)
print("base mortgage:", {k: round(v, 4) for k, v in base.items()})

res = {}
for level in ["gkma", "district", "subcounty", "parish"]:
    res[level] = compute_index(pts, level, base, min_n=min_n)
    res[level].round(4).to_csv(T / f"affordability_index_{level}.csv", index=False)
cols = ["area", "households", "n_rent", "median_rent", "median_income", "rai", "rai_lo", "rai_hi", "agi_rent",
        "n_sale", "median_price", "monthly_payment", "oai", "oai_lo", "oai_hi", "agi_own"]
show = pd.concat([res["gkma"], res["district"]])
print(show[[c for c in cols if c in show]].round(3).to_string(index=False))

# sensitivity (GKMA + districts)
# ranges from Ugandan evidence: CAHF 2024 (rates 16-22%, terms up to 25 years); HFB (LTV 50-80%, cap 35%)
scen = {"base": {}, "rate_16": {"rate": 0.16}, "rate_22": {"rate": 0.22}, "deposit_20": {"deposit": 0.20},
        "deposit_50": {"deposit": 0.50}, "term_15": {"term_years": 15}, "term_25": {"term_years": 25},
        "cap_30": {"cap": 0.30}}
rows = []
for name, change in scen.items():
    mt = {**base, **change}
    for level in ["gkma", "district"]:
        r = compute_index(pts, level, mt, min_n=min_n)
        r["scenario"] = name
        rows.append(r)
sens = pd.concat(rows)
sens[["scenario", "area", "rai", "oai", "agi_rent", "agi_own"]].round(3).to_csv(T / "affordability_index_sensitivity.csv", index=False)
print(sens.pivot_table(index="area", columns="scenario", values="oai").round(1).to_string())

# maps at sub-county level
sub = bg.copy()
g = load_config()["geography"]
import geopandas as gpd  # noqa: E402
sc = gpd.read_file(p(g["subcounties"]))
sc["area"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
sc = sc.merge(res["subcounty"], on="area", how="left")
sc["unit_id"] = sc["area"]
note = (f"Areas with fewer than {min_n} listings are grey. Median household income of all parishes in each "
        "sub-county (modelled; Census 2024 weights).")
maps.choropleth(sc, "rai", "Rental Affordability Index by sub-county (1–2 bedroom rentals)", "19_rai_subcounty",
                cmap=maps.SEQ_RED[::-1], scheme="quantiles", k=5, legend_title="RAI (100 = just affordable)",
                min_n_label=f"Fewer than {min_n} listings", note=note + " RAI = 100 × median income / (median rent / 0.30).")
maps.choropleth(sc, "oai", "Ownership Affordability Index by sub-county", "20_oai_subcounty",
                cmap=maps.SEQ_RED[::-1], scheme="quantiles", k=5, legend_title="OAI (100 = just affordable)",
                min_n_label=f"Fewer than {min_n} listings",
                note=note + f" Mortgage: {base['rate']:.1%} rate, {base['deposit']:.0%} deposit, "
                            f"{base['term_years']} years, {base['cap']:.0%} repayment cap.")
maps.choropleth(sc.assign(pct=100 * sc["agi_rent"]), "pct", "Affordability Gap Index (rent): share of households "
                "unable to afford the median listed 1–2 bedroom rent", "21_agi_rent_subcounty", cmap=maps.SEQ_RED,
                scheme="equal_interval", k=5, legend_title="% of households",
                min_n_label=f"Fewer than {min_n} listings", note=note)

# district chart with CIs
d = pd.concat([res["gkma"], res["district"]]).dropna(subset=["rai"])
d = d.sort_values("rai")
fig, axes = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.32), sharey=True)
for ax, (k, lab) in zip(axes, [("rai", "Rental Affordability Index"), ("oai", "Ownership Affordability Index")]):
    dd = d.dropna(subset=[k])
    y = np.arange(len(dd))
    col = [maps.RED[4] if x == "GKMA" else maps.BLUE[4] for x in dd["area"]]
    ax.barh(y, dd[k], color=col, height=0.55)
    ax.errorbar(dd[k], y, xerr=[dd[k] - dd[f"{k}_lo"], dd[f"{k}_hi"] - dd[k]], fmt="none", ecolor="#333333",
                elinewidth=0.7, capsize=2)
    ax.axvline(100, color="#333333", lw=0.8, ls=(0, (3, 2)))
    ax.text(100, len(dd) - 0.4, " 100 = just affordable", fontsize=5.5, va="bottom")
    ax.set_yticks(y, dd["area"])
    ax.set_xlabel(lab)
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
maps._save(fig, "22_affordability_index_districts",
           title="GKMA Housing Affordability Index by district",
           note=f"Bars: index; whiskers: 95% bootstrap intervals from listing sampling. Mortgage: {base['rate']:.1%}, "
                f"{base['deposit']:.0%} deposit, {base['term_years']} years, {base['cap']:.0%} cap.",
           sources="Listings; UBOS UNHS 2019/20 and Census 2024 (modelled incomes); Bank of Uganda lending rates.")

# supplementary parish maps: coverage, and the index where a parish alone has >= min_n listings
pa = gpd.read_file(p(g["parishes"]))
pa["area"] = pa[g["district_name_col"]].str.title() + "/" + pa[g["parish_name_col"]]
pa = pa.merge(res["parish"], on="area", how="left")
pa["unit_id"] = pa["area"]
pa["n_listings"] = pa[["n_rent", "n_sale"]].sum(axis=1, min_count=1)
pa.loc[pa["n_listings"] == 0, "n_listings"] = np.nan
maps.choropleth(pa, "n_listings", "Listings located in each parish (supplementary)", "S1_listings_parish",
                cmap=maps.SEQ_BLUE, scheme="user", bins=[4, 19, 49, 199, max(200.0, float(pa["n_listings"].max()))], legend_title="Listings",
                min_n_label="No listings",
                note="1–2 bedroom rentals and house/apartment sales. Listings are geocoded to neighbourhoods, so "
                     "parish assignment is only as precise as the neighbourhood point.")
pnote = (f"Supplementary: parishes with fewer than {min_n} listings are grey. Parish values rest on few "
         "neighbourhood points and wide intervals; the sub-county maps are the primary results.")
maps.choropleth(pa, "rai", "Rental Affordability Index by parish (supplementary)", "S2_rai_parish",
                cmap=maps.SEQ_RED[::-1], scheme="quantiles", k=4, legend_title="RAI (100 = just affordable)",
                min_n_label=f"Fewer than {min_n} listings", note=pnote)
maps.choropleth(pa, "oai", "Ownership Affordability Index by parish (supplementary)", "S3_oai_parish",
                cmap=maps.SEQ_RED[::-1], scheme="quantiles", k=4, legend_title="OAI (100 = just affordable)",
                min_n_label=f"Fewer than {min_n} listings",
                note=pnote + f" Mortgage: {base['rate']:.1%}, {base['deposit']:.0%} deposit, "
                             f"{base['term_years']} years, {base['cap']:.0%} cap.")

# burden gradient: tolerable housing-cost burden from 10% to 80% of gross income
bg_ = burden_gradient(pts, base, min_n=min_n)
bg_ = bg_[bg_["area"].isin(["GKMA", "Kampala", "Wakiso", "Mukono"])]
bg_[["area", "burden", "median_income", "median_rent", "monthly_payment", "rai", "oai", "agi_rent", "agi_own",
     "median_hh_rent_burden", "median_hh_own_burden"]].round(4).to_csv(T / "affordability_burden_gradient.csv",
                                                                     index=False)
print(bg_.pivot_table(index="burden", columns="area", values="agi_rent").round(3).to_string())
print(bg_.pivot_table(index="burden", columns="area", values="agi_own").round(3).to_string())
print(bg_.groupby("area")[["median_hh_rent_burden", "median_hh_own_burden"]].first().round(2).to_string())

fig, axes = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.36), sharey=True)
cols = {"GKMA": "#000000", "Kampala": maps.OKABE_ITO[0], "Wakiso": maps.OKABE_ITO[1], "Mukono": maps.OKABE_ITO[2]}
for ax, (k, lab, refs) in zip(axes, [("agi_rent", "Renting the median listed 1–2 bedroom home",
                                      [(0.30, "30% norm"), (0.50, "50% severe")]),
                                     ("agi_own", "Buying the median listed house with a mortgage",
                                      [(0.35, "35% lender cap"), (0.50, "50% severe")])]):
    for area, d in bg_.groupby("area"):
        d = d.dropna(subset=[k]).sort_values("burden")
        ax.plot(100 * d["burden"], 100 * d[k], color=cols[area], lw=1.3 if area == "GKMA" else 1,
                ls="-" if area == "GKMA" else (0, (4, 1.5)), label=area)
    for x, t in refs:
        ax.axvline(100 * x, color="#999999", lw=0.6, ls=(0, (2, 2)))
        ax.text(100 * x + 0.8, 3, t, fontsize=5.3, color="#555555", rotation=90, va="bottom")
    ax.set_xlim(10, 80)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Tolerable housing-cost burden (% of gross income)")
    ax.set_title(lab, fontsize=7, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("Households priced out (%)")
axes[0].legend(frameon=False, fontsize=5.8, loc="lower left")
fig.tight_layout()
maps._save(fig, "23_burden_gradient", title="Affordability across housing-cost burden thresholds of 10–80% of income",
           note="Share of households whose income is below the qualifying income (median listed rent or mortgage "
                f"repayment divided by the burden threshold). Mortgage: {base['rate']:.1%}, {base['deposit']:.0%} "
                f"deposit, {base['term_years']} years; the burden threshold replaces the repayment cap.",
           sources="Listings; UBOS UNHS 2019/20 and Census 2024 (modelled incomes); Bank of Uganda lending rates.")

# residual-income test: who is priced out, and who would be pushed into poverty
ri = pd.concat([res["gkma"], res["district"]])
ri = ri[ri["area"].isin(["GKMA", "Kampala", "Wakiso", "Mukono"])].set_index("area")
print(ri[["median_income", "below_nonhousing_min", "ri_rent", "ri_rent_housing_induced", "ri_rent_median_residual",
          "ri_own", "ri_own_housing_induced"]].round(3).to_string())
order = ["Mukono", "Wakiso", "Kampala", "GKMA"]
fig, axes = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.28), sharey=True)
parts = [("below_nonhousing_min", "Below the non-housing minimum before paying for housing", "#7f7f7f"),
         ("induced", "Pushed below the minimum by the housing cost", maps.RED[4]),
         ("afford", "Can afford it and keep the minimum", maps.BLUE[3])]
for ax, (k, lab) in zip(axes, [("rent", "Renting the median listed 1–2 bedroom home"),
                               ("own", "Buying the median listed house with a mortgage")]):
    d = ri.loc[order].assign(induced=ri[f"ri_{k}_housing_induced"], afford=1 - ri[f"ri_{k}"])
    left = np.zeros(len(d))
    for col, name, c in parts:
        v = 100 * d[col].to_numpy()
        ax.barh(np.arange(len(d)), v, left=left, color=c, height=0.6, label=name, edgecolor="white", linewidth=0.6)
        for i, (x0, w) in enumerate(zip(left, v)):
            if w >= 6:
                ax.text(x0 + w / 2, i, f"{w:.0f}", ha="center", va="center", fontsize=5.5, color="white")
        left += v
    ax.set_yticks(np.arange(len(d)), order)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of households")
    ax.set_title(lab, fontsize=7, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=5.6, loc="lower center", ncol=3)
fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.34, wspace=0.08)
maps._save(fig, "24_residual_income", title="Residual-income test of affordability",
           note="A household can afford the home if income minus the housing cost covers its minimum non-housing "
                "budget: the UBOS upper poverty line (UGX 87,000 per adult equivalent per month, 2019/20; uprated by "
                "CPI) × adult equivalents, less the housing share of spending. "
                f"Mortgage: {base['rate']:.1%}, {base['deposit']:.0%} deposit, {base['term_years']} years.",
           sources="Listings; UBOS UNHS 2019/20 and Census 2024 (modelled incomes, household size); BoU lending rates.")
