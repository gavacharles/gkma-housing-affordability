"""Clean archived RED listings with the shared pipeline (paper 2).

Maps the archived specification fields to the shared raw schema (RAW_COLUMNS) and
runs exactly the steps used for the current listings: price and currency parsing
(BoU exchange rates for the capture month), units, text features, property type,
gazetteer geocoding to the same neighbourhood points, deduplication, the study-area
filter and covariates. The capture date is used as the listing date (an upper bound).

  python paper2_transit/scripts/01_clean_archive.py --year 2017 [--nominatim]
  -> data/processed/listings_archive_<year>.gpkg (+ _cleaning_log.csv, _dedup_report.csv)
"""
import argparse
import logging

import numpy as np
import pandas as pd

import _paper  # noqa: F401
from gkma.clean.pipeline import run
from gkma.collect.base import RAW_COLUMNS
from gkma.config import p

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
ap = argparse.ArgumentParser()
ap.add_argument("--year", type=int, required=True)
ap.add_argument("--nominatim", action="store_true")
a = ap.parse_args()

src = pd.read_csv(p(f"data/raw/red_archive/red_archive_{a.year}.csv"), dtype=str)
src = src.drop(columns=[c for c in src.columns if c.startswith("code.")]).drop_duplicates("code")
typ = src["type"].fillna("")
is_sale = typ.str.contains(r"\bSale\b", case=False) | (src["price"].notna() & src["rent"].isna())
amount = np.where(is_sale, src["price"], src["rent"])
cur = pd.Series(amount, index=src.index).fillna("").str.contains(r"\$|USD", case=False).map({True: "USD", False: "UGX"})
cap = pd.to_datetime(src["capture_timestamp"], format="%Y%m%d%H%M%S", errors="coerce")
raw = pd.DataFrame({
    "source": "red",
    "source_id": src["code"],
    "url": src["url"],
    "scraped_at": cap.dt.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    "listing_date": cap.dt.strftime("%Y-%m-%d"),
    "listing_date_source": "archive_capture",
    "listing_type": np.where(is_sale, "sale", "rent"),
    "property_type": typ.str.replace(r"\s*Sale\s*$", "", regex=True).str.strip(),
    "title": src["headline"].fillna(src["bedrooms"].fillna("") + " bedroom " + typ + " in " + src["location"].fillna("")),
    "description": src["description"],
    "price_raw": amount,
    "currency_raw": cur,
    "price_period": np.where(is_sale, None, "per month"),
    "location_raw": src["location"],
    "district_raw": src["district"],
    "region_raw": None,
    "bedrooms_raw": src["bedrooms"],
    "bathrooms_raw": src["bathrooms"],
    "size_raw": src["plot_size"].fillna(src["size"]),
    "size_unit_raw": None,
    "tenure_raw": src["tenure"] if "tenure" in src else None,             # 2020 layout only
    "furnishing_raw": src["furnished"].map({"Yes": "Furnished", "No": "Unfurnished"}),
    "listed_by": None,
    "agent_key": None,
    "lat": np.nan,
    "lon": np.nan,
})[RAW_COLUMNS]
print(f"{len(raw):,} archived {a.year} records: {(raw.listing_type == 'rent').sum():,} rent, "
      f"{(raw.listing_type == 'sale').sum():,} sale; captured {cap.min():%Y-%m-%d} to {cap.max():%Y-%m-%d}")
gdf = run(use_nominatim=a.nominatim, raw=raw, out_name=f"listings_archive_{a.year}.gpkg")
print(f"clean: {len(gdf):,} listings at {gdf.geometry.to_wkt().nunique()} neighbourhood points")
