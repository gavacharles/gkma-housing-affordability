# Priced out of the formal market: a housing affordability index for Greater Kampala

Python workflow and manuscript for *"Priced out of the formal market: A housing affordability index for Greater Kampala, Uganda, from online listings and spatial machine learning"* (PhD research, University of Johannesburg). It takes online property listings through cleaning, geocoding and spatial modelling to the GKMA Housing Affordability Index (rental, ownership, gap, burden-gradient and residual-income measures), publication maps and the manuscript.

**Data in this repository.** Code, configuration, the neighbourhood gazetteer, small derived inputs (`data/external/*.csv`), aggregate result tables (`outputs/tables/`), figures (`outputs/maps/*.png`) and the manuscript (`docs/manuscript/`). Listing-level data (raw portal pages, cleaned listings) are **not** included: they contain third-party content, and portal consent was still being finalised. The paper uses a frozen dataset of 10,643 listings (24 September 2026) held locally in `data/paper_snapshot_2026-09-24/`.

## Setup (once)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # exact versions: requirements-lock.txt
.venv/bin/python -m pytest -q tests              # parser tests (portal fixture tests skip without local fixtures)
```

Optional: `collection.contact_email` in `config.yaml` adds a contact address to the User-Agent sent to portals. Everything runs without it.

## Workflow

| Step | Script | Answers | Main outputs |
|---|---|---|---|
| 0 | `00_prepare_macro.py` (after the MoFPED download) | Exchange rates and CPI uplift | `data/external/bou_usd_ugx_monthly.csv`, `cpi_uplift.csv` |
| 0 | `00_prepare_construction_costs.py` · `00_prepare_ubos.py` · `00_prepare_census.py` · `00_fetch_night_lights.py` | Construction costs (CAHF + UBOS CIPI), UBOS RPPI, Census 2024 parish profiles, night lights | `data/external/…` |
| 0 | `00_tidy_gazetteer.py` | Places neighbourhoods on official UBOS parishes/sub-counties, adds spelling variants | `data/lookup/neighbourhood_lookup.csv` (`check_status`) |
| 0 | `00_verify_gazetteer.py` | Checks the neighbourhood lookup against OpenStreetMap and UBOS parishes | `data/lookup/lookup_osm_check.csv`, `lookup_parish_check.csv` |
| 1 | `01_collect.py --portal jiji` (weekly) · `--portal red` (resumable crawl) · `--portal red --extract file.csv` · `--manual` | Data | `data/raw/<source>/…csv` |
| 2 | `02_clean.py [--nominatim]` | Cleaning and text-extraction pipeline (methods contribution) | `data/processed/listings.gpkg`, `cleaning_log.csv`, `dedup_report.csv` |
| 3 | `03_spatial_patterns.py` | **RQ1** distribution and clustering | median choropleths, LISA maps, `morans_i.csv` |
| 4 | `04_hedonic_gwr.py [--mgwr]` | **RQ2** drivers, title premium, spatial variation | hedonic tables, `title_premium_houses.csv`, `tenure_premium_land.csv`, GWR coefficient maps |
| 5 | `05_machine_learning.py [--gwr]` | **RQ3** ML vs hedonic, spatial CV, SHAP | `cv_summary_*.csv`, SHAP importance, SHAP-by-location maps |
| 6 | `06_affordability.py` | **RQ4** where, and for what share, housing is unaffordable | affordability-gap maps, `affordability_summary.csv` |
| 7 | `07_land_value.py` | Implied land value (links to HAFE) | land-share and land-value maps, `land_value_scenarios.csv` |
| 8 | `08_validation.py` | Listing-based hedonic index vs UBOS RPPI | `validation_listing_index_vs_rppi.csv`, validation chart |
| 9 | `09_affordability_index.py` | **RQ4** GKMA Housing Affordability Index (RAI, OAI, AGI), mortgage sensitivity, 10–80% burden gradient, residual-income test, parish supplement | `affordability_index_*.csv`, maps 19–24, S1–S3 |
| 10 | `10_sample_adequacy.py` | Precision curve and convergence (justifies the 10,000-listing sample) | `sample_adequacy_*.csv`, S4–S5 |
| 11 | `11_robustness.py` | Neighbourhood-only locations; each portal left out | `robustness.csv` |
| — | `run_paper.sh` | All analysis stages on the frozen dataset, then the manuscript (`build_manuscript.py`, `build_supplement.py`, `build_docx.py`) | `docs/manuscript/manuscript.docx`, `supplementary.docx` |

Run the scripts with `.venv/bin/python scripts/<name>.py`. Tables go to `outputs/tables/`.

### Publication maps
Built once: `.venv/bin/python scripts/00_prepare_basemap.py` (lake, land mask, boundaries, roads, labels, Uganda locator). All figures follow Elsevier, Taylor & Francis and MDPI artwork rules:
- **Formats:** each figure in `outputs/maps/` as vector **PDF** (fonts embedded), **600 dpi TIFF** (LZW) and 300 dpi PNG for drafts.
- **Size and type:** 170 mm full width (90 mm single column), Arial at 6–8 pt at print size.
- **Titles and captions:** titles go in the caption, not the figure. `outputs/maps/captions.md` holds a draft caption for each figure, with notes and data sources.
- **Cartography:** a fixed GKMA extent for every map; parishes clipped to the Lake Victoria shoreline; a Kampala-core inset; degree ticks, scale bar, north arrow; and the OpenStreetMap attribution (required by its ODbL licence).
- **Colour:** ColorBrewer for magnitudes (safe for colour-blind readers and greyscale print), GeoDa colours for LISA clusters, Okabe–Ito for categories.
- **Editable layers:** each mapped layer is also saved to `outputs/gis/<figure>.gpkg`, so any map can be restyled in QGIS or ArcGIS.

## Try it on synthetic data first

```bash
.venv/bin/python scripts/make_demo_data.py
export GKMA_CONFIG=demo/config_demo.yaml
.venv/bin/python scripts/02_clean.py --out demo/processed
for s in 03_spatial_patterns 04_hedonic_gwr 05_machine_learning 06_affordability 07_land_value; do
  .venv/bin/python scripts/$s.py --data demo/processed --out demo/outputs; done
