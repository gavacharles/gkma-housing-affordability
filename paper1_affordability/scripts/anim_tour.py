"""Animated tour of the affordability map (1080 x 1080 MP4, about 48 seconds).

Zooms from Greater Kampala to Kampala, Wakiso and Mukono and to the least and
most affordable sub-counties, with a caption card of each stop's index values.
Parishes are shaded by the share of households unable to afford the median
listed 1-2 bedroom rent of their district at 30% of income.

  python paper1_affordability/scripts/anim_tour.py  ->  outputs/animations/affordability_tour.mp4
Run scripts/export_explorer_data.py first (tour stops and area medians).
"""
import json
import textwrap

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
from scipy.stats import norm

import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import _common  # noqa: F401
from gkma.config import load_config, p
from gkma.viz import pubmaps as pm

try:
    import imageio_ffmpeg
    matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    HAVE_MP4 = True
except ImportError:
    HAVE_MP4 = False

plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
INK, MUTED, ACCENT = "#1f1f1f", "#5a5a5a", "#9b1030"
OUT = p("paper1_affordability/outputs/animations")
cfg = load_config()
g = cfg["geography"]
crs = cfg["project"]["crs_projected"]
D = json.loads(p("paper1_affordability/outputs/interactive/explorer_data.json").read_text())
x0, y0, x1, y1 = pm._extent("main")
S = 1000 / (x1 - x0)

# parishes shaded by share unable to afford their district's median rent at 30%
cpi = float(pd.read_csv(p("data/external/cpi_uplift.csv")).query("series == 'headline'")["uplift"].iloc[0])
inc = pd.read_csv(p(cfg["income"]["table"])).set_index("unit")
sig = pd.Series(np.sqrt(2) * norm.ppf((inc["gini"] + 1) / 2), index=inc.index)
par = gpd.read_file(p(cfg["income"]["parish_income"])).dropna(subset=["median_income_2019_20", "households"])
par["district"] = par[g["district_name_col"]].str.title()
rent = {k: v["rent"] for k, v in D["areas"].items() if v["rent"]}
R = par["district"].map(rent).fillna(rent["GKMA"])
par["out"] = norm.cdf((np.log(R / 0.30) - np.log(par["median_income_2019_20"] * cpi)) / par["district"].map(sig))
par = pm.clip_land(par.to_crs(crs))

