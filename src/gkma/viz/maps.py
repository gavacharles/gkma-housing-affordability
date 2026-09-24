"""Publication maps (matplotlib). Every function saves PNG (300 dpi) + PDF.

Colour rules: sequential = one hue light->dark (blue for prices/rents, red
for unaffordability); diverging = red <-> grey midpoint <-> blue (GWR
coefficients, Gi* z); cluster maps carry text labels in the legend so
identity is never colour-alone. Units with too few listings are hatched
grey ("insufficient listings"), never silently blank.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Patch

from gkma.config import load_config, p

BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
RED = ["#fbe0dc", "#f5b8ae", "#ee8f80", "#e34948", "#bf3534", "#962526", "#6b1718"]
NEUTRAL = "#f0efec"
SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", BLUE)
SEQ_RED = LinearSegmentedColormap.from_list("seq_red", RED)
DIVERGING = LinearSegmentedColormap.from_list("div", RED[::-1][1:5] + [NEUTRAL] + BLUE[2:6])
LISA_COLORS = {"High-High": "#bf3534", "High-Low": "#f5b8ae", "Low-Low": "#184f95",
               "Low-High": "#9ec5f4", "Not significant": NEUTRAL}
INK, MUTED, EDGE = "#0b0b0b", "#898781", "#c3c2b7"

LABELS = {  # readable names for model variables in figures
    "bedrooms": "Bedrooms", "bathrooms": "Bathrooms", "plot_decimals": "Plot size (decimals)",
    "dist_cbd_km": "Distance to CBD", "dist_major_road_km": "Distance to major road",
    "dist_northern_bypass_km": "Distance to Northern Bypass",
    "dist_entebbe_expressway_km": "Distance to Entebbe Expressway",
    "dist_school_km": "Distance to school", "dist_health_km": "Distance to health facility",
    "dist_market_km": "Distance to market", "dist_taxi_stage_km": "Distance to taxi stage",
    "n_school_1km": "Schools within 1 km", "n_health_1km": "Health facilities within 1 km",
    "n_market_1km": "Markets within 1 km", "n_taxi_stage_1km": "Taxi stages within 1 km",
    "ntl_500m": "Night-time lights", "dist_wetland_km": "Distance to wetland",
    "near_wetland_200m": "Within 200 m of wetland",
    "wealth_index": "Parish wealth index (Census 2024)", "sh_grid": "Parish share on grid power",
    "sh_computer": "Parish share owning a computer", "hh_size": "Parish household size", "in_flood_zone": "In flood zone", "n_postings": "Times re-posted",
    "x_km": "Easting (location)", "y_km": "Northing (location)", "ptype": "Property type",
    "tenure_class": "Tenure", "title_status": "Title status", "source": "Portal",
    "f_self_contained": "Self-contained", "f_boys_quarters": "Boys' quarters", "f_gated": "Gated / walled",
    "f_security": "Security", "f_parking": "Parking", "f_tarmac_access": "Tarmac access",
    "f_pool": "Swimming pool", "f_furnished": "Furnished", "f_storeyed": "Storeyed",
    "f_shell_or_incomplete": "Shell / incomplete", "f_negotiable": "Negotiable",
}


def label(var: str) -> str:
    return LABELS.get(var, var.replace("f_", "").replace("_", " ").capitalize())

mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 11,
                     "axes.titleweight": "bold", "figure.dpi": 110, "savefig.dpi": 300,
                     "text.color": INK, "axes.edgecolor": EDGE})


OUT_DIR = "outputs/maps"  # scripts may override (e.g. outputs/demo/maps)


def _save(fig, name: str):
    out = p(OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(out / f"{name}.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out / f"{name}.png"


def _focus(ax, geoms, margin_m: float = 4000):
    """Zoom to where the data are, not the full (largely rural) district extent."""
    if geoms is None or len(geoms) == 0:
        return
    x0, y0, x1, y1 = geoms.total_bounds
    ax.set_xlim(x0 - margin_m, x1 + margin_m)
    ax.set_ylim(y0 - margin_m, y1 + margin_m)


def _frame(ax, gdf, title: str, note: str | None = None, basemap: bool = False):
    ax.set_axis_off()
    ax.set_title(title, loc="left")
    if basemap:
        try:
            import contextily as cx
            cx.add_basemap(ax, crs=gdf.crs, source=cx.providers.CartoDB.PositronNoLabels, attribution_size=5)
        except Exception:
            pass
    # scale bar (projected CRS in metres)
    x0, x1 = ax.get_xlim()
    y0, _ = ax.get_ylim()
    L = 10_000
    bx, by = x0 + 0.05 * (x1 - x0), y0 + 0.04 * (ax.get_ylim()[1] - y0)
    ax.plot([bx, bx + L], [by, by], color=INK, lw=2)
    ax.text(bx + L / 2, by, "10 km\n", ha="center", va="bottom", fontsize=7)
    ax.annotate("N", xy=(0.95, 0.93), xycoords="axes fraction", ha="center", fontsize=10, weight="bold")
    ax.annotate("", xy=(0.95, 0.92), xytext=(0.95, 0.85), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=INK))
    if note:
        ax.annotate(note, xy=(0, -0.02), xycoords="axes fraction", va="top", fontsize=6.5, color=MUTED)


def _missing(ax, gdf, col):
    miss = gdf[gdf[col].isna()]
    if len(miss):
        miss.plot(ax=ax, facecolor="white", edgecolor=EDGE, hatch="////", linewidth=0.2)


def study_area(units: gpd.GeoDataFrame, pts: gpd.GeoDataFrame | None = None, roads=None,
               label_col: str | None = None, name="01_study_area"):
    fig, ax = plt.subplots(figsize=(7, 7))
    units.plot(ax=ax, facecolor=NEUTRAL, edgecolor="white", linewidth=0.3)
    if label_col and label_col in units:
        units.dissolve(label_col).boundary.plot(ax=ax, color=INK, linewidth=0.8)
        for nm, g in units.dissolve(label_col).iterrows():
            c = g.geometry.representative_point()
            ax.annotate(nm, (c.x, c.y), ha="center", fontsize=8, weight="bold")
    if roads is not None and len(roads):
        roads.plot(ax=ax, color=MUTED, linewidth=0.6)
    if pts is not None:
        for lt, col in [("sale", BLUE[5]), ("rent", RED[4])]:
            s = pts[pts["listing_type"] == lt]
            s.plot(ax=ax, markersize=3, color=col, alpha=0.6, label=f"{lt} listings (n={len(s):,})")
        ax.legend(loc="lower right", frameon=False, fontsize=8)
    _frame(ax, units, "Greater Kampala Metropolitan Area: study area and listings")
    return _save(fig, name)


def choropleth(gdf: gpd.GeoDataFrame, col: str, title: str, name: str, cmap=SEQ_BLUE,
               fmt="{:,.0f}", scheme="quantiles", k=5, note=None, legend_title=""):
    fig, ax = plt.subplots(figsize=(7, 7))
    _missing(ax, gdf, col)
    has = gdf.dropna(subset=[col])
    if len(has) >= k:
        has.plot(ax=ax, column=col, cmap=cmap, scheme=scheme, k=k, edgecolor="white", linewidth=0.25,
                 legend=True, legend_kwds={"loc": "lower right", "frameon": False, "fontsize": 7,
                                           "title": legend_title, "fmt": fmt.replace("{:", "{:")})
    else:
        has.plot(ax=ax, column=col, cmap=cmap, edgecolor="white", linewidth=0.25, legend=True)
    leg = ax.get_legend()
    extra = Patch(facecolor="white", edgecolor=EDGE, hatch="////", label="Insufficient listings")
    _focus(ax, has)
    if leg:  # keep the class-range labels, append the hatch swatch
        labels = [t.get_text() for t in leg.get_texts()] + ["Insufficient listings"]
        ax.legend(handles=list(leg.legend_handles) + [extra], labels=labels, loc="lower right",
                  frameon=False, fontsize=7, title=legend_title, title_fontsize=7)
    _frame(ax, gdf, title, note)
    return _save(fig, name)


def lisa_map(gdf: gpd.GeoDataFrame, title: str, name: str, all_units: gpd.GeoDataFrame | None = None, note=None):
    fig, ax = plt.subplots(figsize=(7, 7))
    if all_units is not None:
        all_units.plot(ax=ax, facecolor="white", edgecolor=EDGE, hatch="////", linewidth=0.2)
    for lab, col in LISA_COLORS.items():
        s = gdf[gdf["lisa_cluster"] == lab]
        if len(s):
            s.plot(ax=ax, color=col, edgecolor="white", linewidth=0.25)
    handles = [Patch(facecolor=c, edgecolor=EDGE, label=f"{l} ({(gdf['lisa_cluster'] == l).sum()})")
               for l, c in LISA_COLORS.items()]
    _focus(ax, gdf)
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=7, title="LISA cluster (p<0.05)")
    _frame(ax, gdf, title, note)
    return _save(fig, name)


def coef_points(gdf: gpd.GeoDataFrame, cols: list[str], titles: list[str], name: str,
                units: gpd.GeoDataFrame | None = None, sig_prefix="sig_", ncols=3, note=None):
    """Small multiples of local coefficients. Non-significant points are hollow grey."""
    n = len(cols)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 4 * nrows))
    for ax, col, ttl in zip(np.atleast_1d(axes).ravel(), cols, titles):
        if units is not None:
            units.plot(ax=ax, facecolor=NEUTRAL, edgecolor="white", linewidth=0.2)
        v = gdf[col]
        lim = np.nanpercentile(np.abs(v), 98) or 1
        norm = TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
        sig = gdf.get(sig_prefix + col[2:], np.ones(len(gdf), bool))
        gdf[~sig].plot(ax=ax, markersize=4, facecolor="none", edgecolor=MUTED, linewidth=0.3)
        gdf[sig].plot(ax=ax, column=col, cmap=DIVERGING, norm=norm, markersize=6, legend=True,
                      legend_kwds={"shrink": 0.6, "label": "local coefficient (standardised)"})
        _focus(ax, gdf)
        _frame(ax, gdf, ttl)
    for ax in np.atleast_1d(axes).ravel()[n:]:
        ax.set_axis_off()
    if note:
        fig.text(0.01, 0.0, note, fontsize=7, color=MUTED)
    return _save(fig, name)


def dominant_feature_map(gdf: gpd.GeoDataFrame, name: str, title: str, top: int = 6, note=None):
    cats = gdf["dominant_feature"].value_counts().index[:top].tolist()
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]
    fig, ax = plt.subplots(figsize=(7, 7))
    _missing(ax, gdf, "dominant_feature")
    handles = []
    for c, col in zip(cats, palette):
        s = gdf[gdf["dominant_feature"] == c]
        s.plot(ax=ax, color=col, edgecolor="white", linewidth=0.25)
        handles.append(Patch(facecolor=col, label=f"{c} ({len(s)})"))
    other = gdf[gdf["dominant_feature"].notna() & ~gdf["dominant_feature"].isin(cats)]
    if len(other):
        other.plot(ax=ax, color=MUTED, edgecolor="white", linewidth=0.25)
        handles.append(Patch(facecolor=MUTED, label=f"Other ({len(other)})"))
    _focus(ax, gdf.dropna(subset=["dominant_feature"]))
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=7, title="Largest mean |SHAP|")
    _frame(ax, gdf, title, note)
    return _save(fig, name)
