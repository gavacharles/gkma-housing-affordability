"""Animated visualisations for talks and social media (1080 x 1080).

  1. priced_out_threshold  parish map: share of households unable to afford the
                           typical listed GKMA 1-2 bedroom rent as the tolerable
                           burden rises from 10% to 80% of income
  2. hundred_households    100 households: already below the poverty line, pushed
                           below it by the typical rent, able to afford it

  python scripts/anim_affordability.py  ->  outputs/animations/*.gif, *.mp4
"""
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon, Rectangle
from scipy.stats import norm

import _common  # noqa: F401
from gkma.config import load_config, p
from gkma.viz import pubmaps as pm

try:
    import imageio_ffmpeg
    matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    HAVE_MP4 = True
except ImportError:
    HAVE_MP4 = False

OUT = p("outputs/animations")
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
INK, MUTED, BG = "#1f1f1f", "#5a5a5a", "#ffffff"
GREY, RED, BLUE = "#8c8c8c", "#bd0026", "#08519c"
SIZE, DPI = 10.8, 100                                     # 1080 x 1080 px


def save(anim, name, fps):
    anim.save(OUT / f"{name}.gif", writer=animation.PillowWriter(fps=fps), dpi=DPI)
    if HAVE_MP4:
        anim.save(OUT / f"{name}.mp4", writer=animation.FFMpegWriter(fps=fps, bitrate=4000,
                                                                     extra_args=["-pix_fmt", "yuv420p"]), dpi=DPI)
    print("wrote", name, "(gif" + (", mp4)" if HAVE_MP4 else ")"))


# ---------------------------------------------------------------- shared inputs
cfg = load_config()
g = cfg["geography"]
cpi = float(pd.read_csv(p("data/external/cpi_uplift.csv")).query("series == 'headline'")["uplift"].iloc[0])
inc = pd.read_csv(p(cfg["income"]["table"])).set_index("unit")
sig = pd.Series(np.sqrt(2) * norm.ppf((inc["gini"] + 1) / 2), index=inc.index)
par = gpd.read_file(p(cfg["income"]["parish_income"]))
par["district"] = par[g["district_name_col"]].str.title()
par["income"] = par["median_income_2019_20"] * cpi
par["sigma"] = par["district"].map(sig)
T = p("outputs/tables")
gk = pd.read_csv(T / "affordability_index_gkma.csv").iloc[0]
RENT = float(gk["median_rent"])                           # median listed 1-2 bedroom rent, GKMA
ok = par.dropna(subset=["income", "sigma", "households"])
W = ok["households"] / ok["households"].sum()


def share_out(b):
    """Household-weighted share unable to afford RENT at burden b, and per parish."""
    z = (np.log(RENT / b) - np.log(ok["income"])) / ok["sigma"]
    s = pd.Series(norm.cdf(z), index=ok.index)
    return float((W * s).sum()), s