sc = gpd.read_file(p(g["subcounties"])).to_crs(crs)
sc["area"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
dp = sc.dissolve(g["district_name_col"]).reset_index()
dp["area"] = dp[g["district_name_col"]].str.title()
sc, dp = pm.clip_land(sc), pm.clip_land(dp)                # outlines follow the shoreline


def box_to_lims(b):
    bx, by, bw, bh = b
    return (x0 + bx / S, x0 + (bx + bw) / S), (y1 - (by + bh) / S, y1 - by / S)


cmap = LinearSegmentedColormap.from_list("out", ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"])
fig = plt.figure(figsize=(10.8, 10.8), dpi=100, facecolor="white")
ax = fig.add_axes([0, 0, 1, 1])
pm._background(ax, (x0, y0, x1, y1))
par.plot(ax=ax, column="out", cmap=cmap, vmin=0, vmax=1, edgecolor="white", linewidth=0.25, zorder=3)
pm._overlay(ax, roads=True, labels=True, divisions=False)
ax.set_axis_off()
ax.set_aspect("equal", adjustable="datalim")                # fill the square frame, no white bands
outlines = {}
for t in D["tour"]:
    if t["key"] != "GKMA":
        src = dp if "/" not in t["key"] else sc
        geom = src[src["area"] == t["key"]]
        outlines[t["key"]] = (geom, [])

# caption card
card = FancyBboxPatch((0.035, 0.605), 0.46, 0.365, boxstyle="round,pad=0.012,rounding_size=0.015",
                      transform=fig.transFigure, facecolor="white", edgecolor="#c3cad5", lw=1, zorder=20, alpha=0.96)
fig.patches.append(card)
T = {k: fig.text(0.06, y, "", fontsize=s, color=c, weight=w, zorder=21, va="top")
     for k, y, s, c, w in [("step", 0.955, 12, MUTED, "normal"), ("name", 0.93, 27, INK, "bold"),
                           ("blurb", 0.885, 14, MUTED, "normal"), ("hero", 0.852, 34, ACCENT, "bold"),
                           ("sub", 0.797, 13, MUTED, "normal"), ("kv", 0.705, 14, MUTED, "normal"),
                           ("kv2", 0.705, 14, INK, "bold")]}
T["kv2"].set_x(0.30)
# comparison row: share priced out at 30%, 50%, 80% of income and under the basic-needs test
CMP = [(fig.text(x, 0.772, "", fontsize=19, color=INK, weight="bold", zorder=21, va="top", ha="center"),
        fig.text(x, 0.742, "", fontsize=11, color=MUTED, zorder=21, va="top", ha="center"))
       for x in (0.105, 0.215, 0.325, 0.435)]
fig.text(0.965, 0.02, "Share of households unable to afford their district's median listed 1–2 bedroom rent at 30% "
         "of income.\n10,643 online listings, 2025–26; modelled parish incomes (UBOS UNHS 2019/20, Census 2024).",
         fontsize=9.5, color=MUTED, ha="right", va="bottom", zorder=21,
         bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=3))

drawn = []


def set_card(i):
    for ln in drawn:
        ln.remove()
    drawn.clear()
    if i is None:                                          # closing card, worded as in the explorer
        for k in ("hero", "sub", "kv2"):
            T[k].set_text("")
        for v, lab in CMP:
            v.set_text(""), lab.set_text("")
        T["step"].set_text("AND BUYING?")
        T["name"].set_text("Nowhere comes close")
        T["blurb"].set_text(textwrap.fill(
            "On typical Ugandan mortgage terms (about 18% interest, 30% deposit, 20 years), the Ownership "
            "Affordability Index is 3.7 for Greater Kampala. Even the most affordable sub-county to buy in, "
            "Nansana, scores 20 out of 100.", 50))
        T["blurb"].set_fontsize(15)
        T["kv"].set_position((0.06, 0.70))
        T["kv"].set_text("Explore the map yourself:\ngavacharles.github.io/kampala-affordability-explorer")
        return
    T["blurb"].set_fontsize(14)
    T["kv"].set_position((0.06, 0.705))
    t = D["tour"][i]
    T["step"].set_text(f"STOP {i + 1} OF {len(D['tour'])}")
    T["name"].set_text(t["name"])
    T["blurb"].set_text(t["blurb"])
    T["hero"].set_text(f"{t['out']:.0%} priced out")
    T["sub"].set_text("of households at 30% of income (median 1–2 bedroom rent)")
    for (v, lab), (val, name) in zip(CMP, [(t["grad"]["30"], "at 30%"), (t["grad"]["50"], "at 50%"),
                                           (t["grad"]["80"], "at 80%"), (t["resid"], "basic needs")]):
        v.set_text(f"{val:.0%}"), lab.set_text(name)
    T["kv"].set_text("Median listed rent\nMedian household income\nAffordability index")
    T["kv2"].set_text(f"UGX {t['rent']:,.0f} a month\nUGX {round(t['income'], -3):,.0f} a month\n"
                      f"{t['rai']:.0f} out of 100")
    if t["key"] in outlines:
        drawn.extend(outlines[t["key"]][0].boundary.plot(ax=ax, color=INK, linewidth=2.8, zorder=8).collections[-1:])


def ease(u):
    return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2


FULL = [0, 0, 1000, D["viewbox"][1]]
stops = [t["box"] for t in D["tour"]] + [FULL]
MOVE, HOLD = 30, 110                                     # frames at 24 fps
frames = []
prev = FULL
for i, b in enumerate(stops):
    for k in range(MOVE):
        frames.append((i, prev, b, ease((k + 1) / MOVE)))
    frames += [(i, b, b, 1.0)] * (HOLD + (24 if i == len(stops) - 1 else 0))
    prev = b
state = {"i": -1}


def draw(f):
    i, a, b, u = frames[f]
    if i != state["i"]:
        set_card(i if i < len(D["tour"]) else None)
        state["i"] = i
    box = [a[j] + (b[j] - a[j]) * u for j in range(4)]
    (xa, xb), (ya, yb) = box_to_lims(box)
    ax.set_xlim(xa, xb)
    ax.set_ylim(ya, yb)
    return []


anim = animation.FuncAnimation(fig, draw, frames=len(frames), blit=False)
if HAVE_MP4:
    anim.save(OUT / "affordability_tour.mp4", writer=animation.FFMpegWriter(fps=24, bitrate=2200,
                                                                          extra_args=["-pix_fmt", "yuv420p"]), dpi=100)
draw(len(frames) // 5)
fig.savefig(OUT / "affordability_tour_still.png", dpi=100)
print("wrote affordability_tour", len(frames), "frames")
