"""Stage 2: hedonic OLS (with tenure/title premium) and GWR / MGWR."""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from esda.moran import Moran
from libpysal.weights import KNN

log = logging.getLogger(__name__)

AMENITY_TEXT = ["f_self_contained", "f_boys_quarters", "f_gated", "f_security", "f_parking",
                "f_tarmac_access", "f_pool", "f_furnished", "f_storeyed", "f_shell_or_incomplete"]
ACCESS = ["dist_cbd_km", "dist_major_road_km", "dist_northern_bypass_km",
          "dist_entebbe_expressway_km", "dist_school_km", "dist_health_km",
          "dist_market_km", "dist_taxi_stage_km", "dist_wetland_km"]


def _present(df, cols):
    return [c for c in cols if c in df and df[c].notna().mean() > 0.8 and df[c].nunique() > 1]


def build_formula(df: pd.DataFrame, market: str) -> str:
    y = "log_rent_month_ugx" if market == "rent" else "log_price_ugx"
    x = ["bedrooms", "I(bedrooms**2)"]
    if df["bathrooms"].notna().mean() > 0.8:
        x.append("bathrooms")
    if market == "sale" and df["plot_decimals"].notna().mean() > 0.5:
        x.append("np.log(plot_decimals)")
    x += _present(df, AMENITY_TEXT)
    x += [f"np.log1p({c})" for c in _present(df, ACCESS)]
    if "ntl_500m" in df and df["ntl_500m"].notna().mean() > 0.8:
        x.append("np.log1p(ntl_500m)")
    if "wealth_index" in df and df["wealth_index"].notna().mean() > 0.8:
        x.append("wealth_index")                 # Census 2024 parish socio-economic status
    if "in_flood_zone" in _present(df, ["in_flood_zone"]):
        x.append("in_flood_zone")
    if df["ptype"].nunique() > 1:
        x.append('C(ptype, Treatment("house"))')
    if market == "sale" and df["title_status"].nunique() > 1:
        # Untitled (kibanja) houses are almost absent online (3 of ~2,500), so the
        # estimable contrast is "title stated" vs "tenure not mentioned" (a
        # disclosure premium). Untitled/pending listings are dropped in hedonic_ols.
        x.append('C(title_status, Treatment("unknown"))')
    if df["source"].nunique() > 1:
        x.append("C(source)")                    # portal fixed effects
    if df["listing_quarter"].nunique() > 1:
        x.append("C(listing_quarter)")           # time fixed effects
    return f"{y} ~ " + " + ".join(x)


def hedonic_ols(df: pd.DataFrame, market: str, cluster_col: str = "analysis_unit"):
    d = df[df["listing_type"] == market].copy()
    if market == "sale":
        d = d[(d["ptype"] != "land") & d["title_status"].isin(["titled", "unknown"])]
    formula = build_formula(d, market)
    needed = d.dropna(subset=["bedrooms", "log_rent_month_ugx" if market == "rent" else "log_price_ugx"])
    mod = smf.ols(formula, data=needed)
    groups = needed.loc[mod.data.row_labels, cluster_col].astype(str)
    res = mod.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]})
    return res, needed.loc[mod.data.row_labels]


def tenure_models(df: pd.DataFrame, cluster_col: str = "analysis_unit", min_n: int = 15):
    """Land-only model: log price per decimal on tenure class.
    Isolates the tenure premium without the building."""
    d = df[(df["listing_type"] == "sale") & (df["ptype"] == "land") & df["price_per_decimal"].notna()].copy()
    d["log_ppd"] = np.log(d["price_per_decimal"])
    # Reference: mailo, the dominant registered tenure. Classes with < min_n
    # listings (online: kibanja, customary) are not estimated; report counts.
    counts = d["tenure_class"].value_counts()
    keep = counts[counts >= min_n].index
    d = d[d["tenure_class"].isin(keep)]
    x = ['C(tenure_class, Treatment("mailo"))', "np.log(plot_decimals)"]
    x += [f"np.log1p({c})" for c in _present(d, ACCESS)]
    if d["source"].nunique() > 1:
        x.append("C(source)")
    mod = smf.ols("log_ppd ~ " + " + ".join(x), data=d)
    groups = d.loc[mod.data.row_labels, cluster_col].astype(str)
    return mod.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]})


