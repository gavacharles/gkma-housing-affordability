"""GKMA Housing Affordability Index.

Three transparent components, each computed for an area A (GKMA, district,
sub-county) from the listings located in A and the households living in A:

  RAI  Rental Affordability Index = 100 x m_A / (R_A / t)
       R_A: median listed monthly rent (1-2 bedrooms by default); t = 0.30.
       100 = the area's median household can just afford the median listed rent.
  OAI  Ownership Affordability Index = 100 x m_A / (PMT_A / c)
       PMT_A: monthly repayment on the median listed house or apartment, with
       deposit d, annual rate r, term T years; c = repayment-to-income cap.
       Adapted from the US National Association of Realtors' Housing
       Affordability Index to Ugandan lending conditions.
  AGI  Affordability Gap Index = share of households in A whose income is
       below the qualifying income (for rent: R_A / t; for ownership: PMT_A / c).
  RI   Residual-income measure (Stone 2006; Kutty 2005): a household can afford
       housing cost H only if income - H >= N_p, its minimum non-housing budget
       (UBOS upper poverty line x adult equivalents x (1 - housing share)).
       Share priced out = share with income < H + N_p, split into households
       already below N_p and those pushed below it by H (housing-induced poverty).
       Incomes are a household-weighted mixture of parish lognormals:
       share = sum_p w_p * Phi((ln Q - ln m_p) / sigma_p).

m_A is the household-weighted geometric mean of the modelled parish medians
of ALL parishes in A (Census 2024 households), so the index compares the
typical household living in the area with the typical home listed there.
Confidence intervals bootstrap the listings (sampling uncertainty in the
medians); income-model uncertainty is treated separately in sensitivity.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import norm

from gkma.config import load_config, p


def monthly_payment(principal, annual_rate, years):
    r = annual_rate / 12
    n = years * 12
    return principal * r / (1 - (1 + r) ** -n)


def bou_lending_rate(months: int = 12) -> float:
    """Mean BoU weighted-average shilling lending rate over the last `months`."""
    d = pd.read_csv(p("data/external/mofped/datasets/MOF_POE.csv"), parse_dates=["Date"])
    s = d.set_index("Date")["I_BA_UGX_L"].dropna().sort_index()
    return float(s.tail(months).mean()) / 100


def parish_incomes(crs) -> gpd.GeoDataFrame:
    """Modelled parish medians (current prices) with households and sigma, as points."""
    cfg = load_config()
    g = cfg["geography"]
    pi = gpd.read_file(p(cfg["income"]["parish_income"])).dropna(subset=["median_income_2019_20"])
    cpi = float(pd.read_csv(p("data/external/cpi_uplift.csv")).query("series == 'headline'")["uplift"].iloc[0])
    inc = pd.read_csv(p(cfg["income"]["table"])).set_index("unit")
    sig = pd.Series(np.sqrt(2) * norm.ppf((inc["gini"] + 1) / 2), index=inc.index)
    pi["district"] = pi[g["district_name_col"]].str.title()
    pi["sigma"] = pi["district"].map(sig)
    pi["income"] = pi["median_income_2019_20"] * cpi
    ri = load_config().get("affordability_index", {}).get("residual_income", {})
    hh = pi["hh_size"].fillna(pi["hh_size"].median()) if "hh_size" in pi else 3.4
    pi["nonhousing_min"] = (ri.get("poverty_line_ae_2019_20", 87000) * cpi * ri.get("ae_per_person", 0.787) * hh
                            * (1 - ri.get("housing_share", 0.174)))
    pi["geometry"] = pi.geometry.representative_point()
    return pi.to_crs(crs)


def gap_share(threshold, incomes: pd.DataFrame) -> float:
    w = incomes["households"] / incomes["households"].sum()
    z = (np.log(threshold) - np.log(incomes["income"])) / incomes["sigma"]
    return float((w * norm.cdf(z)).sum())


def residual_shares(housing_cost, incomes: pd.DataFrame) -> tuple[float, float]:
    """(share with income < housing_cost + N_p, share with income < N_p)."""
    w = incomes["households"] / incomes["households"].sum()
    f = lambda q: float((w * norm.cdf((np.log(q) - np.log(incomes["income"])) / incomes["sigma"])).sum())  # noqa: E731
    return f(housing_cost + incomes["nonhousing_min"]), f(incomes["nonhousing_min"])


def _median_ci(x: np.ndarray, B: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    b = np.median(rng.choice(x, (B, len(x))), axis=1)
    return float(np.median(x)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def area_index(rents: np.ndarray, prices: np.ndarray, incomes: pd.DataFrame, mortgage: dict,
               t: float = 0.30, min_n: int = 20) -> dict:
    out = {"households": float(incomes["households"].sum()), "n_rent": len(rents), "n_sale": len(prices)}
    lw = incomes["households"]
    out["median_income"] = float(np.exp((np.log(incomes["income"]) * lw).sum() / lw.sum())) if len(incomes) else np.nan
    m = out["median_income"]
    if len(rents) >= min_n:
        R, lo, hi = _median_ci(rents)
        out.update(median_rent=R, rai=100 * m / (R / t), rai_lo=100 * m / (hi / t), rai_hi=100 * m / (lo / t),
                   rent_income_needed=R / t, agi_rent=gap_share(R / t, incomes))
        tot, poor = residual_shares(R, incomes)
        out.update(ri_rent=tot, ri_rent_housing_induced=tot - poor, below_nonhousing_min=poor,
                   ri_rent_median_residual=m - R - float(np.exp((np.log(incomes["nonhousing_min"]) * lw).sum()
                                                                / lw.sum())))
    if len(prices) >= min_n:
        P, lo, hi = _median_ci(prices)
        c, d, r, T = mortgage["cap"], mortgage["deposit"], mortgage["rate"], mortgage["term_years"]
        q = lambda price: monthly_payment(price * (1 - d), r, T) / c  # noqa: E731
        out.update(median_price=P, monthly_payment=monthly_payment(P * (1 - d), r, T),
                   own_income_needed=q(P), oai=100 * m / q(P), oai_lo=100 * m / q(hi), oai_hi=100 * m / q(lo),
                   agi_own=gap_share(q(P), incomes))
        pmt = monthly_payment(P * (1 - d), r, T)
        tot, poor = residual_shares(pmt, incomes)
        out.update(ri_own=tot, ri_own_housing_induced=tot - poor, below_nonhousing_min=poor)
    return out


def compute_index(pts: gpd.GeoDataFrame, level: str, mortgage: dict, bedrooms=(0.5, 2),
                  min_n: int = 20, t: float = 0.30) -> pd.DataFrame:
    """Index for every area at `level` ("gkma", "district", "subcounty", "parish")."""
    g = load_config()["geography"]
    incomes = parish_incomes(pts.crs)
    rent = pts[(pts["listing_type"] == "rent") & pts["bedrooms"].between(*bedrooms)]
    sale = pts[(pts["listing_type"] == "sale") & pts["ptype"].isin(["house", "apartment"])]
    if level == "gkma":
        areas = {"GKMA": (rent, sale, incomes)}
    else:
        path = {"district": g["subcounties"], "subcounty": g["subcounties"], "parish": g["parishes"]}[level]
        poly = gpd.read_file(p(path)).to_crs(pts.crs)
        if level == "district":
            poly = poly.dissolve(g["district_name_col"]).reset_index()
            poly["area_id"] = poly[g["district_name_col"]].str.title()
        elif level == "subcounty":
            poly["area_id"] = poly[g["district_name_col"]].str.title() + "/" + poly[g["subcounty_name_col"]]
        else:
            poly["area_id"] = poly[g["district_name_col"]].str.title() + "/" + poly[g["parish_name_col"]]
        poly = poly[["area_id", "geometry"]]
        tag = lambda df: gpd.sjoin(df, poly, how="inner", predicate="within")  # noqa: E731
        r, s_, i = tag(rent), tag(sale), tag(incomes)
        areas = {a: (r[r["area_id"] == a], s_[s_["area_id"] == a], i[i["area_id"] == a]) for a in poly["area_id"]}
    rows = []
    for a, (r, s_, i) in areas.items():
        if len(i) == 0:
            continue
        rows.append({"area": a, **area_index(r["rent_month_ugx"].dropna().to_numpy(),
                                             s_["price_ugx"].dropna().to_numpy(), i, mortgage, t=t, min_n=min_n)})
    return pd.DataFrame(rows)


def burden_gradient(pts: gpd.GeoDataFrame, mortgage: dict, thresholds=None, levels=("gkma", "district"),
                    min_n: int = 20) -> pd.DataFrame:
    """Share of households priced out when the tolerable housing-cost burden b
    (rent or mortgage repayment as a share of gross income) runs from 10% to 80%.

    For rent the qualifying income is R_A / b; for ownership PMT_A / b (b replaces
    the lender's repayment cap). Also returns the burden the area's median
    household would bear: R_A / m_A and PMT_A / m_A.
    """
    thresholds = np.round(np.arange(0.10, 0.801, 0.05), 2) if thresholds is None else thresholds
    rows = []
    for level in levels:
        for b in thresholds:
            r = compute_index(pts, level, {**mortgage, "cap": b}, min_n=min_n, t=b)
            r["burden"] = b
            rows.append(r)
    out = pd.concat(rows, ignore_index=True)
    out["median_hh_rent_burden"] = out["median_rent"] / out["median_income"]
    out["median_hh_own_burden"] = out["monthly_payment"] / out["median_income"]
    return out
