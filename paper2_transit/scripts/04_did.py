"""Before-after (difference-in-differences) estimate of the Entebbe Expressway premium (paper 2).

RED listings only, for comparability: archived 2017 (before the June 2018 opening), archived
2020 when available, and current 2025-26. Neighbourhood points present before and after;
point fixed effects absorb each area's fixed level (including the Entebbe Road corridor's),
period effects absorb city-wide change. Treatment: within 15 minutes of an Expressway access
point (and, as a continuous alternative, log travel time to it).

Inference: standard errors clustered by point, plus a wild cluster bootstrap (null imposed,
Webb six-point weights, 1,999 draws), recommended when few clusters are treated.

  python paper2_transit/scripts/04_did.py -> paper2_transit/outputs/tables/did_results.csv
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import patsy

import _paper  # noqa: F401
from gkma.config import p

rng = np.random.default_rng(42)
WEBB = np.array([-np.sqrt(1.5), -1, -np.sqrt(.5), np.sqrt(.5), 1, np.sqrt(1.5)])
COLS = ["listing_type", "ptype", "bedrooms", "bathrooms", "f_furnished", "rent_month_ugx", "price_ugx", "geometry"]

frames = []
for period, f in [("2017", "listings_archive_2017.gpkg"), ("2020", "listings_archive_2020.gpkg"),
                  ("2025", "listings.gpkg")]:
    path = p("data/processed") / f
    if not path.exists():
        continue
    g = gpd.read_file(path)
    if period == "2025":
        g = g[g["source"] == "red"]
    g = g[COLS].assign(period=period)
    frames.append(g)
d = pd.concat(frames, ignore_index=True)
d["pt"] = d.geometry.to_wkt()
A = pd.read_csv(_paper.OUT / "tables" / "neighbourhood_accessibility.csv")[["pt", "tt_expressway_min", "tt_cbd_min"]]
d = d.merge(A, on="pt", how="inner")
pre = set(d.loc[d["period"] == "2017", "pt"])
post = set(d.loc[d["period"] != "2017", "pt"])
d = d[d["pt"].isin(pre & post) & (d["ptype"] != "land")].copy()
d["near"] = (d["tt_expressway_min"] <= 15).astype(float)
d["ln_texp"] = np.log1p(d["tt_expressway_min"])
periods = sorted(d["period"].unique())
posts = [q for q in periods if q != "2017"]
for q in posts:
    d[f"p{q}"] = (d["period"] == q).astype(float)

CTRL = {"rent": "bedrooms + I(bedrooms**2) + bathrooms + f_furnished + C(ptype)",
        "sale": "bedrooms + bathrooms + C(ptype)"}
Y = {"rent": "np.log(rent_month_ugx)", "sale": "np.log(price_ugx)"}


def ols(y, X):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b, y - X @ b


def cluster_t(X, u, g, j, b):
    """Cluster-robust t for coefficient j (CR1)."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    G = np.unique(g)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for c in G:
        s = X[g == c].T @ u[g == c]
        meat += np.outer(s, s)
    n, k = X.shape
    V = XtX_inv @ meat @ XtX_inv * (len(G) / (len(G) - 1)) * ((n - 1) / (n - k))
    return b[j] / np.sqrt(V[j, j]), np.sqrt(V[j, j])


rows = []
for market in ("rent", "sale"):
    s = d[d["listing_type"] == market].dropna(subset=["bedrooms"])
    for tname in ("near", "ln_texp"):
        inter = " + ".join(f"p{q}:{tname}" for q in posts)
        f = f"{Y[market]} ~ C(pt) + " + " + ".join(f"p{q}" for q in posts) + f" + {inter} + {CTRL[market]}"
        y, X = patsy.dmatrices(f, s, return_type="dataframe")
        g = pd.factorize(s.loc[y.index, "pt"])[0]
        yv, Xv = y.values.ravel(), X.values
        b, u = ols(yv, Xv)
        for q in posts:
            name = f"p{q}:{tname}"
            j = list(X.columns).index(name)
            t, se = cluster_t(Xv, u, g, j, b)
            # wild cluster bootstrap, null imposed
            Xr = np.delete(Xv, j, axis=1)
            br, ur = ols(yv, Xr)
            fit_r = Xr @ br
            G = np.unique(g)
            ts = []
            for _ in range(1999):
                w = rng.choice(WEBB, size=len(G))[g]
                yb = fit_r + w * ur
                bb, ub = ols(yb, Xv)
                ts.append(cluster_t(Xv, ub, g, j, bb)[0])
            p_boot = float(np.mean(np.abs(ts) >= abs(t)))
            treated = s.loc[y.index].groupby("pt")["near"].first().sum() if tname == "near" else np.nan
            rows.append({"market": market, "treatment": tname, "post_period": q, "coef": b[j], "se": se, "t": t,
                         "p_boot": p_boot, "n": len(yv), "points": len(G), "treated_points": treated,
                         "listings_by_period": s.loc[y.index].groupby("period").size().to_dict()})
res = pd.DataFrame(rows)
res.round(4).to_csv(_paper.OUT / "tables" / "did_results.csv", index=False)
pd.set_option("display.width", 220)
print(res.assign(pct=lambda r: np.where(r.treatment == "near", (np.exp(r.coef) - 1) * 100, np.nan))
      .round(3).to_string(index=False))
