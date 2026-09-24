import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIX = ROOT / "tests" / "fixtures"
# Saved portal pages contain third-party content and contact details, so they are
# kept out of version control; the fixture tests run only where they exist locally.
needs_fixture = pytest.mark.skipif(not FIX.exists(), reason="portal fixtures not in repository")

from gkma.clean.prices import parse_amount, rent_period_factor  # noqa: E402
from gkma.clean.text_features import classify_tenure, extract_features  # noqa: E402
from gkma.clean.units import parse_floor_m2, parse_plot_decimals  # noqa: E402
from gkma.collect import base, jiji, red, upc  # noqa: E402
from gkma.geo.gazetteer import match_place  # noqa: E402


@pytest.mark.parametrize("text,amount,cur", [
    ("Ugx 160,000,000/=", 160e6, "UGX"),
    ("UGX160M", 160e6, "UGX"),
    ("shs 1.2bn", 1.2e9, "UGX"),
    ("450k per month", 450e3, None),
    ("$250,000", 250e3, "USD"),
    ("USD 1,200 per month", 1200, "USD"),
    (1000000, 1e6, None),
])
def test_parse_amount(text, amount, cur):
    a, c = parse_amount(text)
    assert a == pytest.approx(amount)
    assert c == cur


def test_rent_periods():
    assert rent_period_factor("per month") == 1.0
    assert rent_period_factor("Ugx 12m per year") == pytest.approx(1 / 12)
    assert rent_period_factor("USD 80 per night") is None
    assert rent_period_factor(None, "3 bedroom house") == 1.0
    # regressions: "pa" inside words, and advance-payment phrases
    assert rent_period_factor("2 bedroom apartment with parking") == 1.0
    assert rent_period_factor("UGX 1.2m per month, 6 months advance") == 1.0
    assert rent_period_factor("UGX 1.2m, 3 months deposit") == 1.0
    assert rent_period_factor("USD 24,000 p.a.") == pytest.approx(1 / 12)
    # an explicit field beats free text that mentions "daily"
    assert rent_period_factor("per month", "Ugx 1,200,000/=", "2 bed", "security guard daily") == 1.0


@pytest.mark.parametrize("text,dec", [
    ("12 Decimals", 12), ("0.5 acres", 50), ("half an acre", 50),
    ("50x100 ft", 11.48), ("50 by 100", 11.48), ("100 x 100", 22.96),
    ("1 hectare", 247.1), ("two plots", 22.96),
])
def test_plot_decimals(text, dec):
    v, _ = parse_plot_decimals(text)
    assert v == pytest.approx(dec, rel=0.01)


def test_floor_area():
    assert parse_floor_m2("floor area 180 sqm") == 180
    assert parse_floor_m2("2,000 sq ft") == pytest.approx(185.8, rel=0.01)


@pytest.mark.parametrize("text,tenure,status", [
    ("Private Mailo", "mailo", "titled"),
    ("plot on kibanja, sale agreement", "kibanja", "untitled"),
    ("49 years lease title", "leasehold", "titled"),
    ("freehold land with ready title", "freehold", "titled"),
    ("ready title", "unknown", "titled"),
    ("title in process", "unknown", "title_pending"),
    ("nice house", "unknown", "unknown"),
])
def test_tenure(text, tenure, status):
    assert classify_tenure(text) == (tenure, status)


def test_text_features():
    df = base.to_frame([{
        "title": "3 bedroom self contained house with boys quarters", "description":
        "Gated estate, tarmac road, ready title, negotiable. Real estate agent.",
        "furnishing_raw": None, "tenure_raw": None, "bedrooms_raw": None, "bathrooms_raw": None}])
    f = extract_features(df).iloc[0]
    assert f.bedrooms == 3 and f.f_self_contained and f.f_boys_quarters and f.f_negotiable
    assert f.f_gated and f.f_tarmac_access and f.title_status == "titled"


