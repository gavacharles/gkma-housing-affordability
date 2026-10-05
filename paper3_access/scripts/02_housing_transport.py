"""Moving further out: housing plus transport costs by sub-county (paper 3).

For a household on the GKMA median income, what does it cost each month to rent the
typical listed home in a sub-county and commute from it to the CBD by minibus taxi?

  rent        median asking rent of 1-2 bedroom listings in the sub-county (paper 1 RAI input, n >= 20)
  distance    road distance to the CBD = 1.3 x straight line from each neighbourhood point,
              averaged over the sub-county's points weighted by their rental listings
  fare        one-way minibus fare F(d) = a d^b fitted to 2021 route fares (CBD-Ntinda,
              -Kira, -Entebbe) and uprated by the headline CPI to August 2026; sensitivity:
              the 2016 survey mean of UGX 432 per km (Ndibatya & Booysen 2020), uprated
  travel time network minutes to the CBD at congested speeds (paper 2, 01_accessibility.py)
  commuting   2 trips a day, 22 days a month; 1 commuter (sensitivity: 2)
  time cost   travel hours x half the hourly household income (median income / 176 hours)

H+T burden = (rent + fares) / median income; the generalised burden adds the time cost.
Outputs: tables/housing_transport.csv, housing_transport_fare_model.json;
         maps/P3_03_housing_transport
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from gkma.analysis.household import area_incomes, cpi_uplift, median_income, subcounty_polygons
from gkma.config import load_config, p
from gkma.viz import pubmaps as maps

P1 = _paper.ROOT / "paper1_affordability/outputs/tables"
P2 = _paper.ROOT / "paper2_transit/outputs/tables"
T = _paper.OUT / "tables"
CIRCUITY, DAYS, MIN_N = 1.3, 22, 20
cfg = load_config()
CBD = cfg["geography"]["points_of_interest"]["cbd"]

# ------------------------------------------------------------------ fare model
up = lambda per: cpi_uplift(*per)  # noqa: E731
fares = pd.read_csv(p("data/external/market/commuter_fares.csv"))
lk = pd.read_csv(p("data/lookup/neighbourhood_lookup.csv")).set_index("name")


def road_km(lon, lat):
    t = gpd.GeoSeries(gpd.points_from_xy([lon, CBD[0]], [lat, CBD[1]]), crs="EPSG:4326").to_crs(cfg["project"]["crs_projected"])
    return CIRCUITY * t.iloc[0].distance(t.iloc[1]) / 1000


q = fares[fares["basis"] == "route_quote"].copy()
q["km"] = [road_km(lk.loc[d, "lon"], lk.loc[d, "lat"]) for d in q["destination"]]
b, ln_a = np.polyfit(np.log(q["km"]), np.log(q["fare_ugx"] * up(("2021-01", "2021-12"))), 1)
per_km = float(fares.loc[fares["basis"] == "per_km", "fare_ugx"].iloc[0]) * up(("2016-01", "2016-03"))
FARE = {"route fares (base)": lambda d: np.exp(ln_a) * d ** b, "survey per-km (high)": lambda d: per_km * d}
json.dump({"a": float(np.exp(ln_a)), "b": float(b), "per_km_2026": per_km, "cpi_2021": up(("2021-01", "2021-12")), "cpi_2016": up(("2016-01", "2016-03")),
           "quotes": q[["destination", "km", "fare_ugx"]].round(2).to_dict("records")},
          open(T / "housing_transport_fare_model.json", "w"), indent=2)
print(f"fare = {np.exp(ln_a):.0f} x km^{b:.3f} (2026 UGX); per-km alternative UGX {per_km:.0f}/km")

# ------------------------------------------------------------------ sub-county commute
acc = pd.read_csv(P2 / "neighbourhood_accessibility.csv")
pts = gpd.GeoDataFrame(acc, geometry=gpd.points_from_xy(acc["lon"], acc["lat"]), crs="EPSG:4326").to_crs(
    cfg["project"]["crs_projected"])
cbd = gpd.GeoSeries(gpd.points_from_xy([CBD[0]], [CBD[1]]), crs="EPSG:4326").to_crs(pts.crs).iloc[0]
pts["road_km"] = CIRCUITY * pts.distance(cbd) / 1000
sc = subcounty_polygons()
pts = gpd.sjoin(pts, sc[["area_id", "geometry"]], predicate="within")
pts = pts[pts["n_rent"] > 0]
wavg = lambda g, c: float(np.average(g[c], weights=g["n_rent"]))  # noqa: E731
com = pts.groupby("area_id").apply(lambda g: pd.Series({"road_km": wavg(g, "road_km"), "tt_cbd_min": wavg(g, "tt_cbd_min"),
                                                         "acc_jobs_45": wavg(g, "acc_jobs_45_mix")}))
rent = pd.read_csv(P1 / "affordability_index_subcounty.csv").set_index("area")
rent = rent[rent["n_rent"] >= MIN_N][["median_rent", "n_rent"]].rename(columns={"median_rent": "rent"})
rent["DName2016"] = rent.index.str.split("/").str[0]
d = rent.join(com, how="inner")
m_g = median_income(area_incomes("gkma")["GKMA"])
loc_inc = {a: median_income(i) for a, i in area_incomes("subcounty").items()}
d["local_median_income"] = d.index.map(loc_inc)
vot = 0.5 * m_g / (DAYS * 8)

rows = []
for area, r in d.iterrows():
    for fname, f in FARE.items():
        for commuters in (1, 2):
            fare_m = 2 * DAYS * commuters * float(f(r["road_km"]))
            time_m = 2 * DAYS * commuters * r["tt_cbd_min"] / 60 * vot
            rows.append({"area": area, "district": r["DName2016"], "fare_model": fname, "commuters": commuters,
                         "rent": r["rent"], "n_rent": r["n_rent"], "road_km": r["road_km"], "tt_cbd_min": r["tt_cbd_min"],
                         "fares_month": fare_m, "time_cost_month": time_m, "gkma_median_income": m_g,
                         "local_median_income": r["local_median_income"],
                         "h_burden": r["rent"] / m_g, "t_burden": fare_m / m_g, "ht_burden": (r["rent"] + fare_m) / m_g,
                         "ht_burden_generalised": (r["rent"] + fare_m + time_m) / m_g,
                         "ht_burden_local": (r["rent"] + fare_m) / r["local_median_income"]})
ht = pd.DataFrame(rows)
ht.round(4).to_csv(T / "housing_transport.csv", index=False)
base = ht[(ht["fare_model"] == "route fares (base)") & (ht["commuters"] == 1)].sort_values("tt_cbd_min")
print(base[["area", "rent", "road_km", "tt_cbd_min", "fares_month", "time_cost_month", "h_burden", "ht_burden",
            "ht_burden_generalised"]].round(2).to_string(index=False))
slope = np.polyfit(base["tt_cbd_min"], np.log(base["rent"]), 1)[0]
print(f"rent falls {1 - np.exp(10 * slope):.1%} per 10 extra minutes; fares rise "
      f"UGX {np.polyfit(base['tt_cbd_min'], base['fares_month'], 1)[0] * 10:,.0f}/month per 10 minutes")

# ------------------------------------------------------------------ figure
g = base.copy()
g["label"] = g["area"].str.split("/").str[1].str.replace("  ", " ") + " (" + g["district"] + ")"
fig, ax = plt.subplots(figsize=(maps.FULL, maps.FULL * 0.45))
y = np.arange(len(g))[::-1]
XMAX = 300
parts = [("h_burden", "Rent (median listing)", maps.SEQ_BLUE[3], None),
         ("t_burden", "Minibus fares, one commuter", maps.OKABE_ITO[1], None)]
left = np.zeros(len(g))
for col, lab, c, h in parts:
    ax.barh(y, g[col] * 100, left=left, color=c, height=0.62, label=lab, edgecolor="white", linewidth=0.5)
    left += g[col].to_numpy() * 100
tc = (g["ht_burden_generalised"] - g["ht_burden"]).to_numpy() * 100
ax.barh(y, tc, left=left, color="white", hatch="/////", edgecolor=maps.OKABE_ITO[1], linewidth=0.0, height=0.62,
        label="Commuting time, valued at half the hourly income")
for yy, (_, r), l2 in zip(y, g.iterrows(), left + tc):
    if l2 > XMAX:
        ax.text(XMAX - 2, yy, f"{l2:.0f}% →  {r['tt_cbd_min']:.0f} min", va="center", ha="right", fontsize=5.5,
                color="white", fontweight="bold")
    else:
        ax.text(l2 + 3, yy, f"{l2:.0f}%  ·  {r['tt_cbd_min']:.0f} min", va="center", fontsize=5.5, color=maps.MUTED)
for v, lab in [(30, "30%"), (45, "45% H+T\nbenchmark"), (100, "Whole\nincome")]:
    ax.axvline(v, color=maps.INK, lw=0.5, ls=(0, (3, 2)))
    ax.text(v + 1, len(g) - 0.3, lab, fontsize=5.3, va="bottom", color=maps.MUTED)
ax.set_yticks(y)
ax.set_yticklabels(g["label"], fontsize=5.8)
ax.set_xlabel(f"Monthly cost as % of the GKMA median household income (UGX {m_g:,.0f})")
ax.set_xlim(0, XMAX)
ax.set_ylim(-0.7, len(g) + 0.6)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=5.8, loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=3)
maps._save(fig, "P3_03_housing_transport",
           title="Rent and commuting costs by sub-county for a household on the GKMA median income",
           note=(f"Sub-counties with at least {MIN_N} rental listings, ordered by network travel time to the CBD (labels). "
                 f"Fares: F = {np.exp(ln_a):.0f} × km^{b:.2f} (UGX, 2026 prices), fitted to 2021 route fares and uprated by "
                 f"the CPI; road distance = {CIRCUITY} × straight line; 2 trips a day, {DAYS} days a month. The 45% "
                 "benchmark is the US H+T Index threshold, shown for reference."),
           sources="Listings (RED, Jiji, Uganda Property Centre); OpenStreetMap road network; route fares (Eagle Online "
                   "2021); Ndibatya and Booysen (2020); Bank of Uganda CPI; modelled incomes (UNHS 2019/20, Census 2024).")
