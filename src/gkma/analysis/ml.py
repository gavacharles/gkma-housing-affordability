"""Stage 3: RF / XGBoost / LightGBM vs hedonic OLS (and GWR) under spatial CV,
with SHAP explanations.

Spatial CV: listings are grouped into square blocks of `spatial_cv_block_km`
and whole blocks are held out (GroupKFold), so a model cannot score well by
memorising near-identical neighbours. Random K-fold is also reported: the
gap between the two is itself evidence of spatial leakage.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from gkma.config import load_config

log = logging.getLogger(__name__)

NUMERIC = ["bedrooms", "bathrooms", "plot_decimals", "dist_cbd_km", "dist_major_road_km",
           "dist_northern_bypass_km", "dist_entebbe_expressway_km", "dist_school_km",
           "dist_health_km", "dist_market_km", "dist_taxi_stage_km", "n_school_1km",
           "n_health_1km", "n_market_1km", "n_taxi_stage_1km", "ntl_500m", "in_flood_zone",
           "dist_wetland_km", "near_wetland_200m", "wealth_index", "sh_grid", "sh_computer", "hh_size",
           "n_postings"]
CATEGORICAL = ["ptype", "tenure_class", "title_status", "source"]


def feature_matrix(d: pd.DataFrame, include_xy: bool = True) -> pd.DataFrame:
    num = [c for c in NUMERIC if c in d and d[c].notna().mean() > 0.3]
    fcols = [c for c in d if c.startswith("f_")]
    X = d[num + fcols].astype(float).copy()
    for c in CATEGORICAL:
        if c in d and d[c].nunique() > 1:
            X = X.join(pd.get_dummies(d[c].astype(str), prefix=c, dtype=float))
    if include_xy:  # coordinates let trees learn residual location effects
        X["x_km"], X["y_km"] = d.geometry.x / 1000, d.geometry.y / 1000
    return X


def spatial_blocks(d: gpd.GeoDataFrame, block_km: float) -> np.ndarray:
    bx = np.floor(d.geometry.x / (block_km * 1000)).astype(int)
    by = np.floor(d.geometry.y / (block_km * 1000)).astype(int)
    return pd.factorize(bx.astype(str) + "_" + by.astype(str))[0]


def models(seed: int):
    return {
        "RandomForest": RandomForestRegressor(n_estimators=500, min_samples_leaf=3, max_features=0.5,
                                              n_jobs=-1, random_state=seed),
        "XGBoost": xgb.XGBRegressor(n_estimators=800, learning_rate=0.03, max_depth=6, subsample=0.8,
                                    colsample_bytree=0.8, min_child_weight=3, random_state=seed, n_jobs=-1),
        "LightGBM": lgb.LGBMRegressor(n_estimators=800, learning_rate=0.03, num_leaves=31, subsample=0.8,
                                      subsample_freq=1, colsample_bytree=0.8, min_child_samples=10,
                                      random_state=seed, verbose=-1),
    }


LOG_TERMS = ("plot_decimals", "dist_", "n_", "ntl_500m")


class OLSBaseline:
    """Hedonic OLS on the same features, in hedonic form: log(1+x) for plot
    size, distances, counts and night lights (as in the hedonic model), NaNs
    median-imputed, no x/y. Without the logs a few very large plots drive
    extreme extrapolations and the benchmark is unfairly weak."""

    @staticmethod
    def _transform(X):
        X = X.copy()
        for c in X:
            if c.startswith(LOG_TERMS) or c == "plot_decimals":
                X[c] = np.log1p(X[c].clip(lower=0))
        return X

    def fit(self, X, y):
        X = self._transform(X)
        # Winsorise at the training 1st/99th percentiles so a single typo in a
        # test fold cannot produce an absurd linear extrapolation.
        self.lo, self.hi = X.quantile(0.01), X.quantile(0.99)
        X = X.clip(self.lo, self.hi, axis=1)
        cols = [c for c in X if c not in ("x_km", "y_km") and X[c].nunique() > 1]
        # Drop one level per one-hot group (reference category) to avoid
        # perfect collinearity with the intercept.
        for grp in CATEGORICAL:
            levels = [c for c in cols if c.startswith(grp + "_")]
            if levels:
                cols.remove(max(levels, key=lambda c: X[c].sum()))
        self.cols = cols
        self.med = X[self.cols].median()
        self.m = LinearRegression().fit(X[self.cols].fillna(self.med), y)
        return self

    def predict(self, X):
        Xt = self._transform(X).clip(self.lo, self.hi, axis=1)
        return self.m.predict(Xt[self.cols].fillna(self.med))


def _metrics(y, yhat) -> dict:
    return {"rmse_log": mean_squared_error(y, yhat) ** 0.5, "mae_log": mean_absolute_error(y, yhat),
            "r2": r2_score(y, yhat),
            "mape_ugx": float(np.mean(np.abs(np.exp(yhat) - np.exp(y)) / np.exp(y)))}


def _impute_for_rf(Xtr, Xte):
    med = Xtr.median()
    return Xtr.fillna(med), Xte.fillna(med)


def cross_validate(d: gpd.GeoDataFrame, y_col: str, include_gwr: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (fold-level metrics, out-of-fold predictions)."""
    cfg = load_config()
    seed = cfg["project"]["random_seed"]
    k = cfg["modelling"]["spatial_cv_folds"]
    d = d.dropna(subset=[y_col]).reset_index(drop=True)
    X, y = feature_matrix(d), d[y_col].to_numpy()
    groups = spatial_blocks(d, cfg["modelling"]["spatial_cv_block_km"])
    k_sp = min(k, len(np.unique(groups)))
    schemes = {"spatial_block": GroupKFold(n_splits=k_sp).split(X, y, groups),
               "random": KFold(n_splits=k, shuffle=True, random_state=seed).split(X, y)}
    rows, oof = [], pd.DataFrame(index=d.index)
    for scheme, splits in schemes.items():
        for fold, (tr, te) in enumerate(splits):
            cands = {"HedonicOLS": OLSBaseline(), **models(seed)}
            for name, m in cands.items():
                Xtr, Xte = X.iloc[tr], X.iloc[te]
                if name == "RandomForest":
                    Xtr, Xte = _impute_for_rf(Xtr, Xte)
                m.fit(Xtr, y[tr])
                pred = m.predict(Xte)
                rows.append({"scheme": scheme, "fold": fold, "model": name, "n_test": len(te), **_metrics(y[te], pred)})
                if scheme == "spatial_block":
                    oof.loc[d.index[te], name] = pred
            if include_gwr:
                rows.append({"scheme": scheme, "fold": fold, "model": "GWR", "n_test": len(te),
                             **_gwr_fold(d, X, y, tr, te)})
    oof[y_col] = y
    return pd.DataFrame(rows), oof


