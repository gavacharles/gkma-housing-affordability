"""Affordable supply: which listings fall within a household's budget, and how far away.

  budget_share(rents, budget)               share of listed rents at or below a budget
  nearest_within_budget(origins, listings)  distance from each origin (e.g. a parish point,
                                            with its own budget) to the nearest listing at or
                                            below that budget
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def budget_share(rents: pd.Series, budget: float) -> float:
    r = pd.Series(rents).dropna()
    return float((r <= budget).mean()) if len(r) else np.nan


def nearest_within_budget(origins: gpd.GeoDataFrame, listings: gpd.GeoDataFrame, budget_col: str = "budget",
                          rent_col: str = "rent_month_ugx") -> pd.DataFrame:
    """Metres from each origin to the nearest listing whose rent <= the origin's budget.

    origins and listings must share a projected CRS. Origins are processed by budget so each
    query uses a KD-tree of the listings within that budget only.
    """
    L = listings.dropna(subset=[rent_col]).sort_values(rent_col)
    xy = np.c_[L.geometry.x, L.geometry.y]
    rents = L[rent_col].to_numpy()
    out = pd.DataFrame(index=origins.index, columns=["nearest_m", "n_within_budget"], dtype=float)
    for b, grp in origins.groupby(budget_col):
        k = int(np.searchsorted(rents, b, side="right"))
        if k == 0:
            out.loc[grp.index, ["nearest_m", "n_within_budget"]] = [np.inf, 0]
            continue
        d, _ = cKDTree(xy[:k]).query(np.c_[grp.geometry.x, grp.geometry.y])
        out.loc[grp.index, "nearest_m"] = d
        out.loc[grp.index, "n_within_budget"] = k
    return out
