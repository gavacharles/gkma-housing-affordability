"""Road network for paper 2: a routable graph from the OpenStreetMap road layer.

Tertiary roads and above; motorways are reachable only where they meet another road (their
links), as on the ground. Edge weights are minutes at assumed congested daytime speeds by road
class, scaled by `speed_scale` for sensitivity runs.
"""
from __future__ import annotations

import geopandas as gpd
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from gkma.config import load_config, p

SPEED = {"motorway": 70, "motorway_link": 30, "trunk": 25, "trunk_link": 20, "primary": 22, "primary_link": 18,
         "secondary": 20, "tertiary": 18}                      # km/h, congested daytime (assumption)
BYPASS_SPEED = 40                                                # Northern Bypass: congested, frequent junctions
ACCESS_KMH = 12                                                  # from a point to the network (boda/walk)


class RoadNetwork:
    def __init__(self, speed_scale: float = 1.0):
        self.crs = load_config()["project"]["crs_projected"]
        roads = gpd.read_file(p("data/external/osm/roads.gpkg")).to_crs(self.crs)
        name = roads["name"].fillna("")
        roads["kind"] = np.where(name.str.contains("Expressway", case=False), "expressway",
                                 np.where(name.str.contains("Northern Bypass", case=False), "bypass", roads["highway"]))
        G, kinds = nx.Graph(), {}
        for _, r in roads.iterrows():
            geoms = [r.geometry] if r.geometry.geom_type == "LineString" else list(r.geometry.geoms)
            v = (BYPASS_SPEED if r["kind"] == "bypass" else SPEED.get(r["highway"], 18)) * speed_scale
            for geom in geoms:
                cs = list(geom.coords)
                for u, w in zip(cs[:-1], cs[1:]):
                    ku, kw = self.key(u), self.key(w)
                    t = float(np.hypot(w[0] - u[0], w[1] - u[1])) / 1000 / v * 60
                    if G.has_edge(ku, kw):
                        t = min(t, G[ku][kw]["t"])
                    G.add_edge(ku, kw, t=t)
                for c in cs:
                    kinds.setdefault(self.key(c), set()).add(r["kind"])
        self.G = G.subgraph(max(nx.connected_components(G), key=len)).copy()   # drop small fragments
        self.kinds = kinds
        self.nodes = np.array(list(self.G.nodes))
        self.tree = cKDTree(self.nodes)

    @staticmethod
    def key(xy):
        return (round(xy[0], 1), round(xy[1], 1))

    def access_nodes(self, kind: str) -> list:
        """Nodes where a road of this kind meets any other road (its access points)."""
        return [n for n in self.G.nodes if kind in self.kinds.get(n, set()) and len(self.kinds[n]) > 1]

    def snap(self, pt):
        """Nearest graph node to a projected point, and the minutes to reach it."""
        d, i = self.tree.query([pt.x, pt.y])
        return tuple(self.nodes[i]), d / 1000 / ACCESS_KMH * 60

    def nearest_time(self, targets) -> dict:
        """Minutes from every node to the nearest of `targets` (multi-source Dijkstra)."""
        return nx.multi_source_dijkstra_path_length(self.G, set(targets), weight="t")
