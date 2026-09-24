"""Stage 5: implied land value = asking price − depreciated replacement cost.

Needs data/external/replacement_cost_rates.csv (your QS rates). Runs each
m2_per_bedroom scenario in config.yaml and validates against land-only listings.
"""
import pandas as pd

import _stage
from gkma.analysis.land_value import implied_land_value, land_value_by_unit, validation_stats
from gkma.config import load_config
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
rows = []
scenarios = load_config()["construction"]["m2_per_bedroom"]
for m2 in scenarios:
    ilv = implied_land_value(pts, m2)
    by = land_value_by_unit(ilv, pts, bg)
    by.drop(columns="geometry").to_csv(T / f"land_value_by_unit_{m2}m2.csv", index=False)
    v = validation_stats(by)
    rows.append({"m2_per_bedroom": m2, "n_houses": len(ilv), "median_land_share": ilv["land_share"].median(),
                 "share_negative": ilv["flag_negative_land"].mean(), **v})
    if m2 == scenarios[len(scenarios) // 2]:
        maps.choropleth(by.assign(pct=100 * by["median_land_share"]), "pct",
                        "Implied land share of asking price", "14_land_share", legend_title="% of price",
                        note=f"Price minus depreciated replacement cost ({m2} m² per bedroom). Grey: fewer than 5 listings.")
        maps.choropleth(by, "median_implied_land_per_decimal", "Implied land value per decimal (UGX)",
                        "15_implied_land_value", legend_title="UGX per decimal")
tab = pd.DataFrame(rows)
tab.to_csv(T / "land_value_scenarios.csv", index=False)
print(tab.round(3).to_string())
