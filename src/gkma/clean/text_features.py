"""Tenure classification and rule-based feature extraction from free text.

Rules are deliberately transparent (regex + a documented lexicon) so the
extraction can be audited and its precision/recall reported against a hand-
labelled sample (see scripts/validate_text_extraction.py). An optional
transformer/LLM pass can be benchmarked against these rules later.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Tenure. Uganda has four legal tenure systems (Constitution Art. 237; Land
# Act Cap 227): customary, freehold, mailo, leasehold. "Kibanja" is a
# lawful/bona fide occupancy interest on mailo land, usually unregistered.
# Order matters: the first matching rule wins.
# ---------------------------------------------------------------------------
TENURE_RULES = [
    ("kibanja", r"\bkibanja\b|\bbibanja\b|sale agreement only|\bno title\b|untitled"),
    ("mailo", r"\bmailo\b|\bmailo land\b"),
    ("leasehold", r"\blease\s*hold\b|\bleasehold\b|\blease title\b|\b(49|99)\s*(yr|year)s?\s*lease|\bkcca lease\b|\bulc lease\b"),
    ("freehold", r"\bfree\s*hold\b|\bfreehold\b"),
    ("customary", r"\bcustomary\b|certificate of customary ownership|\bcco\b"),
]
TITLE_EVIDENCE = r"\btitled?\b|ready title|clean title|land title|with title|title deed|certificate of title"
TITLE_PENDING = r"title (in|under) process|processing title|title pending|awaiting title"


def classify_tenure(*texts) -> tuple[str, str]:
    """Return (tenure_class, title_status)."""
    blob = " ".join(str(t) for t in texts if t is not None and t == t).lower()
    tenure = "unknown"
    for name, rx in TENURE_RULES:
        if re.search(rx, blob):
            tenure = name
            break
    if tenure == "kibanja":
        status = "untitled"
    elif re.search(TITLE_PENDING, blob):
        status = "title_pending"
    elif re.search(TITLE_EVIDENCE, blob) or tenure in {"mailo", "freehold", "leasehold"}:
        status = "titled"
    else:
        status = "unknown"
    return tenure, status


# ---------------------------------------------------------------------------
# Binary features from description text. Each entry: column -> regex.
# ---------------------------------------------------------------------------
FEATURES = {
    "self_contained": r"self[\s-]?contain|\bs/?c\b|en[\s-]?suite",
    "boys_quarters": r"boys?'?\s*quarters?|\bbq\b|servants?'?\s*quarters?",
    "negotiable": r"negotiab|\bneg\b|\bnego\b",
    "furnished": r"(?<!un)furnished|fully furnished",
    "gated": r"gated|(?<!real )\bestate\b|compound wall|perimeter wall|walled|fenced",
    "security": r"security|guard|askari|cctv|electric fence",
    "parking": r"parking|garage|car\s*park",
    "tarmac_access": r"tarmac|paved road|main road|off .{0,25} road|along .{0,25} road",
    "pool": r"swimming pool|\bpool\b",
    "water_tank": r"water tank|reservoir|borehole",
    "backup_power": r"generator|standby power|solar|inverter",
    "lake_view": r"lake view|lakeview|view of (?:the )?lake",
    "storeyed": r"storey|storied|story(?:ed)?|duplex|mansion|maisonette",
    "bungalow": r"bungalow",
    "apartment": r"apartment|flat\b|condominium|condo\b",
    "shell_or_incomplete": r"\bshell\b|incomplete|unfinished|lock[\s-]?up|roofing level|wall plate",
    "tiled": r"\btiled?\b|tiles",
    "mortgage_available": r"mortgage|bank financing|installments?|instalments?|payment plan",
    "muzigo": r"\bmuzigo\b|mizigo|single room|double room|\bbedsitter\b|\bbed[\s-]?sitter\b",
    "commercial_use": r"commercial|shops?\b|arcade|warehouse|office space",
}
_COMPILED = {k: re.compile(v, re.I) for k, v in FEATURES.items()}

WORD_NUM = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten".split())}
BED_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[-]?\s*(?:bed(?:room)?s?|bdrms?|br\b|bedroomed)", re.I)
BATH_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six)\s*[-]?\s*(?:bath(?:room)?s?|toilets?)", re.I)


def _num(tok: str | None):
    if tok is None:
        return np.nan
    tok = tok.lower()
    return float(WORD_NUM.get(tok, tok)) if (tok.isdigit() or tok in WORD_NUM) else np.nan


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    text = (out["title"].fillna("") + " . " + out["description"].fillna("")).str.lower()

    for col, rx in _COMPILED.items():
        out[f"f_{col}"] = text.str.contains(rx).astype("int8")
    # "unfurnished" should not count as furnished; the portal field overrides text
    fur = out["furnishing_raw"].fillna("").str.lower()
    out.loc[fur.str.startswith("unfurn"), "f_furnished"] = 0
    out.loc[fur.str.startswith("furn"), "f_furnished"] = 1

    ten = [classify_tenure(t, d, tr) for t, d, tr in zip(out["title"], out["description"], out["tenure_raw"])]
    out["tenure_class"] = [t[0] for t in ten]
    out["title_status"] = [t[1] for t in ten]
    # Structured tenure field (RED) beats text inference when present
    has_field = out["tenure_raw"].notna() & out["tenure_raw"].astype(str).str.strip().ne("")
    field_cls = out["tenure_raw"].where(has_field).map(lambda x: classify_tenure(x)[0] if x == x else "unknown")
    out.loc[field_cls.ne("unknown"), "tenure_class"] = field_cls
    out["tenure_source"] = np.where(has_field, "portal_field", np.where(out["tenure_class"].ne("unknown"), "text", "none"))

    beds = pd.to_numeric(out["bedrooms_raw"].map(lambda v: WORD_NUM.get(str(v).lower(), v)), errors="coerce")
    beds_txt = text.map(lambda s: _num(m.group(1)) if (m := BED_RE.search(s)) else np.nan)
    out["bedrooms"] = beds.fillna(beds_txt)
    out["bedrooms_source"] = np.where(beds.notna(), "portal_field", np.where(beds_txt.notna(), "text", "none"))
    baths = pd.to_numeric(out["bathrooms_raw"], errors="coerce")
    out["bathrooms"] = baths.fillna(text.map(lambda s: _num(m.group(1)) if (m := BATH_RE.search(s)) else np.nan))
    # Muzigo / single rooms: count as half a bedroom so per-bedroom rent is defined
    out.loc[out["bedrooms"].isna() & out["f_muzigo"].eq(1), "bedrooms"] = 0.5
    out["flag_bedrooms_implausible"] = out["bedrooms"] > 15
    # Data-entry errors (e.g. "520 bathrooms"): impossible counts become missing
    out.loc[out["bedrooms"] > 15, "bedrooms"] = np.nan
    out.loc[out["bathrooms"] > 15, "bathrooms"] = np.nan
    return out


def classify_property_type(df: pd.DataFrame) -> pd.Series:
    """Harmonised type: land | apartment | house | commercial | room."""
    blob = (df["property_type"].fillna("") + " " + df["title"].fillna("")).str.lower()
    conds = [
        blob.str.contains(r"land|plot|acre|decimal"),
        blob.str.contains(r"muzigo|single room|double room|bed[- ]?sitter|\broom\b|\brooms for rent"),
        blob.str.contains(r"commercial|office|shop|warehouse|hotel|arcade"),
        blob.str.contains(r"apartment|flat|condo"),
    ]
    return pd.Series(np.select(conds, ["land", "room", "commercial", "apartment"], default="house"),
                     index=df.index)
