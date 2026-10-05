"""Upfront payment terms in rental listing text.

Kampala landlords commonly ask for several months' rent in advance, sometimes with a
separate security deposit. This module reads those terms from the title and description:

  advance_months   months of rent asked up front ("6 months advance", "pay 3 months",
                   "minimum of 6 months", "rent paid quarterly" = 3, "half year" = 6,
                   "per annum / yearly payment" = 12)
  deposit_months   a security deposit stated in months ("1 month deposit")
  terms_stated     1 if any upfront term was found

Numbers may be digits or words ("six months"). A stated amount wins over a payment
frequency. Values above 12 months are treated as noise.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "a": 1}
NUM = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
ADVANCE = [
    re.compile(rf"\b{NUM}\s*(?:\([a-z0-9]+\)\s*)?months?\s*(?:rent\s*)?(?:in\s*)?(?:advance|upfront|up\s*front|prepay)", re.I),
    re.compile(rf"(?:advance|upfront|up\s*front)\s*(?:payment\s*)?(?:of\s*)?{NUM}\s*months?", re.I),
    re.compile(rf"(?:pay|payment|paid|minimum(?:\s*of)?|min\.?|at\s*least)\s*(?:of\s*)?{NUM}\s*months?(?!\s*deposit)", re.I),
    re.compile(rf"\b{NUM}\s*months?\s*(?:payment|minimum|required)", re.I),
]
FREQ = [(re.compile(r"\b(?:paid|payable|payment)?\s*quarterly\b|per\s*quarter|every\s*3\s*months", re.I), 3),
        (re.compile(r"half[\s-]*(?:a\s*)?year(?:ly)?|bi[\s-]*annual(?:ly)?|semi[\s-]*annual(?:ly)?|every\s*6\s*months", re.I), 6),
        (re.compile(r"\b(?:paid|payable|payment)\s*(?:annually|yearly)\b|per\s*annum\b|per\s*year\b", re.I), 12)]
DEPOSIT = re.compile(rf"\b{NUM}\s*months?\s*(?:security\s*)?deposit|(?:security\s*)?deposit\s*(?:of\s*)?{NUM}\s*months?", re.I)


def _n(tok: str | None) -> int | None:
    if not tok:
        return None
    tok = tok.lower()
    v = int(tok) if tok.isdigit() else WORDS.get(tok)
    return v if v and 1 <= v <= 12 else None


def parse_terms(text: str | None) -> dict:
    t = str(text or "")
    adv = None
    for rx in ADVANCE:
        hits = [_n(m.group(1)) for m in rx.finditer(t)]
        hits = [h for h in hits if h]
        if hits:
            adv = max(hits)
            break
    if adv is None:
        for rx, v in FREQ:
            if rx.search(t):
                adv = v
                break
    dep = None
    for m in DEPOSIT.finditer(t):
        dep = _n(m.group(1) or m.group(2))
        if dep:
            break
    return {"advance_months": adv, "deposit_months": dep, "terms_stated": int(adv is not None or dep is not None)}


def payment_terms(df: pd.DataFrame) -> pd.DataFrame:
    text = df.get("title", pd.Series("", index=df.index)).fillna("") + " . " + \
        df.get("description", pd.Series("", index=df.index)).fillna("")
    out = pd.DataFrame([parse_terms(x) for x in text], index=df.index)
    out["upfront_months"] = out["advance_months"].fillna(1) + out["deposit_months"].fillna(0)
    out.loc[out["terms_stated"] == 0, "upfront_months"] = np.nan
    return out
