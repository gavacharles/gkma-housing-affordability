"""Reference layers for publication maps -> data/external/basemap/*.gpkg

  lake.gpkg          Lake Victoria (OSM, via Nominatim) clipped to the map window
  land.gpkg          study-area land: GKMA district polygons minus the lake
  districts.gpkg     district boundaries (dissolved UBOS sub-counties)
  divisions.gpkg     Kampala's five divisions
  roads.gpkg         trunk/primary roads and the two corridors (OSM cache)
  wetlands.gpkg      OSM wetlands, simplified for display
  uganda.gpkg        national outline + districts (UBOS COD-AB 2020) for the locator
  labels.gpkg        reference place labels (main map and Kampala-core inset)

Run once (needs internet for the lake); publication maps read these files.
"""
import _common  # noqa: F401
import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import box

from gkma.config import load_config, p

cfg = load_config()
g = cfg["geography"]
CRS = cfg["project"]["crs_projected"]
out = p("data/external/basemap")
out.mkdir(parents=True, exist_ok=True)
WINDOW = box(32.0, -0.4, 33.3, 0.9)

ox.settings.requests_timeout = 300
lake = ox.geocode_to_gdf("Lake Victoria")[["geometry"]].clip(WINDOW).to_crs(CRS)
lake.to_file(out / "lake.gpkg", driver="GPKG")

sub = gpd.read_file(p(g["subcounties"])).to_crs(CRS)
districts = sub.dissolve(g["district_name_col"]).reset_index()[[g["district_name_col"], "geometry"]]
districts = districts.rename(columns={g["district_name_col"]: "district"})
districts["geometry"] = districts.geometry.difference(lake.union_all()).buffer(0)
districts.to_file(out / "districts.gpkg", driver="GPKG")
land = districts.dissolve()[["geometry"]]
land.to_file(out / "land.gpkg", driver="GPKG")

kla = sub[sub[g["district_name_col"]].str.title() == "Kampala"]
divisions = kla.dissolve(g["subcounty_name_col"]).reset_index()[[g["subcounty_name_col"], "geometry"]]
divisions = divisions.rename(columns={g["subcounty_name_col"]: "division"})
divisions.to_file(out / "divisions.gpkg", driver="GPKG")

roads = gpd.read_file(p("data/external/osm/roads.gpkg")).to_crs(CRS)
roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])]
nm = roads["name"].fillna("").str.lower()
roads["kind"] = "other"
roads.loc[roads["highway"].isin(["trunk", "primary", "motorway"]), "kind"] = "major"
roads.loc[nm.str.contains("northern bypass"), "kind"] = "northern_bypass"
roads.loc[nm.str.contains("entebbe") & nm.str.contains("expressway"), "kind"] = "expressway"
roads = roads[roads["kind"] != "other"][["kind", "name", "geometry"]]
roads["geometry"] = roads.geometry.simplify(15)
roads.to_file(out / "roads.gpkg", driver="GPKG")

wet = gpd.read_file(p("data/external/osm/wetlands.gpkg")).to_crs(CRS)
wet = wet[wet.geom_type.isin(["Polygon", "MultiPolygon"])][["geometry"]]
wet["geometry"] = wet.geometry.simplify(20).buffer(0)
wet[wet.area > 20_000].to_file(out / "wetlands.gpkg", driver="GPKG")

cod = p("data/external/boundaries/uga_admin_boundaries.gdb")
uga = gpd.read_file(cod, layer="uga_admin0")[["geometry"]]
uga_d = gpd.read_file(cod, layer="uga_admin2")[["adm2_name", "geometry"]]
uga.to_file(out / "uganda.gpkg", layer="country", driver="GPKG")
uga_d.to_file(out / "uganda.gpkg", layer="districts", driver="GPKG")

lk = pd.read_csv(p(g["neighbourhood_lookup"])).set_index("name")
MAIN = ["Kampala CBD", "Ntinda", "Muyenga", "Kawempe", "Rubaga", "Nansana", "Kira", "Namugongo", "Mukono Town",
        "Seeta", "Entebbe", "Kajjansi", "Kasangati", "Gayaza", "Wakiso Town", "Kyengera", "Munyonyo", "Matugga",
        "Bweyogerere", "Nsangi"]
CORE = ["Kololo", "Nakasero", "Ntinda", "Bukoto", "Bugolobi", "Muyenga", "Makindye", "Mengo", "Rubaga",
        "Kawempe", "Kisaasi", "Kyanja", "Nakawa", "Luzira", "Ggaba", "Kiwatule", "Najjera"]
rows = []
for level, names in [("main", MAIN), ("core", CORE)]:
    for n in names:
        if n in lk.index:
            r = lk.loc[n]
            label = {"Kampala CBD": "Kampala", "Mukono Town": "Mukono", "Wakiso Town": "Wakiso"}.get(n, n)
            rows.append({"label": label, "level": level, "lat": r["lat"], "lon": r["lon"]})
labels = gpd.GeoDataFrame(rows, geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]),
                          crs="EPSG:4326").to_crs(CRS)
labels.to_file(out / "labels.gpkg", driver="GPKG")
print("basemap layers:", sorted(x.name for x in out.glob("*.gpkg")))
print(f"lake {lake.area.sum() / 1e6:,.0f} km2 in window; land {land.area.sum() / 1e6:,.0f} km2; "
      f"{len(roads)} road segments; {len(labels)} labels")
