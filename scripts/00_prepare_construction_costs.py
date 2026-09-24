"""Replacement construction cost per m2 for Kampala house types, in current prices.

Base: CAHF (2020) "Uganda's Housing Construction and Housing Rental Activities",
Table 10: bill-of-quantities costs for six Kampala typologies at 2019 prices,
converted by CAHF at US$1 = UGX 3,693 (data/external/cahf/). "Construction" is
Level-1 category D: labour + materials + contractor indirect costs. It excludes
land (A), plot infrastructure (B), approvals/fees (C), finance and marketing (E),
developer margin (F) and VAT (G). The full non-land cost (C..G) is kept too, for
sensitivity.

Indexed to the target month with the UBOS Construction Input Price Index
(headline CIPI_ALL) from the cio_pipeline-2 panel (tools/cio_pipeline-2),
base = 2019 average.

Writes data/external/replacement_cost_rates.csv.

  python scripts/00_prepare_construction_costs.py [--target YYYY-MM]
"""
import argparse

import _common  # noqa: F401
import pandas as pd

from gkma.config import p

CAHF_FX = 3693  # UGX per US$ used by CAHF for the 2019 benchmarking
# CAHF Table 10 (US$ per unit, 2019): gross floor area, D total, total excl. land (A) and infrastructure (B)
CAHF = {
    "G1 CAHF 55m2 house (2-bed)":        {"m2": 55, "D": 25092, "non_land": 58596 - 3165 - 8102},
    "G4 5-storey walk-up (40m2 2-bed)":  {"m2": 40, "D": 27675, "non_land": 51710 - 1148 - 1625},
    "G5 8-storey with lifts (40m2)":     {"m2": 40, "D": 31754, "non_land": 59302 - 1068 - 1694},
    "G6 65m2 market bungalow (3-bed)":   {"m2": 65, "D": 28138, "non_land": 65034 - 2729 - 9459},
}
# Finishes (CAHF Table 11, G1): labour 1,433 + materials 6,605 = 8,038 of 20,119
# labour+materials, i.e. 40%. A shell house therefore costs ~60% of a finished one.
SHELL_SHARE = 1 - (1433 + 721 + 514 + 83 + 640 + 780 + 1333 + 2306 + 228) / (4447 + 15672)

ap = argparse.ArgumentParser()
ap.add_argument("--target", help="index target month YYYY-MM (default: latest CIPI month)")
a = ap.parse_args()

panel = pd.read_csv(p("tools/cio_pipeline-2/data/processed/panel_v1.0_filled_sparse.csv"),
                    parse_dates=["date"]).set_index("date")["CIPI_ALL"].dropna()
base = panel["2019"].mean()
target = pd.Timestamp(a.target + "-01") if a.target else panel.index.max()
factor = panel.loc[target] / base
print(f"UBOS CIPI_ALL: 2019 mean {base:.1f} -> {target:%Y-%m} {panel.loc[target]:.1f}, factor {factor:.4f}")

per_m2 = {k: {"D": v["D"] * CAHF_FX / v["m2"], "full": v["non_land"] * CAHF_FX / v["m2"]} for k, v in CAHF.items()}
bung, apt = per_m2["G6 65m2 market bungalow (3-bed)"], per_m2["G4 5-storey walk-up (40m2 2-bed)"]

rows = [
    ("bungalow_standard", bung["D"], bung["full"], "CAHF G6 (65m2 3-bed bungalow, mortgage standard)"),
    ("bungalow_high", bung["D"] * 1.3, bung["full"] * 1.3,
     "CAHF G6 x 1.3 - ASSUMED high-spec premium (no published source); test in sensitivity"),
    ("storeyed", (bung["D"] + apt["D"]) / 2, (bung["full"] + apt["full"]) / 2,
     "Mean of CAHF G6 (bungalow) and G4 (5-storey walk-up) - ASSUMED for 2-3 storey houses"),
    ("apartment", apt["D"], apt["full"], "CAHF G4 (5-storey walk-up, 40m2 units)"),
    ("shell", bung["D"] * SHELL_SHARE, bung["full"] * SHELL_SHARE,
     f"CAHF G6 x {SHELL_SHARE:.2f} (excludes finishes: CAHF Table 11 finishes = {1 - SHELL_SHARE:.0%} of labour+materials)"),
]
out = pd.DataFrame(rows, columns=["cost_class", "rate_2019_ugx_per_m2", "rate_full_2019_ugx_per_m2", "basis"])
out["rate_ugx_per_m2"] = (out["rate_2019_ugx_per_m2"] * factor).round(-3)
out["rate_full_ugx_per_m2"] = (out["rate_full_2019_ugx_per_m2"] * factor).round(-3)
out["rate_2019_ugx_per_m2"] = out["rate_2019_ugx_per_m2"].round(-3)
out["rate_full_2019_ugx_per_m2"] = out["rate_full_2019_ugx_per_m2"].round(-3)
out["year"] = target.strftime("%Y-%m")
out["cipi_factor"] = round(factor, 4)
out["source"] = ("CAHF 2020, Uganda's Housing Construction and Housing Rental Activities, Table 10 (2019 prices, "
                 "US$1=UGX3,693); indexed with UBOS CIPI headline (cio_pipeline-2 panel)")
cols = ["cost_class", "rate_ugx_per_m2", "rate_full_ugx_per_m2", "rate_2019_ugx_per_m2",
        "rate_full_2019_ugx_per_m2", "cipi_factor", "year", "basis", "source"]
out[cols].to_csv(p("data/external/replacement_cost_rates.csv"), index=False)
print(out[["cost_class", "rate_2019_ugx_per_m2", "rate_ugx_per_m2", "rate_full_ugx_per_m2"]].to_string(index=False))
