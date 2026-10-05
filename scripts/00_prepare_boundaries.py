"""Parish and sub-county layers for the six GKMA districts -> data/external/boundaries/*.gpkg

Source: UBOS, "Uganda administrative boundaries as of 17-08-2018" (parishes 2016,
sub-counties 2017), HDX, CC0:
https://data.humdata.org/dataset/uganda-administrative-boundaries-as-of-17-08-2018
Unzip the shapefiles to data/external/boundaries/ubos_2018/ first.

  uga_admin4_parishes.gpkg      553 parishes (PName2016, SName2016, DName2016)
  uga_admin3_subcounties.gpkg   80 sub-counties/divisions (Koome is dropped at analysis time)

Names are title-cased, as in every output table (e.g. "Wakiso/Gombe Division").
"""
import _common  # noqa: F401  (adds src/ to the path)
import geopandas as gpd

from gkma.config import load_config, p

cfg = load_config()
g = cfg["geography"]
SRC = p("data/external/boundaries/ubos_2018/UGANDA BOUNDARIES SHAPEFILES AS OF 17 08 2018")
DISTRICTS = [d.upper() for d in g["gkma_districts"] + g["gkma_fringe_districts"]]
COLS = [g["district_name_col"], g["subcounty_name_col"]]

for name, shp, cols in [("parishes", "PARISHES_2016_UTM_36N.shp", COLS + [g["parish_name_col"]]),
                        ("subcounties", "SUBCOUNTIES_2017_UTM_36N.shp", COLS)]:
    gdf = gpd.read_file(SRC / shp)
    gdf = gdf[gdf[g["district_name_col"]].str.upper().isin(DISTRICTS)][cols + ["geometry"]].copy()
    for c in cols:
        gdf[c] = gdf[c].str.strip().str.title()
    if name == "subcounties":                         # sub-counties come in several parts; parishes stay as published
        gdf = gdf.dissolve(cols).reset_index()
    gdf = gdf.to_crs(cfg["project"]["crs_projected"])
    gdf["geometry"] = gdf.geometry.buffer(0)
    out = p(g[name])
    gdf.to_file(out, driver="GPKG")
    print(name, len(gdf), "->", out)
