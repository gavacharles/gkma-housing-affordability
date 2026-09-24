"""Census 2024 parish tables and a parish-level income model from published
UBOS figures only (no microdata).

Parish income model (a transparent, simplified small-area estimate):
  1. Wealth index for every parish in Uganda from Census 2024 shares
     (TV, computer, grid power, improved water, improved sanitation,
     non-subsistence), first principal component, national standardisation.
  2. Across the 15 UNHS 2019/20 sub-regions, regress log median monthly
     household income (UNHS 2019/20 report, Table 5.21) on the sub-region's
     household-weighted mean wealth index -> slope b.
  3. Parish median = sub-region median x exp(b x (w_parish - w_mean_subregion)),
     so each sub-region still matches its official UNHS median.
Caveats to report: ecological calibration on 15 points; asset-based wealth
proxies income; census 2024 vs survey 2019/20 timing.
"""
from __future__ import annotations

import re

import numpy as np
import openpyxl
import pandas as pd

from gkma.config import p

SRC = "data/external/ubos/harvest/NPHC-2024-Subcounty-Profiles-Excel-Tables.xlsx"
TABLES = {
    "Table2": {"household_pop": 1, "households": 2, "hh_size": 3},
    "Table7": {"n_radio": 1, "n_tv": 2, "n_computer": 3},
    "Table12": {"n_unimproved_water": 1, "n_improved_water": 2, "n_improved_sanitation": 3,
                "n_unimproved_sanitation": 4, "n_open_defecation": 5},
    "Table13": {"n_grid": 1, "n_solar": 2},
    "Table14": {"n_subsistence": 1, "n_pdm": 2},
}
WEALTH_COLS = ["sh_tv", "sh_computer", "sh_grid", "sh_improved_water", "sh_improved_sanitation", "sh_subsistence"]

# UNHS 2019/20 sub-regions (report, sampling annex) and Table 5.21 medians (UGX '000, total 2019/20)
SUBREGIONS = {
    "Kampala": "Kampala",
    "Buganda South": "Butambala, Gomba, Mpigi, Bukomansimbi, Kalangala, Kalungu, Lwengo, Lyantonde, Masaka, Rakai, Sembabule, Wakiso, Kyotera",
    "Buganda North": "Buikwe, Buvuma, Kayunga, Kiboga, Kyankwanzi, Luwero, Mityana, Mubende, Mukono, Nakaseke, Nakasongola, Kassanda",
    "Busoga": "Bugiri, Namutumba, Buyende, Iganga, Jinja, Kaliro, Kamuli, Luuka, Mayuge, Namayingo, Bugweri",
    "Bukedi": "Budaka, Butaleja, Kibuku, Pallisa, Tororo, Busia, Butebo",
    "Elgon": "Bulambuli, Kapchorwa, Kween, Bududa, Manafwa, Mbale, Sironko, Bukwo, Namisindwa",
    "Teso": "Amuria, Bukedea, Katakwi, Kumi, Ngora, Soroti, Kaberamaido, Serere, Kapelebyong",
    "Lango": "Alebtong, Amolatar, Dokolo, Lira, Otuke, Apac, Kole, Oyam, Kwania",
    "Acholi": "Agago, Amuru, Gulu, Lamwo, Pader, Kitgum, Nwoya",
    "Karamoja": "Abim, Amudat, Kaabong, Kotido, Moroto, Nakapiripirit, Napak, Nabilatuk",
    "West Nile": "Adjumani, Arua, Koboko, Maracha, Moyo, Nebbi, Yumbe, Zombo, Pakwach, Obongi, Terego",
    "Tooro": "Bundibugyo, Kabarole, Kasese, Ntoroko, Kyenjojo, Kamwenge, Kyegegwa, Bunyangabu, Fort Portal",
    "Bunyoro": "Buliisa, Hoima, Kibaale, Kiryandongo, Masindi, Kikuube, Kagadi, Kakumiro, Kitagwenda",
    "Ankole": "Buhweju, Bushenyi, Ibanda, Isingiro, Kiruhura, Mbarara, Mitooma, Ntungamo, Rubirizi, Sheema, Rwampara, Kazo",
    "Kigezi": "Kabale, Kisoro, Kanungu, Rukungiri, Rukiga",
}
UNHS_MEDIAN_2019_20 = {  # UGX per month, Table 5.21 "Total (2019/20)"
    "Kampala": 667_000, "Buganda South": 302_000, "Buganda North": 208_000, "Busoga": 136_000,
    "Bukedi": 174_000, "Elgon": 192_000, "Teso": 263_000, "Karamoja": 99_000, "Lango": 72_000,
    "Acholi": 105_000, "West Nile": 152_000, "Bunyoro": 250_000, "Tooro": 145_000,
    "Ankole": 195_000, "Kigezi": 133_000,
}


