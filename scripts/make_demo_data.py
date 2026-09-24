"""Generate a SYNTHETIC demo dataset to test the full workflow end to end.

!!! Nothing produced from demo/ may be used in the paper. !!!
Prices follow a made-up surface with known effects (so we can check the
models recover them): distance decay from the CBD, an elite-area premium,
a title premium of +18 % (houses) and tenure premia on land, and a bedroom
effect that grows eastwards (for GWR to find). Raw text is deliberately
messy (USD prices, '50x100' plots, re-posts) so the cleaning code is
exercised too. Income and construction-cost tables are placeholders.

Usage:
  python scripts/make_demo_data.py
  export GKMA_CONFIG=demo/config_demo.yaml
  python scripts/02_clean.py --out demo/processed
  python scripts/03_spatial_patterns.py --data demo/processed --out demo/outputs   (etc.)
"""
import _common  # noqa: F401
import numpy as np
import pandas as pd
import yaml

from gkma.collect.base import to_frame

ROOT = _common.ROOT
DEMO = ROOT / "demo"
rng = np.random.default_rng(7)

lk = pd.read_csv(ROOT / "data/lookup/neighbourhood_lookup.csv")
lk = lk[lk["district"].isin(["Kampala", "Wakiso", "Mukono"])].reset_index(drop=True)
CBD = (0.3136, 32.5825)
ELITE = {"Kololo", "Nakasero", "Muyenga", "Bugolobi", "Naguru", "Munyonyo", "Lubowa", "Mbuya", "Buziga", "Kansanga"}
dist = 111 * np.hypot(lk["lat"] - CBD[0], (lk["lon"] - CBD[1]) * np.cos(np.radians(0.3)))
lk["dist"], lk["elite"] = dist, lk["name"].isin(ELITE).astype(float)
# popularity: more listings in popular suburbs
w = np.exp(-dist / 12) + 0.3 * lk["elite"] + 0.05
w = w / w.sum()

