"""Number citations in order of first appearance (MDPI style) and append the
reference list.

  python scripts/build_manuscript.py
  -> docs/manuscript/manuscript_draft.md

Citation keys in the source look like [@key] or [@key1; @key2]. Every key must
exist in REFS; unknown keys stop the build. Entries marked VERIFY need a check
of the bibliographic details before submission.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/manuscript/manuscript_source.md"
OUT = ROOT / "docs/manuscript/manuscript_draft.md"

REFS = {
    "unhabitat2011": "UN-Habitat. *Affordable Land and Housing in Africa*; Adequate Housing Series, Vol. 3; United Nations Human Settlements Programme: Nairobi, Kenya, 2011.",
    "lall2017": "Lall, S.V.; Henderson, J.V.; Venables, A.J. *Africa's Cities: Opening Doors to the World*; World Bank: Washington, DC, USA, 2017.",
    "molhud2016": "Ministry of Lands, Housing and Urban Development. *The Uganda National Housing Policy*; Government of Uganda: Kampala, Uganda, 2016.",
    "ubos2021unhs": "Uganda Bureau of Statistics. *Uganda National Household Survey 2019/2020*; UBOS: Kampala, Uganda, 2021.",
    "ubos2026rppi": "Uganda Bureau of Statistics. *Residential Property Price Index: Quarterly Tables, Q4 2025/26*; UBOS: Kampala, Uganda, 2026.",
    "boeing2017": "Boeing, G.; Waddell, P. New Insights into Rental Housing Markets across the United States: Web Scraping and Analyzing Craigslist Rental Listings. *J. Plan. Educ. Res.* **2017**, *37*, 457–476.",
    "boeing2020": "Boeing, G. Online Rental Housing Market Representation and the Digital Reproduction of Urban Inequality. *Environ. Plan. A* **2020**, *52*, 449–468.",
    "irumba2015": "Irumba, R. An Empirical Examination of the Effects of Land Tenure on Housing Values in Kampala, Uganda. *Int. J. Hous. Mark. Anal.* **2015**, *8*, 359–374. https://doi.org/10.1108/IJHMA-11-2014-0044.",
    "embaye2021": "Embaye, W.T.; Zereyesus, Y.A.; Chen, B. Predicting the Rental Value of Houses in Household Surveys in Tanzania, Uganda and Malawi: Evaluations of Hedonic Pricing and Machine Learning Approaches. *PLoS ONE* **2021**, *16*, e0244953. https://doi.org/10.1371/journal.pone.0244953.",
    "mirembe2016": "Mirembe, R.D.; Matovu, A.; Nkote, I.N.; Nabirye, I. The Effect of Housing Price on Housing Affordability in Kampala, Uganda. In Proceedings of the European Real Estate Society (ERES) Conference, Regensburg, Germany, 2016; eres2016_166.",
    "birdvenables2020": "Bird, J.; Venables, A.J. Land Tenure and Land-Use in a Developing City: A Quantitative Spatial Model Applied to Kampala, Uganda. *J. Urban Econ.* **2020**, *119*, 103268.",
    "rosen1974": "Rosen, S. Hedonic Prices and Implicit Markets: Product Differentiation in Pure Competition. *J. Political Econ.* **1974**, *82*, 34–55.",
    "sirmans2005": "Sirmans, G.S.; Macpherson, D.A.; Zietz, E.N. The Composition of Hedonic Pricing Models. *J. Real Estate Lit.* **2005**, *13*, 3–43.",
    "can1992": "Can, A. Specification and Estimation of Hedonic Housing Price Models. *Reg. Sci. Urban Econ.* **1992**, *22*, 453–474.",
    "alonso1964": "Alonso, W. *Location and Land Use: Toward a General Theory of Land Rent*; Harvard University Press: Cambridge, MA, USA, 1964.",
    "muth1969": "Muth, R.F. *Cities and Housing*; University of Chicago Press: Chicago, IL, USA, 1969.",
    "mills1967": "Mills, E.S. An Aggregative Model of Resource Allocation in a Metropolitan Area. *Am. Econ. Rev.* **1967**, *57*, 197–210.",
    "anas1998": "Anas, A.; Arnott, R.; Small, K.A. Urban Spatial Structure. *J. Econ. Lit.* **1998**, *36*, 1426–1464.",
    "davis2007": "Davis, M.A.; Heathcote, J. The Price and Quantity of Residential Land in the United States. *J. Monet. Econ.* **2007**, *54*, 2595–2620.",
    "glaeser2005": "Glaeser, E.L.; Gyourko, J.; Saks, R.E. Why Have Housing Prices Gone Up? *Am. Econ. Rev.* **2005**, *95*, 329–333.",
    "desoto2000": "de Soto, H. *The Mystery of Capital: Why Capitalism Triumphs in the West and Fails Everywhere Else*; Basic Books: New York, NY, USA, 2000.",
    "besley1995": "Besley, T. Property Rights and Investment Incentives: Theory and Evidence from Ghana. *J. Political Econ.* **1995**, *103*, 903–937.",
    "payne2009": "Payne, G.; Durand-Lasserve, A.; Rakodi, C. The Limits of Land Titling and Home Ownership. *Environ. Urban.* **2009**, *21*, 443–462.",
    "landact1998": "Government of Uganda. *The Land Act, Cap. 227*; Government of Uganda: Kampala, Uganda, 1998. See also the Constitution of the Republic of Uganda (1995), Article 237.",
    "deininger2008": "Deininger, K.; Ali, D.A. Do Overlapping Land Rights Reduce Agricultural Investment? Evidence from Uganda. *Am. J. Agric. Econ.* **2008**, *90*, 869–882.",
    "hulchanski1995": "Hulchanski, J.D. The Concept of Housing Affordability: Six Contemporary Uses of the Housing Expenditure-to-Income Ratio. *Hous. Stud.* **1995**, *10*, 471–491.",
    "kutty2005": "Kutty, N.K. A New Measure of Housing Affordability: Estimates and Analytical Results. *Hous. Policy Debate* **2005**, *16*, 113–142.",
    "haffner2021": "Haffner, M.E.A.; Hulse, K. A Fresh Look at Contemporary Perspectives on Urban Housing Affordability. *Int. J. Urban Sci.* **2021**, *25*, 59–79. [VERIFY]",
    "hud2014": "U.S. Department of Housing and Urban Development, Office of Policy Development and Research. Rental Burdens: Rethinking Affordability Measures. *PD&R Edge* **2014**. Available online: https://www.huduser.gov/portal/pdredge/pdr_edge_featd_article_092214.html (accessed on 24 September 2026). [VERIFY]",
    "stone2006": "Stone, M.E. What Is Housing Affordability? The Case for the Residual Income Approach. *Hous. Policy Debate* **2006**, *17*, 151–184.",
    "tobler1970": "Tobler, W.R. A Computer Movie Simulating Urban Growth in the Detroit Region. *Econ. Geogr.* **1970**, *46*, 234–240.",
    "moran1950": "Moran, P.A.P. Notes on Continuous Stochastic Phenomena. *Biometrika* **1950**, *37*, 17–23.",
    "anselin1995": "Anselin, L. Local Indicators of Spatial Association—LISA. *Geogr. Anal.* **1995**, *27*, 93–115.",
    "getis1992": "Getis, A.; Ord, J.K. The Analysis of Spatial Association by Use of Distance Statistics. *Geogr. Anal.* **1992**, *24*, 189–206.",
    "fotheringham2002": "Fotheringham, A.S.; Brunsdon, C.; Charlton, M. *Geographically Weighted Regression: The Analysis of Spatially Varying Relationships*; Wiley: Chichester, UK, 2002.",
    "fotheringham2017": "Fotheringham, A.S.; Yang, W.; Kang, W. Multiscale Geographically Weighted Regression (MGWR). *Ann. Am. Assoc. Geogr.* **2017**, *107*, 1247–1265.",
    "oshan2019": "Oshan, T.M.; Li, Z.; Kang, W.; Wolf, L.J.; Fotheringham, A.S. mgwr: A Python Implementation of Multiscale Geographically Weighted Regression for Investigating Process Spatial Heterogeneity and Scale. *ISPRS Int. J. Geo-Inf.* **2019**, *8*, 269.",
    "breiman2001": "Breiman, L. Random Forests. *Mach. Learn.* **2001**, *45*, 5–32.",
    "chen2016": "Chen, T.; Guestrin, C. XGBoost: A Scalable Tree Boosting System. In Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, San Francisco, CA, USA, 13–17 August 2016; pp. 785–794.",
    "ke2017": "Ke, G.; Meng, Q.; Finley, T.; Wang, T.; Chen, W.; Ma, W.; Ye, Q.; Liu, T.-Y. LightGBM: A Highly Efficient Gradient Boosting Decision Tree. In *Advances in Neural Information Processing Systems 30*; Curran Associates: Red Hook, NY, USA, 2017; pp. 3146–3154.",
    "mullainathan2017": "Mullainathan, S.; Spiess, J. Machine Learning: An Applied Econometric Approach. *J. Econ. Perspect.* **2017**, *31*, 87–106.",
    "roberts2017": "Roberts, D.R.; Bahn, V.; Ciuti, S.; Boyce, M.S.; Elith, J.; Guillera-Arroita, G.; Hauenstein, S.; Lahoz-Monfort, J.J.; Schröder, B.; Thuiller, W.; et al. Cross-Validation Strategies for Data with Temporal, Spatial, Hierarchical, or Phylogenetic Structure. *Ecography* **2017**, *40*, 913–929.",
    "ploton2020": "Ploton, P.; Mortier, F.; Réjou-Méchain, M.; Barbier, N.; Picard, N.; Rossi, V.; Dormann, C.; Cornu, G.; Viennois, G.; Bayol, N.; et al. Spatial Validation Reveals Poor Predictive Performance of Large-Scale Ecological Mapping Models. *Nat. Commun.* **2020**, *11*, 4540.",
    "lundberg2017": "Lundberg, S.M.; Lee, S.-I. A Unified Approach to Interpreting Model Predictions. In *Advances in Neural Information Processing Systems 30*; Curran Associates: Red Hook, NY, USA, 2017; pp. 4765–4774.",
    "li2022": "Li, Z. Extracting Spatial Effects from Machine Learning Model Using Local Interpretation Method: An Example of SHAP and XGBoost. *Comput. Environ. Urban Syst.* **2022**, *96*, 101845. [VERIFY]",
    "elbers2003": "Elbers, C.; Lanjouw, J.O.; Lanjouw, P. Micro-Level Estimation of Poverty and Inequality. *Econometrica* **2003**, *71*, 355–364.",
    "filmer2001": "Filmer, D.; Pritchett, L.H. Estimating Wealth Effects without Expenditure Data—or Tears: An Application to Educational Enrollments in States of India. *Demography* **2001**, *38*, 115–132.",
    "ubos2024census": "Uganda Bureau of Statistics. *National Population and Housing Census 2024: Sub-county Profiles*; UBOS: Kampala, Uganda, 2025. [VERIFY year of release]",
    "ubos2019poverty": "Uganda Bureau of Statistics; UNICEF; World Bank. *Poverty Maps of Uganda: Mapping the Spatial Distribution of Poor Households and Child Poverty Based on Data from the 2016/17 Uganda National Household Survey and the 2014 National Housing and Population Census*; UBOS: Kampala, Uganda, 2019. [VERIFY exact title]",
    "cahf2020": "Centre for Affordable Housing Finance in Africa. *Uganda's Housing Construction and Housing Rental Activities: Housing Economic Value Chain and Housing Cost Benchmarking Analysis*; CAHF: Johannesburg, South Africa, 2020.",
    "nar": "National Association of REALTORS. Housing Affordability Index: Methodology. Available online: https://www.nar.realtor/research-and-statistics/housing-statistics/housing-affordability-index/methodology (accessed on 24 September 2026).",
    "hfb": "Housing Finance Bank. Mortgage Frequently Asked Questions; Housing Finance Bank: Kampala, Uganda. Available online: https://www.housingfinance.co.ug/wp-content/uploads/2019/11/FAQS.pdf (accessed on 24 September 2026).",
    "cahf2024": "Centre for Affordable Housing Finance in Africa (CAHF). Uganda. In Housing Finance in Africa Yearbook 2024, 15th ed.; CAHF: Johannesburg, South Africa, 2024. Available online: https://housingfinanceafrica.org/yearbook-profile/2024-housing-finance-yearbook-uganda-profile/ (accessed on 24 September 2026).",
    "bou": "Bank of Uganda. Commercial Banks' Weighted Average Lending Rates (Shillings) and Consumer Price Index; accessed through the Ministry of Finance, Planning and Economic Development Macro Data Portal. Available online: https://mepd.finance.go.ug/apps/macro-data-portal/ (accessed on 23 September 2026).",
    "osm": "OpenStreetMap Contributors. OpenStreetMap. Available online: https://www.openstreetmap.org (accessed on 22 September 2026).",
    "roman2018": "Román, M.O.; Wang, Z.; Sun, Q.; Kalb, V.; Miller, S.D.; Molthan, A.; Schultz, L.; Bell, J.; Stokes, E.C.; Pandey, B.; et al. NASA's Black Marble Nighttime Lights Product Suite. *Remote Sens. Environ.* **2018**, *210*, 113–143.",
}

text = SRC.read_text(encoding="utf-8").replace(
    " Citation keys [@…] are numbered by `scripts/build_manuscript.py`.", "")
order: list[str] = []


def repl(m):
    keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
    nums = []
    for k in keys:
        if k not in REFS:
            sys.exit(f"Unknown citation key: {k}")
        if k not in order:
            order.append(k)
        nums.append(order.index(k) + 1)
    nums = sorted(set(nums))
    # compress runs: 3,4,5 -> 3–5
    parts, start = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != a + 1:
            parts.append(f"{start}–{a}" if a - start >= 2 else ", ".join(str(x) for x in range(start, a + 1)))
            start = b
    return "[" + ", ".join(parts) + "]"


body = re.sub(r"\[(@[^\]]+)\]", repl, text)
refs = "\n".join(f"{i}. {REFS[k]}" for i, k in enumerate(order, 1))
unused = sorted(set(REFS) - set(order))
OUT.write_text(body.rstrip() + "\n\n## References\n\n" + refs + "\n", encoding="utf-8")
words = len(re.findall(r"\b\w+\b", re.sub(r"\n## References.*", "", body, flags=re.S)))
print(f"wrote {OUT.relative_to(ROOT)}: {len(order)} references, ~{words} words" +
      (f"; unused keys: {unused}" if unused else ""))
print("entries to verify:", [k for k in order if "VERIFY" in REFS[k]])
