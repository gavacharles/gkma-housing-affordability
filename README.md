# gkma-housing-affordability

Python pipeline, analysis scripts, results and manuscripts for a housing affordability index and spatial machine-learning analysis of Greater Kampala, Uganda, built from online property listings, census, income and map data.

## Repository contents

| Path | What it is |
|---|---|
| `src/gkma/` | Shared package: listing parsers, cleaning and location, affordability index, hedonic, household, land-value and machine-learning analysis |
| `scripts/` | Pipeline stages 00–02: boundaries, census, income, macro, construction costs, basemap, night lights, gazetteer and listing preparation |
| `config.yaml` | Pipeline configuration |
| `paper1_affordability/` | Paper 1 analysis scripts, results, manuscript and interactive explorer (`docs/explorer/`) |
| `paper2_transit/`, `paper3_access/`, `paper4_finance/` | Later studies: plans, scripts and outputs (tables and maps) |
| `data/external/` | Small public inputs (exchange rates, census by parish, CPI uplift, earnings, income), with a README |
| `demo/` | Demo configuration with synthetic income and rates (`*_SYNTHETIC.csv`) for running without private inputs |
| `docs/` | Pipeline notes (`pipeline.md`), portal assessment, letter template |
| `tests/` | Parser, payment-terms and supply tests |
| `requirements.txt`, `requirements-lock.txt` | Dependencies (loose and pinned) |

Listing-level data are not included, because they contain third-party content from the listing portals. Setup and workflow are in [`docs/pipeline.md`](docs/pipeline.md).

## Licence and citation

Code: MIT. Manuscripts, figures and derived tables: CC BY 4.0 (see `LICENSE`). Third-party data keep their own terms. Cite with the "Cite this repository" button or `CITATION.cff`.
