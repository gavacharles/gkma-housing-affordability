"""Supplementary Materials (Figures S1-S5, Tables S1-S5) from the outputs.

  python paper1_affordability/scripts/build_supplement.py  ->  docs/manuscript/supplementary.md
"""
import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "paper1_affordability/outputs/tables"
OUT = ROOT / "paper1_affordability/docs/manuscript/supplementary.md"
AREAS = ["GKMA", "Kampala", "Wakiso", "Mukono"]


def md(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False))


parts = ["# Supplementary Materials\n",
         "*Priced out of the formal market: A housing affordability index for Greater Kampala, Uganda, "
         "from online listings and spatial machine learning*\n"]

figs = [("S1_listings_parish", "Figure S1. Listings located in each parish (1–2 bedroom rentals and house/apartment "
                               "sales). Listings are geocoded to neighbourhoods, so parish assignment is only as "
                               "precise as the neighbourhood point."),
        ("S2_rai_parish", "Figure S2. Rental Affordability Index by parish, for parishes with at least 20 rental "
                          "listings (indicative; the sub-county maps are the primary results)."),
        ("S3_oai_parish", "Figure S3. Ownership Affordability Index by parish, for parishes with at least 20 sale "
                          "listings (indicative)."),
        ("S4_precision_curve", "Figure S4. Precision of area medians by number of listings: 95% bootstrap interval "
                               "half-width as a share of the median, from subsamples of sub-counties with at least "
                               "60 listings (30 draws × 500 resamples per size)."),
        ("S5_convergence", "Figure S5. Stability of the affordability index as the sample grows: mean over 20 random "
                           "subsamples of 50–90% of listings, with ±1.96 s.d.")]
for f, cap in figs:
    parts.append(f"![{cap}](../../outputs/maps/{f}.png)\n")

# S1 mortgage sensitivity
s = pd.read_csv(T / "affordability_index_sensitivity.csv")
pv = s.pivot_table(index="area", columns="scenario", values="oai").loc[AREAS]
names = {"base": "Base", "rate_16": "Rate 16%", "rate_22": "Rate 22%", "deposit_20": "Deposit 20%",
         "deposit_50": "Deposit 50%", "term_15": "15 years", "term_25": "25 years", "cap_30": "Cap 30%"}
pv = pv[list(names)].rename(columns=names).round(1).reset_index().rename(columns={"area": "Area"})
parts.append("**Table S1. Ownership Affordability Index under alternative mortgage terms.** Base: BoU 12-month "
             "mean lending rate (18.3%), 30% deposit, 20 years, 35% repayment cap; each column changes one term.\n\n"
             + md(pv) + "\n")

# S2 robustness
r = pd.read_csv(T / "robustness.csv", index_col=0)
lab = {"full": "Full sample", "neighbourhood_only": "Neighbourhood-level locations only", "drop_jiji": "Without Jiji",
       "drop_red": "Without RED", "drop_upc": "Without Uganda Property Centre"}
rows = []
for v, name in lab.items():
    x = r.loc[v]
    f = lambda k: f"{x[k]:.3f}" + ("*" if x.get(k + ':p', 1) < 0.05 else "") if pd.notna(x.get(k)) else "—"  # noqa
    rows.append([name, f"{int(x['n']):,}", f"{x['GKMA:rai']:.1f}", f"{x['GKMA:oai']:.1f}",
                 f("sale:wealth_index"), f("sale:np.log(plot_decimals)"),
                 f('sale:C(title_status, Treatment("unknown"))[T.titled]'),
                 f("sale:np.log1p(dist_entebbe_expressway_km)"), f("rent:np.log1p(dist_cbd_km)")])
cols = ["Sample", "Listings", "GKMA RAI", "GKMA OAI", "Wealth (sale)", "ln plot size (sale)", "Title stated (sale)",
        "ln dist. Expressway (sale)", "ln dist. CBD (rent)"]
parts.append("**Table S2. Robustness of key results to the sample.** Hedonic coefficients; * p < 0.05.\n\n"
             + md(pd.DataFrame(rows, columns=cols)) + "\n")

# S3 RPPI validation
v = pd.read_csv(T / "validation_listing_index_vs_rppi.csv")
v = v[["area", "qstart", "n", "listing_index", "rppi_rebased"]].rename(columns={
    "area": "Area", "qstart": "Quarter start", "n": "Listings", "listing_index": "Listing index",
    "rppi_rebased": "UBOS RPPI (rebased)"}).round(1).fillna("—")
parts.append("**Table S3. Listing-based hedonic index and the UBOS Residential Property Price Index.** Reported "
             "for completeness; most quarters rest on fewer than 20 listings and are not interpreted.\n\n"
             + md(v) + "\n")

# S4 burden gradient
g = pd.read_csv(T / "affordability_burden_gradient.csv")
g = g[g["burden"].isin([0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8])]
w = g.pivot_table(index="burden", columns="area", values="agi_rent")[AREAS].mul(100).round(1)
w.columns = [f"{c}: rent" for c in w.columns]
w2 = g.pivot_table(index="burden", columns="area", values="agi_own")[AREAS].mul(100).round(1)
w2.columns = [f"{c}: own" for c in w2.columns]
w = w.join(w2).reset_index()
w["burden"] = (w["burden"] * 100).round().astype(int).astype(str) + "%"
w = w.rename(columns={"burden": "Burden threshold"})
parts.append("**Table S4. Share of households priced out (%) across burden thresholds of 10–80% of income.**\n\n"
             + md(w) + "\n")

# S5 cleaning log
c = pd.read_csv(ROOT / "data/processed/cleaning_log.csv")[["step", "n"]]
c.columns = ["Step", "Records"]
parts.append("**Table S5. Cleaning log.** Location methods among resolved records: gazetteer exact 8,393; "
             "gazetteer contained name 2,568; district-level label 467; OpenStreetMap 342; sub-county 264; "
             "fuzzy 219; UBOS parish name 58.\n\n" + md(c) + "\n")

OUT.write_text("\n".join(parts), encoding="utf-8")
print("wrote", OUT.relative_to(ROOT))
