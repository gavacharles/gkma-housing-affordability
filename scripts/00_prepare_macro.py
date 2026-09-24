"""Build exchange-rate and CPI inputs from the MoFPED Macro Data Portal download.

First refresh the download (your repo, cloned into tools/):
  Rscript tools/mofped-macrodata-api-downloader/download_all_macrodata.R data/external/mofped
Then:
  python scripts/00_prepare_macro.py [--target YYYY-MM]

Writes
  data/external/bou_usd_ugx_monthly.csv   month, usd_ugx (BoU period-average rate E_PA,
                                          falling back to the interbank mid-rate E_IFEM_MR)
  data/external/cpi_uplift.csv            headline CPI ratio target / UNHS 2019/20 fieldwork
and fills the cpi_uplift column of data/external/unhs_income_by_unit.csv.

UNHS 2019/20 fieldwork ran from September 2019 to November 2020 (interrupted by
COVID-19), so the base is the mean headline CPI over those months. The target
defaults to the latest month available; for the paper, set it to the middle of the
listing collection window.
"""
import argparse

import _common  # noqa: F401
import pandas as pd

from gkma.config import load_config, p

ap = argparse.ArgumentParser()
ap.add_argument("--target", help="CPI target month YYYY-MM (default: latest available)")
a = ap.parse_args()

src = p("data/external/mofped/datasets")
fx = pd.read_csv(src / "BOU_E_M.csv", parse_dates=["Date"])
fx["month"] = fx["Date"].dt.strftime("%Y-%m")
fx["usd_ugx"] = fx["E_PA"].fillna(fx["E_IFEM_MR"])
fx = fx.dropna(subset=["usd_ugx"])[["month", "usd_ugx", "E_IFEM_MR", "E_OFF_MR", "E_EP"]]
fx.to_csv(p("data/external/bou_usd_ugx_monthly.csv"), index=False)
print(f"FX: {len(fx)} months, {fx.month.iloc[0]} to {fx.month.iloc[-1]}; "
      f"latest period-average rate {fx.usd_ugx.iloc[-1]:,.1f} UGX/USD")

cpi = pd.read_csv(src / "BOU_CPI.csv", parse_dates=["Date"]).set_index("Date")
head = cpi["CPI_16"].dropna()                     # headline CPI, 2016/17 = 100
housing = cpi["CPI_HWEGF_16"].dropna()            # housing, water, electricity, gas & fuels
base_window = slice("2019-09-01", "2020-11-30")
target = pd.Timestamp(a.target + "-01") if a.target else head.index.max()
rows = []
for name, s in [("headline", head), ("housing_water_energy", housing)]:
    base = s[base_window].mean()
    rows.append({"series": name, "base_period": "2019-09..2020-11 (UNHS fieldwork)",
                 "base_value": base, "target_month": target.strftime("%Y-%m"),
                 "target_value": s.loc[target], "uplift": s.loc[target] / base})
up = pd.DataFrame(rows)
up.to_csv(p("data/external/cpi_uplift.csv"), index=False)
print(up.round(4).to_string(index=False))

inc_path = p(load_config()["income"]["table"])
inc = pd.read_csv(inc_path)
inc["cpi_uplift"] = round(float(up.loc[up.series == "headline", "uplift"].iloc[0]), 4)
inc.to_csv(inc_path, index=False)
print(f"cpi_uplift = {inc.cpi_uplift.iloc[0]} written to {inc_path.name} (headline CPI)")
