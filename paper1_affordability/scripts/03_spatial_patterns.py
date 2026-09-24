"""Stage 1 — RQ1: how are prices/rents distributed and where do they cluster?

Outputs: study area map, median choropleths (rent/bedroom, sale price,
land price per decimal), LISA cluster maps, Moran's I table.
"""
import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import _stage
import geopandas as gpd
from gkma.analysis.spatial_stats import moran_lisa, unit_medians
from gkma.config import load_config
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
k = load_config()["geography"]["min_listings_per_unit"]
maps.study_area(bg, pts)

measures = [
    ("rent", "rent_month_ugx", "Median monthly asking rent (UGX)", "02_median_rent"),
    ("rent", "rent_per_bedroom", "Median monthly rent per bedroom (UGX)", "03_median_rent_per_bedroom"),
    ("sale", "price_ugx", "Median asking sale price, houses and apartments (UGX)", "04_median_sale_price"),
    ("sale", "price_per_bedroom", "Median asking price per bedroom (UGX)", "05_median_price_per_bedroom"),
    ("land", "price_per_decimal", "Median asking price per decimal, land listings (UGX)", "06_median_land_per_decimal"),
]
morans, panel_specs = [], []
for market, col, title, name in measures:
    sub = pts[pts["ptype"] == "land"] if market == "land" else \
        pts[(pts["listing_type"] == market) & (pts["ptype"] != "land")]
    med = unit_medians(sub, bg, col, unit_col="analysis_unit", min_n=k)
    med.drop(columns="geometry").to_csv(out / "tables" / f"{name}.csv", index=False)
    if col in ("rent_per_bedroom", "price_per_bedroom", "price_per_decimal", "rent_month_ugx"):
        panel_specs.append({"gdf": med, "col": "median", "subtitle": title.replace(" (UGX)", ""),
                            "legend_title": "UGX (quintiles)", "cmap": maps.SEQ_BLUE})
    maps.choropleth(med, "median", title, name, legend_title="UGX (quintiles)",
                    note=f"Grey: fewer than {k} listings. Asking prices, deduplicated.")
    # primary test: neighbourhood points (the resolution at which listings are located)
    pt = sub.dropna(subset=[col]).assign(_k=lambda d: d.geometry.to_wkt())
    pm = pt.groupby("_k").agg(median=(col, "median"), n=(col, "size"), geometry=("geometry", "first"))
    pm = gpd.GeoDataFrame(pm[pm["n"] >= 5].reset_index(drop=True), geometry="geometry", crs=pts.crs)
    if len(pm) >= 20:
        s_pt, _ = moran_lisa(pm, "median", kind="knn")
        morans.append({**s_pt, "measure": col, "level": "neighbourhood points (n>=5), KNN k=6"})
    if med["median"].notna().sum() >= 10:
        summ, lisa = moran_lisa(med, "median")
        summ["measure"] = col
        summ["level"] = f"sub-counties (n>={k}), queen"
        morans.append(summ)
        maps.lisa_map(lisa, f"Clusters: {title[0].lower() + title[1:]}", f"{name}_lisa", all_units=bg,
                      note=f"Moran's I = {summ['moran_I']:.3f} (pseudo p = {summ['p_sim']:.3f}, 999 permutations).")
import pandas as pd
order = ["rent", "rent per bedroom", "price per bedroom", "per decimal"]
panel_specs.sort(key=lambda s: [o in s["subtitle"].lower() for o in order].index(True) if any(o in s["subtitle"].lower() for o in order) else 9)
maps.panels(panel_specs, "02_price_rent_overview", title="Asking rents and prices across GKMA parishes",
            note=f"Medians by parish (sub-county where a parish has fewer than {k} listings); quintile classes per panel.")
pd.DataFrame(morans).to_csv(out / "tables" / "morans_i.csv", index=False)
print(pd.DataFrame(morans).round(3).to_string())
