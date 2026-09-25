"""Road-network accessibility for every neighbourhood point (paper 2).

Builds a routable graph from the OpenStreetMap road layer (tertiary and above;
motorways reachable only through their links, as on the ground), with assumed
congested speeds by road class. For each of the neighbourhood points at which
listings are located it computes:

  tt_cbd_min          travel time to the CBD (Constitutional Square)
  tt_expressway_min   travel time to the nearest Entebbe Expressway access point
  tt_bypass_min       travel time to the nearest Northern Bypass access point
  tt_rail_min         travel time to the nearest commuter-rail station on the URC schedule
                      (Kampala, Namanve, Mukono)
  acc_ntl_{30,45,60}  night-time radiance reachable within 30/45/60 minutes
  acc_jobs_{T}_{w}    jobs reachable within T = 30/45/60 minutes, with each division's or
                      district's COBE employment spread over its grid cells by w =
                      bld (building footprint area), ntl (night lights) or mix (both)

Speeds (km/h) are assumptions for typical daytime congestion, varied in
sensitivity runs with --speed-scale.

  python paper2_transit/scripts/01_accessibility.py [--speed-scale 1.0]
  -> paper2_transit/outputs/tables/neighbourhood_accessibility.csv
"""
import argparse

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from shapely.geometry import Point

import _paper  # noqa: F401  (shared pipeline + paper-2 outputs)
from gkma.config import load_config, p

ap = argparse.ArgumentParser()
ap.add_argument("--speed-scale", type=float, default=1.0)
a = ap.parse_args()

cfg = load_config()
crs = cfg["project"]["crs_projected"]
SPEED = {"motorway": 70, "motorway_link": 30, "trunk": 25, "trunk_link": 20, "primary": 22, "primary_link": 18,
         "secondary": 20, "tertiary": 18}                      # km/h, congested daytime (assumption)
BYPASS_SPEED = 40                                                # Northern Bypass: congested, frequent junctions
ACCESS_KMH = 12                                                  # from a neighbourhood point to the network (boda/walk)

roads = gpd.read_file(p("data/external/osm/roads.gpkg")).to_crs(crs)
roads["kind"] = np.where(roads["name"].fillna("").str.contains("Expressway", case=False), "expressway",
                         np.where(roads["name"].fillna("").str.contains("Northern Bypass", case=False), "bypass",
                                  roads["highway"]))


def key(xy):
    return (round(xy[0], 1), round(xy[1], 1))


G = nx.Graph()
node_kinds = {}
for _, r in roads.iterrows():
    geoms = [r.geometry] if r.geometry.geom_type == "LineString" else list(r.geometry.geoms)
    v = (BYPASS_SPEED if r["kind"] == "bypass" else SPEED.get(r["highway"], 18)) * a.speed_scale
    for geom in geoms:
        cs = list(geom.coords)
        for u, w in zip(cs[:-1], cs[1:]):
            ku, kw = key(u), key(w)
            d = float(np.hypot(w[0] - u[0], w[1] - u[1]))
            t = d / 1000 / v * 60                                # minutes
            if G.has_edge(ku, kw):
                t = min(t, G[ku][kw]["t"])
            G.add_edge(ku, kw, t=t)
        for c in cs:
            node_kinds.setdefault(key(c), set()).add(r["kind"])
# keep the largest connected component (fragments of the tertiary network are dropped)
G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
nodes = np.array(list(G.nodes))
tree = cKDTree(nodes)
print(f"graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")


def access_nodes(kind):
    """Nodes where a motorway of this kind meets any other road (its access points)."""
    return [n for n in G.nodes if kind in node_kinds.get(n, set()) and len(node_kinds[n]) > 1]


def snap(pt):
    d, i = tree.query([pt.x, pt.y])
    return tuple(nodes[i]), d / 1000 / ACCESS_KMH * 60           # node, access minutes


poi = cfg["geography"]["points_of_interest"]
to_xy = lambda lonlat: gpd.GeoSeries([Point(lonlat)], crs="EPSG:4326").to_crs(crs).iloc[0]  # noqa: E731
cbd_node, cbd_walk = snap(to_xy(poi["cbd"]))
stations = gpd.read_file(p("data/external/rail/urc_commuter_stations.gpkg")).to_crs(crs)
stations = stations[stations["on_urc_schedule"].astype(bool)]
rail_nodes = [snap(g)[0] for g in stations.geometry]
exp_nodes, byp_nodes = access_nodes("expressway"), access_nodes("bypass")
print(f"expressway access points: {len(exp_nodes)}, bypass access points: {len(byp_nodes)}, stations: {len(rail_nodes)}")


def nearest_time(targets):
    """Multi-source Dijkstra from a set of targets: minutes from every node to the nearest target."""
    return nx.multi_source_dijkstra_path_length(G, set(targets), weight="t")


t_exp, t_byp, t_rail = nearest_time(exp_nodes), nearest_time(byp_nodes), nearest_time(rail_nodes)
t_cbd = nx.single_source_dijkstra_path_length(G, cbd_node, weight="t")

# night-light cells -> nearest node (with access time)
nl_path = cfg["covariates"]["night_lights"] if "covariates" in cfg and "night_lights" in cfg["covariates"] else \
    "data/external/viirs_annual_2024_uganda.tif"
