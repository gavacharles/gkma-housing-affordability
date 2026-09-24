"""Parse Ugandan asking prices into UGX, and rents into UGX per month.

Handles: "Ugx 160,000,000/=", "UGX160M", "shs 1.2bn", "450k", "$250,000",
"USD 1,200 per month", "2.5m per month", "Ugx 15,000,000 per year",
"negotiable", "on request". USD converts at the Bank of Uganda monthly
mid-rate for the listing month when data/external/bou_usd_ugx_monthly.csv
exists (columns: month=YYYY-MM, usd_ugx), else the config fallback.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
import pandas as pd

from gkma.config import load_config, p

MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "mil": 1e6, "million": 1e6,
        "millions": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}
USD_RE = re.compile(r"\$|\busd\b|\bus\s?dollars?\b|\bdollars?\b", re.I)
NUM_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|mn|mil|millions?|m|bn|billion|b)?\b", re.I)

# Rent period -> multiplier to a monthly figure. First match wins, so an
# explicit monthly quote beats phrases like "6 months advance" / "3 months
# deposit", which in Kampala ads are payment terms, not the billing period.
PERIODS = [
    (re.compile(r"per\s*night|/\s*night|\bnightly\b|per\s*day\b|/\s*day\b|\bdaily\b", re.I), None),  # short-stay: excluded
    (re.compile(r"per\s*month|/\s*m(?:on)?th\b|\bmonthly\b|\bp\.?m\.?(?=[\s,;)]|$)|a\s+month\b", re.I), 1.0),
    (re.compile(r"per\s*week|\bweekly\b", re.I), 52 / 12),
    (re.compile(r"per\s*(?:year|annum)|/\s*y(?:ea)?r\b|\bannual(?:ly)?\b|\bp\.a\.?(?=[\s,;)]|$)|\bpa(?=[\s,;)]|$)", re.I), 1 / 12),
    (re.compile(r"per\s*quarter|\bquarterly\b", re.I), 1 / 3),
    (re.compile(r"semi[- ]annual|per\s*6\s*months|every\s*6\s*months", re.I), 1 / 6),
]


def parse_amount(text) -> tuple[float | None, str | None]:
    """Return (amount, currency) from a raw price value or string."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return None, None
    if isinstance(text, (int, float, np.integer, np.floating)):
        return float(text), None
    s = str(text).replace("/=", " ").replace("\xa0", " ")
    currency = "USD" if USD_RE.search(s) else ("UGX" if re.search(r"ug|shs?|ush", s, re.I) else None)
    best = None
    for m in NUM_RE.finditer(s):
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        val = num * MULT.get(unit, 1)
        # Skip stray small numbers ("3 bedroom ... 450k"): keep the largest
        if best is None or val > best:
            best = val
    return best, currency


def rent_period_factor(*texts) -> float | None:
    """Monthly multiplier; None for nightly/daily short-stay listings.

    Texts are checked in order and the first one that states a period wins,
    so pass the portal's price-period field and the price string before the
    free-text title and description (a description mentioning "daily
    security" must not override a price quoted "per month")."""
    for t in texts:
        if t is None or t != t:
            continue
        for rx, factor in PERIODS:
            if rx.search(str(t)):
                return factor
    return 1.0  # Kampala rents are quoted monthly unless stated


@lru_cache(maxsize=1)
def _fx_table() -> pd.Series | None:
    path = p(load_config()["cleaning"]["fx_table"])
    if not path.exists():
        return None
    fx = pd.read_csv(path, dtype={"month": str})
    return fx.set_index("month")["usd_ugx"]


def usd_to_ugx(amount: float, date=None) -> float:
    fx = _fx_table()
    rate = load_config()["cleaning"]["usd_ugx_fallback"]
    if fx is not None and date is not None and date == date:
        month = str(pd.Timestamp(date).to_period("M"))
        rate = fx.get(month, rate)
    return amount * rate


def normalise_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Add price_ugx (sale), rent_month_ugx (rent), currency, flags."""
    out = df.copy()
    parsed = out["price_raw"].map(parse_amount)
    out["amount"] = parsed.map(lambda t: t[0])
    cur_from_text = parsed.map(lambda t: t[1])
    cur_field = out["currency_raw"].astype(str).str.upper().str.extract(r"(USD|UGX)")[0]
    # Text evidence of USD (e.g. "$1,200" in the price string) overrides a default field
    out["currency"] = np.where(cur_from_text == "USD", "USD", cur_field.fillna(cur_from_text).fillna("UGX"))
    # USD sanity: an "UGX" rent below 10,000 is almost surely USD mis-labelled
    tiny = (out["currency"] == "UGX") & (out["amount"] < 10_000) & (out["listing_type"] == "rent")
    out.loc[tiny, "currency"] = "USD"
    out["flag_currency_inferred"] = tiny

    date = pd.to_datetime(out["listing_date"].fillna(out["scraped_at"]), errors="coerce", utc=True)
    ugx = [usd_to_ugx(a, d) if c == "USD" and a == a else a
           for a, c, d in zip(out["amount"], out["currency"], date)]
    out["amount_ugx"] = ugx

    is_rent = out["listing_type"].eq("rent")
    factor = [rent_period_factor(pp, pr, t, d) if r else np.nan
              for pp, pr, t, d, r in zip(out["price_period"], out["price_raw"], out["title"],
                                         out["description"], is_rent)]
    out["rent_period_factor"] = factor
    out["flag_short_stay"] = is_rent & out["rent_period_factor"].isna()
    out["rent_month_ugx"] = np.where(is_rent, out["amount_ugx"] * out["rent_period_factor"], np.nan)
    out["price_ugx"] = np.where(out["listing_type"].eq("sale"), out["amount_ugx"], np.nan)

    text = (out["title"].fillna("") + " " + out["description"].fillna("")).str.lower()
    out["flag_negotiable"] = text.str.contains(r"negotiab|\bneg\b|\bnego\b", regex=True)
    out["flag_price_missing"] = out["amount"].isna() | text.str.contains("price on request|call for price")

    b = load_config()["cleaning"]["bounds"]
    out["flag_price_outlier"] = (
        (is_rent & ~out["rent_month_ugx"].between(*b["rent_month"]))
        | (out["listing_type"].eq("sale") & ~out["price_ugx"].between(*b["sale"]))
    ) & ~out["flag_price_missing"]
    return out
