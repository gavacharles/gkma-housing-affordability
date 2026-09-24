"""Stage 5: implied land value = asking price - depreciated replacement cost.

Replacement cost rates: data/external/replacement_cost_rates.csv with
    cost_class, rate_ugx_per_m2, year, source
cost_class values used below: bungalow_standard, bungalow_high, storeyed,
apartment, shell. Fill them with your own QS rates and cite the UBOS
construction input price index used to bring them to the listing date.

Floor area is rarely listed, so it is floor_m2 where stated, otherwise
bedrooms x m2_per_bedroom; each m2_per_bedroom value in config is run as a
sensitivity scenario. Results are validated against the price per decimal of
LAND-ONLY listings in the same unit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gkma.config import load_config, p

HIGH_SPEC = ["f_pool", "f_boys_quarters", "f_gated", "f_furnished"]


def load_rates() -> pd.Series:
    path = p(load_config()["construction"]["table"])
    r = pd.read_csv(path)
    if r["rate_ugx_per_m2"].isna().any():
        missing = r.loc[r["rate_ugx_per_m2"].isna(), "cost_class"].tolist()
        raise ValueError(f"Fill replacement cost rates for: {missing} in {path}")
    return r.set_index("cost_class")["rate_ugx_per_m2"]


def cost_class(d: pd.DataFrame) -> pd.Series:
    high = d[[c for c in HIGH_SPEC if c in d]].sum(axis=1) >= 2
    return pd.Series(np.select(
        [d["f_shell_or_incomplete"].eq(1), d["ptype"].eq("apartment"), d["f_storeyed"].eq(1), high],
        ["shell", "apartment", "storeyed", "bungalow_high"], default="bungalow_standard"), index=d.index)


def implied_land_value(pts: pd.DataFrame, m2_per_bedroom: float, rates: pd.Series | None = None,
                       depreciation: float | None = None) -> pd.DataFrame:
    cfg = load_config()["construction"]
    rates = rates if rates is not None else load_rates()
    dep = cfg["depreciation_default"] if depreciation is None else depreciation
    d = pts[(pts["listing_type"] == "sale") & pts["ptype"].isin(["house", "apartment"])
            & pts["price_ugx"].notna() & pts["bedrooms"].notna()].copy()
    d["cost_class"] = cost_class(d)
    d["floor_m2_est"] = d["floor_m2"].fillna(d["bedrooms"].clip(lower=1) * m2_per_bedroom)
    d["replacement_cost"] = d["floor_m2_est"] * d["cost_class"].map(rates) * (1 - dep)
    d["implied_land_value"] = d["price_ugx"] - d["replacement_cost"]
    d["land_share"] = d["implied_land_value"] / d["price_ugx"]
    d["implied_land_per_decimal"] = d["implied_land_value"] / d["plot_decimals"]
    d["flag_negative_land"] = d["implied_land_value"] <= 0
    d["scenario_m2_per_bedroom"] = m2_per_bedroom
    return d


def land_value_by_unit(ilv: pd.DataFrame, pts: pd.DataFrame, units, unit_col="analysis_unit", min_n=5):
    """Unit medians of implied land share / land value per decimal, plus the
    observed price per decimal of land-only listings for validation."""
    ok = ilv[~ilv["flag_negative_land"]]
    land = pts[(pts["listing_type"] == "sale") & (pts["ptype"] == "land") & pts["price_per_decimal"].notna()]
    g = pd.DataFrame({
        "median_land_share": ok.groupby(unit_col)["land_share"].median(),
        "median_implied_land_per_decimal": ok.groupby(unit_col)["implied_land_per_decimal"].median(),
        "n_houses": ok.groupby(unit_col).size(),
        "share_negative": ilv.groupby(unit_col)["flag_negative_land"].mean(),
        "median_landonly_per_decimal": land.groupby(unit_col)["price_per_decimal"].median(),
        "n_land": land.groupby(unit_col).size(),
    })
    g.loc[g["n_houses"].fillna(0) < min_n, ["median_land_share", "median_implied_land_per_decimal"]] = np.nan
    g.loc[g["n_land"].fillna(0) < min_n, "median_landonly_per_decimal"] = np.nan
    return units.merge(g, left_on="unit_id", right_index=True, how="left")


def validation_stats(by_unit: pd.DataFrame) -> dict:
    v = by_unit.dropna(subset=["median_implied_land_per_decimal", "median_landonly_per_decimal"])
    if len(v) < 3:
        return {"n_units": len(v)}
    a, b = np.log(v["median_implied_land_per_decimal"]), np.log(v["median_landonly_per_decimal"])
    return {"n_units": len(v), "spearman": a.corr(b, method="spearman"),
            "median_ratio_implied_to_landonly": float(np.median(np.exp(a - b)))}