x0, y0, x1, y1 = gpd.GeoSeries.from_xy(nodes[:, 0], nodes[:, 1], crs=crs).to_crs("EPSG:4326").total_bounds
with rasterio.open(p(nl_path)) as src:
    # clip the window to the raster: the road network extends beyond the night-light tile, and an
    # out-of-bounds window would shift every cell's coordinates
    win = rasterio.windows.from_bounds(x0 - 0.05, y0 - 0.05, x1 + 0.05, y1 + 0.05, src.transform)
    win = win.round_offsets().round_lengths().intersection(rasterio.windows.Window(0, 0, src.width, src.height))
    arr = src.read(1, window=win).astype(float)
    tr = src.window_transform(win)
    nodata = src.nodata
if nodata is not None:
    arr[arr == nodata] = 0
arr[~np.isfinite(arr) | (arr < 0)] = 0
with rasterio.open(p("data/external/buildings/building_grid.tif")) as bsrc:   # same grid as the night lights
    bld = bsrc.read(1, window=win).astype(float)
rows, cols = np.nonzero((arr > 0) | (bld > 0))
lon, lat = rasterio.transform.xy(tr, rows, cols)
cells = gpd.GeoSeries.from_xy(lon, lat, crs="EPSG:4326").to_crs(crs)
cd, ci = tree.query(np.c_[cells.x, cells.y])
cell_node = [tuple(nodes[i]) for i in ci]
cell_walk = cd / 1000 / ACCESS_KMH * 60
cell_val = arr[rows, cols]
cell_bld = bld[rows, cols]
print(f"grid cells with lights or buildings: {len(cell_val):,}")

# jobs per cell: COBE employment of each Kampala division / GKMA district spread by weights
g_ = cfg["geography"]
sc = gpd.read_file(p(g_["subcounties"])).to_crs(crs)
sc["unit"] = np.where(sc[g_["district_name_col"]].str.title() == "Kampala", sc[g_["subcounty_name_col"]],
                      sc[g_["district_name_col"]].str.title())
units = sc.dissolve("unit").reset_index()[["unit", "geometry"]]
cell_unit = gpd.sjoin(gpd.GeoDataFrame(geometry=cells.values, crs=crs), units, how="left",
                      predicate="within")["unit"].groupby(level=0).first().reindex(range(len(cells))).values
jobs_tab = pd.read_csv(p("data/external/ubos/cobe/cobe_employment_gkma.csv")).set_index("unit")["jobs_2019_20"]
cell_jobs = {}
for wname, w in {"bld": cell_bld, "ntl": cell_val, "mix": np.sqrt(cell_bld * cell_val)}.items():
    jobs = np.zeros(len(cells))
    for u_, total in jobs_tab.items():
        m_ = cell_unit == u_
        if m_.any() and w[m_].sum() > 0:
            jobs[m_] = total * w[m_] / w[m_].sum()
    cell_jobs[wname] = jobs
print("jobs allocated:", {k: f"{v.sum():,.0f}" for k, v in cell_jobs.items()}, f"(COBE total {jobs_tab.sum():,})")

# origins: the distinct neighbourhood points where listings are located
L = gpd.read_file(p("data/processed/listings.gpkg"))
L["pt"] = L.geometry.to_wkt()
pts = L.groupby("pt").agg(n_listings=("pt", "size"), n_rent=("listing_type", lambda s: (s == "rent").sum()),
                         n_sale=("listing_type", lambda s: (s == "sale").sum()),
                         geometry=("geometry", "first")).reset_index()
pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=L.crs).to_crs(crs)
rows_out = []
for i, r in pts.iterrows():
    n0, walk = snap(r.geometry)
    dist = nx.single_source_dijkstra_path_length(G, n0, cutoff=60, weight="t")
    reach = np.array([dist.get(n, np.inf) for n in cell_node]) + walk + cell_walk
    rec = {"pt": r["pt"], "n_listings": r["n_listings"], "n_rent": r["n_rent"], "n_sale": r["n_sale"],
           "access_min": walk, "tt_cbd_min": walk + t_cbd.get(n0, np.nan) + cbd_walk,
           "tt_expressway_min": walk + t_exp.get(n0, np.nan), "tt_bypass_min": walk + t_byp.get(n0, np.nan),
           "tt_rail_min": walk + t_rail.get(n0, np.nan)}
    for T in (30, 45, 60):
        rec[f"acc_ntl_{T}"] = float(cell_val[reach <= T].sum())
        for wname, jobs in cell_jobs.items():
            rec[f"acc_jobs_{T}_{wname}"] = float(jobs[reach <= T].sum())
    rows_out.append(rec)
out = pd.DataFrame(rows_out)
g4326 = pts.to_crs("EPSG:4326")
out["lon"], out["lat"] = g4326.geometry.x.values, g4326.geometry.y.values
dest = _paper.OUT / "tables" / ("neighbourhood_accessibility.csv" if a.speed_scale == 1.0 else
                                f"neighbourhood_accessibility_speed{a.speed_scale:g}.csv")
out.round(3).to_csv(dest, index=False)
print(out.drop(columns=["pt"]).describe().round(1).T[["count", "mean", "min", "50%", "max"]].to_string())
print("wrote", dest.relative_to(_paper.ROOT))
