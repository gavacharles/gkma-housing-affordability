"""Social graphic for "Just move further out?" (square 1080 x 1080 and wide 1600 x 900).

For three stops moving out from the centre (Central Division -> Kira -> Goma), it shows
the rent the area's median household can afford at 30% of income against the
median listed 1-2 bedroom rent. Figures from outputs/interactive/explorer_data.json
(the explorer's tour stops, which reproduce the paper's index).

  python scripts/social_move_further_out.py  ->  outputs/social/move_further_out_{square,wide}.png
"""
import json

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import _common  # noqa: F401
from gkma.config import p

plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
INK, MUTED, FAINT = "#1d2330", "#5b6474", "#d9dee6"
RED, BLUE, BG = "#9b1030", "#1f5fa8", "#f5f7f9"

D = json.loads(p("outputs/interactive/explorer_data.json").read_text())
T = {t["key"]: t for t in D["tour"]}
STOPS = [("Kampala/Central Division", "Central Division", "Kampala · the city centre"),
         ("Wakiso/Kira Division", "Kira Division", "Wakiso · north-east suburb"),
         ("Mukono/Goma Division", "Goma Division", "Mukono · most affordable area measured")]
rows = [{"name": n, "where": w, "rent": T[k]["rent"], "inc": T[k]["income"], "ok": 0.30 * T[k]["income"],
         "out": T[k]["grad"]["30"]} for k, n, w in STOPS]
rent_drop = 1 - rows[-1]["rent"] / rows[0]["rent"]
inc_drop = 1 - rows[-1]["inc"] / rows[0]["inc"]
m = lambda v: f"{v / 1e6:.1f}m".replace(".0m", "m") if v >= 1e6 else f"{round(v, -3) / 1e3:.0f}k"  # noqa: E731


def draw(w, h, name):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)
    wide = w > h
    L = 0.06                                        # left margin (figure fraction)
    fs = 1.0 if not wide else 0.92
    fig.text(L, 0.94 if not wide else 0.92, "Just move further out?", fontsize=40 * fs, weight="bold", color=INK,
             va="top")
    fig.text(L, 0.868 if not wide else 0.815,
             "What the typical household can afford, against the typical listed 1–2 bedroom rent,\n"
             "moving out from Kampala's centre", fontsize=16 * fs, color=MUTED, va="top", linespacing=1.35)

    top, bot = (0.74, 0.25) if not wide else (0.68, 0.27)
    ax = fig.add_axes([L + 0.3, bot, 0.36 if not wide else 0.46, top - bot])
    ax.set_xlim(0, 1.72e6)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.axis("off")
    for i, r in enumerate(rows):
        ax.plot([r["ok"], r["rent"]], [i, i], color=RED, lw=16 * fs, alpha=0.18, solid_capstyle="round", zorder=1)
        ax.plot([r["ok"], r["rent"]], [i, i], color=RED, lw=2.2, zorder=2)
        ax.scatter([r["ok"]], [i], s=260 * fs, color=BLUE, zorder=3, edgecolor="white", linewidth=2)
        ax.scatter([r["rent"]], [i], s=260 * fs, color=RED, zorder=3, edgecolor="white", linewidth=2)
        x = r["rent"] + 0.07e6
        ax.text(x, i - 0.2, f"UGX {m(r['rent'])} rent", ha="left", va="center", fontsize=14.5 * fs, color=RED,
                weight="bold")
        ax.text(x, i + 0.02, f"UGX {m(r['ok'])} affordable", ha="left", va="center", fontsize=14.5 * fs, color=BLUE,
                weight="bold")
        sep = " · " if wide else "\n"
        ax.text(x, i + 0.24, f"rent = {r['rent'] / r['inc']:.0%} of income{sep}{r['out']:.0%} priced out", ha="left",
                va="top" if not wide else "center", fontsize=12.5 * fs, color=INK, linespacing=1.3)
    # journey rail with stop labels
    rail = fig.add_axes([L, bot, 0.28, top - bot])
    rail.set_xlim(0, 1)
    rail.set_ylim(len(rows) - 0.4, -0.6)
    rail.axis("off")
    rail.plot([0.05, 0.05], [0, len(rows) - 1], color=MUTED, lw=2, ls=(0, (2, 3)), zorder=1)
    for i, r in enumerate(rows):
        rail.scatter([0.05], [i], s=180 * fs, color=INK, zorder=2)
        rail.text(0.13, i - 0.1, r["name"], fontsize=17 * fs, weight="bold", color=INK, va="bottom")
        rail.text(0.13, i + 0.02, r["where"], fontsize=12 * fs, color=MUTED, va="top")

    # legend
    ly = bot - (0.045 if not wide else 0.055)
    fig.text(L, ly, "●", color=BLUE, fontsize=16 * fs, va="center")
    fig.text(L + 0.025, ly, "Affordable rent: 30% of the area's median household income", fontsize=13 * fs,
             color=INK, va="center")
    fig.text(L, ly - 0.035, "●", color=RED, fontsize=16 * fs, va="center")
    fig.text(L + 0.025, ly - 0.035, "Median listed 1–2 bedroom rent in the area", fontsize=13 * fs, color=INK,
             va="center")
    # punchline card
    cy = 0.085 if not wide else 0.05
    card = FancyBboxPatch((L, cy - 0.005), 0.88, 0.07 if not wide else 0.075,
                          boxstyle="round,pad=0.008,rounding_size=0.012", transform=fig.transFigure,
                          facecolor="white", edgecolor=FAINT, lw=1)
    fig.patches.append(card)
    fig.text(L + 0.02, cy + 0.03, f"Rent falls {rent_drop:.0%}. Income falls {inc_drop:.0%}. The gap narrows, but it "
             "never closes.", fontsize=17 * fs, weight="bold", color=INK, va="center")
    fig.text(L, 0.018 if not wide else 0.008 + 0.0,
             "10,643 online listings, 2025–26; modelled household incomes (UBOS UNHS 2019/20, Census 2024). "
             "Areas with at least 20 rental listings.", fontsize=9.5 * fs, color=MUTED, va="bottom") if not wide else None
    if wide:
        fig.text(0.94, 0.94, "10,643 online listings, 2025–26\nmodelled incomes (UBOS)", fontsize=10, color=MUTED,
                 ha="right", va="top", linespacing=1.4)
    fig.savefig(p("outputs/social") / name, dpi=100, facecolor=BG)
    plt.close(fig)
    print("wrote", name)


draw(1080, 1080, "move_further_out_square.png")
draw(1600, 900, "move_further_out_wide.png")
