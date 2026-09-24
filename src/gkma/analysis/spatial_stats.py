"""Stage 1: unit medians, global Moran's I, LISA clusters (and Getis-Ord Gi*)."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from esda.getisord import G_Local
from esda.moran import Moran, Moran_Local
from libpysal.weights import KNN, Queen


def unit_medians(pts: gpd.GeoDataFrame, units: gpd.GeoDataFrame, value: str,
                 unit_col: str = "parish_id", min_n: int = 5) -> gpd.GeoDataFrame:
    """Median/IQR/n of `value` per unit; units with n < min_n are masked."""
    g = pts.dropna(subset=[value]).groupby(unit_col)[value]
    stats = pd.DataFrame({"median": g.median(), "q25": g.quantile(.25), "q75": g.quantile(.75), "n": g.size()})
    out = units.merge(stats, left_on="unit_id", right_index=True, how="left")
    out.loc[out["n"].fillna(0) < min_n, "median"] = np.nan
    return out


def weights(gdf: gpd.GeoDataFrame, kind: str = "queen", k: int = 6):
    if kind == "queen":
        w = Queen.from_dataframe(gdf, use_index=False, silence_warnings=True)
        if w.islands:  # islands break Moran: fall back to KNN
            w = KNN.from_dataframe(gdf.set_geometry(gdf.centroid), k=k)
    else:
        w = KNN.from_dataframe(gdf.set_geometry(gdf.centroid), k=k)
    w.transform = "r"
    return w


def moran_lisa(gdf: gpd.GeoDataFrame, value: str = "median", kind: str = "queen",
               permutations: int = 999, alpha: float = 0.05, seed: int = 42):
    """Return (global Moran summary dict, gdf with LISA cluster labels)."""
    d = gdf.dropna(subset=[value]).reset_index(drop=True).copy()
    y = np.log(d[value].to_numpy())
    w = weights(d, kind)
    np.random.seed(seed)  # esda's global Moran has no seed argument
    mi = Moran(y, w, permutations=permutations)
    lisa = Moran_Local(y, w, permutations=permutations, seed=seed)
    labels = np.array(["ns", "High-High", "Low-High", "Low-Low", "High-Low"], dtype=object)
    d["lisa_q"] = lisa.q
    d["lisa_p"] = lisa.p_sim
    d["lisa_cluster"] = np.where(lisa.p_sim < alpha, labels[lisa.q], "Not significant")
    gi = G_Local(y, w, star=True, permutations=permutations, seed=seed)
    d["gi_z"], d["gi_p"] = gi.Zs, gi.p_sim
    summary = {"n_units": len(d), "moran_I": mi.I, "expected_I": mi.EI, "z": mi.z_sim,
               "p_sim": mi.p_sim, "weights": kind}
    return summary, d