def _gwr_fold(d, X, y, tr, te):
    from mgwr.gwr import GWR
    from mgwr.sel_bw import Sel_BW
    cols = [c for c in ["bedrooms", "bathrooms", "dist_cbd_km", "dist_major_road_km"] if c in X]
    Xa = X[cols].fillna(X[cols].median()).to_numpy(dtype=float)
    mu, sd = Xa[tr].mean(0), Xa[tr].std(0)
    Xa = (Xa - mu) / np.where(sd > 0, sd, 1)
    rng = np.random.default_rng(0)
    coords = np.c_[d.geometry.x, d.geometry.y] + rng.uniform(-50, 50, (len(d), 2))
    # Listings share neighbourhood points: the kernel must span more than the largest
    # co-located group, or a local window holds one point and the fit is singular.
    xy = pd.Series(list(zip(d.geometry.x.round().iloc[tr], d.geometry.y.round().iloc[tr])))
    bw_min = int(xy.value_counts().max()) + 20
    bw = Sel_BW(coords[tr], y[tr, None], Xa[tr]).search(bw_min=bw_min)
    model = GWR(coords[tr], y[tr, None], Xa[tr], bw)
    pred = model.predict(coords[te], Xa[te]).predictions.ravel()
    return _metrics(y[te], pred)


def summarise_cv(res: pd.DataFrame) -> pd.DataFrame:
    return res.groupby(["scheme", "model"])[["rmse_log", "mae_log", "r2", "mape_ugx"]] \
              .agg(["mean", "std"]).round(3)


def fit_and_explain(d: gpd.GeoDataFrame, y_col: str, model_name: str = "LightGBM",
                    max_shap: int = 5000):
    """Fit on all data; return model, SHAP values frame (row-aligned with d)."""
    seed = load_config()["project"]["random_seed"]
    d = d.dropna(subset=[y_col]).reset_index(drop=True)
    X, y = feature_matrix(d), d[y_col].to_numpy()
    m = models(seed)[model_name]
    Xf = X.fillna(X.median()) if model_name == "RandomForest" else X
    m.fit(Xf, y)
    idx = d.sample(min(max_shap, len(d)), random_state=seed).index
    sv = shap.TreeExplainer(m).shap_values(Xf.loc[idx])
    shap_df = pd.DataFrame(sv, index=idx, columns=X.columns)
    return m, shap_df, d.loc[idx]


def shap_importance(shap_df: pd.DataFrame, group_dummies: bool = True) -> pd.Series:
    s = shap_df.abs().mean()
    if group_dummies:  # sum one-hot parts back to their parent variable
        parent = s.index.to_series().str.replace(r"^(ptype|tenure_class|title_status|source)_.*$", r"\1", regex=True)
        s = s.groupby(parent.values).sum()
    return s.sort_values(ascending=False)


def shap_by_unit(shap_df: pd.DataFrame, meta: pd.DataFrame, unit_col: str = "analysis_unit",
                 min_n: int = 5) -> pd.DataFrame:
    """Per unit: mean |SHAP| per feature, the dominant feature, and the mean
    contribution of location (x/y + distances) vs structure."""
    a = shap_df.abs().copy()
    a[unit_col] = meta[unit_col].values
    g = a.groupby(unit_col)
    agg = g.mean()
    n = g.size()
    agg = agg[n >= min_n]
    loc_cols = [c for c in shap_df if c.startswith(("dist_", "n_", "x_km", "y_km", "ntl", "in_flood"))]
    signed = shap_df.copy()
    signed[unit_col] = meta[unit_col].values
    sg = signed.groupby(unit_col)
    out = pd.DataFrame({
        "n": n[n >= min_n],
        "dominant_feature": agg.idxmax(axis=1),
        "location_effect": sg[loc_cols].mean().sum(axis=1)[n >= min_n],
        "location_share": agg[loc_cols].sum(axis=1) / agg.sum(axis=1),
    })
    return out