FEATS = ["self contained", "boys quarters", "gated estate", "tarmac road", "parking", "security"]
N = 3200
rows = []
for i in range(N):
    j = rng.choice(len(lk), p=w)
    place = lk.iloc[j]
    east = (place["lon"] - 32.58) * 10  # -3..+3
    kind = rng.choice(["rent", "sale", "land"], p=[0.5, 0.33, 0.17])
    feats = [f for f in FEATS if rng.random() < 0.35 + 0.25 * place["elite"]]
    beds = int(np.clip(rng.poisson(1.3 + 1.2 * place["elite"]) + 1, 1, 7))
    lat = place["lat"] + rng.normal(0, 0.006)
    lon = place["lon"] + rng.normal(0, 0.006)
    coords = rng.random() < 0.6  # 60 % carry portal coordinates, rest use the gazetteer
    loc_eff = -0.035 * place["dist"] + 0.55 * place["elite"]
    tenure_txt, title = "", ""
    if kind == "rent":
        y = 12.55 + (0.30 + 0.05 * east) * beds + loc_eff + 0.15 * ("self contained" in feats) \
            + 0.2 * ("gated estate" in feats) + rng.normal(0, 0.3)
        price = np.exp(y)
        ptype = rng.choice(["house", "apartment"], p=[0.6, 0.4])
        title = f"{beds} bedroom {ptype} for rent in {place['name']}"
        pstr = (f"USD {price / 3700:,.0f} per month" if rng.random() < 0.08 else f"UGX {price:,.0f} per month")
        plot = ""
    elif kind == "sale":
        titled = rng.random() < 0.7
        tenure_txt = rng.choice(["mailo land with ready title", "freehold title", "private mailo"]) if titled \
            else "on kibanja, sale agreement"
        dec = rng.choice([8, 10, 12, 15, 20, 25, 50])
        y = 18.4 + (0.28 + 0.04 * east) * beds + 0.25 * np.log(dec) + 1.3 * loc_eff \
            + np.log(1.18) * titled + 0.2 * ("gated estate" in feats) + rng.normal(0, 0.35)
        price = np.exp(y)
        ptype = rng.choice(["house", "bungalow", "storeyed house"], p=[0.5, 0.3, 0.2])
        title = f"{beds} bedroom {ptype} for sale in {place['name']}"
        pstr = f"$ {price / 3700:,.0f}" if rng.random() < 0.1 else f"Ugx {price:,.0f}/="
        plot = f"{dec} decimals" if rng.random() < 0.6 else ("50x100 ft" if dec == 12 else f"{dec} decimals")
        feats.append(tenure_txt)
    else:
        ten = rng.choice(["mailo", "freehold", "leasehold", "kibanja"], p=[0.45, 0.2, 0.1, 0.25])
        prem = {"mailo": 0.15, "freehold": 0.25, "leasehold": 0.10, "kibanja": 0.0}[ten]
        dec = rng.choice([10, 12, 25, 50, 100])
        ppd = np.exp(16.9 + 1.4 * loc_eff + prem + rng.normal(0, 0.35))
        price = ppd * dec
        title = f"Plot of land for sale in {place['name']}"
        pstr = f"UGX {price:,.0f}"
        plot = {10: "10 decimals", 12: "50 by 100", 25: "quarter acre", 50: "half an acre", 100: "1 acre"}[dec]
        tenure_txt = {"kibanja": "kibanja", "mailo": "mailo title", "freehold": "freehold", "leasehold": "49 years lease"}[ten]
        feats = [tenure_txt]
        ptype, beds = "land", None
    desc = f"{title}. {', '.join(feats)}. {plot}. {'Negotiable.' if rng.random() < 0.3 else ''}"
    rec = {
        "source": "demo", "source_id": f"d{i}", "url": "", "scraped_at": "2026-10-15T00:00:00+00:00",
        "listing_date": str(pd.Timestamp("2026-10-01") + pd.Timedelta(days=int(rng.integers(0, 90))))[:10],
        "listing_type": "rent" if kind == "rent" else "sale", "property_type": ptype, "title": title,
        "description": desc, "price_raw": pstr, "currency_raw": None, "price_period": None,
        "location_raw": place["name"], "district_raw": place["district"], "bedrooms_raw": beds,
        "size_raw": plot, "agent_key": f"a{rng.integers(0, 400)}",
        "lat": lat if coords else None, "lon": lon if coords else None,
    }
    rows.append(rec)
    if rng.random() < 0.12:  # re-post of the same unit
        rows.append({**rec, "source_id": f"d{i}r", "title": rec["title"] + "!", "lat": rec["lat"], "lon": rec["lon"]})

(DEMO / "raw" / "demo").mkdir(parents=True, exist_ok=True)
to_frame(rows).to_csv(DEMO / "raw" / "demo" / "demo_listings.csv", index=False)

ext = DEMO / "external"
ext.mkdir(exist_ok=True)
pd.DataFrame({  # PLACEHOLDER numbers — replace with UNHS / Census 2024 values
    "unit": ["Kampala", "Wakiso", "Mukono"],
    "median_monthly_income_ugx": [1_100_000, 900_000, 650_000],
    "households": [500_000, 900_000, 250_000],
    "gini": [0.42, 0.40, 0.38],
    "survey_median_rent_ugx": [250_000, 180_000, 120_000],
}).to_csv(ext / "income_SYNTHETIC.csv", index=False)
pd.DataFrame({  # PLACEHOLDER rates — replace with your QS replacement-cost rates
    "cost_class": ["bungalow_standard", "bungalow_high", "storeyed", "apartment", "shell"],
    "rate_ugx_per_m2": [1_500_000, 2_200_000, 2_400_000, 2_000_000, 800_000],
    "year": 2026, "source": "SYNTHETIC placeholder",
}).to_csv(ext / "rates_SYNTHETIC.csv", index=False)

cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
cfg["project"]["raw_dir"] = "demo/raw"
cfg["income"]["table"] = "demo/external/income_SYNTHETIC.csv"
cfg["construction"]["table"] = "demo/external/rates_SYNTHETIC.csv"
(DEMO / "config_demo.yaml").write_text("# SYNTHETIC DEMO CONFIG - do not use for the paper\n" + yaml.safe_dump(cfg, sort_keys=False))
print(f"wrote {len(rows)} synthetic raw rows to {DEMO}")
