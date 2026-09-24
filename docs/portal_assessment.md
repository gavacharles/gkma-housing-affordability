# Listing portals: access assessment (checked 22 September 2026)

This note records what each portal allows. Keep it with the ethics application and cite it in the paper's data section.

## Summary

| Portal | Scale (22 Sep 2026) | Structured fields | Terms on automated copying | Route |
|---|---|---|---|---|
| **Jiji.ug** | ~945 rentals nationally; houses for sale and land in separate categories | Price, period ("per month", "per Plot", "Outright Price"), bedrooms, bathrooms, "property size" (sqm), furnishing, listed-by, region | No clause against scraping. Rules §7.14 bans only software that interferes with the platform. robots.txt blocks only /test, /admin, /crm and Facebook auth for all agents | **Collect** through the public listing API at ≥4 s per request with a contact User-Agent. Optional courtesy email to support@jiji.ug |
| **Real Estate Database (RED)** – realestatedatabase.net | ~24,000 listing URLs in the sitemap (includes expired ones) | Location, district, price, category, bedrooms, bathrooms, size (decimals), **tenure** (e.g. "Private Mailo"), status, post date | Terms (Zillion Technologies Ltd) forbid copying, publishing or distributing content without consent. The XML/CSV feed sits under /FindAHouseOld/, which robots.txt disallows | **Request a research extract.** Contact: info@RealEstateDatabase.net, +256 705 162000 (Julius), Plot 24 Sir Apollo Kaggwa Rd, Bifro House |
| **Lamudi.co.ug** | Same database as RED | Same as RED | Same as RED | **Not a separate source.** lamudi.co.ug runs on RED's platform (identical robots.txt, shared HouseCode ids). Collecting both would double-count |
| **Uganda Property Centre (UPC)** | ~1,020 live listings nationally | schema.org JSON-LD (price, currency, datePosted). The URL encodes deal / type / region / district / area | Terms (Dilmak Solutions Ventures Ltd) say: "not to use any automated software to view the Services without consent", "not to attempt to copy our data … without our consent" | **Request consent** through ugandapropertycentre.com/contact-us. Their quarterly market reports and average-price pages can be **cited** as an external benchmark |

## Data problems found in the pilot sample (use in the paper)

1. **Portal admin labels are wrong.** Jiji tags Kisaasi, Ntinda and Kyanja as "Central Division", but they are in Nakawa Division. The workflow takes location from the listing title and text through the gazetteer, and uses the portal's region field only outside Kampala.
2. **"Property size" is ambiguous.** On Jiji a 1-bedroom house can show "900 sqm", which is plot area or noise. It is kept as `portal_size_sqm` and never used as floor area.
3. **Land priced per plot.** About 1 in 5 Jiji land ads is priced "per Plot" (50×100 ft ≈ 11.5 decimals), not for the whole parcel. `price_unit` records this, and the priced area is set to one plot.
4. **Re-posting.** The same furnished Kyanja apartment appeared four times on one results page. `dedup.py` clusters re-posts and keeps `n_postings` as a variable.
5. **Out-of-area listings.** About 10% of "Uganda" listings are outside GKMA (Lira, Mbarara, Jinja). They are dropped by the study-area filter.
6. **Size units** seen: "12 Decimals", "50x100ft", "50 by 100", "50*60ft", "100x50ft", "1 Acre", "4acres", "25 to 60" (a range).

## Decision log

- **2026-09-23, RED:** at the researcher's instruction, collection from RED's public detail pages started while written consent is sought (`permission: researcher_authorised` in config.yaml). Safeguards: only paths robots.txt allows (the /FindAHouseOld/ feed is never touched); one request every 4 s plus page load, about 10 pages a minute; newest-first, stopping at listings posted before 2025-10-01; phone numbers and emails redacted from text; agent names stored only as a hash; no photos. Output: `data/raw/red/red_crawl.csv`.

- **2026-09-23, Jiji (full) and UPC:** at the researcher's instruction, full collection of Jiji (public API; terms permit) and Uganda Property Centre (`permission: researcher_authorised`; written consent being sought). Same safeguards as RED: robots.txt respected, 4 s between requests, personal data redacted or hashed. Lamudi is not crawled separately because it serves RED's database.

## Recommended data strategy

1. **Jiji:** automated weekly snapshots over the fixed window (e.g. 1 Oct – 31 Dec 2026). Jiji is the best source for the lower and middle rental market.
2. **RED:** send the letter (docs/letter_template.md), asking for an extract with coordinates if RED stores them. RED is the only source with tenure as a field, which makes it essential for the title-premium result.
3. **UPC:** send the letter. If UPC declines, use its published market reports only as a validation benchmark.
4. **Fallback:** a documented manual sample. Run `python scripts/01_collect.py --manual` for the template, record listings by hand, and save them in `data/raw/manual/`.

Record each permission decision in `config.yaml` (`permission`, `consent_reference`). Collectors refuse to run without one.
