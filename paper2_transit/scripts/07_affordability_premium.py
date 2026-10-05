"""Who pays for access? The Expressway premium in household terms (paper 2, RQ4).

The before-after estimates put a premium of about 0.19-0.26 log points on house prices
within 15 minutes of an Expressway access point, and no robust premium on rents. This
stage expresses the sale-price premium in the incomes of the households who live in the
catchment, using the paper-1 income model:

  premium per home   value x (1 - exp(-beta)), for the lower-quartile and median listed
                     house in the catchment (values from 06_value_capture.py)
  years of income    premium / (12 x median household income of catchment parishes)
  qualifying income  extra monthly income needed to finance the premium on base mortgage
                     terms (paper 1), and the share of catchment households who could buy
                     the lower-quartile house with and without it

  python paper2_transit/scripts/07_affordability_premium.py
  -> paper2_transit/outputs/tables/affordability_premium.csv, maps/P2_affordability_premium
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _paper  # noqa: F401
from _network import RoadNetwork
from gkma.analysis.affordability_index import bou_lending_rate, gap_share, monthly_payment, parish_incomes
from gkma.config import load_config
from gkma.viz import pubmaps as maps

maps.OUT_DIR = str(_paper.OUT / "maps")
cfg = load_config()
m = cfg["affordability_index"]["mortgage"]
BASE = {"rate": bou_lending_rate(), "deposit": m["deposit"], "term_years": m["term_years"], "cap": m["cap"]}
vc = pd.read_csv(_paper.OUT / "tables" / "value_capture.csv")
VALUES = vc.drop_duplicates("value_basis").set_index("value_basis")["value_per_home_ugx"].to_dict()
BETAS = vc.drop_duplicates("beta").set_index("beta")["uplift_per_home_ugx"].div(
    vc.drop_duplicates("beta").set_index("beta")["value_per_home_ugx"]).pipe(lambda s: -np.log(1 - s)).to_dict()

net = RoadNetwork()
t_exp = net.nearest_time(net.access_nodes("expressway"))
inc = parish_incomes(net.crs).dropna(subset=["households", "income"])
tt = []
for pt in inc.geometry:
    n0, walk = net.snap(pt)
    tt.append(walk + t_exp.get(n0, np.inf))
inc["tt_expressway_min"] = tt
catch = inc[inc["tt_expressway_min"] <= 15]
w = catch["households"]
m_c = float(np.exp((np.log(catch["income"]) * w).sum() / w.sum()))


def qualifying(price):
    return monthly_payment(price * (1 - BASE["deposit"]), BASE["rate"], BASE["term_years"]) / BASE["cap"]


rows = []
for vname, v in VALUES.items():
    for bname, b in BETAS.items():
        prem = v * (1 - np.exp(-b))
        without = v - prem
        rows.append({"value_basis": vname, "beta": bname, "beta_value": b, "price_with": v, "price_without": without,
                     "premium_ugx": prem, "catchment_households": float(w.sum()), "catchment_median_income": m_c,
                     "premium_years_of_median_income": prem / (12 * m_c),
                     "income_needed_with": qualifying(v), "income_needed_without": qualifying(without),
                     "extra_income_needed": qualifying(v) - qualifying(without),
                     "share_able_with": 1 - gap_share(qualifying(v), catch),
                     "share_able_without": 1 - gap_share(qualifying(without), catch)})
res = pd.DataFrame(rows)
res.round(5).to_csv(_paper.OUT / "tables" / "affordability_premium.csv", index=False)
print(f"catchment: {len(catch)} parishes, {w.sum():,.0f} households, median income UGX {m_c:,.0f}/month")
print(res[["value_basis", "beta", "premium_ugx", "premium_years_of_median_income", "extra_income_needed",
           "share_able_with", "share_able_without"]].round(4).to_string(index=False))

# figure: premium in years of the catchment median household's income
d = res.copy()
d["label"] = d["value_basis"].str.capitalize() + " house"
fig, ax = plt.subplots(figsize=(maps.SINGLE, maps.SINGLE * 0.62))
order = list(BETAS)
x = np.arange(len(VALUES))
wdt = 0.24
for k, bname in enumerate(order):
    g = d[d["beta"] == bname].set_index("value_basis").loc[list(VALUES)]
    bars = ax.bar(x + (k - 1) * wdt, g["premium_years_of_median_income"], wdt * 0.92, color=maps.SEQ_BLUE[2 + k],
                  label=bname, edgecolor="none")
    for bb, val in zip(bars, g["premium_years_of_median_income"]):
        ax.text(bb.get_x() + bb.get_width() / 2, val + 0.3, f"{val:.0f}", ha="center", fontsize=5.5)
ax.set_xticks(x)
ax.set_xticklabels([f"{k.capitalize()} listed house\n(UGX {v/1e6:,.0f}m)" for k, v in VALUES.items()], fontsize=6)
ax.set_ylabel("Years of median household income")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(title="Expressway premium (log points)", frameon=False, fontsize=5.5, title_fontsize=6, loc="upper left")
ax.set_ylim(0, d["premium_years_of_median_income"].max() * 1.3)
maps._save(fig, "P2_affordability_premium",
           title="The Expressway premium on a listed house, in years of the catchment's median household income",
           note=(f"Premium = value × (1 − e^−β) for houses within 15 minutes of an Expressway access point; catchment "
                 f"median household income UGX {m_c:,.0f} a month ({len(catch)} parishes, {w.sum():,.0f} households, "
                 "modelled from UNHS 2019/20 and Census 2024)."),
           sources="RED listings 2017–2026; OpenStreetMap road network; UBOS Census 2024; UNHS 2019/20.")
