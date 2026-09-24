"""Cross-post and re-post detection.

Agents re-post the same unit on one portal and cross-post on several.
Candidate pairs are blocked on (listing_type, property class, bedrooms,
resolved place), then linked when prices agree within a tolerance AND the
titles/descriptions are similar, or when the same agent posts an identical
price in the same place. Linked records form clusters (union-find); one
representative per cluster is kept and n_postings is retained as a
variable (heavily re-posted units may be harder to let/sell).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from gkma.config import load_config


class _UF:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a: int, b: int) -> None:
        self.p[self.find(a)] = self.find(b)


def _completeness(df: pd.DataFrame) -> pd.Series:
    cols = ["bedrooms", "bathrooms", "plot_decimals", "tenure_class", "description", "lat"]
    score = sum(df[c].notna().astype(int) for c in cols if c in df)
    if "tenure_class" in df:
        score = score - df["tenure_class"].eq("unknown").astype(int)
    return score


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()["cleaning"]["dedup"]
    tol, sim_min = cfg["price_tolerance"], cfg["title_similarity"]
    d = df.reset_index(drop=True).copy()
    d["_price"] = d["rent_month_ugx"].fillna(d["price_ugx"])
    # Compare descriptions where both exist: RED titles are generated from a
    # template ("2 bedroom Apartment for rent in Namugongo ...") and cannot tell
    # two units apart. Fall back to the title only when a description is missing.
    desc = d["description"].fillna("").str[:400].str.lower()
    d["_text"] = desc.where(desc.str.len() >= 40, d["title"].fillna("").str.lower())
    d["_place"] = d.get("place_id", d["location_raw"]).fillna(d["location_raw"]).astype(str).str.lower()
    d["_beds"] = d["bedrooms"].fillna(-1)

    uf = _UF(len(d))
    # Exact same portal id: always the same listing (repeated snapshots)
    for _, idx in d.groupby(["source", "source_id"]).groups.items():
        idx = list(idx)
        for j in idx[1:]:
            uf.union(idx[0], j)

    for _, g in d.groupby(["listing_type", "ptype", "_beds", "_place"], dropna=False):
        if len(g) < 2:
            continue
        rows = g.sort_values("_price")
        ix, price = rows.index.to_numpy(), rows["_price"].to_numpy()
        text, agent = rows["_text"].to_numpy(), rows["agent_key"].to_numpy()
        for a in range(len(rows)):
            for b in range(a + 1, len(rows)):
                pa, pb = price[a], price[b]
                if not (pa == pa and pb == pb) or pb > pa * (1 + tol):
                    break  # sorted by price: nothing further can match
                same_agent = agent[a] is not None and agent[a] == agent[b]
                same_price = abs(pb - pa) <= 1e-3 * pa
                if (same_agent and same_price and fuzz.token_sort_ratio(text[a], text[b]) >= 60) \
                        or fuzz.token_sort_ratio(text[a], text[b]) >= sim_min:
                    uf.union(ix[a], ix[b])

    d["dup_cluster"] = [uf.find(i) for i in range(len(d))]
    d["n_postings"] = d.groupby("dup_cluster")["dup_cluster"].transform("size")
    d["n_portals"] = d.groupby("dup_cluster")["source"].transform("nunique")
    d["first_seen"] = d.groupby("dup_cluster")["scraped_at"].transform("min")
    d["_score"] = _completeness(d)
    keep = d.sort_values(["dup_cluster", "_score", "scraped_at"], ascending=[True, False, False]) \
            .drop_duplicates("dup_cluster")
    return keep.drop(columns=[c for c in keep if c.startswith("_")]).reset_index(drop=True)


def dedup_report(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    rep = pd.DataFrame({
        "records_in": before.groupby("source").size(),
        "unique_out": after.groupby("source").size(),
    }).fillna(0).astype(int)
    rep["share_duplicate"] = 1 - rep["unique_out"] / rep["records_in"]
    rep.loc["all"] = [len(before), len(after), 1 - len(after) / max(len(before), 1)]
    return rep
