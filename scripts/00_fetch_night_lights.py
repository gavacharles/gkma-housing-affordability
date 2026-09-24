"""Download NASA Black Marble annual night-time lights (VNP46A4) for GKMA.

Needs a NASA Earthdata token. Put it in a file named `.env` in the project root
(never commit it; .env is git-ignored):

    EARTHDATA_TOKEN=eyJ0eXAiOiJKV1Qi...

Get the token at https://urs.earthdata.nasa.gov  ->  log in  ->  "Generate Token".
The script reads it from the environment and never prints it.

  python scripts/00_fetch_night_lights.py [--year 2024]

GKMA lies in Black Marble tiles h21v08 and h21v09 (10-degree tiles, 2400 x 2400
cells of 15 arc-seconds, ~500 m). The script mosaics the snow-free near-nadir
composite (radiance, nW/cm2/sr), clips to GKMA and writes the GeoTIFF named in
config.yaml (geography.night_lights).
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import _common  # noqa: F401
import numpy as np
import requests

from gkma.config import load_config, p

ARCHIVE = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A4/{year}/001"
TILES = ["h21v08", "h21v09"]
LAYER = "NearNadir_Composite_Snow_Free"
BBOX = (32.25, -0.05, 33.05, 0.65)  # lon_min, lat_min, lon_max, lat_max

ap = argparse.ArgumentParser()
ap.add_argument("--year", type=int, default=2024)
a = ap.parse_args()

try:
    from dotenv import load_dotenv
    load_dotenv(p(".env"))
except ImportError:
    pass
token = os.environ.get("EARTHDATA_TOKEN", "").strip()
if not token:
    sys.exit("No EARTHDATA_TOKEN found. Create .env in the project root with EARTHDATA_TOKEN=<your token> "
             "(see the docstring at the top of this script).")
auth = {"Authorization": f"Bearer {token}"}


class EarthdataSession(requests.Session):
    """Keep the bearer token across redirects between NASA hosts only
    (requests drops it on any cross-host redirect by default)."""
    NASA = (".earthdata.nasa.gov", ".eosdis.nasa.gov")

    def rebuild_auth(self, prepared_request, response):
        host = requests.utils.urlparse(prepared_request.url).hostname or ""
        if host.endswith(self.NASA):
            prepared_request.headers["Authorization"] = auth["Authorization"]
        else:
            prepared_request.headers.pop("Authorization", None)


http = EarthdataSession()

listing = http.get(ARCHIVE.format(year=a.year) + ".json", headers=auth, timeout=120)
listing.raise_for_status()
entries = listing.json()
entries = entries.get("content", entries) if isinstance(entries, dict) else entries
names = [e["name"] for e in entries if any(t in e["name"] for t in TILES) and e["name"].endswith(".h5")]
if len(names) < len(TILES):
    sys.exit(f"Tiles {TILES} not found for {a.year}: {names}")

import h5py  # noqa: E402
import rasterio  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

cell = 10 / 2400
mosaic = np.full((4800, 2400), np.nan, dtype="float32")   # v08 above v09, both h21
tmp = Path(tempfile.mkdtemp())
for n in names:
    path = tmp / n
    with http.get(f"{ARCHIVE.format(year=a.year)}/{n}", headers=auth, stream=True, timeout=600) as r:
        r.raise_for_status()
        if "html" in r.headers.get("Content-Type", ""):
            sys.exit("NASA returned a login page instead of data: the token may be expired or LAADS "
                     "not yet authorised for your account (Earthdata Login > Applications > Authorized Apps).")
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    with h5py.File(path, "r") as h:
        grp = h["HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields"]
        ds = grp[LAYER]
        arr = ds[()].astype("float32")
        fill = ds.attrs.get("_FillValue", [65535])[0]
        scale = ds.attrs.get("scale_factor", [1.0])[0]
        offset = ds.attrs.get("add_offset", [0.0])[0]
        arr[arr == fill] = np.nan
        arr = arr * scale + offset
    row = 0 if "v08" in n else 2400
    mosaic[row:row + 2400, :] = arr
    print(f"read {n}")

# h21 spans lon 30..40 E; v08 spans lat 10..0 N; v09 spans 0..-10
transform = from_origin(30.0, 10.0, cell, cell)
win = from_bounds(*BBOX, transform=transform).round_offsets().round_lengths()
r0, c0 = int(win.row_off), int(win.col_off)
clip = mosaic[r0:r0 + int(win.height), c0:c0 + int(win.width)]
out = p(load_config()["geography"]["night_lights"])
out.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(out, "w", driver="GTiff", height=clip.shape[0], width=clip.shape[1], count=1,
                   dtype="float32", crs="EPSG:4326", nodata=np.nan,
                   transform=rasterio.windows.transform(win, transform)) as dst:
    dst.write(clip, 1)
    dst.update_tags(source=f"NASA Black Marble VNP46A4 {a.year}, {LAYER}", units="nW/cm2/sr")
print(f"wrote {out} ({clip.shape[1]} x {clip.shape[0]} cells, median radiance {np.nanmedian(clip):.1f})")