def premium_table(res, prefix: str) -> pd.DataFrame:
    """Coefficients for a categorical term as % premia: 100*(exp(b)-1)."""
    rows = [(k, v) for k, v in res.params.items() if k.startswith(prefix)]
    t = pd.DataFrame(rows, columns=["term", "coef"]).set_index("term")
    t["se"] = res.bse[t.index]
    t["p"] = res.pvalues[t.index]
    t["premium_pct"] = 100 * (np.exp(t["coef"]) - 1)
    ci = res.conf_int().loc[t.index]
    t["premium_lo"], t["premium_hi"] = 100 * (np.exp(ci[0]) - 1), 100 * (np.exp(ci[1]) - 1)
    return t


def residual_moran(res, d: gpd.GeoDataFrame, k: int = 8) -> dict:
    w = KNN.from_dataframe(d, k=k)
    w.transform = "r"
    np.random.seed(42)
    m = Moran(res.resid.to_numpy(), w, permutations=999)
    return {"moran_I_resid": m.I, "p_sim": m.p_sim}


def gwr_fit(d: gpd.GeoDataFrame, y_col: str, x_cols: list[str], multiscale: bool = False,
            max_n: int = 3000, seed: int = 42):
    """GWR/MGWR on standardised X. MGWR is O(n^2 k): subsample above max_n."""
    from mgwr.gwr import GWR, MGWR
    from mgwr.sel_bw import Sel_BW

    d = d.dropna(subset=[y_col] + x_cols)
    if len(d) > max_n:
        log.info("subsampling %d -> %d for (M)GWR", len(d), max_n)
        d = d.sample(max_n, random_state=seed)
    # Jitter identical coordinates (gazetteer centroids) by <= 50 m, else the
    # kernel matrix is singular. Report this in the methods section.
    rng = np.random.default_rng(seed)
    coords = np.c_[d.geometry.x, d.geometry.y] + rng.uniform(-50, 50, (len(d), 2))
    y = d[[y_col]].to_numpy()
    X = d[x_cols].to_numpy(dtype=float)
    X = (X - X.mean(0)) / X.std(0)
    y = (y - y.mean()) / y.std()
    if multiscale:
        # Listings share neighbourhood points, so a window smaller than the largest
        # co-located group can hold a single point with constant dummies (singular).
        largest = int(pd.Series(list(zip(d.geometry.x.round(), d.geometry.y.round()))).value_counts().max())
        bw_min = max(30, largest + 20)
        log.info("MGWR minimum bandwidth %d (largest co-located group %d)", bw_min, largest)
        sel = Sel_BW(coords, y, X, multi=True)
        sel.search(multi_bw_min=[bw_min])
        res = MGWR(coords, y, X, sel).fit()
        bws = sel.bw[0]
    else:
        sel = Sel_BW(coords, y, X)
        bw = sel.search()
        res = GWR(coords, y, X, bw).fit()
        bws = [bw] * (X.shape[1] + 1)
    out = d[["geometry"]].copy()
    names = ["intercept"] + x_cols
    for i, n in enumerate(names):
        out[f"b_{n}"] = res.params[:, i]
        out[f"t_{n}"] = res.tvalues[:, i]
    out["local_r2"] = getattr(res, "localR2", np.full(len(d), np.nan)).ravel() if not multiscale else np.nan
    # Significance after the da Silva-Fotheringham multiple-testing correction
    crit = res.critical_tval() if hasattr(res, "critical_tval") else None
    if crit is not None:
        crit = np.atleast_1d(crit)
        for i, n in enumerate(names):
            c = crit[i] if len(crit) > 1 else crit[0]
            out[f"sig_{n}"] = np.abs(out[f"t_{n}"]) > c
    summary = {"aicc": res.aicc, "r2": getattr(res, "R2", np.nan), "bandwidths": dict(zip(names, bws)), "n": len(d)}
    return res, out, summary
