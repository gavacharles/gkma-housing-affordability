import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gkma.clean.payment_terms import parse_terms, payment_terms  # noqa: E402


@pytest.mark.parametrize("text, adv, dep", [
    ("Self contained double room in Kyanja, 6 months advance required", 6, None),
    ("Rent 450k. Payment: 3 months upfront plus 1 month deposit", 3, 1),
    ("Minimum of six months payment", 6, None),
    ("pay 4 months", 4, None),
    ("Advance payment of 3 months only", 3, None),
    ("Rent paid quarterly, gated compound", 3, None),
    ("Payable half yearly", 6, None),
    ("USD 1,200 per month payable annually", 12, None),
    ("Two bedroom apartment in Ntinda with parking", None, None),
    ("Security deposit of two months, 3 months advance", 3, 2),
    ("3 (three) months in advance", 3, None),
    ("built 24 months ago", None, None),
])
def test_parse_terms(text, adv, dep):
    r = parse_terms(text)
    assert r["advance_months"] == adv
    assert r["deposit_months"] == dep


def test_payment_terms_frame():
    df = pd.DataFrame({"title": ["Single room", "Flat"], "description": ["6 months advance, 1 month deposit", "nice view"]})
    out = payment_terms(df)
    assert out.loc[0, "upfront_months"] == 7
    assert pd.isna(out.loc[1, "upfront_months"]) and out.loc[1, "terms_stated"] == 0
