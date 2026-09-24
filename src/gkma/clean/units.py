"""Plot and floor sizes -> decimals and m².

Ugandan listings mix: "12 Decimals", "0.5 acres", "half an acre", "50x100 ft",
"50 by 100", "100 x 100", "1 hectare", "600 sqm", "2 plots". A "plot" in
agent usage is conventionally 50x100 ft (~11.5 decimals); it is converted
but flagged because the convention is loose.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from gkma.config import load_config

DEC_M2 = None  # set lazily from config
SQFT_M2 = 0.09290304
ACRE_DEC = 100.0
HECTARE_M2 = 10_000.0
STD_PLOT_SQFT = 50 * 100

WORD_FRAC = {"half": 0.5, "quarter": 0.25, "a": 1, "an": 1, "one": 1, "two": 2, "three": 3,
             "four": 4, "five": 5, "ten": 10}

NUM = r"(\d+(?:\.\d+)?)"
DIM_RE = re.compile(rf"{NUM}\s*(?:ft|feet|')?\s*(?:x|×|by|\*)\s*{NUM}\s*(ft|feet|m\b|metres|meters|')?", re.I)
DEC_RE = re.compile(rf"{NUM}\s*(?:decimals?|decs?\b|dcml)", re.I)
ACRE_RE = re.compile(rf"{NUM}\s*(?:acres?|ac\b)", re.I)
WORD_ACRE_RE = re.compile(r"\b(half|quarter|an?|one|two|three|four|five|ten)\s+(?:an?\s+)?acres?", re.I)
HA_RE = re.compile(rf"{NUM}\s*(?:hectares?|ha\b)", re.I)
SQM_RE = re.compile(rf"{NUM}\s*(?:sq\.?\s*m\b|sqm|m2|m²|square\s*met)", re.I)
SQFT_RE = re.compile(rf"{NUM}\s*(?:sq\.?\s*ft|sqft|square\s*f(ee|oo)t)", re.I)
PLOT_RE = re.compile(r"\b(\d+|one|two|three|four|a)\s+plots?\b", re.I)


def _dec_m2() -> float:
    global DEC_M2
    if DEC_M2 is None:
        DEC_M2 = float(load_config()["cleaning"]["decimal_m2"])
    return DEC_M2


def parse_plot_decimals(text) -> tuple[float | None, str | None]:
    """Return (plot size in decimals, method) from free text."""
    if text is None or text != text:
        return None, None
    s = str(text).replace(",", "")
    if m := DEC_RE.search(s):
        return float(m.group(1)), "decimals"
    if m := ACRE_RE.search(s):
        return float(m.group(1)) * ACRE_DEC, "acres"
    if m := WORD_ACRE_RE.search(s):
        return WORD_FRAC[m.group(1).lower()] * ACRE_DEC, "acres_word"
    if m := HA_RE.search(s):
        return float(m.group(1)) * HECTARE_M2 / _dec_m2(), "hectares"
    if m := DIM_RE.search(s):
        a, b, unit = float(m.group(1)), float(m.group(2)), (m.group(3) or "ft").lower()
        # Dimensions in metres are rare; small products with no unit are feet.
        area_m2 = a * b if unit.startswith("m") else a * b * SQFT_M2
        return area_m2 / _dec_m2(), "dimensions"
    if m := PLOT_RE.search(s):
        n = m.group(1).lower()
        n = WORD_FRAC.get(n, None) if not n.isdigit() else float(n)
        return n * STD_PLOT_SQFT * SQFT_M2 / _dec_m2(), "plot_convention"
    return None, None


def parse_floor_m2(text) -> float | None:
    if text is None or text != text:
        return None
    s = str(text).replace(",", "")
    if m := SQM_RE.search(s):
        return float(m.group(1))
    if m := SQFT_RE.search(s):
        return float(m.group(1)) * SQFT_M2
    return None


def normalise_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """plot_decimals / plot_method / floor_m2, preferring structured fields."""
    out = df.copy()
    size_field = out["size_raw"].astype(str) + " " + out["size_unit_raw"].fillna("").astype(str)
    text = out["title"].fillna("") + " " + out["description"].fillna("")

    field = size_field.map(parse_plot_decimals)
    free = text.map(parse_plot_decimals)
    out["plot_decimals"] = [f[0] if f[0] is not None else t[0] for f, t in zip(field, free)]
    out["plot_method"] = [f[1] if f[0] is not None else t[1] for f, t in zip(field, free)]

    # Jiji "Property size" in sqm is ambiguous (floor vs plot). Keep it as a
    # separate, flagged variable; only trust sqm stated in text as floor area.
    out["floor_m2"] = text.map(parse_floor_m2)
    jiji_sqm = out["source"].eq("jiji") & out["size_unit_raw"].eq("sqm")
    out["portal_size_sqm"] = np.where(jiji_sqm, pd.to_numeric(out["size_raw"], errors="coerce"), np.nan)

    lo, hi = 0.5, 5_000  # decimals: ~20 m² to 50 acres
    out["flag_plot_implausible"] = out["plot_decimals"].notna() & ~out["plot_decimals"].between(lo, hi)
    # RED fills "0 Decimals" / "0 Sq Meters" when the agent gave no size:
    # that means missing, not zero, and log(0) would break every model.
    out.loc[out["plot_decimals"].notna() & (out["plot_decimals"] < lo), ["plot_decimals", "plot_method"]] = [np.nan, None]
    return out


PER_UNIT = [
    ("per_decimal", re.compile(r"per\s*decimal|/\s*decimal|a\s+decimal\b", re.I)),
    ("per_acre", re.compile(r"per\s*acre|/\s*acre|an?\s+acre\s+at\b", re.I)),
    ("per_plot", re.compile(r"per\s*plot|/\s*plot|a\s+plot\b", re.I)),
]


def apply_price_units(df: pd.DataFrame) -> pd.DataFrame:
    """Land is often priced per plot/acre/decimal rather than for the parcel.
    Then the priced area is ONE unit, whatever total area the ad offers."""
    out = df.copy()
    blob = out["price_period"].fillna("") + " " + out["price_raw"].astype(str) + " " + out["title"].fillna("")
    unit = pd.Series("total", index=out.index)
    for name, rx in PER_UNIT[::-1]:  # most specific wins
        unit[blob.str.contains(rx) & out["listing_type"].eq("sale")] = name
    out["price_unit"] = unit
    std_plot = STD_PLOT_SQFT * SQFT_M2 / _dec_m2()
    dims = (out["title"].fillna("") + " " + out["description"].fillna("")).map(
        lambda s: parse_plot_decimals(s) if DIM_RE.search(s) else (None, None))
    per_plot = unit.eq("per_plot")
    out.loc[per_plot, "plot_decimals"] = [d[0] or std_plot for d in dims[per_plot]]
    out.loc[per_plot, "plot_method"] = "per_plot_price"
    out.loc[unit.eq("per_acre"), ["plot_decimals", "plot_method"]] = [ACRE_DEC, "per_acre_price"]
    out.loc[unit.eq("per_decimal"), ["plot_decimals", "plot_method"]] = [1.0, "per_decimal_price"]
    return out