def test_gazetteer():
    assert match_place("Kisaasi")[0] == "kisaasi"
    assert match_place("Standalone Kisaasi Ntinda Road")[1] in {"lookup_contains", "lookup_exact"}
    assert match_place("Najeera")[0] == "najjera"      # alias
    assert match_place("Xyzzy Hill")[0] is None


@needs_fixture
def test_jiji_fixture():
    ads = json.loads((FIX / "jiji_api.json").read_text())["adverts_list"]["adverts"]
    r = jiji.parse_advert(ads[0], "houses-apartments-for-rent")
    assert r["listing_type"] == "rent" and r["location_raw"] == "Kisaasi"
    assert r["price_raw"] == 1000000 and r["bedrooms_raw"] == 3
    assert jiji.parse_title("Furnished 1bdrm Apartment in Kyanja, Central Division for rent")["place"] == "Kyanja"


@needs_fixture
def test_red_fixture():
    r = red.parse_detail((FIX / "red_detail.html").read_text(encoding="utf-8"), "u")
    assert r["source_id"] == "233811" and r["district_raw"] == "Mukono"
    assert r["tenure_raw"] == "Private Mailo" and r["bedrooms_raw"] == 4
    assert r["listing_type"] == "sale" and r["listing_date"] is None  # page date is not the post date
    assert parse_amount(r["price_raw"])[0] == 160e6


@needs_fixture
def test_upc_fixture():
    url = "https://ugandapropertycentre.com/for-sale/houses/eastern-region/soroti/11184-4-bedroom-house-tile-floor"
    r = upc.parse_detail((FIX / "upc_detail.html").read_text(encoding="utf-8"), url)
    assert r["source_id"] == "11184" and r["listing_type"] == "sale"
    assert float(r["price_raw"]) == 300e6 and r["currency_raw"] == "UGX"
    assert r["bedrooms_raw"] == "4" and r["listing_date"] == "2026-09-21"
    assert upc.parse_url("https://x/for-rent/houses/central-region/wakiso/entebbe-municipality/11182-3-bedroom-house")["area"] == "entebbe-municipality"


def test_permission_gate():
    from gkma.config import load_config
    portals = load_config()["collection"]["portals"]
    portals["_test"] = {"permission": "not_granted", "consent_reference": ""}
    try:
        with pytest.raises(base.PermissionNotGranted):
            base.check_permission("_test")
        portals["_test"] = {"permission": "researcher_authorised", "consent_reference": ""}
        with pytest.raises(base.PermissionNotGranted):   # needs a dated note
            base.check_permission("_test")
    finally:
        portals.pop("_test")
    assert base.check_permission("jiji")


def test_price_units():
    from gkma.clean.units import apply_price_units, normalise_sizes
    df = base.to_frame([
        {"title": "Land 2 acres in Kira", "price_period": "per Plot", "price_raw": 20e6, "listing_type": "sale", "source": "jiji"},
        {"title": "Land Sell 100x50ft at 20m", "price_period": "per Plot", "price_raw": 20e6, "listing_type": "sale", "source": "jiji"},
        {"title": "5 acres Mukono", "price_period": "Outright Price", "price_raw": 5e8, "listing_type": "sale", "source": "jiji"},
    ])
    out = apply_price_units(normalise_sizes(df))
    assert list(out["price_unit"]) == ["per_plot", "per_plot", "total"]
    assert out["plot_decimals"].tolist() == pytest.approx([11.48, 11.48, 500], rel=0.01)


def test_property_type():
    from gkma.clean.text_features import classify_property_type
    df = pd.DataFrame({"property_type": [None, None, None, "Land"],
                       "title": ["3 bedroom house for sale", "Single room muzigo for rent",
                                 "2 bedroom apartment", "12 decimals plot"]})
    assert classify_property_type(df).tolist() == ["house", "room", "apartment", "land"]


def test_zero_plot_is_missing():
    from gkma.clean.units import normalise_sizes
    df = base.to_frame([{"title": "2 bedroom apartment", "size_raw": "0 Decimals", "source": "red"}])
    assert pd.isna(normalise_sizes(df)["plot_decimals"].iloc[0])
