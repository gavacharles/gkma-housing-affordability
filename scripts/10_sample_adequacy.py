"""Sample adequacy: is the listing sample large enough for the outputs reported?

  1. Precision curve: bootstrap 95% CI half-width of an area's median rent / price,
     as a share of the median, against the number of listings in the area
     (subsamples drawn from sub-counties that have at least 60 listings).
  2. Convergence: headline index values (GKMA and districts) re-estimated on random
     subsamples of 50-100% of the listings (20 draws each).
  3. Observations per parameter for the hedonic models, and distinct locations.

Outputs
  tables/sample_adequacy_precision.csv, sample_adequacy_convergence.csv, sample_adequacy_summary.json
  maps/S4_precision_curve, S5_convergence
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _stage
from gkma.analysis.affordability_index import bou_lending_rate, compute_index
from gkma.config import load_config, p
from gkma.viz import pubmaps as maps

a, out, pts, units, bg = _stage.setup(__doc__)
T = out / "tables"
cfg = load_config()
ai = cfg.get("affordability_index", {})
m = ai.get("mortgage", {})
base = {"rate": bou_lending_rate() if m.get("rate", "bou") == "bou" else float(m["rate"]),
        "deposit": m.get("deposit", 0.30), "term_years": m.get("term_years", 20), "cap": m.get("cap", 0.35)}
min_n = ai.get("min_listings", 20)
rng = np.random.default_rng(42)

# --- 1. precision curve ------------------------------------------------------------
g = cfg["geography"]
sc = gpd.read_file(p(g["subcounties"])).to_crs(pts.crs)
sc["area"] = sc[g["district_name_col"]].str.title() + "/" + sc[g["subcounty_name_col"]]
tagged = gpd.sjoin(pts, sc[["area", "geometry"]], how="inner", predicate="within")
sets = {"rent (1–2 bedrooms)": tagged[(tagged["listing_type"] == "rent") & tagged["bedrooms"].between(0.5, 2)]
        ["rent_month_ugx"],
        "sale (houses, apartments)": tagged[(tagged["listing_type"] == "sale") &
                                            tagged["ptype"].isin(["house", "apartment"])]["price_ugx"]}
sizes = [5, 10, 15, 20, 30, 50, 75, 100]
rows = []
for market, s in sets.items():
    grp = s.dropna().groupby(tagged.loc[s.index, "area"])
    for area, x in grp:
        x = x.to_numpy()
        if len(x) < 60:
            continue
        for n in sizes:
            if n > len(x):
                continue
            for _ in range(30):
                sub = rng.choice(x, n, replace=False)
                b = np.median(rng.choice(sub, (500, n)), axis=1)
                lo, hi = np.percentile(b, [2.5, 97.5])
                rows.append({"market": market, "area": area, "n": n, "half_width": (hi - lo) / 2 / np.median(sub)})
prec = pd.DataFrame(rows)
curve = prec.groupby(["market", "n"])["half_width"].agg(["median", lambda v: v.quantile(0.25),
                                                          lambda v: v.quantile(0.75)])
curve.columns = ["median", "q25", "q75"]
curve = curve.reset_index()
curve.round(4).to_csv(T / "sample_adequacy_precision.csv", index=False)
print(curve.round(3).to_string(index=False))

fig, ax = plt.subplots(figsize=(maps.SINGLE * 1.25, maps.SINGLE * 0.9))
for (market, d), col in zip(curve.groupby("market"), [maps.BLUE[4], maps.RED[4]]):
    ax.plot(d["n"], 100 * d["median"], marker="o", ms=3, lw=1, color=col, label=market)
    ax.fill_between(d["n"], 100 * d["q25"], 100 * d["q75"], color=col, alpha=0.15, lw=0)
ax.axvline(min_n, color="#333333", lw=0.7, ls=(0, (3, 2)))
ax.text(min_n, ax.get_ylim()[1] * 0.95, f" threshold ({min_n})", fontsize=5.5, va="top")
ax.set_xlabel("Listings in the area")
ax.set_ylabel("95% CI half-width of the median\n(% of the median)")
ax.legend(frameon=False, fontsize=5.8)
ax.spines[["top", "right"]].set_visible(False)
maps._save(fig, "S4_precision_curve", title="Precision of area medians by number of listings",
           note=f"Subsamples from sub-counties with at least 60 listings; 30 draws × 500 bootstrap resamples per size. "
                "Line: median; band: interquartile range across draws and sub-counties.",
           sources="Listings.")

# --- 2. convergence ------------------------------------------------------------------
fracs = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
rows = []
for f in fracs:
    for draw in range(1 if f == 1.0 else 20):
        sub = pts if f == 1.0 else pts.sample(frac=f, random_state=int(rng.integers(1e9)))
        for level in ("gkma", "district"):
            r = compute_index(sub, level, base, min_n=min_n)
            r["frac"], r["draw"], r["n_listings"] = f, draw, len(sub)
            rows.append(r)
conv = pd.concat(rows)
conv = conv[conv["area"].isin(["GKMA", "Kampala", "Wakiso", "Mukono"])]
cs = conv.groupby(["area", "frac"])[["n_listings", "rai", "oai", "agi_rent"]].agg(["mean", "std"])
cs.columns = ["_".join(c) for c in cs.columns]
cs = cs.reset_index()
cs.round(4).to_csv(T / "sample_adequacy_convergence.csv", index=False)
print(cs.round(3).to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(maps.FULL, maps.FULL * 0.3))
cols = {"GKMA": "#000000", "Kampala": maps.OKABE_ITO[0], "Wakiso": maps.OKABE_ITO[1], "Mukono": maps.OKABE_ITO[2]}
for ax, (k, lab) in zip(axes, [("rai", "Rental Affordability Index"), ("oai", "Ownership Affordability Index")]):
    for area, d in cs.groupby("area"):
        ax.errorbar(d["n_listings_mean"], d[f"{k}_mean"], yerr=1.96 * d[f"{k}_std"].fillna(0), marker="o", ms=2.5,
                    lw=0.9, capsize=1.5, color=cols[area], label=area)
    ax.set_xlabel("Listings used (random subsample)")
    ax.set_ylabel(lab)
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].legend(frameon=False, fontsize=5.8, ncol=2)
fig.tight_layout()
maps._save(fig, "S5_convergence", title="Stability of the affordability index as the sample grows",
           note="Points: mean over 20 random subsamples of 50–90% of listings (full sample at right); "
                "whiskers: ±1.96 s.d. across subsamples.", sources="Listings; modelled incomes; BoU lending rates.")

# --- 3. summary ----------------------------------------------------------------------
import json  # noqa: E402
hs = json.load(open(T / "hedonic_summary.json"))
k = {}
for market in ("rent", "sale"):
    try:
        k[market] = len(pd.read_csv(T / f"hedonic_{market}.csv"))
    except Exception:  # noqa: BLE001
        k[market] = None
full = conv[conv["frac"] == 1.0].set_index("area")
half = cs[cs["frac"] == 0.5].set_index("area")
summary = {
    "n_listings": len(pts),
    "distinct_locations": int(pts.geometry.to_wkt().nunique()),
    "hedonic": {mk: {"n": hs[mk]["n"], "parameters": k[mk],
                     "obs_per_parameter": round(hs[mk]["n"] / k[mk], 1) if k[mk] else None} for mk in ("rent", "sale")},
    "precision_at": {mk: {int(n): round(float(v), 3) for n, v in d.set_index("n")["median"].items()}
                     for mk, d in curve.groupby("market")},
    "convergence_max_abs_change_50pct_to_full": {
        a_: {kk: round(float(abs(half.loc[a_, f"{kk}_mean"] - full.loc[a_, kk])), 3) for kk in ("rai", "oai")}
        for a_ in full.index},
}
_stage.save_json(summary, T / "sample_adequacy_summary.json")
print(json.dumps(summary, indent=1, default=str))
