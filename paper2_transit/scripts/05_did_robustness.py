"""Robustness of the Expressway before-after estimate (paper 2).

Same sample and model as 04_did.py (RED; 2017 pre, 2020 and 2025-26 post; point and period
fixed effects; hedonic controls; cluster-robust t and wild cluster bootstrap p, 999 draws).
  threshold   treatment = within 10 / 15 / 20 / 25 minutes of Expressway access
  dose        separate effects for 0-15 and 15-30 minutes (reference: over 30)
  placebo     within 2 km of other radial trunk roads that did not change (Jinja, Bombo/Gulu,
              Gayaza, Hoima, Masaka, Fort Portal roads), and of the old Entebbe Road beyond
              the Expressway catchment
  mix         houses only; 1-4 bedrooms; prices trimmed at the 5th/95th percentile by period

  python paper2_transit/scripts/05_did_robustness.py -> paper2_transit/outputs/tables/did_robustness.csv
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import patsy

import _paper  # noqa: F401
from gkma.config import load_config, p

rng = np.random.default_rng(7)
WEBB = np.array([-np.sqrt(1.5), -1, -np.sqrt(.5), np.sqrt(.5), 1, np.sqrt(1.5)])
B = 999
crs = load_config()["project"]["crs_projected"]
COLS = ["listing_type", "ptype", "bedrooms", "bathrooms", "f_furnished", "rent_month_ugx", "price_ugx", "geometry"]
frames = []
for period, f in [("2017", "listings_archive_2017.gpkg"), ("2020", "listings_archive_2020.gpkg"),
                  ("2025", "listings_current_full.gpkg")]:
    g = gpd.read_file(p("data/processed") / f)
    if period == "2025":
        g = g[g["source"] == "red"]
    frames.append(g[COLS].assign(period=period))
d = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)
d["pt"] = d.geometry.to_wkt()
A = pd.read_csv(_paper.OUT / "tables" / "neighbourhood_accessibility.csv")[["pt", "tt_expressway_min"]]
d = d.merge(A, on="pt", how="inner")
d = d[d["pt"].isin(set(d.loc[d.period == "2017", "pt"]) & set(d.loc[d.period != "2017", "pt"]))]
d = d[d["ptype"] != "land"].copy()
posts = ["2020", "2025"]
for q in posts:
    d[f"p{q}"] = (d["period"] == q).astype(float)
for m_ in (10, 15, 20, 25):
    d[f"near{m_}"] = (d["tt_expressway_min"] <= m_).astype(float)
d["band0_15"] = (d["tt_expressway_min"] <= 15).astype(float)
d["band15_30"] = ((d["tt_expressway_min"] > 15) & (d["tt_expressway_min"] <= 30)).astype(float)

roads = gpd.read_file(p("data/external/osm/roads.gpkg")).to_crs(crs)
RADIALS = {"jinja_road": ["Jinja Road", "Jinja - Kampala Road"], "bombo_road": ["Bombo Road", "Gulu - Kampala Road"],
           "gayaza_road": ["Gayaza Road"], "hoima_road": ["Hoima Road"],
           "masaka_road": ["Kampala - Masaka Road", "Masaka Road"], "fortportal_road": ["Fort Portal - Kampala Road"],
           "entebbe_road": ["Entebbe Road", "Entebbe - Kampala Road"]}
pts = d.drop_duplicates("pt")[["pt", "geometry"]]
pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=d.crs).to_crs(crs)
for k, names in RADIALS.items():
    dist = pts.geometry.distance(roads[roads["name"].isin(names)].union_all()) / 1000
    d[f"pl_{k}"] = d["pt"].map(dict(zip(pts["pt"], (dist <= 2).astype(float))))
d["pl_entebbe_road"] = d["pl_entebbe_road"] * (1 - d["near15"])        # old road, outside the Expressway catchment

CTRL = {"rent": "bedrooms + I(bedrooms**2) + bathrooms + f_furnished + C(ptype)", "sale": "bedrooms + bathrooms + C(ptype)"}
Y = {"rent": "np.log(rent_month_ugx)", "sale": "np.log(price_ugx)"}


def ols(y, X):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b, y - X @ b


def cl_t(X, u, g, j, b, XtXi):
    G = np.unique(g)
    s = np.zeros((len(G), X.shape[1]))
    np.add.at(s, g, X * u[:, None])
    V = XtXi @ (s.T @ s) @ XtXi * (len(G) / (len(G) - 1)) * ((len(u) - 1) / (len(u) - X.shape[1]))
    return b[j] / np.sqrt(V[j, j]), np.sqrt(V[j, j])


def did(s, market, treats, label):
    inter = " + ".join(f"p{q}:{t}" for q in posts for t in treats)
    f = f"{Y[market]} ~ C(pt) + p2020 + p2025 + {inter} + {CTRL[market]}"
    y, X = patsy.dmatrices(f, s, return_type="dataframe")
    g = pd.factorize(s.loc[y.index, "pt"])[0]
    yv, Xv = y.values.ravel(), X.values
    XtXi = np.linalg.pinv(Xv.T @ Xv)
    b, u = ols(yv, Xv)
    out = []
    for q in posts:
        for t in treats:
            name = f"p{q}:{t}"
            j = list(X.columns).index(name)
            tstat, se = cl_t(Xv, u, g, j, b, XtXi)
            Xr = np.delete(Xv, j, axis=1)
            br, ur = ols(yv, Xr)
            fit = Xr @ br
            ts = np.empty(B)
            for i in range(B):
                yb = fit + rng.choice(WEBB, size=g.max() + 1)[g] * ur
                bb, ub = ols(yb, Xv)
                ts[i] = cl_t(Xv, ub, g, j, bb, XtXi)[0]
            treated = int(s.loc[y.index].groupby("pt")[t].first().sum())
            out.append({"check": label, "market": market, "treatment": t, "period": q, "coef": b[j], "se": se,
                        "t": tstat, "p_boot": float(np.mean(np.abs(ts) >= abs(tstat))), "n": len(yv),
                        "points": g.max() + 1, "treated_points": treated})
    return out


rows = []
for market in ("sale", "rent"):
    s = d[d["listing_type"] == market].dropna(subset=["bedrooms"])
    for m_ in (10, 20, 25):
        rows += did(s, market, [f"near{m_}"], f"threshold {m_} min")
    rows += did(s, market, ["band0_15", "band15_30"], "dose")
    for k in RADIALS:
        rows += did(s, market, [f"pl_{k}"], f"placebo {k.replace('_', ' ')}")
    y_ = "price_ugx" if market == "sale" else "rent_month_ugx"
    lo, hi = s.groupby("period")[y_].transform(lambda v: v.quantile(.05)), \
        s.groupby("period")[y_].transform(lambda v: v.quantile(.95))
    rows += did(s[(s[y_] >= lo) & (s[y_] <= hi)], market, ["near15"], "mix: trimmed 5-95%")
    rows += did(s[s["bedrooms"].between(1, 4)], market, ["near15"], "mix: 1-4 bedrooms")
    if market == "sale":
        rows += did(s[s["ptype"] == "house"], market, ["near15"], "mix: houses only")
    print(market, "done")
res = pd.DataFrame(rows)
res.round(4).to_csv(_paper.OUT / "tables" / "did_robustness.csv", index=False)
pd.set_option("display.width", 220)
star = lambda v: "**" if v < .01 else "*" if v < .05 else "+" if v < .1 else ""  # noqa: E731
res["est"] = [f"{c:+.3f}{star(pb)} (p={pb:.2f})" for c, pb in zip(res.coef, res.p_boot)]
print(res.pivot_table(index=["market", "check", "treatment", "treated_points"], columns="period", values="est",
                      aggfunc="first").to_string())
