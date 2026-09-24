"""Publication-grade maps (Elsevier / Taylor & Francis / MDPI).

Conventions
* Size: full width 170 mm (fits Elsevier double column 190 mm, T&F 170 mm,
  MDPI ~170 mm); single column 90 mm. Arial 6-8 pt at print size; TrueType
  fonts embedded in the PDF.
* Output per figure: vector PDF, 600 dpi TIFF (LZW), 300 dpi PNG, plus a
  GeoPackage of the mapped layer (outputs/gis/) for restyling in QGIS/ArcGIS.
  Titles are not drawn in the figure; they go with notes and data sources to
  outputs/maps/captions.md, because journals set captions themselves.
* Cartography: fixed GKMA extent for every map; parishes clipped to the
  shoreline; Lake Victoria, district and Kampala-division boundaries, major
  roads and reference labels; Kampala-core inset; degree ticks on the frame;
  segmented scale bar; north arrow; OSM attribution (ODbL).
* Colour: ColorBrewer sequential/diverging schemes (colour-blind and greyscale
  safe), GeoDa LISA colours, Okabe-Ito for categories; "no data" as flat grey.

Requires the layers built by scripts/00_prepare_basemap.py.
"""
from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import mapclassify
import matplotlib as mpl
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer

from gkma.config import load_config, p
from gkma.viz.maps import LABELS, label  # noqa: F401  (shared variable names)

MM = 1 / 25.4
FULL, SINGLE = 170 * MM, 90 * MM
OUT_DIR = "outputs/maps"

# ColorBrewer
SEQ_BLUE = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
SEQ_RED = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]
DIVERGING = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#67a9cf", "#2166ac"]  # RdBu, no neutral class
BLUE, RED = SEQ_BLUE[1:] + ["#08306b", "#041f4a"], SEQ_RED + ["#800026", "#4d0017"]  # for line charts
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442"]
LISA_COLORS = {"High-High": "#d7191c", "Low-Low": "#2c7bb6", "Low-High": "#abd9e9", "High-Low": "#fdae61",
               "Not significant": "#eeeeee"}
NODATA, OUTSIDE, LAKE, LAKE_EDGE = "#e7e7e4", "#f7f7f5", "#dbe8f3", "#9fbfd9"
INK, MUTED = "#1a1a1a", "#6e6e6e"

mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "font.size": 7, "legend.fontsize": 6.5, "legend.title_fontsize": 7, "axes.linewidth": 0.5,
    "xtick.labelsize": 6, "ytick.labelsize": 6, "xtick.major.width": 0.4, "ytick.major.width": 0.4,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.direction": "in", "ytick.direction": "in",
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "savefig.dpi": 600, "figure.dpi": 150, "text.color": INK, "axes.edgecolor": INK,
})


# --------------------------------------------------------------------------- layers
@lru_cache(maxsize=1)
def base():
    b = p("data/external/basemap")
    crs = load_config()["project"]["crs_projected"]
    rd = lambda n, **kw: gpd.read_file(b / f"{n}.gpkg", **kw).to_crs(crs)  # noqa: E731
    return {"lake": rd("lake"), "land": rd("land"), "districts": rd("districts"), "divisions": rd("divisions"),
            "roads": rd("roads"), "wetlands": rd("wetlands"), "labels": rd("labels"),
            "uganda": rd("uganda", layer="country"), "uga_districts": rd("uganda", layer="districts")}


def _extent(which: str):
    g = load_config()["geography"]
    lon0, lat0, lon1, lat1 = g.get("map_extent" if which == "main" else "map_extent_core",
                                   [32.33, 0.02, 32.88, 0.55] if which == "main" else [32.535, 0.262, 32.668, 0.378])
    t = Transformer.from_crs("EPSG:4326", load_config()["project"]["crs_projected"], always_xy=True)
    (x0, x1), (y0, y1) = t.transform([lon0, lon1], [lat0, lat1])
    return x0, y0, x1, y1


