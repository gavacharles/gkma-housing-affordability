# Paper 2 — Transit access and housing prices in Greater Kampala

**Working title:** Is Transit Access Capitalised in an Informal Housing Market? Evidence from Online Listings in Greater Kampala

**Target journals:** Journal of Transport Geography; Cities; Transport Policy; Land Use Policy (check current quartiles).

This paper reuses the shared pipeline at the project root: listing collection, cleaning, deduplication, geocoding, census and income data, and the OpenStreetMap layers. Paper-specific scripts go in `scripts/` (start each with `import _paper`), results in `outputs/`, and the manuscript in `docs/manuscript/`.

## Plan

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
