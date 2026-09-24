"""Stage 4 — RQ4: where, and for what share of households, is housing
unaffordable at a 30 % rent-to-income threshold?

Needs data/external/unhs_income_by_unit.csv (see data/external/README.md).
Runs three scenarios: all rentals, modest 1–2 bedroom units, and a sigma
sensitivity (±20 %) on the income distribution.
"""
import pandas as pd

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import _stage
from gkma.analysis.affordability import affordability_by_unit, household_weighted_summary
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
scen = {"all_rentals": {}, "beds_1_2": {"bedrooms": (0.5, 2)},
        "beds_1_2_sigma_lo": {"bedrooms": (0.5, 2), "sigma_scale": 0.8},
        "beds_1_2_sigma_hi": {"bedrooms": (0.5, 2), "sigma_scale": 1.2}}
rows = []
for name, kw in scen.items():
    aff = affordability_by_unit(pts, bg, **kw)
    aff.drop(columns="geometry").to_csv(T / f"affordability_{name}.csv", index=False)
    s = household_weighted_summary(aff, pts, kw.get("bedrooms"))
    s["scenario"] = name
    rows.append(s.reset_index())
    if name in ("all_rentals", "beds_1_2"):
        lab = "all rental listings" if name == "all_rentals" else "1–2 bedroom rentals"
        maps.choropleth(aff.assign(pct=100 * aff["share_cannot_afford"]), "pct",
                        f"Households unable to afford median rent ({lab})", f"11_affordability_gap_{name}",
                        cmap=maps.SEQ_RED, scheme="equal_interval", k=5, legend_title="% of households",
                        note="Unaffordable = median asking rent > 30% of household income; lognormal "
                             "district income distribution (UNHS). Grey: fewer than 5 listings.")
        maps.choropleth(aff, "rent_to_income", f"Median rent-to-income ratio ({lab})",
                        f"12_rent_to_income_{name}", cmap=maps.SEQ_RED, legend_title="ratio")
aff_all = affordability_by_unit(pts, bg)
maps.choropleth(aff_all, "price_to_income", "Median price-to-annual-income ratio",
                "13_price_to_income", cmap=maps.SEQ_RED, legend_title="years of income")
summary = pd.concat(rows)
summary.to_csv(T / "affordability_summary.csv", index=False)
print(summary.round(3).to_string())