def clip_land(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clip polygons to the shoreline (UBOS lakeside parishes include open water)."""
    land = base()["land"]
    out = gdf.to_crs(land.crs).copy()
    out["geometry"] = out.geometry.intersection(land.union_all())
    return out[~out.geometry.is_empty]


# --------------------------------------------------------------------------- furniture
def _background(ax, extent, context=True):
    b = base()
    b["uga_districts"].plot(ax=ax, facecolor=OUTSIDE, edgecolor="#e2e2de", linewidth=0.3, zorder=0)
    b["lake"].plot(ax=ax, facecolor=LAKE, edgecolor=LAKE_EDGE, linewidth=0.3, zorder=1)
    x0, y0, x1, y1 = extent
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_facecolor(OUTSIDE)


PANEL_LABELS = {"Kampala", "Entebbe", "Mukono", "Kira", "Nansana", "Wakiso", "Gayaza", "Kajjansi", "Munyonyo"}


def _overlay(ax, core=False, roads=True, labels=True, divisions=True, small=False):
    b = base()
    if roads:
        r = b["roads"]
        r[r["kind"] == "major"].plot(ax=ax, color="#8c8c8c", linewidth=0.35, zorder=6)
        r[r["kind"].isin(["northern_bypass", "expressway"])].plot(ax=ax, color="#4d4d4d", linewidth=0.8, zorder=6)
    b["districts"].boundary.plot(ax=ax, color="#3c3c3c", linewidth=0.6, zorder=7)
    if divisions:
        b["divisions"].boundary.plot(ax=ax, color="#3c3c3c", linewidth=0.35, linestyle=(0, (3, 2)), zorder=7)
    if labels:
        lab = b["labels"][b["labels"]["level"] == ("core" if core else "main")]
        if small:
            lab = lab[lab["label"].isin(PANEL_LABELS)]
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        for _, r in lab.iterrows():
            x, y = r.geometry.x, r.geometry.y
            if x0 < x < x1 and y0 < y < y1:
                ax.plot(x, y, "o", ms=1.6, color=INK, zorder=9)
                ax.annotate(r["label"], (x, y), xytext=(2.5, 2.5), textcoords="offset points",
                            fontsize=5.8 if (core or small) else 6.2, color=INK, zorder=10,
                            path_effects=[pe.withStroke(linewidth=1.6, foreground="white")])


def _ticks(ax):
    """Degree ticks on the frame (UTM 36N is near-aligned with meridians here)."""
    t = Transformer.from_crs(load_config()["project"]["crs_projected"], "EPSG:4326", always_xy=True)
    ti = Transformer.from_crs("EPSG:4326", load_config()["project"]["crs_projected"], always_xy=True)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    lon_mid, lat_mid = t.transform((x0 + x1) / 2, (y0 + y1) / 2)
    lons = np.arange(np.ceil(t.transform(x0, lat_mid)[0] * 10) / 10, t.transform(x1, lat_mid)[0], 0.1)
    lats = np.arange(np.ceil(t.transform(lon_mid, y0)[1] * 10) / 10, t.transform(lon_mid, y1)[1], 0.1)
    xs = [ti.transform(lo, lat_mid)[0] for lo in lons]
    ys = [ti.transform(lon_mid, la)[1] for la in lats]
    ax.set_xticks(xs, [f"{lo:.1f}°E" for lo in lons])
    ax.set_yticks(ys, [f"{abs(la):.1f}°{'N' if la >= 0 else 'S'}" for la in lats])
    ax.tick_params(top=True, right=True, labeltop=False, labelright=False, pad=1.5)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)


def _scalebar(ax, km=10, loc=(0.04, 0.955)):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bx, by = x0 + loc[0] * (x1 - x0), y0 + loc[1] * (y1 - y0)
    seg, h = km * 1000 / 2, (y1 - y0) * 0.008
    for i, c in enumerate(["black", "white"]):
        ax.add_patch(Rectangle((bx + i * seg, by), seg, h, facecolor=c, edgecolor="black", lw=0.4, zorder=11))
    for i, v in enumerate([0, km // 2, km]):
        ax.text(bx + i * seg, by + 2.2 * h, f"{v}", ha="center", va="bottom", fontsize=5.8, zorder=11,
                path_effects=[pe.withStroke(linewidth=1.4, foreground="white")])
    ax.text(bx + 2 * seg + 400, by + 0.5 * h, "km", ha="left", va="center", fontsize=5.8, zorder=11,
            path_effects=[pe.withStroke(linewidth=1.4, foreground="white")])


def _north(ax, loc=(0.955, 0.93)):
    ax.annotate("N", xy=(loc[0], loc[1] + 0.035), xycoords="axes fraction", ha="center", va="bottom",
                fontsize=7, fontweight="bold", zorder=11)
    ax.annotate("", xy=(loc[0], loc[1] + 0.035), xytext=(loc[0], loc[1] - 0.02), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>,head_width=0.25,head_length=0.5", color=INK, lw=0.8), zorder=11)


def _credit(fig, ax=None):
    """Attribution inside the map frame, bottom-right (over the lake)."""
    txt = "Basemap © OpenStreetMap contributors (ODbL); boundaries: UBOS"
    if ax is None:
        ax = fig.axes[0]
    ax.text(0.995, 0.006, txt, transform=ax.transAxes, ha="right", va="bottom", fontsize=4.6, color=MUTED,
            zorder=15, path_effects=[pe.withStroke(linewidth=1.2, foreground="white")])


def _panel_letter(ax, letter):
    ax.text(0.015, 0.985, f"({letter})", transform=ax.transAxes, ha="left", va="top", fontsize=8,
            fontweight="bold", zorder=12, path_effects=[pe.withStroke(linewidth=2, foreground="white")])


# --------------------------------------------------------------------------- classes & legends
def _scale(values):
    """Unit chosen from typical values (75th percentile), not the maximum."""
    v = pd.Series(values).dropna()
    ref = float(v.quantile(0.75)) if len(v) else 1.0
    for div, word in [(1e9, "billion"), (1e6, "million"), (1e3, "thousand")]:
        if ref >= div:
            return div, word
    return 1, ""


def _fmt(v, div):
    x = v / div
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 10:
        return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}".rstrip("0").rstrip(".")
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def classify(values, scheme="quantiles", k=5, bins=None, symmetric=False):
    v = pd.Series(values).dropna()
    if bins is not None:
        return list(bins)
    if symmetric:
        m = float(np.nanpercentile(np.abs(v), 97))
        step = m / 3
        return [-2 * step, -step, 0, step, 2 * step, max(float(v.max()), 3 * step)]
    k = min(k, max(2, v.nunique() - 1))
    cls = {"quantiles": mapclassify.Quantiles, "fisher_jenks": mapclassify.FisherJenks,
           "natural_breaks": mapclassify.NaturalBreaks, "equal_interval": mapclassify.EqualInterval}[scheme]
    return list(cls(v, k=k).bins)


def _class_labels(bins, vmin, div, pct=False):
    edges = [vmin] + list(bins)
    f = (lambda x: f"{x:.0f}") if pct else (lambda x: _fmt(x, div))
    return [f"{f(a)}–{f(b)}" for a, b in zip(edges[:-1], edges[1:])]


# --------------------------------------------------------------------------- core renderer
def _draw_choropleth(ax, gdf, col, colors, bins, extent, core=False, small=False):
    _background(ax, extent)
    base()["land"].plot(ax=ax, facecolor=NODATA, edgecolor="none", zorder=2)
    has = gdf.dropna(subset=[col])
    if len(has):
        idx = np.digitize(has[col].to_numpy(dtype=float), bins, right=True).clip(0, len(colors) - 1)
        has.plot(ax=ax, color=[colors[i] for i in idx], edgecolor="white",
                 linewidth=0.3 if core else 0.15, zorder=3)
    gdf[gdf[col].isna()].plot(ax=ax, facecolor=NODATA, edgecolor="white", linewidth=0.15, zorder=3)
    _overlay(ax, core=core, roads=True, labels=True, small=small)


def _legend(ax, colors, labels, title, nodata_label="Fewer than 5 listings", extra=None, loc="below", ncol=3):
    h = [Patch(facecolor=c, edgecolor="#7a7a7a", linewidth=0.3) for c in colors]
    lab = list(labels)
    if nodata_label:
        h.append(Patch(facecolor=NODATA, edgecolor="#7a7a7a", linewidth=0.3))
        lab.append(nodata_label)
    if extra:
        for handle, text in extra:
            h.append(handle)
            lab.append(text)
    if loc == "below":   # outside the frame: never hides map content
        leg = ax.legend(h, lab, title=title, loc="upper center", bbox_to_anchor=(0.5, -0.045), ncol=ncol,
                        frameon=False, handlelength=1.4, handleheight=0.9, labelspacing=0.35, columnspacing=1.4)
    else:
        leg = ax.legend(h, lab, title=title, loc=loc, frameon=True, framealpha=0.92, edgecolor="#bdbdbd",
                        fancybox=False, borderpad=0.5, handlelength=1.4, handleheight=0.9, labelspacing=0.3)
    leg.get_frame().set_linewidth(0.4)
    leg._legend_box.align = "left"
    leg.set_zorder(20)
    return leg


def _road_legend():
    return [(Line2D([0], [0], color="#4d4d4d", lw=0.8), "Expressway / Northern Bypass"),
            (Line2D([0], [0], color="#8c8c8c", lw=0.35), "Trunk and primary roads"),
            (Line2D([0], [0], color="#3c3c3c", lw=0.6), "District boundary")]


def _core_inset(ax, gdf, col, colors, bins, rect=(0.625, 0.025, 0.355, 0.40)):
    ext = _extent("core")
    ax.add_patch(Rectangle((ext[0], ext[1]), ext[2] - ext[0], ext[3] - ext[1], fill=False, edgecolor=INK,
                           lw=0.6, zorder=13))
    ins = ax.inset_axes(rect)
    _draw_choropleth(ins, gdf, col, colors, bins, ext, core=True)
    ins.set_xticks([])
    ins.set_yticks([])
    for s in ins.spines.values():
        s.set_linewidth(0.6)
    ins.text(0.03, 0.97, "Kampala core", transform=ins.transAxes, va="top", fontsize=6, fontweight="bold",
             path_effects=[pe.withStroke(linewidth=1.6, foreground="white")], zorder=12)
    _scalebar(ins, km=2, loc=(0.06, 0.05))
    return ins


# --------------------------------------------------------------------------- captions & saving
def _caption(name, title, note=None, sources=None):
    path = p(OUT_DIR) / "captions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else "# Figure captions (draft)\n"
    blocks = [b for b in text.split("\n## ") if not b.startswith(f"{name}\n")]
    src = sources or ("Listings: RED, Jiji, Uganda Property Centre (asking prices, deduplicated); boundaries: "
                      "UBOS (parishes 2016); basemap: OpenStreetMap; lake: OSM.")
    entry = f"{name}\n**{title}.** {note or ''} Sources: {src}\n"
    path.write_text("\n## ".join(blocks + [entry]))


def _save(fig, name, layer: gpd.GeoDataFrame | None = None, title=None, note=None, sources=None):
    out = p(OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out / f"{name}.tif", dpi=600, bbox_inches="tight", pad_inches=0.02,
                pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    if layer is not None:
        gis = out.parent / "gis"
        gis.mkdir(parents=True, exist_ok=True)
        lyr = layer.copy()
        for c in lyr.columns:
            if lyr[c].dtype == object and c != "geometry":
                lyr[c] = lyr[c].astype("string")
        lyr.to_file(gis / f"{name}.gpkg", driver="GPKG")
    if title:
        _caption(name, title, note, sources)
    return out / f"{name}.png"


# --------------------------------------------------------------------------- public API
def choropleth(gdf, col, title, name, cmap=SEQ_BLUE, fmt=None, scheme="quantiles", k=5, note=None,
               legend_title="", bins=None, inset=True, min_n_label="Fewer than 5 listings"):
    gdf = clip_land(gdf)
    v = gdf[col].dropna()
    colors = list(cmap)
    symmetric = cmap is DIVERGING
    pct = "%" in legend_title
    b = classify(v, scheme, k=len(colors) if bins is None else k, bins=bins, symmetric=symmetric)
    colors = colors[:len(b)] if not symmetric else colors
    div, word = (1, "") if pct or symmetric else _scale(v)
    unit_title = legend_title.replace("UGX", f"UGX {word}".strip()) if word and "UGX" in legend_title else legend_title
    fig, ax = plt.subplots(figsize=(FULL, FULL * 0.98))
    ext = _extent("main")
    _draw_choropleth(ax, gdf, col, colors, b, ext)
    labels = (_class_labels(b, v.min(), div, pct=pct) if not symmetric else
              [f"< {b[0]:.2f}", f"{b[0]:.2f} to {b[1]:.2f}", f"{b[1]:.2f} to 0", f"0 to {b[3]:.2f}",
               f"{b[3]:.2f} to {b[4]:.2f}", f"> {b[4]:.2f}"])
    if len(v):
        _legend(ax, colors, labels, unit_title, nodata_label=min_n_label, extra=_road_legend())
    if inset:
        _core_inset(ax, gdf, col, colors, b)
    _ticks(ax)
    _scalebar(ax)
    _north(ax)
    _credit(fig, ax)
    return _save(fig, name, layer=gdf[[c for c in gdf.columns if c in ("unit_id", "unit_name", col, "n", "geometry")]],
                 title=title, note=note)


def panels(specs, name, title, note=None, ncols=2, shared_bins=False, width=FULL):
    """Multi-panel choropleth figure. specs: dicts with gdf, col, subtitle,
    legend_title and optional cmap/scheme/bins."""
    n = len(specs)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(width, width / ncols * nrows * 1.2), squeeze=False)
    ext = _extent("main")
    shared = None
    if shared_bins:
        allv = pd.concat([clip_land(s["gdf"])[s["col"]] for s in specs]).dropna()
        shared = classify(allv, specs[0].get("scheme", "quantiles"), k=len(specs[0].get("cmap", SEQ_BLUE)))
    for i, (ax, s) in enumerate(zip(axes.ravel(), specs)):
        g = clip_land(s["gdf"])
        cmap = list(s.get("cmap", SEQ_BLUE))
        v = g[s["col"]].dropna()
        pct = "%" in s.get("legend_title", "")
        b = shared or classify(v, s.get("scheme", "quantiles"), k=len(cmap), bins=s.get("bins"))
        cmap = cmap[:len(b)]
        div, word = (1, "") if pct else _scale(v)
        lt = s.get("legend_title", "")
        lt = lt.replace("UGX", f"UGX {word}".strip()) if word and "UGX" in lt else lt
        _draw_choropleth(ax, g, s["col"], cmap, b, ext, small=True)
        if len(v):
            _legend(ax, cmap, _class_labels(b, v.min(), div, pct=pct), lt, ncol=2)
        _ticks(ax)
        ax.tick_params(labelsize=5)
        _scalebar(ax, loc=(0.60, 0.05))
        _panel_letter(ax, "abcdefgh"[i])
        ax.set_title(s.get("subtitle", ""), fontsize=7, loc="left", pad=3)
    for ax in axes.ravel()[n:]:
        ax.set_axis_off()
    _north(axes.ravel()[0])
    fig.subplots_adjust(hspace=0.36, wspace=0.14)
    _credit(fig, axes.ravel()[n - 1])
    return _save(fig, name, title=title, note=note)


def study_area(units, pts=None, name="01_study_area", **_):
    b = base()
    fig, ax = plt.subplots(figsize=(FULL, FULL * 0.98))
    ext = _extent("main")
    _background(ax, ext)
    b["land"].plot(ax=ax, facecolor="#fbfbf8", edgecolor="none", zorder=2)
    b["wetlands"].plot(ax=ax, facecolor="#d4e3cf", edgecolor="none", zorder=3)
    _overlay(ax, roads=True, labels=False)
    lab = b["labels"][(b["labels"]["level"] == "main") & (b["labels"]["label"] != "Kampala")]
    for _, r in lab.iterrows():
        ax.plot(r.geometry.x, r.geometry.y, "o", ms=1.6, color=INK, zorder=9)
        ax.annotate(r["label"], (r.geometry.x, r.geometry.y), xytext=(2.5, 2.5), textcoords="offset points",
                    fontsize=6.2, zorder=10, path_effects=[pe.withStroke(linewidth=1.6, foreground="white")])
    t = Transformer.from_crs("EPSG:4326", b["land"].crs, always_xy=True)
    for text, lon, lat in [("KAMPALA", 32.585, 0.322), ("WAKISO", 32.43, 0.47), ("MUKONO", 32.80, 0.30),
                           ("WAKISO", 32.47, 0.16)]:
        x, y = t.transform(lon, lat)
        ax.text(x, y, text, fontsize=7.5, color="#555555", ha="center", style="italic", fontweight="bold",
                zorder=9, path_effects=[pe.withStroke(linewidth=2, foreground="white")])
    extra = [(Patch(facecolor="#d4e3cf"), "Wetland (OSM)"), (Patch(facecolor=LAKE, edgecolor=LAKE_EDGE), "Lake Victoria")]
    if pts is not None and len(pts):
        # Graduated circles: listings per parish (many listings share a
        # neighbourhood point, so individual dots would stack and mislead).
        par = units.to_crs(b["land"].crs)
        j = gpd.sjoin(pts.to_crs(par.crs)[["listing_type", "geometry"]], par[["unit_id", "geometry"]],
                      how="inner", predicate="within")
        cnt = j.groupby("unit_id").size()
        c = par.set_index("unit_id").loc[cnt.index].geometry.representative_point()
        smax = 260
        size = lambda n: smax * np.sqrt(n / cnt.max())  # noqa: E731
        ax.scatter(c.x, c.y, s=size(cnt.values), facecolor="#0072B2", edgecolor="white", linewidth=0.4,
                   alpha=0.75, zorder=8)
        for n in [v for v in [10, 50, 200, 500] if v <= cnt.max()][-3:]:
            extra.append((Line2D([0], [0], marker="o", color="none", markerfacecolor="#0072B2", alpha=0.75,
                                 markeredgecolor="white", markersize=np.sqrt(size(n))), f"{n} listings"))
        n_sale, n_rent = (pts["listing_type"] == "sale").sum(), (pts["listing_type"] == "rent").sum()
        extra.append((Patch(facecolor="none", edgecolor="none"), f"Total: {n_sale:,} for sale, {n_rent:,} for rent"))
    _legend(ax, [], [], None, nodata_label=None, extra=extra + _road_legend() +
            [(Line2D([0], [0], color="#3c3c3c", lw=0.35, ls=(0, (3, 2))), "Kampala division boundary")])
    loc = ax.inset_axes((0.73, 0.67, 0.26, 0.315))
    uga = b["uga_districts"].copy()
    uga["geometry"] = uga.geometry.buffer(0)
    uga.dissolve().plot(ax=loc, facecolor="#efefec", edgecolor="#8c8c8c", linewidth=0.4)
    uga[uga["adm2_name"].isin(["Kampala", "Wakiso", "Mukono", "Mpigi", "Buikwe", "Luwero"])] \
        .plot(ax=loc, facecolor="#bd0026", edgecolor="none")
    x0, y0, x1, y1 = ext
    loc.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor=INK, lw=0.6))
    loc.set_xticks([])
    loc.set_yticks([])
    loc.set_facecolor("white")
    loc.set_aspect("equal")
    loc.text(0.5, 0.97, "UGANDA", transform=loc.transAxes, ha="center", va="top", fontsize=5.5, color=MUTED)
    _ticks(ax)
    _scalebar(ax)
    _north(ax, loc=(0.68, 0.93))
    _credit(fig)
    return _save(fig, name, title="Study area: Greater Kampala Metropolitan Area and listing locations",
                 note="Study districts shaded red on the locator map; the frame shows the map extent used in all figures.")


def lisa_map(gdf, title, name, all_units=None, note=None):
    g = clip_land(gdf)
    fig, ax = plt.subplots(figsize=(FULL, FULL * 0.98))
    ext = _extent("main")
    _background(ax, ext)
    base()["land"].plot(ax=ax, facecolor=NODATA, edgecolor="none", zorder=2)
    for lab, c in LISA_COLORS.items():
        s = g[g["lisa_cluster"] == lab]
        if len(s):
            s.plot(ax=ax, color=c, edgecolor="white", linewidth=0.15, zorder=3)
    _overlay(ax)
    counts = g["lisa_cluster"].value_counts()
    _legend(ax, list(LISA_COLORS.values()), [f"{k} ({counts.get(k, 0)})" for k in LISA_COLORS],
            "Local Moran's I cluster (p < 0.05)", nodata_label="Fewer than 5 listings", extra=_road_legend())
    ins_g = g.assign(_lisa=g["lisa_cluster"].map({k: i for i, k in enumerate(LISA_COLORS)}))
    _core_inset(ax, ins_g, "_lisa", list(LISA_COLORS.values()), [0.5, 1.5, 2.5, 3.5, 4.5])
    _ticks(ax)
    _scalebar(ax)
    _north(ax)
    _credit(fig)
    return _save(fig, name, layer=g[["unit_id", "median", "lisa_cluster", "lisa_p", "gi_z", "geometry"]]
                 if "unit_id" in g else g, title=title,
                 note=(note or "") + " Queen contiguity, 999 permutations; clusters shown where pseudo p < 0.05.")


def coef_points(gdf, cols, titles, name, units=None, note=None, ncols=3, **_):
    """GWR/MGWR local coefficients summarised to parishes (median of local
    estimates; parishes where under half of the estimates are significant
    after the multiple-testing correction are shown grey)."""
    if units is None:
        raise ValueError("coef_points needs the parish units to aggregate to")
    u = units.to_crs(gdf.crs)
    j = gpd.sjoin(gdf, u[["unit_id", "geometry"]], how="inner", predicate="within")
    specs = []
    for c, t in zip(cols, titles):
        sig = "sig_" + c[2:]
        agg = j.groupby("unit_id").agg(med=(c, "median"), n=(c, "size"),
                                       sig=(sig, "mean") if sig in j else (c, lambda s: 1.0))
        agg.loc[(agg["n"] < 3) | (agg["sig"] < 0.5), "med"] = np.nan
        g = u.merge(agg, left_on="unit_id", right_index=True, how="left")
        specs.append({"gdf": g, "col": "med", "subtitle": t, "cmap": DIVERGING, "legend_title": "Local coefficient"})
    n = len(specs)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(FULL, FULL / ncols * nrows * 1.05), squeeze=False)
    ext = _extent("main")
    allv = pd.concat([s["gdf"]["med"] for s in specs]).dropna()
    m = float(np.nanpercentile(np.abs(allv), 97)) if len(allv) else 1
    b = [-2 * m / 3, -m / 3, 0, m / 3, 2 * m / 3, max(float(allv.max()) if len(allv) else m, m)]
    for i, (ax, s) in enumerate(zip(axes.ravel(), specs)):
        _draw_choropleth(ax, clip_land(s["gdf"]), "med", DIVERGING, b, ext, small=True)
        _ticks(ax)
        ax.tick_params(labelsize=4.5)
        _panel_letter(ax, "abcdefghi"[i])
        ax.set_title(s["subtitle"], fontsize=6.5, loc="left", pad=2)
    for ax in axes.ravel()[n:]:
        ax.set_axis_off()
    labels = [f"< {b[0]:.2f}", f"{b[0]:.2f} to {b[1]:.2f}", f"{b[1]:.2f} to 0", f"0 to {b[3]:.2f}",
              f"{b[3]:.2f} to {b[4]:.2f}", f"> {b[4]:.2f}"]
    h = [Patch(facecolor=c, edgecolor="#7a7a7a", lw=0.3) for c in DIVERGING] + \
        [Patch(facecolor=NODATA, edgecolor="#7a7a7a", lw=0.3)]
    fig.legend(h, labels + ["Not significant / < 3 estimates"], loc="lower center", ncol=4, frameon=False,
               title="Local coefficient (standardised variables)", bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _credit(fig)
    return _save(fig, name, title="Spatially varying effects: local regression coefficients by parish",
                 note=note)


def dominant_feature_map(gdf, name, title, top=6, note=None):
    g = clip_land(gdf)
    cats = g["dominant_feature"].value_counts().index[:top].tolist()
    code = {c: i for i, c in enumerate(cats)}
    g["_k"] = g["dominant_feature"].map(code)
    g.loc[g["dominant_feature"].notna() & g["_k"].isna(), "_k"] = len(cats)
    colors = OKABE_ITO[:len(cats)] + (["#999999"] if (g["_k"] == len(cats)).any() else [])
    labs = cats + (["Other"] if len(colors) > len(cats) else [])
    fig, ax = plt.subplots(figsize=(FULL, FULL * 0.98))
    ext = _extent("main")
    bins = [i + 0.5 for i in range(len(colors))]
    _draw_choropleth(ax, g, "_k", colors, bins, ext)
    counts = g["_k"].value_counts()
    _legend(ax, colors, [f"{l} ({counts.get(i, 0)})" for i, l in enumerate(labs)],
            "Largest mean |SHAP|", nodata_label="Fewer than 5 listings", extra=_road_legend())
    _core_inset(ax, g, "_k", colors, bins)
    _ticks(ax)
    _scalebar(ax)
    _north(ax)
    _credit(fig)
    return _save(fig, name, layer=g[["unit_id", "dominant_feature", "geometry"]] if "unit_id" in g else g,
                 title=title, note=note)
