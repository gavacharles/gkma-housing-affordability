# Paper 2 — Paying for access in a paratransit city

**Working title:** Paying for access in a paratransit city: road accessibility, the Entebbe Expressway and housing prices in Greater Kampala

**Target journals:** Journal of Transport Geography; Cities; Transport Policy; Land Use Policy (check current quartiles).

**Status (25 September 2026):** framing adopted. The original transit-capitalisation plan is kept below for reference; the feasibility findings explain the change.

This paper reuses the shared pipeline at the project root: listing collection, cleaning, deduplication, geocoding, census and income data, and the OpenStreetMap layers. Paper-specific scripts go in `scripts/` (start each with `import _paper`), results in `outputs/`, and the manuscript in `docs/manuscript/`.

## Adopted design

**Framing.** In Greater Kampala most trips are made by minibus taxi and boda-boda on the road network, and the commuter rail runs four trips a day between Kampala, Namanve and Mukono (URC schedule, https://urc.go.ug/schedules/). The transport variable that can shape housing prices is therefore access by road. The tolled, limited-access Entebbe Expressway and the open Northern Bypass provide the central contrast; rail enters as a value-capture scenario.

**Research questions**
1. Is road-network accessibility — travel time to the CBD and access to jobs — priced into rents and sale prices?
2. Is a tolled, limited-access expressway priced differently from an open bypass, and does the premium follow access to its interchanges?
3. How do these effects differ between rents and sales, and across the city?
4. What do the estimates imply for affordability and for value capture on the Expressway and on future rail or bus rapid transit corridors?

**Data**

| Layer | Source | Script |
|---|---|---|
| Listings (10,643) | Shared pipeline, paper-1 snapshot | — |
| Road network, Expressway and Bypass access points | OpenStreetMap | `01_accessibility.py` |
| Commuter-rail stations | URC schedule (Kampala, Namanve, Mukono); OSM station nodes; Mukono located approximately on the line | `data/external/rail/urc_commuter_stations.gpkg` |
| Jobs | UBOS COBE 2019/20 sub-region totals split by COBE 2010/11 division and district shares | `00_jobs_totals.py` |
| Building footprints | Microsoft Global Building Footprints (2026 release) | download in `data/external/buildings/ms/` |
| Economic activity | NASA Black Marble night lights 2024 (shared) | — |

**Accessibility measures.** Network travel time (congested speeds by road class, with sensitivity runs) to the CBD, Expressway and Bypass access points and stations; cumulative access to jobs within 30/45/60 minutes, with jobs allocated within each division or district by building footprint area and, as alternatives, by night lights or both.

**Models.** Hedonic OLS clustered by neighbourhood point; spatial Durbin model; multiscale GWR; gradient-boosting with SHAP as a comparison. Robustness: speed assumptions, jobs-allocation variants, distance bands, placebo corridors, listing-quality filters, and controls for the Entebbe Road corridor's affluence.

## Original plan (superseded)


### 1. Introduction
Most studies of how transit access is priced into property values come from the Global North and China. They assume formal transit and formal housing markets. Greater Kampala has neither in the usual sense: a nascent commuter rail service, a transport system dominated by minibus taxis and boda-bodas, and a largely informal rental market.

Research questions:
1. Is proximity to rail stations and taxi corridors priced into rents and sale prices?
2. Does the effect differ between formal and informal submarkets, or between rents and sales?
3. What does this mean for affordability, and for value-capture financing of future rail?

### 2. Literature
Hedonic studies of transit capitalisation and their meta-analyses; research on paratransit in African cities; the affordability framing from paper 1 and the wider HAFE work.

### 3. Study area and data
- **Listings:** the shared, cleaned and deduplicated GKMA dataset.
- **Transit layers:** commuter-rail stations, main taxi stages and routes (OpenStreetMap or digitised maps), and the road network.
- **Controls:** property attributes, neighbourhood amenities, flood exposure, distance to the CBD, and building density (Google Open Buildings).

### 4. Methods
- **Accessibility:** network travel time to the nearest station or stage; cumulative-opportunity access to jobs within travel-time isochrones.
- **Models:** baseline hedonic OLS; a spatial Durbin model; multiscale GWR for effects that vary by place; random forest or XGBoost with SHAP as a comparison.
- **Robustness:** distance bands, placebo stations, listing-quality filters.
- **Identification:** cross-sectional, so the paper claims association, not causation. A difference-in-differences design becomes possible with listings from before and after a rail service change.

### 5. Results
Capitalisation estimates; maps of where effects vary; rents versus sales. Travel-time isochrones and an animated accessibility surface go in the supplement.

### 6. Discussion
- Transit premiums and affordability, including displacement risk around new stations.
- Value capture as a way to finance the SGR and commuter-rail expansion.
- How listings lean towards the formal, upper-market segment, and what that means for the findings.

### 7. Conclusion and policy

### How the two papers relate
They share one spatial pipeline (geocoding, the OpenStreetMap network, animation), so building it once serves both.

## What the shared pipeline already provides (checked 25 September 2026)

| Need | Status |
|---|---|
| Cleaned listings | 10,643 listings (paper-1 snapshot); the RED crawl is still running and can extend this |
| Distance to taxi stages | Yes: `dist_taxi_stage_km`, `n_taxi_stage_1km` (224 OpenStreetMap taxi stages) |
| Roads and corridors | Yes: major roads, Northern Bypass, Entebbe Expressway distances; OSM road layer |
| Controls | Yes: CBD distance, amenities, wetlands (flood proxy), night lights, Census 2024 wealth index |
| Rail stations | **Not yet** — needs OpenStreetMap stations or digitising the Uganda Railways commuter stops |
| Taxi routes | **Not yet** — OSM has stages, not routes; routes need digitising or another source |
| Network travel times, isochrones | **Not yet** — needs a routable network (osmnx is installed) |
| Jobs data for accessibility | **Not yet** — needs a source (e.g. UBOS business census, or a proxy such as building density) |
| Building density | **Not yet** — Google Open Buildings download |

## Issues to settle before designing the analysis

1. **Location precision.** Listings are located to 187 neighbourhood points, not addresses; no portal gives coordinates. Capitalisation studies usually look at 400–800 m distance bands around stations. At neighbourhood resolution the paper can estimate neighbourhood-level access effects, but not within-neighbourhood gradients. Options: coarser bands (e.g. within 1, 1–2, 2–5 km), neighbourhood-level models, or a source with exact coordinates.
2. **The informal submarket.** The listings are almost entirely formal: 15 kibanja plots, 21 untitled houses, and only 16 rentals described as single rooms or room-and-parlour. Research question 2 needs either a different comparison (e.g. lower- versus upper-priced listings, Jiji versus RED) or an additional data source on informal rents.
3. **Rail coverage.** The commuter service has few stations, so the number of listings near a station may be small; this needs counting once stations are mapped.
4. **Time.** One cross-section (2025–26). The continuing RED crawl could support a later before–after comparison if a rail service change falls within the collection period.

## Feasibility findings (25 September 2026)

**Rail capitalisation is not identifiable with these data.** OpenStreetMap maps four stations (Kampala, Namboole, Namanve, one unnamed stop). No listing lies within 500 m of a station; 98 listings (14 rentals) lie within 1 km, on only 2 neighbourhood points; within 2 km there are 15 points, and the main station sits in the CBD, so any station effect is confounded with CBD access. The taxi-stage layer (224 points) mixes taxi parks, bus stations and 92 bus stops, and OSM coverage of Kampala taxi stages is incomplete.

**Road-network accessibility is measurable** (`scripts/01_accessibility.py` → `outputs/tables/neighbourhood_accessibility.csv`): travel time from each of the 187 neighbourhood points to the CBD, to the 12 Entebbe Expressway and 37 Northern Bypass access points, and to the mapped stations, plus night-light activity reachable within 30/45/60 minutes, on a 55,884-node road graph with assumed congested speeds.

**First look** (`scripts/02_first_look.py` → `outputs/tables/first_look.csv`; clustered by neighbourhood point, 110–123 points):
- Travel time to Expressway access points is priced into sale prices (elasticity −0.36, p < 0.01, with the wealth control) and, unlike straight-line distance, also into rents (−0.25, p < 0.05).
- Travel time to the CBD is priced into rents (−0.38, p < 0.01). The Northern Bypass shows no premium.
- Activity access (night lights within 60 min) adds nothing beyond CBD travel time: the two correlate at −0.84 to −0.94 in this monocentric city.
- Whether the Expressway premium runs through its access points rather than proximity to the road cannot be separated: time and distance correlate at 0.83–0.89 across the neighbourhood points.

## Proposed reframing

**Paying for access in a paratransit city: road accessibility, the Entebbe Expressway and housing prices in Greater Kampala.** Access by road (the network that taxis and boda-bodas use) replaces rail-station proximity; the tolled, limited-access Expressway against the open Northern Bypass becomes the central comparison; rail enters as a value-capture scenario rather than an estimated effect.

Open decisions: (1) adopt the reframing; (2) confirm the commuter-rail stops from Uganda Railways' timetable; (3) choose the jobs proxy (night lights now; building footprints or a business census if available); (4) handle the Entebbe Road corridor, a high-value area on its own (paper 1 LISA), so the Expressway effect is not simply the corridor's affluence.

## Progress (25 September 2026)

- **Rail:** URC's schedule lists one commuter service, Kampala–Namanve–Mukono, four trips a day; no intermediate stops are named. `data/external/rail/urc_commuter_stations.gpkg` holds Kampala and Namanve (OSM), Mukono (approximate: the point on the railway nearest Mukono town centre, 2.7 km from it; to be confirmed), and Namboole (in OSM, not on the schedule).
- **Jobs:** `data/external/ubos/cobe/cobe_employment_gkma.csv` — 1,409,073 jobs in GKMA units (Central Division 428,236; Wakiso 307,505), from COBE 2019/20 totals and 2010/11 shares.
- **Buildings:** 1,461,188 Microsoft footprints (149.6 km²) summed on the night-light grid (`data/external/buildings/building_grid.tif`).
- **Job access:** jobs reachable in 30/45/60 minutes, three allocation variants, added to `neighbourhood_accessibility.csv`.

**Findings so far**
- Job access is almost the same variable as travel time to the CBD (Spearman −0.93 to −0.95), and the three allocation variants agree (0.994). In this monocentric city, "access to jobs" and "access to the centre" cannot be separated; the proxy choice does not change results.
- Travel time to Expressway access points is priced into rents (about −0.48) and sale prices (about −0.34), p < 0.01 in every variant, with job access and the wealth index controlled. The Northern Bypass is not priced.

**Next steps**
1. Separate the Expressway effect from the Entebbe Road corridor's affluence: control for access to the old Entebbe Road, compare neighbourhoods with similar CBD travel times but different Expressway access, and run placebo corridors.
2. Speed-assumption sensitivity (`--speed-scale 0.7` and `1.3`).
3. Spatial Durbin model and MGWR at neighbourhood level; rents versus sales.
4. Value-capture illustration: land-value uplift implied by the Expressway estimates, compared with toll revenue.

## Corridor tests and the before–after design (25 September 2026)

**Corridor confounding** (`scripts/03_corridor.py` → `outputs/tables/corridor_models.csv`, `corridor_placebo.csv`):
- Adding distance to the old Entebbe Road removes the Expressway effect (rents −0.25 → +0.12; sales −0.36 → 0.00); the old road takes it over (sales −0.30, p < 0.05).
- Placebo radials (Jinja, Bombo/Gulu, Gayaza, Hoima, Masaka, Fort Portal roads) carry no premium, and the Expressway term stays significant beside each of them — except beside the Entebbe Road.
- Within sectors around the CBD (8 wedges) the Expressway term remains significant (rents −1.05, sales −0.23; with CBD-time bands −0.61 and −0.30).
- The two roads run about 2 km apart; their distances correlate at 0.79 across neighbourhood points, and only 32 points lie within 5 km of the Expressway.
- Conclusion: the premium is real and specific to the south-western Entebbe corridor, but a cross-section cannot tell the Expressway (2018) from the old Entebbe Road.
- Speed assumptions do not matter: results are the same with speeds 30% lower or higher (`corridor_models_speed0.7.csv`, `_speed1.3.csv`).

**Before–after design (in progress).** The Internet Archive holds 7,860 distinct RED listing pages captured in 2017 — before the Expressway opened in June 2018 — and about 8,600 (2020) and 25,000 (2021) afterwards. The 2017 pages parse cleanly (location, district, bedrooms, type, rent or price, furnishing, description): `src/gkma/collect/red_archive.py`, `scripts/00_collect_archive.py` → `data/raw/red_archive/`. Collection runs at one page every 1.5 s.

Planned specification: log price on neighbourhood fixed effects (absorbing each area's fixed affluence, including the Entebbe Road corridor's), period effects, and period × Expressway access, with hedonic controls, RED listings only for comparability across periods, prices deflated by CPI. The Expressway effect is identified from how prices changed near its access points after opening, relative to other corridors.

**Commuter-rail termini (URC, checked 25 September 2026).** URC's passenger-services page: "URC currently operates passenger trains between Kampala to Mukono." Termini are Kampala and Mukono; Namanve is the turn-back point for the shorter trips. The two URC pages give different times (schedules page: 06:30, 08:15, 17:30, 19:30; passenger-services page: 06:40, 07:45, 17:30, 18:50) — four trips a day either way. Neither page, nor OpenStreetMap, gives the location of Mukono station; it stays approximate in `urc_commuter_stations.gpkg` (32.7626 E, 0.3293 N, on the line nearest Mukono town). Sources: https://urc.go.ug/schedules/, https://urc.go.ug/service/passenger-services/

## Archive cleaning and a first before–after estimate (25 September 2026, evening)

- 2021 dropped: the "after" periods are 2020 (archive) and 2025–26 (current data). Collection continues for 2017, then 2020.
- `scripts/01_clean_archive.py` maps archived pages to the shared raw schema and runs the shared cleaning pipeline unchanged (`gkma.clean.pipeline.run` now accepts supplied raw records). First 2,359 archived 2017 records (captured April–June 2017) → 2,175 clean listings, all located (98% exact gazetteer matches), on 42 neighbourhood points; 41 of these are also in the current RED data. Median 1–2 bedroom rent 2017: UGX 700,000.
- Treatment coverage: 8 shared points within 15 minutes of an Expressway access point (222 listings in 2017, 346 in 2025–26); 33 comparison points.

**Preliminary estimate** (RED only; neighbourhood-point fixed effects; hedonic controls; clustered by point; partial 2017 sample):

| | Post × within 15 min of Expressway access | Post × ln travel time to access |
|---|---|---|
| Sale prices | +0.313 (se 0.071, p < 0.001) ≈ +37% | −0.268 (se 0.101, p = 0.008) |
| Rents | +0.076 (se 0.213, p = 0.72) | −0.008 (p = 0.97) |

Caveats before this is a result: only 8 treated points (inference needs a wild cluster bootstrap), 2017 sample still partial, listing mix differs between periods, and 2020 is needed to check that the change came after opening rather than before.

## Full 2017 archive and the before–after estimate (26 September 2026)

- 2017 archive complete: 7,860 pages (99.7% parsed; captured April–November 2017) → 7,202 clean listings at 104 neighbourhood points (`data/processed/listings_archive_2017.gpkg`). 2020 archive (8,513 pages) collecting.
- `scripts/04_did.py` → `outputs/tables/did_results.csv`: RED listings, points present before and after, point and period fixed effects, hedonic controls; cluster-robust t and wild cluster bootstrap p-values (null imposed, Webb weights, 1,999 draws).

| 2017 → 2025–26 | Estimate | Cluster t | Wild bootstrap p | Points (treated) |
|---|---|---|---|---|
| Sales: within 15 min of Expressway access | +0.280 (≈ +32%) | 3.24 | 0.076 | 77 (11) |
| Sales: log travel time to access | −0.195 | −3.12 | 0.031 | 77 |
| Rents: within 15 min | +0.018 | 0.10 | 0.878 | 67 (7) |
| Rents: log travel time | −0.027 | −0.16 | 0.884 | 67 |

Sale prices rose more near the Expressway's access points after it opened; rents did not. Next: add 2020 (does the change appear after opening, and is it already there by 2020?), check pre-2017 trends are not available (no earlier archive), and test sensitivity to the 15-minute threshold and to listing mix.

## Complete current data (26 September 2026)

- `scripts/01_clean_current.py`: all raw snapshots including the full RED crawl → `data/processed/listings_current_full.gpkg`, 20,389 listings (15,775 RED) at 219 neighbourhood points (27,421 raw records). Paper 1's frozen dataset is unchanged.
- Accessibility recomputed for all 235 neighbourhood points used in paper 2 (current + archives).
- DiD, 2017 → 2025–26 with the full current RED data (`outputs/tables/did_results.csv`):

| | Estimate | Cluster t | Wild bootstrap p | Points (treated) |
|---|---|---|---|---|
| Sales: within 15 min of Expressway access | +0.231 (≈ +26%) | 3.76 | 0.060 | 83 (11) |
| Sales: log travel time to access | −0.098 | −1.45 | 0.167 | 83 |
| Rents: within 15 min | −0.082 | −0.77 | 0.776 | 75 (8) |

The sale-price effect is of similar size to the earlier estimate but weaker in the continuous form once the larger 2025–26 sample is used. 2020 (collecting) will add the intermediate period.

**Data safety:** the project sits in iCloud Drive with Optimise Mac Storage on; macOS offloaded `red_crawl.csv` and the 2017 archive (restored with `brctl download`). Keep the folder downloaded.

## Three-period before–after result (26 September 2026, evening)

- 2020 archive complete: 8,513 pages (all parsed; captured August–December 2020) → 8,016 clean listings at 232 points (`data/processed/listings_archive_2020.gpkg`). Accessibility now covers 322 points.
- DiD with 2017 (pre), 2020 and 2025–26 (post), RED only, points present before and after (88 points for sales, 12 treated; 82 for rents, 11 treated):

| Relative to 2017 | Sales: within 15 min of Expressway access | Rents: within 15 min |
|---|---|---|
| 2020 | +0.259 (≈ +30%); cluster t 3.30; wild bootstrap p = 0.020 | −0.103; p = 0.133 |
| 2025–26 | +0.212 (≈ +24%); cluster t 3.57; wild bootstrap p = 0.079 | −0.107; p = 0.697 |

Log travel time to the access points (continuous) is not significant in either period (sales p = 0.41 and 0.21): the premium is concentrated in the immediate catchment rather than declining smoothly with travel time.

**Reading:** sale prices within 15 minutes of the Expressway's access points rose about 30% more than elsewhere between 2017 and 2020, two years after the June 2018 opening, and the premium persists in 2025–26. Rents did not respond. With one pre-period, parallel pre-trends cannot be tested directly.

**Next:** placebo treatments (catchments of other radial roads; the 15–30 minute band as a dose test), sensitivity to the 15-minute threshold and to listing mix (bedroom and property-type composition), then the value-capture calculation and the manuscript.
