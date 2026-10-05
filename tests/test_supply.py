import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gkma.analysis.supply import budget_share, nearest_within_budget  # noqa: E402


def test_budget_share():
    assert budget_share(pd.Series([100, 200, 300, np.nan]), 200) == 2 / 3
    assert np.isnan(budget_share(pd.Series([], dtype=float), 100))


def test_nearest_within_budget():
    listings = gpd.GeoDataFrame({"rent_month_ugx": [100, 500, 1000]},
                                geometry=gpd.points_from_xy([0, 1000, 10], [0, 0, 0]), crs="EPSG:32636")
    origins = gpd.GeoDataFrame({"budget": [150, 600, 50]},
                               geometry=gpd.points_from_xy([900, 900, 0], [0, 0, 0]), crs="EPSG:32636")
    r = nearest_within_budget(origins, listings)
    assert r.loc[0, "nearest_m"] == 900          # only the 100 listing is affordable
    assert r.loc[1, "nearest_m"] == 100          # the 500 listing at x=1000 is now within budget
    assert np.isinf(r.loc[2, "nearest_m"]) and r.loc[2, "n_within_budget"] == 0
