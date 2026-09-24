"""Map version of the "Just move further out?" graphic (square 1080 x 1080, wide 1600 x 900).

Central Division -> Kira Division -> Goma Division on a map of Greater Kampala, with a
card per stop: median monthly rent of listed 1-2 bedroom homes, the rent the area's
median household can afford at 30% of income, and the share of households priced out.
Other sub-counties are shown as outlines for context.

  python scripts/social_move_further_out_map.py  ->  outputs/social/move_further_out_map_{square,wide,substack}.png
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch, FancyBboxPatch
from pyproj import Transformer

import _common  # noqa: F401
from gkma.config import load_config, p
from gkma.viz import pubmaps as pm

plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
INK, MUTED, FAINT, RED, BLUE, BG = "#1d2330", "#5b6474", "#d9dee6", "#9b1030", "#1f5fa8", "#f5f7f9"
cfg = load_config()
g = cfg["geography"]
crs = cfg["project"]["crs_projected"]
D = json.loads(p("outputs/interactive/explorer_data.json").read_text())
T = {t["key"]: t for t in D["tour"]}

sc = gpd.read_file(p(g["subcounties"])).to_crs(crs)
sc["key"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
sc = pm.clip_land(sc)

STOPS = [("Kampala/Central Division", "1", "Central Division", "Kampala · city centre"),
         ("Wakiso/Kira Division", "2", "Kira Division", "Wakiso"),
         ("Mukono/Goma Division", "3", "Goma Division", "Mukono · most affordable area measured")]
k = lambda v: f"UGX {v / 1e6:.1f} million".replace(".0 million", " million") if v >= 1e6 else f"UGX {round(v, -3):,.0f}"  # noqa: E731


def draw(w, h, name, cards, extent, map_rect, labels=("Entebbe", "Mukono", "Nansana", "Kajjansi", "Gayaza", "Kasangati")):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)
    wide = w > h
    ax = fig.add_axes(map_rect)
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    (x0, x1), (y0, y1) = t.transform([extent[0], extent[2]], [extent[1], extent[3]])
    pm._background(ax, (x0, y0, x1, y1))
    ax.set_aspect("equal", adjustable="datalim")
    pm.base()["land"].plot(ax=ax, facecolor="#eceae4", edgecolor="none", zorder=2)
    sc.boundary.plot(ax=ax, color="#c9c6be", lw=0.6, zorder=3)                  # sub-county outlines for context
    r = pm.base()["roads"]
    r[r["kind"].isin(["northern_bypass", "expressway"])].plot(ax=ax, color="#8c8c8c", lw=1.2, zorder=4)
    pm.base()["districts"].boundary.plot(ax=ax, color="#8a8f98", lw=0.8, zorder=4)
    pts = []
    for key, num, *_ in STOPS:
        poly = sc[sc["key"] == key]
        poly.plot(ax=ax, facecolor=RED, alpha=0.85, edgecolor=INK, lw=2, zorder=5)
        c = poly.geometry.union_all().representative_point()
        pts.append((c.x, c.y))
        ax.scatter([c.x], [c.y], s=560, color="white", edgecolor=INK, lw=2, zorder=7)
        ax.text(c.x, c.y, num, ha="center", va="center", fontsize=15, weight="bold", color=INK, zorder=8)
    for (ax_, ay), (bx, by) in zip(pts, pts[1:]):
        ax.annotate("", xy=(bx, by), xytext=(ax_, ay), zorder=6,
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=2, ls=(0, (4, 3)), shrinkA=16, shrinkB=16,
                                    mutation_scale=18))
    lab = pm.base()["labels"]
    for nm in labels:
        rr = lab[(lab["label"] == nm) & (lab["level"] == "main")]
        if len(rr):
            x, y = rr.geometry.iloc[0].x, rr.geometry.iloc[0].y
            if x0 < x < x1 and y0 < y < y1:
                ax.text(x, y, nm, fontsize=11, color=MUTED, ha="center", va="center", zorder=6, style="italic")
    ax.set_axis_off()

    # title
    fig.text(0.05, 0.955, "Just move further out?", fontsize=38 if not wide else 36, weight="bold", color=INK,
             va="top")
    fig.text(0.05, 0.885 if not wide else 0.855,
             "Median monthly rent of listed 1–2 bedroom homes, against what each area's median household\n"
             "can afford at 30% of income, moving out from Kampala's centre",
             fontsize=15 if not wide else 14.5, color=MUTED, va="top", linespacing=1.35)

    # cards
    for (key, num, nm, where), (cx, cy), (px, py) in zip(STOPS, cards, pts):
        s = T[key]
        cw, ch = (0.35, 0.19) if not wide else (0.235, 0.24)
        fig.patches.append(FancyBboxPatch((cx, cy), cw, ch, boxstyle="round,pad=0.006,rounding_size=0.01",
                                          transform=fig.transFigure, facecolor="white", edgecolor=FAINT, lw=1.2,
                                          zorder=10))
        lx = cx + 0.015
        fig.text(lx, cy + ch - 0.018, f"{num}  {nm}", fontsize=16, weight="bold", color=INK, va="top", zorder=11)
        fig.text(lx, cy + ch - 0.052, where, fontsize=11, color=MUTED, va="top", zorder=11)
        yy = cy + ch - (0.085 if not wide else 0.1)
        step = 0.034 if not wide else 0.046
        fig.text(lx, yy, "Median monthly rent", fontsize=11, color=MUTED, va="top", zorder=11)
        fig.text(cx + cw - 0.012, yy, k(s["rent"]), fontsize=13.5, color=RED, weight="bold", va="top", ha="right",
                 zorder=11)
        fig.text(lx, yy - step, "Affordable at 30% of income", fontsize=11, color=MUTED, va="top", zorder=11)
        fig.text(cx + cw - 0.012, yy - step, k(0.3 * s["income"]), fontsize=13.5, color=BLUE, weight="bold",
                 va="top", ha="right", zorder=11)
        fig.text(lx, yy - 2 * step, "Households priced out", fontsize=11, color=MUTED, va="top", zorder=11)
        fig.text(cx + cw - 0.012, yy - 2 * step, f"{s['grad']['30']:.0%}", fontsize=13.5, color=INK, weight="bold",
                 va="top", ha="right", zorder=11)
        # leader line from the card to the area
        edge = (cx + cw / 2, cy + ch) if cy < 0.3 else (cx + cw, cy + ch / 2)
        fig.add_artist(ConnectionPatch(xyA=edge, coordsA=fig.transFigure, xyB=(px, py), coordsB=ax.transData,
                                       color=INK, lw=1, alpha=0.6, zorder=9))

    # punchline + source
    by = 0.055 if not wide else 0.05
    fig.patches.append(FancyBboxPatch((0.05, by), 0.9, 0.055, boxstyle="round,pad=0.006,rounding_size=0.01",
                                      transform=fig.transFigure, facecolor=INK, edgecolor="none", zorder=10))
    rd = 1 - T[STOPS[2][0]]["rent"] / T[STOPS[0][0]]["rent"]
    idr = 1 - T[STOPS[2][0]]["income"] / T[STOPS[0][0]]["income"]
    fig.text(0.5, by + 0.0275, f"Median rent falls {rd:.0%}. Median income falls {idr:.0%}. "
             "The gap narrows, but it never closes.", fontsize=15.5 if not wide else 16, weight="bold",
             color="white", ha="center", va="center", zorder=11)
    fig.text(0.05, 0.018, "Median asking rents of 10,643 online listings, 2025–26; modelled household incomes "
             "(UBOS UNHS 2019/20, Census 2024). Figures are for sub-counties with at least 20 rental "
             "listings. Basemap © OpenStreetMap contributors.", fontsize=8.5, color=MUTED,
             va="bottom", wrap=True)
    fig.savefig(p("outputs/social") / name, dpi=100, facecolor=BG)
    plt.close(fig)
    print("wrote", name)


draw(1080, 1080, "move_further_out_map_square.png",
     cards=[(0.03, 0.40), (0.03, 0.625), (0.60, 0.16)],
     extent=[32.48, 0.24, 32.83, 0.49], map_rect=[0.0, 0.1, 1.0, 0.72], labels=("Mukono", "Nansana", "Kajjansi"))
draw(1600, 900, "move_further_out_map_wide.png",
     cards=[(0.05, 0.14), (0.05, 0.47), (0.715, 0.2)],
     extent=[32.42, 0.24, 32.89, 0.49], map_rect=[0.0, 0.1, 1.0, 0.68])


# ---- Substack version: 1456 x 762 (1.91:1), the ratio Substack uses for post previews, so nothing is cropped.
def draw_substack(name="move_further_out_map_substack.png", w=1456, h=762):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)
    # map on the right
    ax = fig.add_axes([0.44, 0.0, 0.56, 1.0])
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    (x0, x1), (y0, y1) = t.transform([32.53, 32.84], [0.26, 0.49])
    pm._background(ax, (x0, y0, x1, y1))
    ax.set_aspect("equal", adjustable="datalim")
    pm.base()["land"].plot(ax=ax, facecolor="#eceae4", edgecolor="none", zorder=2)
    sc.boundary.plot(ax=ax, color="#c9c6be", lw=0.6, zorder=3)
    r = pm.base()["roads"]
    r[r["kind"].isin(["northern_bypass", "expressway"])].plot(ax=ax, color="#8c8c8c", lw=1.2, zorder=4)
    pm.base()["districts"].boundary.plot(ax=ax, color="#8a8f98", lw=0.8, zorder=4)
    pts = []
    for key, num, *_ in STOPS:
        poly = sc[sc["key"] == key]
        poly.plot(ax=ax, facecolor=RED, alpha=0.85, edgecolor=INK, lw=2, zorder=5)
        c = poly.geometry.union_all().representative_point()
        pts.append((c.x, c.y))
        ax.scatter([c.x], [c.y], s=620, color="white", edgecolor=INK, lw=2, zorder=7)
        ax.text(c.x, c.y, num, ha="center", va="center", fontsize=16, weight="bold", color=INK, zorder=8)
    for (ax_, ay), (bx, by) in zip(pts, pts[1:]):
        ax.annotate("", xy=(bx, by), xytext=(ax_, ay), zorder=6,
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=2, ls=(0, (4, 3)), shrinkA=17, shrinkB=17,
                                    mutation_scale=18))
    lab = pm.base()["labels"]
    for nm in ("Mukono", "Nansana", "Gayaza"):
        rr = lab[(lab["label"] == nm) & (lab["level"] == "main")]
        if len(rr):
            x, y = rr.geometry.iloc[0].x, rr.geometry.iloc[0].y
            if x0 < x < x1 and y0 < y < y1:
                ax.text(x, y, nm, fontsize=11, color=MUTED, ha="center", va="center", zorder=6, style="italic")
    ax.set_axis_off()
    # left panel
    fig.patches.append(FancyBboxPatch((0, 0), 0.44, 1, boxstyle="square,pad=0", transform=fig.transFigure,
                                      facecolor=BG, edgecolor="none", zorder=1))
    L = 0.035
    fig.text(L, 0.9, "Just move further out?", fontsize=34, weight="bold", color=INK, va="top", zorder=2)
    fig.text(L, 0.79, "Median monthly rent of listed 1–2 bedroom homes, against\nwhat each area's median household "
             "can afford at 30%\nof income, moving out from Kampala's centre", fontsize=13.5, color=MUTED, va="top",
             linespacing=1.35, zorder=2)
    cols = [L, L + 0.165, L + 0.26, L + 0.35]
    hy = 0.585
    for x, txt in zip(cols, ["", "Median\nmonthly rent", "Affordable\n(30% of income)", "Priced\nout"]):
        fig.text(x, hy, txt, fontsize=10.5, color=MUTED, va="bottom", linespacing=1.2, zorder=2)
    fig.add_artist(plt.Line2D([L, 0.425], [hy - 0.012, hy - 0.012], color=FAINT, lw=1.2,
                              transform=fig.transFigure))
    for i, (key, num, nm, where) in enumerate(STOPS):
        s = T[key]
        y = hy - 0.05 - i * 0.095
        fig.text(cols[0], y, f"{num}  {nm}", fontsize=14.5, weight="bold", color=INK, va="center", zorder=2)
        fig.text(cols[0] + 0.022, y - 0.038, where.split(" · ")[0], fontsize=10.5, color=MUTED, va="center", zorder=2)
        short = lambda v: f"{v / 1e6:.1f}m".replace(".0m", "m") if v >= 1e6 else f"{round(v, -3) / 1e3:.0f}k"  # noqa
        fig.text(cols[1], y, f"UGX {short(s['rent'])}", fontsize=14.5, weight="bold", color=RED, va="center", zorder=2)
        fig.text(cols[2], y, f"UGX {short(0.3 * s['income'])}", fontsize=14.5, weight="bold", color=BLUE,
                 va="center", zorder=2)
        fig.text(cols[3], y, f"{s['grad']['30']:.0%}", fontsize=14.5, weight="bold", color=INK, va="center", zorder=2)
    rd = 1 - T[STOPS[2][0]]["rent"] / T[STOPS[0][0]]["rent"]
    idr = 1 - T[STOPS[2][0]]["income"] / T[STOPS[0][0]]["income"]
    fig.patches.append(FancyBboxPatch((L, 0.1), 0.39, 0.105, boxstyle="round,pad=0.006,rounding_size=0.012",
                                      transform=fig.transFigure, facecolor=INK, edgecolor="none", zorder=2))
    fig.text(L + 0.015, 0.1525, f"Median rent falls {rd:.0%}. Median income falls {idr:.0%}.\n"
             "The gap narrows, but it never closes.", fontsize=14, weight="bold", color="white", va="center",
             linespacing=1.35, zorder=3)
    fig.text(L, 0.035, "Median asking rents, 10,643 online listings, 2025–26; modelled incomes (UBOS).\n"
             "Sub-counties with at least 20 rental listings. Basemap © OpenStreetMap contributors.", fontsize=8.5,
             color=MUTED, va="bottom", linespacing=1.3, zorder=2)
    fig.savefig(p("outputs/social") / name, dpi=100, facecolor=BG)
    plt.close(fig)
    print("wrote", name)


draw_substack()
