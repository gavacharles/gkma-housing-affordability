"""Tidy data/lookup/neighbourhood_lookup.csv against official UBOS geography.

1. A neighbourhood whose name is an official UBOS parish in the same district,
   within 5 km of the draft point, is moved to that parish's representative
   point (coord_source = ubos_parish_2016). Farther matches are left alone and
   flagged: a same-named parish elsewhere is usually a different place.
2. A few town/division names are placed on their UBOS sub-county instead.
3. New places and spelling variants found in the listings are added.
Adds `check_status`: ubos_parish | osm_agrees | needs_review.
Nothing is marked verified: `verified` stays for the researcher.
"""
import re

import _common  # noqa: F401
import geopandas as gpd
import numpy as np
import pandas as pd

from gkma.config import load_config, p
from gkma.geo.gazetteer import lg_key

g = load_config()["geography"]
path = p(g["neighbourhood_lookup"])
lk = pd.read_csv(path)
lk["note"] = lk["note"].fillna("")

par = gpd.read_file(p(g["parishes"]))
rp = par.geometry.representative_point()
par_pts = gpd.GeoDataFrame(par.drop(columns="geometry"), geometry=rp, crs=par.crs).to_crs("EPSG:4326")
sub = gpd.read_file(p(g["subcounties"]))
sub_pts = gpd.GeoDataFrame(sub.drop(columns="geometry"), geometry=sub.geometry.representative_point(),
                           crs=sub.crs).to_crs("EPSG:4326")


def pkey(s):
    s = re.sub(r"\s+(i{1,3}|iv|v|vi|ward|central|a|b)$", "", str(s).lower().strip())
    return lg_key(s).replace(" ", "")


par_pts["_k"] = par_pts[g["parish_name_col"]].map(pkey)
par_pts["_d"] = par_pts[g["district_name_col"]].str.title()


def km(lat1, lon1, lat2, lon2):
    return 111.2 * np.hypot(lat2 - lat1, (lon2 - lon1) * np.cos(np.radians(lat1)))


# 1) namesake UBOS parishes
moved = 0
for i, r in lk.iterrows():
    if r.get("level") == "subcounty":
        continue
    cand = par_pts[(par_pts["_k"] == pkey(r["name"])) & (par_pts["_d"] == str(r["district"]).title())]
    if cand.empty:
        continue
    lat, lon = cand.geometry.y.mean(), cand.geometry.x.mean()   # e.g. Kololo I-IV -> centre of the group
    d = km(r["lat"], r["lon"], lat, lon)
    if d <= 5:
        lk.loc[i, ["lat", "lon"]] = [round(lat, 5), round(lon, 5)]
        lk.loc[i, "coord_source"] = "ubos_parish_2016"
        lk.loc[i, "note"] = f"placed on UBOS parish {', '.join(cand[g['parish_name_col']].unique())} (moved {d:.1f} km)"
        moved += 1
    else:
        lk.loc[i, "note"] = (r["note"] + "; " if r["note"] else "") + \
            f"a UBOS parish of this name lies {d:.0f} km away - probably a different place; please verify"

# 2) towns/divisions -> UBOS sub-county representative point
SUBCOUNTY_PLACES = {"Wakiso Town": ("Wakiso", "Wakiso Town Council"), "Goma": ("Mukono", "Goma Division")}
scol, dcol = g["subcounty_name_col"], g["district_name_col"]
for name, (dist, subname) in SUBCOUNTY_PLACES.items():
    hit = sub_pts[(sub_pts[dcol].str.title() == dist) & (sub_pts[scol].str.lower() == subname.lower())]
    if len(hit) and (lk["name"] == name).any():
        i = lk.index[lk["name"] == name][0]
        lk.loc[i, ["lat", "lon"]] = [round(hit.geometry.y.iloc[0], 5), round(hit.geometry.x.iloc[0], 5)]
        lk.loc[i, ["coord_source", "note"]] = ["ubos_subcounty_2017", f"placed on UBOS sub-county {subname}"]

