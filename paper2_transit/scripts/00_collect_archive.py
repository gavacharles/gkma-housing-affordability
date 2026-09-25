"""Collect historical RED listings from the Internet Archive (paper 2, before/after design).

  python paper2_transit/scripts/00_collect_archive.py --year 2017 [--max-pages 20]
  -> data/raw/red_archive/red_archive_<year>.csv   (resumable)

2017 captures predate the Entebbe Expressway's opening (June 2018); 2020-21 captures
follow it. Requests go to web.archive.org at one page every 1.5 s.
"""
import argparse
import logging

import _paper  # noqa: F401
from gkma.collect.red_archive import collect
from gkma.config import p

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
ap = argparse.ArgumentParser()
ap.add_argument("--year", type=int, required=True)
ap.add_argument("--max-pages", type=int, default=None)
ap.add_argument("--delay", type=float, default=1.5)
a = ap.parse_args()
out = p("data/raw/red_archive")
out.mkdir(parents=True, exist_ok=True)
df = collect(a.year, out / f"red_archive_{a.year}.csv", delay=a.delay, max_pages=a.max_pages)
print(f"{len(df):,} archived listings in red_archive_{a.year}.csv")
