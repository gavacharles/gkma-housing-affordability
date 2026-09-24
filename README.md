# Priced out of the formal market

**A housing affordability index for Greater Kampala, Uganda, from online listings and spatial machine learning**

This project measures how affordable the housing on offer in the Greater Kampala Metropolitan Area (GKMA) is to the households who live there, and where. It is part of PhD research at the University of Johannesburg.

## Why it matters

Housing policy in Uganda has relied on national figures—the housing deficit, mortgage penetration, average rents—that cannot show where in the city housing is priced beyond what local households earn, or by how much. This project builds that evidence at metropolitan, district and sub-county level from sources that are open and can be updated.

## What the project does

- **Collects and cleans online property listings** from three Ugandan portals (Jiji, Real Estate Database and Uganda Property Centre): 10,643 deduplicated rentals, houses and land plots, located to neighbourhoods across Kampala, Wakiso, Mukono and the surrounding districts.
- **Links them to published statistics**: the 2024 Population and Housing Census, the Uganda National Household Survey 2019/20, Bank of Uganda lending rates and prices, OpenStreetMap and NASA night-time lights.
- **Models what drives prices and rents** with hedonic and geographically weighted regression and with machine learning (random forest, XGBoost, LightGBM) tested by spatial cross-validation and interpreted with SHAP.
- **Builds the GKMA Housing Affordability Index**, which compares the typical listed home with the incomes of the households in the same area:
  - a Rental Affordability Index and an Ownership Affordability Index adapted to Ugandan mortgage terms;
  - the share of households priced out, across housing-cost burdens from 10% to 80% of income;
  - a residual-income test of whether households could pay for the home and still meet their basic needs.
- **Estimates the land share of house prices** by subtracting the cost of the building from asking prices.

## Main findings

- Online listings show an almost entirely titled, formal housing market, concentrated in better-off neighbourhoods.
- Prices and rents are strongly clustered; location and neighbourhood status matter more than the building itself.
- The median household earns about 18% of the income needed to rent the typical listed one- to two-bedroom home, and about 4% of that needed to buy the typical listed house with a mortgage.
- The typical listed rent would push about three in five households below the poverty line.
- Land accounts for about half or more of house prices.

## Research questions

1. How are housing prices and rents distributed across the GKMA, and where do they cluster?
2. What drives them, and how do those effects vary across the city, including land tenure and title?
3. How well do machine-learning models predict prices compared with hedonic models, once validated spatially?
4. How affordable is the housing on offer, for renting and for ownership, and where is the gap widest?

## Repository contents

- `docs/manuscript/`: the paper and its supplementary materials
- `outputs/maps/` and `outputs/tables/`: figures and aggregate results
- `src/` and `scripts/`: the data pipeline and analysis code
- `docs/pipeline.md`: setup, workflow and technical notes

Listing-level data are not included, because they contain third-party content from the portals.

## Licence and citation

The code is released under the MIT licence and the manuscript, figures and derived tables under CC BY 4.0 (see `LICENSE`). Third-party data keep their own terms. To cite this work, use the "Cite this repository" button or `CITATION.cff`.
