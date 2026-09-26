"""Clean the complete current listings for paper 2 (the 2025-26 'after' period).

Runs the shared cleaning pipeline on every raw snapshot, now including the full RED crawl
(codes 233,000-256,100, which fill the late-2025 to mid-2026 gap left in paper 1), and
writes a separate file so paper 1's frozen dataset (data/processed/listings.gpkg and
data/paper_snapshot_2026-09-24) is not changed.

  python paper2_transit/scripts/01_clean_current.py
  -> data/processed/listings_current_full.gpkg (+ _cleaning_log.csv, _dedup_report.csv)
"""
import logging

import _paper  # noqa: F401
from gkma.clean.pipeline import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
gdf = run(use_nominatim=True, out_name="listings_current_full.gpkg")
print(f"clean: {len(gdf):,} listings ({(gdf['source'] == 'red').sum():,} RED) at "
      f"{gdf.geometry.to_wkt().nunique()} neighbourhood points")
