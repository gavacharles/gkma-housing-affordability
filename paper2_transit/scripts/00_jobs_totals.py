"""Employment totals for GKMA units from the UBOS Censuses of Business Establishments.

COBE 2019/20 publishes employment only by sub-region: Kampala 896,732 and Buganda
(the Central region excluding Kampala) 794,046 employees (Table 3.5.3). COBE 2010/11
gives employment by Kampala division and by district (Appendix 1). The 2019/20 totals
are split in proportion to the 2010/11 shares: Kampala's divisions within the Kampala
total, and each GKMA district within the Buganda total. The Buganda totals match across
the two censuses (2010/11: 271,204 - 133,663 = 137,541 businesses outside Kampala in
the Central region, as reported for Buganda in COBE 2019/20 Table 3.3).

Assumption: each unit's share of its sub-region's employment is unchanged since 2010/11.
Covers businesses with a fixed location; government administration and defence are
excluded by the census, and mobile or home-based work is not counted.

  python paper2_transit/scripts/00_jobs_totals.py  ->  data/external/ubos/cobe/cobe_employment_gkma.csv
"""
import pandas as pd

import _paper  # noqa: F401
from gkma.config import p

TOTAL_2019_20 = {"Kampala": 896_732, "Buganda": 794_046}          # COBE 2019/20, Table 3.5.3
KAMPALA_2010 = {"Central": 181_115, "Rubaga": 52_740, "Makindye": 52_026, "Kawempe": 40_896,
                "Nakawa": 51_988, "Makerere University": 492}      # COBE 2010/11, Appendix 1.a
KAMPALA_2010_TOTAL = 379_257
CENTRAL_2010_TOTAL, KAMPALA_IN_CENTRAL_2010 = 660_626, 379_257     # COBE 2010/11, Appendix 1.1b
GKMA_DISTRICTS_2010 = {"Wakiso": 108_964, "Mukono": 25_640, "Buikwe": 23_478, "Luwero": 13_889, "Mpigi": 9_576}
BUGANDA_2010 = CENTRAL_2010_TOTAL - KAMPALA_IN_CENTRAL_2010

rows = []
for div, n in KAMPALA_2010.items():
    if div == "Makerere University":                               # campus: allocate to Kawempe division
        continue
    n_ = n + (KAMPALA_2010["Makerere University"] if div == "Kawempe" else 0)
    rows.append({"district": "Kampala", "unit": f"{'Rubaga' if div == 'Rubaga' else div} Division",
                 "jobs_2010_11": n_, "share": n_ / KAMPALA_2010_TOTAL,
                 "jobs_2019_20": round(TOTAL_2019_20["Kampala"] * n_ / KAMPALA_2010_TOTAL)})
for dist, n in GKMA_DISTRICTS_2010.items():
    rows.append({"district": dist, "unit": dist, "jobs_2010_11": n, "share": n / BUGANDA_2010,
                 "jobs_2019_20": round(TOTAL_2019_20["Buganda"] * n / BUGANDA_2010)})
out = pd.DataFrame(rows)
dest = p("data/external/ubos/cobe/cobe_employment_gkma.csv")
out.round(4).to_csv(dest, index=False)
print(out.to_string(index=False))
print("GKMA total 2019/20 (estimated):", f"{out['jobs_2019_20'].sum():,}")
