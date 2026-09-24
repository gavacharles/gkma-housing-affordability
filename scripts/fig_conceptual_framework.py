"""Conceptual framework figure (publication format, 170 mm wide).

  python scripts/fig_conceptual_framework.py   -> outputs/maps/00_conceptual_framework.{pdf,tif,png}
"""
import _common  # noqa: F401
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from gkma.viz import pubmaps as pm

W, H = pm.FULL, pm.FULL * 0.73
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(5, 78)
ax.axis("off")

INK, MUTED = "#1a1a1a", "#555555"
C_THEORY, C_DRIVER, C_CORE, C_OUT, C_FILTER = "#eef3fa", "#f7f7f5", "#dbe8f5", "#fde9e4", "#fff7df"


def box(x, y, w, h, title, body="", fc="#ffffff", ec="#7a7a7a", tag=None, bold=True, fs=6.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                fc=fc, ec=ec, lw=0.6))
    ax.text(x + 1.2, y + h - 1.4, title, fontsize=fs + 0.4, fontweight="bold" if bold else "normal",
            va="top", ha="left", color=INK)
    if body:
        ax.text(x + 1.2, y + h - 4.3 - 2.3 * title.count("\n"), body, fontsize=fs - 0.6, va="top", ha="left", color=MUTED, linespacing=1.25)
    if tag:
        ax.text(x + w - 1.0, y + h - 1.4, tag, fontsize=5.6, va="top", ha="right", color="#2166ac",
                fontweight="bold")


def arrow(x0, y0, x1, y1, style="-|>", ls="-", color="#4d4d4d", lw=0.8, rad=0.0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=7, lw=lw,
                                 color=color, linestyle=ls, connectionstyle=f"arc3,rad={rad}"))


# --- theory band -------------------------------------------------------------
ax.text(1, 77.2, "Theoretical lenses", fontsize=7, fontweight="bold", va="top")
theories = [("T1  Hedonic price theory", "Rosen (1974)"),
            ("T2  Bid-rent theory", "Alonso (1964); Mills (1967);\nMuth (1969)"),
            ("T3  Property rights &\n      tenure security", "de Soto (2000); Besley (1995)"),
            ("T4  Housing affordability", "Hulchanski (1995); Stone (2006);\nKutty (2005); NAR index"),
            ("T5  Spatial heterogeneity\n      & dependence", "Anselin (1995);\nFotheringham et al. (2002)")]
for i, (name, auth) in enumerate(theories):
    x = 1 + i * 19.8
    box(x, 65.2, 18.6, 9.8, name, auth, fc=C_THEORY, ec="#9fbfd9", fs=5.9)

# --- determinants (left) -----------------------------------------------------
ax.text(1, 63.6, "Determinants", fontsize=7, fontweight="bold", va="top")
drivers = [("Structural attributes", "bedrooms, bathrooms, plot size,\ntype, finish (text-mined)", "T1"),
           ("Location & accessibility", "CBD, Expressway, Northern Bypass,\nroads, schools, markets, taxi stages", "T2"),
           ("Neighbourhood status", "Census 2024 wealth index,\nnight-time lights", "T2"),
           ("Tenure & title", "mailo, freehold, leasehold, kibanja;\ntitle disclosed or not", "T3"),
           ("Environmental risk", "wetlands / flood exposure", "T2")]
for i, (t, b, tag) in enumerate(drivers):
    y = 52.5 - i * 11
    box(1, y, 27, 8.8, t, b, fc=C_DRIVER, tag=tag)
    arrow(28.6, y + 4.4, 35.5, 38 + (2 - i) * 1.8)

# --- core: price formation ---------------------------------------------------
box(36, 27, 27, 22.5, "Asking prices & rents", "per bedroom, per decimal\n\n"
    "• implicit prices of attributes (hedonic OLS)\n"
    "• vary across space (GWR / MGWR)\n"
    "• non-linear, interacting effects\n  (RF, XGBoost, LightGBM + SHAP)",
    fc=C_CORE, ec="#6a8fbf", tag="T1 T5", fs=6.6)

# --- visibility filter (below core) -------------------------------------------
box(36, 7.5, 27, 12.5, "Market visibility filter",
    "Online listings capture the formal, titled,\nupper segment; informal rentals (muzigo)\nand kibanja are largely invisible",
    fc=C_FILTER, ec="#d9b44a", tag="T3", fs=6.2)
arrow(49.5, 20.3, 49.5, 26.7, color="#b8860b")
ax.text(51, 23.5, "selects what is observed", fontsize=5.4, color="#8a6d1a", va="center", style="italic")

# --- right column ------------------------------------------------------------
box(70, 56, 27, 8.2, "Incomes & mortgage terms",
    "parish incomes (UNHS × Census 2024);\nBoU lending rate, deposit, term", fc="#ffffff", ec="#7a7a7a", fs=6.0)
box(70, 41, 27, 12.5, "Affordability index",
    "RAI / OAI: rent, repayment vs income\nAGI: share priced out (10–80% burden)\nResidual income vs poverty line",
    fc=C_OUT, ec="#e08a6d", tag="T4", fs=6.2)
box(70, 24.5, 27, 12.5, "Implied land value",
    "price − depreciated replacement\ncost (CAHF, UBOS CIPI)\n→ land share of house prices",
    fc=C_OUT, ec="#e08a6d", tag="T2", fs=6.2)
box(70, 7.5, 27, 12.5, "Policy evidence",
    "GKMA, district and sub-county\nevidence on prices, drivers,\naffordability and land value",
    fc="#ffffff", ec="#7a7a7a", fs=6.2)
arrow(83.5, 55.8, 83.5, 53.9)                     # income -> affordability
arrow(63.4, 44, 69.6, 47.5)                       # prices -> affordability
arrow(63.4, 32, 69.6, 31)                         # prices -> land value
arrow(83.5, 24.3, 83.5, 20.4)                     # land value -> policy
ax.plot([97.4, 98.9, 98.9], [47, 47, 14], color="#4d4d4d", lw=0.8)   # affordability -> policy (margin route)
arrow(98.9, 14, 97.4, 14)
ax.text(64.2, 47.4, "vs incomes", fontsize=5.2, color=MUTED, style="italic")
ax.text(64.4, 33.2, "residual", fontsize=5.2, color=MUTED, style="italic")

pm._save(fig, "00_conceptual_framework",
         title="Conceptual framework of the study",
         note="Theoretical lenses (T1–T5) inform the determinants of asking prices and rents, the "
              "decomposition into land and structure, and the affordability gap. Online listings observe "
              "the formal, titled segment of the market, which conditions all observed outcomes.",
         sources="Authors' elaboration.")
print("saved outputs/maps/00_conceptual_framework.*")
