"""Stage 4: rent-to-income, price-to-income and the share of households who
can afford the local median rent at a 30 % rent-to-income threshold.

Income input (data/external/unhs_income_by_unit.csv), one row per income unit
(district by default — the finest level UNHS supports for GKMA):
    unit                        e.g. "Kampala", "Wakiso", "Mukono"
    median_monthly_income_ugx   household income (or consumption; say which)
    households                  Census 2024 household count
    income_log_sd               sigma of log income (optional)
    gini                        used for sigma if income_log_sd missing
    survey_median_rent_ugx      UNHS median rent actually paid (optional; for
                                the listing-vs-survey "formal market gap")
    cpi_uplift                  CPI(listing period) / CPI(survey period); applied
                                to income and survey rent (optional, warned if missing)

Income is assumed lognormal within a unit: P(afford) = 1 - Phi((ln(R/t) - ln m)/s).
The spatial mismatch (parish prices vs district incomes) is a stated
limitation; sensitivity to sigma is reported via `sigma_scale`.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import norm

from gkma.config import load_config, p

log = logging.getLogger(__name__)


def sigma_from_gini(g: float) -> float:
    """Lognormal: G = 2*Phi(sigma/sqrt2) - 1."""
    return float(np.sqrt(2) * norm.ppf((g + 1) / 2))


def load_income() -> pd.DataFrame:
    path = p(load_config()["income"]["table"])
    inc = pd.read_csv(path)
    # Bring survey-year incomes/rents to listing-period prices (CPI ratio).
    up = pd.to_numeric(inc.get("cpi_uplift"), errors="coerce") if "cpi_uplift" in inc else None
    if up is None or up.isna().any():
        log.warning("income table: cpi_uplift missing for some units - incomes are left at "
                    "survey-year prices, which overstates unaffordability. Fill cpi_uplift "
                    "(CPI at listing date / CPI at survey mid-point).")
    if up is not None:
        up = up.fillna(1.0)
        inc["median_monthly_income_ugx"] = inc["median_monthly_income_ugx"] * up
        if "survey_median_rent_ugx" in inc:
            inc["survey_median_rent_ugx"] = pd.to_numeric(inc["survey_median_rent_ugx"], errors="coerce") * up
    if "income_log_sd" not in inc or inc["income_log_sd"].isna().any():
        if "gini" not in inc:
            raise ValueError("income table needs income_log_sd or gini")
        inc["income_log_sd"] = inc.get("income_log_sd", pd.Series(np.nan, index=inc.index)) \
            .fillna(inc["gini"].map(sigma_from_gini))
    return inc.set_index("unit")


def share_affording(rent: np.ndarray, median_income: np.ndarray, sigma: np.ndarray,
                    threshold: float = 0.30) -> np.ndarray:
    z = (np.log(rent / threshold) - np.log(median_income)) / sigma
    return 1 - norm.cdf(z)


def income_key(pts: pd.DataFrame, level: str) -> pd.Series:
    """Map each listing to its income unit (district name by default)."""
    if level == "district":
        from_units = pts["subcounty_id"].astype("string").str.split("/").str[0]
        return from_units.where(from_units.notna() & ~from_units.str.startswith("hex"), pts["place_district"])
    return pts[f"{level}_id"]


def affordability_by_unit(pts: pd.DataFrame, units, unit_col: str = "analysis_unit",
                          bedrooms: tuple | None = None, sigma_scale: float = 1.0,
                          min_n: int = 5) -> pd.DataFrame:
    """Unit-level medians joined to income, with affordability metrics.

    bedrooms: e.g. (1, 2) to price a modest 'standard' unit rather than the
    all-listings median, which is dominated by larger formal homes.
    """
    cfg = load_config()["income"]
    t = cfg["affordability_threshold"]
    inc = load_income()
    d = pts.copy()
    # District table supplies dispersion (Gini) and the CPI factor; with
    # join_level "parish" the parish model supplies the median (below).
    d["income_unit"] = income_key(d, "district")
    rent = d[d["listing_type"] == "rent"]
    if bedrooms:
        rent = rent[rent["bedrooms"].between(*bedrooms)]
    sale = d[(d["listing_type"] == "sale") & (d["ptype"] != "land")]

    g = pd.DataFrame({
        "median_rent": rent.groupby(unit_col)["rent_month_ugx"].median(),
        "n_rent": rent.groupby(unit_col).size(),
        "median_price": sale.groupby(unit_col)["price_ugx"].median(),
        "n_sale": sale.groupby(unit_col).size(),
        "income_unit": d.groupby(unit_col)["income_unit"].agg(lambda s: s.mode().iat[0] if s.notna().any() else None),
    })
    g = g.join(inc, on="income_unit")
    if cfg.get("join_level") == "parish" and p(cfg.get("parish_income", "")).exists():
        # Modelled parish medians (UBOS-published data only, see census.py),
        # aggregated to each analysis unit as a household-weighted geometric
        # mean, uprated with the same CPI factor; dispersion stays district-level.
        import geopandas as gpd
        pi = gpd.read_file(p(cfg["parish_income"])).dropna(subset=["median_income_2019_20"]).to_crs(units.crs)
        pi["geometry"] = pi.geometry.representative_point()
        j = gpd.sjoin(pi[["households", "median_income_2019_20", "geometry"]], units[["unit_id", "geometry"]],
                      how="inner", predicate="within")
        j["_l"] = np.log(j["median_income_2019_20"]) * j["households"]
        agg = j.groupby("unit_id").agg(_l=("_l", "sum"), _h=("households", "sum"))
        parish_med = np.exp(agg["_l"] / agg["_h"])
        up = pd.to_numeric(inc["cpi_uplift"], errors="coerce").dropna()
        up = float(up.iloc[0]) if len(up) else 1.0
        g["income_source"] = np.where(g.index.isin(parish_med.index), "parish_model", "district_table")
        g["median_monthly_income_ugx"] = (parish_med.reindex(g.index) * up).fillna(g["median_monthly_income_ugx"])
    m, s = g["median_monthly_income_ugx"], g["income_log_sd"] * sigma_scale
    ok_r = g["n_rent"].fillna(0) >= min_n
    ok_s = g["n_sale"].fillna(0) >= min_n
    g["rent_to_income"] = np.where(ok_r, g["median_rent"] / m, np.nan)
    g["price_to_income"] = np.where(ok_s, g["median_price"] / (12 * m), np.nan)
    g["share_can_afford"] = np.where(ok_r, share_affording(g["median_rent"], m, s, t), np.nan)
    g["share_cannot_afford"] = 1 - g["share_can_afford"]
    g["income_needed"] = g["median_rent"] / t
    g["affordability_gap_ugx"] = g["income_needed"] - m
    if "survey_median_rent_ugx" in g:
        g["listing_vs_survey_rent"] = g["median_rent"] / g["survey_median_rent_ugx"]
    out = units.merge(g, left_on="unit_id", right_index=True, how="left")
    # Census 2024 households per unit -> number of households priced out
    census = p("data/external/census2024_parish.gpkg")
    if census.exists():
        import geopandas as gpd
        cz = gpd.read_file(census).to_crs(out.crs)
        pts_c = cz[["households", "geometry"]].dropna(subset=["households"]).copy()
        pts_c["geometry"] = pts_c.geometry.representative_point()
        j = gpd.sjoin(pts_c, out[["unit_id", "geometry"]], how="inner", predicate="within")
        out["census_households"] = out["unit_id"].map(j.groupby("unit_id")["households"].sum())
        out["households_cannot_afford"] = out["census_households"] * out["share_cannot_afford"]
    return out


def household_weighted_summary(aff: pd.DataFrame, pts: pd.DataFrame | None = None,
                               bedrooms: tuple | None = None) -> pd.DataFrame:
    """District summary of the unit-level results.

    * share_cannot_afford: mean of unit shares weighted by Census 2024
      households (falls back to rental-listing counts where census counts
      are missing), i.e. the share of *households* in units with data.
    * households_cannot_afford: sum over units of households x share.
    * median_rent_pooled: median asking rent over all qualifying listings in
      the district (not an average of unit medians, which extreme units skew).
    * median_income_units: household-weighted geometric mean of unit median
      incomes (current prices).
    """
    a = aff.dropna(subset=["share_cannot_afford"]).copy()
    w = a["census_households"] if "census_households" in a else pd.Series(np.nan, index=a.index)
    a["_w"] = w.fillna(a["n_rent"])
    a["_ws"] = a["share_cannot_afford"] * a["_w"]
    a["_wl"] = np.log(a["median_monthly_income_ugx"]) * a["_w"]
    agg = {"units": ("unit_id", "size"), "rent_listings": ("n_rent", "sum"),
           "_ws": ("_ws", "sum"), "_wl": ("_wl", "sum"), "_w": ("_w", "sum")}
    if "households_cannot_afford" in a:
        agg.update(census_households=("census_households", "sum"),
                   households_cannot_afford=("households_cannot_afford", "sum"))
    g = a.groupby("income_unit").agg(**agg)
    g["share_cannot_afford"] = g.pop("_ws") / g["_w"]
    g["median_income_units"] = np.exp(g.pop("_wl") / g.pop("_w"))
    if pts is not None:
        d = pts[pts["listing_type"] == "rent"].copy()
        if bedrooms:
            d = d[d["bedrooms"].between(*bedrooms)]
        d["income_unit"] = income_key(d, "district")
        d = d[d["analysis_unit"].isin(a["unit_id"])]           # same units as the shares
        g["median_rent_pooled"] = d.groupby("income_unit")["rent_month_ugx"].median()
        g["income_needed_at_30pct"] = g["median_rent_pooled"] / 0.30
    return g