# 2b) sub-county rows -> their UBOS sub-county representative point
sub_pts["_k"] = sub_pts[scol].map(lambda x: pkey(re.sub(r"(?i)\b(division|town council|municipality|sub ?county)\b", "", str(x))))
for i, r in lk[lk.get("level").eq("subcounty")].iterrows():
    k = pkey(re.sub(r"(?i)\b(division|town council|municipality)\b", "", r["name"]))
    hit = sub_pts[(sub_pts[dcol].str.title() == str(r["district"]).title()) & (sub_pts["_k"] == k)]
    if len(hit):
        lk.loc[i, ["lat", "lon"]] = [round(hit.geometry.y.mean(), 5), round(hit.geometry.x.mean(), 5)]
        lk.loc[i, ["coord_source", "note"]] = ["ubos_subcounty_2017", f"placed on UBOS sub-county {', '.join(hit[scol].unique())}"]

# 3) spelling variants and new places seen in the listings
ALIASES = {"Bwaise": ["Bwayiise"], "Makindye": ["Makyinde"], "Munyonyo": ["Muyonyoyo"], "Naguru": ["Naguri"],
           "Lungujja": ["Lungunja"], "Kololo": ["Acacia Avenue", "Acacia", "Elizabeth Avenue", "Elizabethavenue"],
           "Kikaaya": ["Bahai", "Bahai Temple"], "Najjanankumbi": ["Najja"]}
for name, al in ALIASES.items():
    i = lk.index[lk["name"] == name]
    if len(i):
        cur = [a for a in str(lk.loc[i[0], "aliases"]).split(";") if a and a != "nan"]
        lk.loc[i[0], "aliases"] = ";".join(dict.fromkeys(cur + al))
NEW = [  # name, aliases, district, division/town, lat, lon (draft; relocated below if a UBOS parish exists)
    ("Namuwongo", "", "Kampala", "Makindye", 0.3050, 32.6060),
    ("Namungoona", "Namugoonaa;Namugoona", "Kampala", "Rubaga", 0.3420, 32.5370),
    ("Lugogo", "", "Kampala", "Nakawa", 0.3290, 32.6010),
    ("Nsasa", "", "Wakiso", "Kira Municipality", 0.4080, 32.6680),
]
for n, al, dist, div, lat, lon in NEW:
    if (lk["name"] == n).any():
        continue
    row = {"name": n, "aliases": al, "district": dist, "division_or_town": div, "lat": lat, "lon": lon,
           "coord_source": "draft_approx", "verified": 0, "level": "neighbourhood", "note": "added from listings"}
    cand = par_pts[(par_pts["_k"] == pkey(n)) & (par_pts["_d"] == dist)]
    if len(cand) and km(lat, lon, cand.geometry.y.mean(), cand.geometry.x.mean()) <= 5:
        row.update(lat=round(cand.geometry.y.mean(), 5), lon=round(cand.geometry.x.mean(), 5),
                   coord_source="ubos_parish_2016", note="added from listings; placed on UBOS parish")
    lk = pd.concat([lk, pd.DataFrame([row])], ignore_index=True)

# status
osm = pd.read_csv(p("data/lookup/lookup_osm_check.csv")).set_index("name")["check"]
lk["check_status"] = np.select(
    [lk["coord_source"].str.startswith("ubos"),
     (lk["name"].map(osm).eq("ok") | lk["coord_source"].eq("osm_nominatim")) & ~lk["note"].str.contains("verify")],
    ["ubos_official", "osm_agrees"], default="needs_review")
lk.to_csv(path, index=False)
print(f"moved to UBOS parish: {moved}; rows now {len(lk)}")
print(lk["check_status"].value_counts().to_string())
print(lk[lk["check_status"] == "needs_review"][["name", "district", "note"]].to_string(index=False, max_colwidth=90))