def _key(s: str) -> str:
    s = re.sub(r"\b(city|district|municipality)\b", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def district_to_subregion() -> dict:
    out = {}
    for sr, ds in SUBREGIONS.items():
        for d in ds.split(","):
            out[_key(d)] = sr
    out[_key("Luweero")] = "Buganda North"
    out[_key("Ssembabule")] = "Buganda South"
    out[_key("Toroo")] = out.get(_key("Tororo"))
    return out


def _read_table(ws, cols, districts=None):
    rows, path = [], {}
    for r in range(7, ws.max_row + 1):
        c = ws.cell(r, 1)
        if c.value is None or c.alignment.indent is None:
            continue
        level = int(c.alignment.indent)
        path[level] = str(c.value).strip()
        for deeper in [k for k in path if k > level]:
            del path[deeper]
        if level != 3 or (districts and path.get(0) not in districts):
            continue
        rec = {"district": path.get(0), "county": path.get(1), "subcounty": path.get(2), "parish": path[3]}
        for name, j in cols.items():
            rec[name] = ws.cell(r, j + 1).value
        rows.append(rec)
    return pd.DataFrame(rows)


def parse_census(districts: set | None = None) -> pd.DataFrame:
    """Parish rows (all Uganda by default) with counts and household shares."""
    wb = openpyxl.load_workbook(p(SRC), read_only=False, data_only=True)
    keys = ["district", "county", "subcounty", "parish"]
    df = None
    for sheet, cols in TABLES.items():
        t = _read_table(wb[sheet], cols, districts)
        df = t if df is None else df.merge(t, on=keys, how="left")
    for c in df.columns.difference(keys):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["households"] > 0].reset_index(drop=True)
    df["district"] = df["district"].replace({"LUWEERO": "LUWERO"})
    hh = df["households"]
    for short, n in [("tv", "n_tv"), ("computer", "n_computer"), ("grid", "n_grid"),
                     ("improved_water", "n_improved_water"), ("improved_sanitation", "n_improved_sanitation"),
                     ("subsistence", "n_subsistence")]:
        df[f"sh_{short}"] = (df[n] / hh).clip(0, 1)
    return df


def wealth_index(df: pd.DataFrame) -> tuple[pd.Series, float]:
    Z = df[WEALTH_COLS].apply(lambda s: (s - s.mean()) / s.std()).fillna(0)
    Z["sh_subsistence"] *= -1
    vals, vecs = np.linalg.eigh(np.cov(Z.T.to_numpy()))
    pc1 = vecs[:, -1] * np.sign(vecs[:, -1].sum())
    w = pd.Series(Z.to_numpy() @ pc1, index=df.index)
    return (w - w.mean()) / w.std(), float(vals[-1] / vals.sum())


def parish_income_model(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = df.copy()
    d["wealth_nat"], explained = wealth_index(d)
    m = district_to_subregion()
    d["subregion"] = d["district"].map(lambda x: m.get(_key(x)))
    d = d[d["subregion"].notna()].copy()
    sr = d.groupby("subregion").apply(lambda g: np.average(g["wealth_nat"], weights=g["households"]))
    sr = pd.DataFrame({"wealth_mean": sr, "median": pd.Series(UNHS_MEDIAN_2019_20)}).dropna()
    X = np.c_[np.ones(len(sr)), sr["wealth_mean"]]
    coef, *_ = np.linalg.lstsq(X, np.log(sr["median"]), rcond=None)
    pred = X @ coef
    ss_res = ((np.log(sr["median"]) - pred) ** 2).sum()
    ss_tot = ((np.log(sr["median"]) - np.log(sr["median"]).mean()) ** 2).sum()
    b = float(coef[1])
    d = d.join(sr["wealth_mean"], on="subregion")
    d["median_income_2019_20"] = d["subregion"].map(UNHS_MEDIAN_2019_20) * np.exp(b * (d["wealth_nat"] - d["wealth_mean"]))
    info = {"slope_b": b, "intercept": float(coef[0]), "r2_subregions": float(1 - ss_res / ss_tot),
            "n_subregions": int(len(sr)), "pc1_share": explained, "n_parishes": int(len(d))}
    return d, info
