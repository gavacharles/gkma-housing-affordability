"""Value-capture illustration for the Entebbe Expressway (paper 2).

Property-value uplift in the Expressway catchment implied by the before-after estimates,
compared with toll revenue.

  catchment    parishes whose representative point is within 15 minutes of an Expressway
               access point on the road network (the treatment definition in 04_did.py)
  households   Census 2024 households in those parishes (parishes matched to 2016 boundaries)
  value        lower-quartile and median asking price of houses listed in the catchment (RED,
               2025-26) -- formal, upper-market homes, so value applies only to the share of the
               stock resembling them: scenarios of 10%, 25% and 50%
  uplift       share of today's value attributable to the Expressway = 1 - exp(-beta), with beta
               from the before-after models: 0.19 (lower robustness estimate), 0.21 (2025-26),
               0.26 (2020)
  comparison   toll revenue: about UGX 4 billion a month in 2026 (about UGX 48 billion a year) and
               UGX 192 billion collected since tolling began in January 2022 (Daily Monitor,
               25 August 2026)

  python paper2_transit/scripts/06_value_capture.py -> paper2_transit/outputs/tables/value_capture.csv
"""
import geopandas as gpd
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from _network import RoadNetwork
from gkma.config import load_config, p

TOLL_YEAR, TOLL_TO_DATE = 48e9, 192e9
BETAS = {"lower (robustness, 0.19)": 0.19, "2025-26 (0.21)": 0.212, "2020 (0.26)": 0.259}
SHARES = [0.10, 0.25, 0.50]

cfg = load_config()
net = RoadNetwork()
t_exp = net.nearest_time(net.access_nodes("expressway"))
par = gpd.read_file(p(cfg["income"]["parish_income"])).dropna(subset=["households"]).to_crs(net.crs)
par["pt"] = par.geometry.representative_point()
tt = []
for pt in par["pt"]:
    n0, walk = net.snap(pt)
    tt.append(walk + t_exp.get(n0, np.inf))
par["tt_expressway_min"] = tt
catch = par[par["tt_expressway_min"] <= 15]
hh = float(catch["households"].sum())

L = gpd.read_file(p("data/processed/listings_current_full.gpkg"))
L["pt"] = L.geometry.to_wkt()
A = pd.read_csv(_paper.OUT / "tables" / "neighbourhood_accessibility.csv")[["pt", "tt_expressway_min"]]
L = L.merge(A, on="pt")
houses = L[(L["source"] == "red") & (L["listing_type"] == "sale") & (L["ptype"] == "house") &
           (L["tt_expressway_min"] <= 15)]["price_ugx"].dropna()
values = {"lower quartile": float(houses.quantile(.25)), "median": float(houses.median())}

rows = []
for vname, v in values.items():
    for bname, b in BETAS.items():
        per_home = v * (1 - np.exp(-b))
        for s in SHARES:
            total = hh * s * per_home
            rows.append({"value_basis": vname, "value_per_home_ugx": v, "beta": bname, "uplift_per_home_ugx": per_home,
                         "share_of_stock": s, "homes": hh * s, "uplift_total_ugx": total,
                         "years_of_toll_revenue": total / TOLL_YEAR, "x_toll_to_date": total / TOLL_TO_DATE,
                         "annual_1pct_rate_on_uplift_ugx": 0.01 * total})
res = pd.DataFrame(rows)
res.round(2).to_csv(_paper.OUT / "tables" / "value_capture.csv", index=False)
print(f"catchment: {len(catch)} parishes, {hh:,.0f} households (Census 2024, matched parishes)")
print(f"listed houses in catchment (RED 2025-26): n = {len(houses)}, lower quartile UGX {values['lower quartile']/1e6:,.0f}m, "
      f"median UGX {values['median']/1e6:,.0f}m")
show = res[res["beta"] == "2025-26 (0.21)"].copy()
show["uplift_total_bn"] = show["uplift_total_ugx"] / 1e9
print(show[["value_basis", "share_of_stock", "homes", "uplift_per_home_ugx", "uplift_total_bn", "years_of_toll_revenue"]]
      .round(1).to_string(index=False))
print("full range across betas, values and shares: UGX "
      f"{res['uplift_total_ugx'].min()/1e9:,.0f}bn to {res['uplift_total_ugx'].max()/1e9:,.0f}bn "
      f"({res['years_of_toll_revenue'].min():.1f} to {res['years_of_toll_revenue'].max():.1f} years of toll revenue)")
