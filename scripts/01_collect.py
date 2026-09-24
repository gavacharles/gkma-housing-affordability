"""Stage 0: collect listings.

  python scripts/01_collect.py --portal jiji            # public API, terms permit
  python scripts/01_collect.py --portal red --extract path/to/red_extract.csv
  python scripts/01_collect.py --portal red             # newest-first crawl, resumable, stops at min_listing_date
  python scripts/01_collect.py --manual                 # write the manual-entry template

Run on a fixed schedule (e.g. weekly) through the collection window; each
run appends a dated snapshot so first-seen dates and re-posting can be tracked.
Portals without a permission basis in config.yaml refuse to run.
"""
import argparse

import _common  # noqa: F401
from gkma.collect import base

ap = argparse.ArgumentParser()
ap.add_argument("--portal", choices=["jiji", "red", "upc"])
ap.add_argument("--extract", help="consented data extract file (RED)")
ap.add_argument("--max-pages", type=int)
ap.add_argument("--limit", type=int, help="max detail pages (red/upc)")
ap.add_argument("--manual", action="store_true")
a = ap.parse_args()

if a.manual:
    path = _common.ROOT / "data/raw/manual/manual_entry_template.csv"
    base.to_frame([]).to_csv(path, index=False)
    print(f"Template written: {path}\nSave filled sheets as data/raw/manual/manual_<date>.csv "
          "(source=manual, one row per listing, copy values exactly as shown).")
elif a.portal == "jiji":
    from gkma.collect import jiji
    base.save_raw(jiji.collect(max_pages=a.max_pages), "jiji")
elif a.portal == "red":
    from gkma.collect import red
    if a.extract:
        base.save_raw(red.load_extract(a.extract), "red")
    else:
        red.collect(limit=a.limit)   # appends to data/raw/red/red_crawl.csv; resumable
elif a.portal == "upc":
    from gkma.collect import upc
    base.save_raw(upc.collect(limit=a.limit), "upc")
else:
    ap.print_help()
