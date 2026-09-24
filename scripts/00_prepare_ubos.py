"""Tidy UBOS tables used for time adjustment and validation.

UBOS Residential Property Price Index (RPPI), quarterly, 2015/16 Q4 = 100,
from data/external/ubos/07_2026RPPI_Tables_Q4_2025-26.xlsx (harvested by
tools/cio_pipeline-2). Areas: Wakiso, Kampala Central & Makindye, Nakawa,
Kawempe & Rubaga, Headline. Fiscal-year quarters: Q1 = Jul-Sep.

Writes data/external/ubos_rppi_quarterly.csv (long format). Uses:
  * validation: compare a hedonic quarterly index from the listings with the RPPI
  * robustness: deflate sale prices to a common quarter within the window
"""
import _common  # noqa: F401
import pandas as pd

from gkma.config import p

raw = pd.read_excel(p("data/external/ubos/07_2026RPPI_Tables_Q4_2025-26.xlsx"), header=None)
areas = ["Wakiso", "Kampala Central & Makindye", "Nakawa", "Kawempe & Rubaga", "Headline"]
t = raw.iloc[3:, [0, 1, 2, 3, 4, 5, 6]].copy()
t.columns = ["fy", "quarter"] + areas
t["fy"] = t["fy"].ffill()
t = t.dropna(subset=["quarter"])
start_year = t["fy"].str[:4].astype(int)
q = t["quarter"].str[1].astype(int)
t["period_start"] = pd.to_datetime(dict(year=start_year + (q >= 3), month=((q - 1) * 3 + 7 - 1) % 12 + 1, day=1))
long = t.melt(id_vars=["fy", "quarter", "period_start"], value_vars=areas, var_name="area", value_name="rppi")
long["rppi"] = pd.to_numeric(long["rppi"]).round(3)
long.to_csv(p("data/external/ubos_rppi_quarterly.csv"), index=False)
w = long.pivot(index="period_start", columns="area", values="rppi")
print(w.tail(6).round(1).to_string())
print("year-on-year to 2025/26 Q4:", (w.iloc[-1] / w.iloc[-5] - 1).mul(100).round(1).to_dict())
