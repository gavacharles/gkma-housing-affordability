"""Household income distributions by area, for analyses that start from the
published area tables rather than the listings (papers 1, 3 and 4 extensions).

Each area's incomes are the household-weighted mixture of its parish lognormals,
exactly as in affordability_index.py: parish median m_p (modelled, 2026 prices),
dispersion sigma_p from the district Gini, Census 2024 household weights.

  area_incomes(level)        {area_id: parish rows}   level = gkma | district | subcounty
  share_below(q, inc)        share of households with income < q
  income_quantile(s, inc)    income below which a share s of households fall
  subcounty_polygons()       sub-county polygons with area_id ("District/Sub-county") for maps
  headline_cpi()             monthly headline CPI (2016/17 = 100), spliced onto the 2009/10 base before July 2017
  cpi_uplift(start, end)     August-2026 CPI over the mean CPI of a period, for uprating
"""
from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

from gkma.analysis.affordability_index import gap_share, parish_incomes
from gkma.config import load_config, p


@lru_cache(maxsize=1)
def headline_cpi() -> pd.Series:
    c = pd.read_csv(p("data/external/mofped/datasets/BOU_CPI.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    link = c.loc["2017-07", "CPI_16"].iloc[0] / c.loc["2017-07", "CPI_09"].iloc[0]
    return c["CPI_16"].combine_first(c["CPI_09"] * link).dropna()


def cpi_uplift(start: str, end: str, target: str = "2026-08") -> float:
    cpi = headline_cpi()
    return float(cpi.loc[target].iloc[0] / cpi.loc[start:end].mean())


def subcounty_polygons() -> gpd.GeoDataFrame:
    g = load_config()["geography"]
    sc = gpd.read_file(p(g["subcounties"])).to_crs(load_config()["project"]["crs_projected"])
    sc = sc[~sc[g["subcounty_name_col"]].isin(g.get("exclude_subcounties", []))]
    sc["area_id"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
    sc["district"] = sc[g["district_name_col"]].str.title()
    sc["unit_id"] = sc["area_id"]
    return sc.reset_index(drop=True)


@lru_cache(maxsize=1)
def _parishes() -> gpd.GeoDataFrame:
    sc = subcounty_polygons()
    pi = parish_incomes(sc.crs).dropna(subset=["households", "income"])
    pi = pi.drop(columns=[c for c in pi.columns if c.startswith("index_") or c in ("district", "area_id")])
    pi = gpd.sjoin(pi, sc[["area_id", "district", "geometry"]], predicate="within").drop(columns="index_right")
    return pi


def area_incomes(level: str) -> dict[str, pd.DataFrame]:
    pi = _parishes()
    if level == "gkma":
        return {"GKMA": pi}
    key = {"district": "district", "subcounty": "area_id"}[level]
    return {a: d for a, d in pi.groupby(key)}


def median_income(inc: pd.DataFrame) -> float:
    """Household-weighted geometric mean of parish medians (the index's m_A)."""
    w = inc["households"]
    return float(np.exp((np.log(inc["income"]) * w).sum() / w.sum()))


def share_below(q: float, inc: pd.DataFrame) -> float:
    return gap_share(q, inc)


def income_quantile(s: float, inc: pd.DataFrame) -> float:
    """Inverse of the mixture CDF: income below which a share s of households fall."""
    lo, hi = float(inc["income"].min()) * 1e-3, float(inc["income"].max()) * 1e3
    return brentq(lambda q: gap_share(q, inc) - s, lo, hi)


def z_distance(q: float, inc: pd.DataFrame) -> float:
    """Distance of a qualifying income q above the area's median household, in
    household-weighted standard deviations of log income: (ln q - ln m_A) / sigma_A.
    Unlike the share priced out, it does not saturate near 100%."""
    w = inc["households"] / inc["households"].sum()
    mu = float((w * np.log(inc["income"])).sum())
    var = float((w * (inc["sigma"] ** 2 + (np.log(inc["income"]) - mu) ** 2)).sum())
    return (np.log(q) - mu) / np.sqrt(var)


def households_able(q: float, inc: pd.DataFrame) -> float:
    return float(inc["households"].sum() * (1 - gap_share(q, inc)))


__all__ = ["area_incomes", "median_income", "share_below", "income_quantile", "z_distance", "households_able",
           "subcounty_polygons", "headline_cpi", "cpi_uplift", "norm"]
