"""Stage 0b: raw snapshots -> data/processed/listings.gpkg + cleaning log."""
import argparse

import _common  # noqa: F401
from gkma.clean.pipeline import run

ap = argparse.ArgumentParser()
ap.add_argument("--nominatim", action="store_true", help="geocode unmatched places via OSM")
ap.add_argument("--no-covariates", action="store_true")
ap.add_argument("--out", default="data/processed")
a = ap.parse_args()
gdf = run(use_nominatim=a.nominatim, with_covariates=not a.no_covariates, out_dir=a.out)
print(gdf.groupby(["listing_type", "ptype"]).size().to_string())
