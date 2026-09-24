"""raw portal snapshots -> analysis-ready listing panel.

Output: data/processed/listings.gpkg (points, projected CRS) and
data/processed/cleaning_log.csv (record counts after every step — this table
goes straight into the paper's data section).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from gkma.clean.dedup import dedup_report, deduplicate
from gkma.clean.prices import normalise_prices
from gkma.clean.text_features import classify_property_type, extract_features
from gkma.clean.units import apply_price_units, normalise_sizes
from gkma.config import load_config, p
from gkma.geo.boundaries import attach_units, in_study_area, points_gdf
from gkma.geo.gazetteer import resolve_locations

log = logging.getLogger(__name__)


def load_raw(sources=("jiji", "red", "upc", "manual", "demo")) -> pd.DataFrame:
    frames = []
    for s in sources:
        for f in sorted((p(load_config()["project"]["raw_dir"]) / s).glob("*.csv")):
            frames.append(pd.read_csv(f, dtype=str))
    if not frames:
        raise FileNotFoundError("No raw files in data/raw/<source>/. Run scripts/01_collect.py first.")
    df = pd.concat(frames, ignore_index=True)
    for c in ["lat", "lon"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


class StepLog:
    def __init__(self):
        self.rows = []

    def __call__(self, step: str, df: pd.DataFrame, note: str = ""):
        self.rows.append({"step": step, "n": len(df), "note": note})
        log.info("%-38s %6d  %s", step, len(df), note)
        return df

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def derive_measures(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    beds = out["bedrooms"].where(out["bedrooms"] > 0)
    out["rent_per_bedroom"] = out["rent_month_ugx"] / beds
    out["price_per_bedroom"] = out["price_ugx"] / beds
    out["price_per_decimal"] = out["price_ugx"] / out["plot_decimals"]
    out = out.replace([np.inf, -np.inf], np.nan)
    out["log_rent_month_ugx"] = np.log(out["rent_month_ugx"])
    out["log_price_ugx"] = np.log(out["price_ugx"])
    ts = pd.to_datetime(out["listing_date"].fillna(out["first_seen"]), errors="coerce", utc=True)
    out["listing_month"] = ts.dt.strftime("%Y-%m")
    out["listing_quarter"] = ts.dt.to_period("Q").astype(str)
    return out


def run(use_nominatim: bool = False, with_covariates: bool = True, out_dir: str | Path = "data/processed"):
    steps = StepLog()
    raw = steps("raw records (all snapshots)", load_raw())

    df = normalise_prices(raw)
    df = normalise_sizes(df)
    df = apply_price_units(df)
    df = extract_features(df)
    df["ptype"] = classify_property_type(df)
    df = steps("parsed", df)

    df = steps("drop short-stay / nightly", df[~df["flag_short_stay"]])
    df = steps("drop missing price", df[~df["flag_price_missing"]])
    df = steps("drop listing_type unknown", df[df["listing_type"].isin(["rent", "sale"])])

    df = resolve_locations(df, use_nominatim=use_nominatim)
    df = steps("location resolved", df[df["lat"].notna()],
               note=df["geo_method"].value_counts(dropna=False).to_dict().__repr__())

    out = p(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = df
    df = deduplicate(df)
    steps("after de-duplication", df)
    dedup_report(before, df).to_csv(out / "dedup_report.csv")

    gdf = points_gdf(df)
    gdf = steps("inside GKMA study area", gdf[in_study_area(gdf)])
    gdf = steps("drop price outliers (flagged)", gdf[~gdf["flag_price_outlier"]])
    gdf = steps("drop commercial", gdf[gdf["ptype"] != "commercial"])

    gdf = attach_units(gdf)
    if with_covariates:
        from gkma.geo.covariates import add_covariates
        gdf = add_covariates(gdf)
    gdf = derive_measures(gdf)

    # GeoPackage cannot store mixed-type object columns cleanly
    for c in gdf.columns:
        if gdf[c].dtype == object and c != "geometry":
            gdf[c] = gdf[c].astype("string")
    gdf.to_file(out / "listings.gpkg", driver="GPKG")
    steps.frame().to_csv(out / "cleaning_log.csv", index=False)
    log.info("wrote %s", out / "listings.gpkg")
    return gdf