# ---------------------------------------------------------------- 1. threshold map
def threshold_map():
    land = pm.clip_land(par.to_crs(cfg["project"]["crs_projected"]))
    ext = pm._extent("main")
    cmap = LinearSegmentedColormap.from_list("out", ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"])
    steps = list(np.round(np.arange(0.10, 0.801, 0.01), 2))
    holds = {0.30: 14, 0.50: 12, 0.80: 22}                 # pause on the reference thresholds
    frames = [b for b in steps for _ in range(holds.get(b, 1))]

    fig = plt.figure(figsize=(SIZE, SIZE), dpi=DPI, facecolor=BG)
    ax = fig.add_axes([0.03, 0.17, 0.94, 0.61])
    pm._background(ax, ext)
    pm._overlay(ax, roads=True, labels=True, divisions=False)
    polys = land[land.index.isin(ok.index)]
    none = land[~land.index.isin(ok.index)]
    none.plot(ax=ax, facecolor="#d9d9d9", edgecolor="white", linewidth=0.2, zorder=2)
    coll = polys.plot(ax=ax, column=pd.Series(0.0, index=polys.index), cmap=cmap, vmin=0, vmax=1,
                      edgecolor="white", linewidth=0.2, zorder=3).collections[-1]
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    fig.text(0.05, 0.955, "Who can afford the typical listed rent?", fontsize=30, weight="bold", color=INK)
    fig.text(0.05, 0.915, f"Median listed 1–2 bedroom rent in Greater Kampala: UGX {RENT:,.0f} a month",
             fontsize=16, color=MUTED)
    big = fig.text(0.05, 0.858, "", fontsize=22, color=INK)
    # colour bar
    cb = fig.add_axes([0.05, 0.806, 0.36, 0.016])
    cb.imshow(np.linspace(0, 1, 256)[None, :], aspect="auto", cmap=cmap, extent=[0, 100, 0, 1])
    cb.set_yticks([]), cb.set_xticks([0, 50, 100], ["0%", "50%", "100%"])
    cb.tick_params(labelsize=11, length=0, colors=MUTED)
    for s in cb.spines.values():
        s.set_visible(False)
    fig.text(0.43, 0.807, "share of each parish's households who cannot afford it", fontsize=12, color=MUTED)
    # threshold slider
    sl = fig.add_axes([0.08, 0.075, 0.84, 0.05])
    sl.set_xlim(8.5, 81.5), sl.set_ylim(0, 1), sl.axis("off")
    sl.add_patch(Rectangle((10, 0.42), 70, 0.16, color="#e5e5e5", zorder=1))
    fill = sl.add_patch(Rectangle((10, 0.42), 0, 0.16, color=INK, zorder=2))
    knob, = sl.plot([10], [0.5], "o", ms=18, color=INK, zorder=3)
    for x, t in [(10, "10%"), (30, "30%\nusual norm"), (50, "50%\n'severe'"), (80, "80%")]:
        sl.text(x, -0.25, t, ha="center", va="top", fontsize=12, color=MUTED)
    fig.text(0.08, 0.135, "Share of income a household is willing to spend on rent", fontsize=14, color=INK)
    fig.text(0.05, 0.012, "Modelled parish incomes (UBOS UNHS 2019/20, Census 2024); 10,643 online listings, 2025–26. "
             "Grey: parish not matched to census.", fontsize=9.5, color=MUTED)

    def draw(b):
        tot, s = share_out(b)
        coll.set_array(s.reindex(polys.index).to_numpy())
        big.set_text(f"At {b:.0%} of income, {tot:.0%} of households are priced out")
        fill.set_width(100 * b - 10)
        knob.set_data([100 * b], [0.5])
        return coll, big, fill, knob

    anim = animation.FuncAnimation(fig, lambda i: draw(frames[i]), frames=len(frames), blit=False)
    save(anim, "priced_out_threshold", fps=10)
    draw(0.30)
    fig.savefig(OUT / "priced_out_threshold_still.png", dpi=DPI)
    plt.close(fig)


# ---------------------------------------------------------------- 2. 100 households
def hundred_households():
    d = pd.read_csv(T / "affordability_index_gkma.csv").iloc[0]
    poor = int(round(100 * d["below_nonhousing_min"]))
    pushed = int(round(100 * d["ri_rent"])) - poor
    afford = 100 - poor - pushed
    shortfall = -float(d["ri_rent_median_residual"])

    fig = plt.figure(figsize=(SIZE, SIZE), dpi=DPI, facecolor=BG)
    ax = fig.add_axes([0.14, 0.2, 0.72, 0.56])
    ax.set_xlim(-0.6, 9.6), ax.set_ylim(-0.6, 9.6), ax.set_aspect("equal"), ax.axis("off")
    house = np.array([[-0.34, -0.36], [0.34, -0.36], [0.34, 0.08], [0.0, 0.40], [-0.34, 0.08]])
    order = [(r, c) for r in range(9, -1, -1) for c in range(10)]          # fill top-left first
    icons = [ax.add_patch(Polygon(house + [c, r], closed=True, color="#d0d7e1")) for r, c in order]
    head = fig.text(0.05, 0.93, "", fontsize=30, weight="bold", color=INK)
    sub = fig.text(0.05, 0.875, "", fontsize=17, color=MUTED, wrap=True)
    legend = [fig.text(0.14, 0.14 - 0.035 * i, "", fontsize=15, color=c)
              for i, c in enumerate([GREY, RED, BLUE])]
    fig.text(0.05, 0.02, "Residual-income test: income minus rent must cover basic non-housing needs (UBOS upper "
             "poverty line, uprated to 2026).\nTypical rent = median listed 1–2 bedroom rent in Greater Kampala. "
             "Modelled incomes; 10,643 online listings, 2025–26.", fontsize=9.5, color=MUTED)

    seq = []                                   # (frame kind, index)
    seq += [("intro", 0)] * 18
    seq += [("poor", i) for i in range(1, poor + 1)] + [("poor", poor)] * 18
    seq += [("pushed", i) for i in range(1, pushed + 1)] + [("pushed", pushed)] * 20
    seq += [("afford", afford)] * 34

    def draw(k):
        kind, n = seq[k]
        n_poor = poor if kind in ("pushed", "afford") else (n if kind == "poor" else 0)
        n_push = pushed if kind == "afford" else (n if kind == "pushed" else 0)
        for i, ic in enumerate(icons):
            if i < n_poor:
                ic.set_color(GREY)
            elif i < n_poor + n_push:
                ic.set_color(RED)
            elif kind == "afford":
                ic.set_color(BLUE)
            else:
                ic.set_color("#d0d7e1")
        if kind == "intro":
            head.set_text("100 households in Greater Kampala")
            sub.set_text(f"What happens if each pays the typical listed rent of UGX {RENT:,.0f} a month?")
        elif kind == "poor":
            head.set_text(f"{n_poor} are already below the poverty line")
            sub.set_text("before paying any rent at all.")
        elif kind == "pushed":
            head.set_text(f"{n_push} more would be pushed below it")
            sub.set_text("by paying the rent: housing-induced poverty.")
        else:
            head.set_text(f"Only {afford} in 100 can afford it")
            sub.set_text(f"and still meet their basic needs. The median household would be\n"
                         f"about UGX {round(shortfall, -3):,.0f} a month short.")
        legend[0].set_text(f"■  {n_poor} below the poverty line before rent" if n_poor else "")
        legend[1].set_text(f"■  {n_push} pushed into poverty by the rent" if n_push else "")
        legend[2].set_text(f"■  {afford} can afford it" if kind == "afford" else "")
        return icons

    anim = animation.FuncAnimation(fig, draw, frames=len(seq), blit=False)
    save(anim, "hundred_households", fps=12)
    draw(len(seq) - 1)
    fig.savefig(OUT / "hundred_households_still.png", dpi=DPI)
    plt.close(fig)


threshold_map()
hundred_households()