unset GKMA_CONFIG
```

The demo data is **synthetic**, with made-up income and cost placeholders. It exists only to show that the code runs and recovers known effects. Never cite it.

## What you need to supply

1. **Permissions.** See `docs/portal_assessment.md` (with a decision log) and `docs/letter_template.md`. Record each one in `config.yaml`.
2. **Neighbourhood lookup.** In `data/lookup/neighbourhood_lookup.csv`, correct the rows with a `note`, set `verified=1`, and add names as they appear in listings.
3. **External data.** See `data/external/README.md`: parish/sub-county boundaries, UNHS income, your replacement-cost rates, Bank of Uganda FX, night lights and flood layer.

## Design choices to report in the paper

- **Price measures.** Floor area is rarely listed, so the main measures are rent or price per bedroom and price per decimal (1 decimal = 40.47 m²).
- **Location precision.** Every listing carries a `geo_method` value (`portal_coords`, `lookup_exact`, `lookup_contains`, `lookup_fuzzy`, `subcounty_centroid`, `admin_region`, `nominatim`). Report the mix, and run a robustness check that keeps only neighbourhood-level matches.
- **Analysis unit.** The unit is the parish, falling back to the sub-county when a parish has fewer than 5 listings (`min_listings_per_unit`).
- **Spatial CV.** Held-out blocks of 3 km (`spatial_cv_block_km`). Random-CV scores are reported alongside to show leakage.
- **Title premium.** Estimated relative to untitled (kibanja) listings, in two ways: in the house hedonic model, and in a land-only price-per-decimal model.
- **Affordability.** Share of households unable to afford the unit's median rent at 30% of income, assuming lognormal district income. Reported for all rentals and for 1–2 bedroom units, with ±20% sensitivity on sigma.
- **Implied land value.** Price minus depreciated replacement cost, with floor area = bedrooms × {25, 32, 40} m² as scenarios. Validated against land-only listings in the same unit.

## Layout

```
config.yaml                 all settings and permission gates
src/gkma/collect/           jiji.py, red.py, upc.py, base.py (polite HTTP, permission gate)
src/gkma/clean/             prices.py, units.py, text_features.py, dedup.py, pipeline.py
src/gkma/geo/               gazetteer.py, boundaries.py, covariates.py
src/gkma/analysis/          spatial_stats.py, hedonic.py, ml.py, affordability.py, land_value.py
src/gkma/viz/maps.py        publication map styles
scripts/                    numbered stage scripts
docs/                       portal assessment, data-request letter
data/lookup/                neighbourhood gazetteer (needs your corrections)
tests/                      parser tests with saved portal pages
```

## Licence and citation

Code: MIT (see `LICENSE`). Manuscript, figures and derived tables: CC BY 4.0. Third-party data keep their own terms (UBOS, Bank of Uganda; OpenStreetMap under ODbL). To cite, use `CITATION.cff` (GitHub shows a "Cite this repository" button).
