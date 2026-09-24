"""Simplified affordability map for social media (1080 x 1080 px).

Deliberately coarser than the paper figure: parish results are aggregated to
sub-counties / Kampala divisions (household-weighted), shown in three broad
bands, with no parish boundaries or exact values. Reads the 1-2 bedroom
scenario from outputs/tables/affordability_beds_1_2.csv.

  python scripts/social_affordability_map.py
"""
import _common  # noqa: F401
import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from gkma.config import load_config, p
from gkma.viz import pubmaps as pm

g = load_config()["geography"]
aff = pd.read_csv(p("outputs/tables/affordability_beds_1_2.csv")).dropna(subset=["share_cannot_afford"])
sub = pm.clip_land(gpd.read_file(p(g["subcounties"])))

# sub-county results (household-weighted parish incomes); needs >= 20 rental listings, as in the paper
sub["unit_id"] = sub[g["district_name_col"]].str.title() + "/" + sub[g["subcounty_name_col"]]
sub = sub.merge(aff[["unit_id", "share_cannot_afford", "n_rent"]]
                .rename(columns={"share_cannot_afford": "share", "n_rent": "n"}), on="unit_id", how="left")
sub.loc[sub["n"].fillna(0) < 20, "share"] = np.nan

bands = [(0, 0.75, "Under 75%", "#fecc5c"), (0.75, 0.90, "75–90%", "#f03b20"), (0.90, 1.01, "Over 90%", "#99000d")]

px = 1080
fig = plt.figure(figsize=(px / 200, px / 200), dpi=200, facecolor="white")
ax = fig.add_axes([0.03, 0.10, 0.94, 0.76])
from pyproj import Transformer  # noqa: E402
t = Transformer.from_crs("EPSG:4326", sub.crs, always_xy=True)
(x0, x1), (y0, y1) = t.transform([32.40, 32.86], [0.16, 0.51])   # crop to where there are results
ext = (x0, y0, x1, y1)
pm._background(ax, ext)
pm.base()["land"].plot(ax=ax, facecolor="#eeeeea", edgecolor="none", zorder=2)
for lo, hi, _, c in bands:
    s = sub[(sub["share"] >= lo) & (sub["share"] < hi)]
    if len(s):
        s.plot(ax=ax, color=c, edgecolor="white", linewidth=0.5, zorder=3)
pm.base()["districts"].boundary.plot(ax=ax, color="#555555", linewidth=0.5, zorder=4)
lab = pm.base()["labels"]
for name in ["Kampala", "Entebbe", "Mukono", "Kira", "Nansana", "Wakiso", "Kajjansi"]:
    r = lab[(lab["label"] == name) & (lab["level"] == "main")]
    if len(r):
        x, y = r.geometry.iloc[0].x, r.geometry.iloc[0].y
        ax.plot(x, y, "o", ms=2.2, color="#1a1a1a", zorder=6)
        ax.annotate(name, (x, y), xytext=(3, 3), textcoords="offset points", fontsize=6.5, zorder=7,
                    fontweight="bold" if name == "Kampala" else "normal",
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")])
ax.set_xticks([])
ax.set_yticks([])
for s_ in ax.spines.values():
    s_.set_visible(False)

fig.text(0.05, 0.955, "Who can afford a home in Greater Kampala?", fontsize=11.5, fontweight="bold", va="top")
fig.text(0.05, 0.91, "Share of households for whom the typical listed 1–2 bedroom rent\nwould take more than 30% of income",
         fontsize=7.2, color="#333333", va="top", linespacing=1.3)
handles = [Patch(facecolor=c, edgecolor="none") for *_, c in bands] + [Patch(facecolor="#eeeeea", edgecolor="none")]
leg = fig.legend(handles, [b[2] for b in bands] + ["Too few listings"], loc="lower left", ncol=4,
                 bbox_to_anchor=(0.04, 0.055), frameon=False, fontsize=6.8, handlelength=1.3, columnspacing=1.2)
fig.text(0.05, 0.035, "Early findings from PhD research, University of Johannesburg. Full study in preparation for peer review.",
         fontsize=5.4, color="#555555")
fig.text(0.05, 0.015, "Data: online property listings; UBOS Census 2024 & UNHS 2019/20. Basemap © OpenStreetMap contributors.",
         fontsize=5.0, color="#777777")
out = p("outputs/social")
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / "affordability_social_1080.png", dpi=200, facecolor="white")
print("saved", out / "affordability_social_1080.png", "| sub-counties shown:", int(sub["share"].notna().sum()))
