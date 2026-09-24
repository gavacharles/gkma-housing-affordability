"""Check data/lookup/neighbourhood_lookup.csv against OpenStreetMap and UBOS parishes.

Writes data/lookup/lookup_osm_check.csv and data/lookup/lookup_parish_check.csv.
Rows flagged in either file need a human decision: correct lat/lon, then set verified=1.
"""
import _common  # noqa: F401
from gkma.geo.gazetteer import check_against_parishes, verify_lookup_against_osm

osm = verify_lookup_against_osm()
osm.to_csv(_common.ROOT / "data/lookup/lookup_osm_check.csv", index=False)
print(osm["check"].value_counts().to_string())
par = check_against_parishes()
par.to_csv(_common.ROOT / "data/lookup/lookup_parish_check.csv", index=False)
print(f"\n{len(par)} names whose point lies outside the UBOS parish of the same name:")
print(par.to_string(index=False))
