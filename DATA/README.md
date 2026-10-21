# DATA: metadata

This folder holds the data for the bird-of-prey population trend project: the
raw inputs, the analysis-ready (final) datasets, and the explanatory plots
below. Scripts in `SCRIPTS/` turn the raw data into the final data.

> **Status:** the repository is being reorganised to the TIER Protocol layout.
> File locations marked *(planned)* are where files will live once the scripts
> are moved into `SCRIPTS/`; variable definitions are final.

## Data Summary

The project uses two sources.

| Dataset | What it contains | Records used | Years | Size |
|---|---|---|---|---|
| **Living Planet Database (LPD) 2026.1, public** | 37,040 vertebrate population time series (one row per series, one column per year), compiled by ZSL and WWF | 3 series: bald eagle (ID 2910), peregrine falcon (ID 28210), California condor (ID 3328) | 1950-2022 (columns); used series cover 1970-2022 and 1982-1993 | ~34 MB CSV, 104 columns |
| **USFWS California Condor Recovery Program annual population status reports** | Year-end counts of wild condors by flock, and deaths in the wild by flock | California wild flock, Arizona/Utah wild flock | 2012-2025 | 31 values, typed in from the reports |

**What each series measures**

| Series | Species | Area | Units | Role in the analysis |
|---|---|---|---|---|
| LPD 2910 | Bald eagle | United States + Canada | Breeding Bird Survey relative abundance index (not a bird count) | Modelled: interrupted time series (break at 2007 delisting) and forecasts |
| LPD 28210 | Peregrine falcon | North America (US + Canada) | Breeding Bird Survey relative abundance index (not a bird count) | Modelled: interrupted time series (break at 1999 delisting) and forecasts |
| LPD 3328 | California condor | California | Number of wild individuals | Descriptive only: the 1982-1987 collapse and 1992 reintroduction |
| USFWS-CA-WILD | California condor | California wild flock (Southern + Central CA) | Wild individuals at year-end (Dec 31) | Modelled: comparison around the 2019 statewide lead ammunition ban, and forecasts |
| USFWS-AZUT-WILD | California condor | Arizona/Utah wild flock | Wild individuals at year-end (Dec 31) | Comparison flock (no mandatory lead ban), and forecasts |
| USFWS-CA-WILD-DEATHS, USFWS-AZUT-WILD-DEATHS | California condor | Same flocks | Deaths in the wild during the year | Secondary outcome (collected, not yet modelled) |

**Important limitations**

- The California flock series has only **6 yearly counts** (2012, 2016, 2017, 2020, 2024, 2025). Other years appear only in report copies hosted by third parties and were deliberately left out; no years are imputed.
- The bald eagle and peregrine series are model-based indices from the North American Breeding Bird Survey; they show relative change, not numbers of birds.
- Bald eagle 2009 (index 0.352, above both 2008 and 2010) is flagged as an outlier (`outlier_flag`), not removed.

## Provenance

**Living Planet Database**

- Downloaded on 10/15/2026 from the [LPI Data Portal](https://www.livingplanetindex.org/data_portal) as the public CSV (`LPD_2026.1_public.csv`, saved as `DATA/raw/LPD_public.csv` *(planned)*).
- Citation: ZSL/WWF 2026. Living Planet Database 2026.1 <www.livingplanetindex.org/data_portal>. Downloaded on 10/15/2026.
- Original sources of the records used, as given in the LPD:
  - 2910 and 28210: Hostetler, J.A. et al. (2023). *The North American Breeding Bird Survey, Analysis Results 1966-2022.* <https://doi.org/10.5066/P9IU1UZ6>
  - 3328: Pattee, O. H. and R. Mesta (1995). "California condors." *Our Living Resources: A report to the nation on the distribution, abundance, and health of U.S. plants, animals, and ecosystems.* USGS.
- The raw file is **not** in this repository (see License). To obtain it, follow `DATA/OBTAIN_LPD_DATA.md` *(planned)*.

**USFWS condor flock counts**

Every value was typed in by hand from the reports below, and each row of the
final file records its exact report, page and figure in a `source_detail`
column. Only official copies were used (fws.gov, ecos.fws.gov, and the 2017
report as hosted by the California Department of Fish and Wildlife). When two
official reports disagreed, the most recent was used and the other value noted.

| Report | Used for | Link |
|---|---|---|
| USFWS California Condor Recovery Program, 2025 Annual Population Status (as of Dec 31, 2025) | AZ/UT flock 2012-2025 (p.11 chart), CA flock 2025, deaths 2023-2025 | [PDF](https://www.fws.gov/sites/default/files/documents/2026-02/2025-california-condor-population-status_508-compliant.pdf) |
| 2024 Annual Population Status | CA flock 2024 | [PDF](https://www.fws.gov/sites/default/files/documents/2025-03/2024-california-condor-population-status508-compliant.pdf) |
| 2020 Annual Population Status | CA flock 2020, deaths 2019-2020 | [PDF](https://www.fws.gov/sites/default/files/documents/2020-California-Condor-Population-Status.pdf) |
| 2017 Annual Population Status (hosted by CDFW) | CA flock 2016-2017, deaths 2017 | [PDF](https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=83849) |
| USFWS California Condor 5-Year Review (June 2013) | CA flock 2012 | [PDF](https://ecos.fws.gov/docs/five_year_review/doc4163.pdf) |

The report PDFs are linked rather than stored here, as the Department of the
Interior asks.

**Processing** (raw to final; details in the script headers in `SCRIPTS/`)

1. Select the three LPD records by ID and reshape from wide (one column per year) to long (one row per year); drop years with no value.
2. Compute `log_count` = ln(count); leave it blank where count = 0 (condor 3328, 1987-1991) and set `zero_count`.
3. Flag the bald eagle 2009 outlier.
4. Build the USFWS flock file from the typed-in report values.
5. Add the segmented-regression variables (`time`, `after`, `time_after`, and the flock comparison terms).

No values are imputed, and series with different IDs, units or locations are never combined.

## License

- **LPD data** are used under the [LPI Data Use Policy](https://www.livingplanetindex.org/documents/LPI_Data_Use_Policy_2026.pdf): for conservation, scientific analysis or research only; not for financial gain; not to be passed to third parties or published in their original format; derived data only under the same terms. For that reason neither the raw LPD file nor any LPD-derived dataset is committed. Figures and tables derived from the LPD carry the citation above.
- **USFWS data** are US government works and in the public domain. The Department of the Interior asks to be credited as the source, which the `source` and `source_detail` columns do.
- The project's own code and documentation are covered by the repository's `LICENSE.md` *(planned)*.

## Ethical Statements

- **No human subjects or personal data.** The data are counts and indices of wild bird populations.
- **No sensitive locations.** All series are aggregated to state, flock or continental level; no nest or roost locations are used or published. This matters for the California condor, which is endangered.
- **Data owners' terms are respected.** LPD data stay out of the repository under the LPI policy, and USFWS reports were used only from official copies. Report copies hosted by a third party were excluded because they could not be verified against the originals.
- **Honest limits.** The small California flock series (6 counts), the index nature of the BBS series, and the outlier flag are reported rather than hidden, and no missing years are filled in.
- **Acknowledgement.** As the LPI policy requests, a copy of the final products should be sent to LivingPlanetIndex@ioz.ac.uk.

## Data Dictionary

### Raw: `DATA/raw/LPD_public.csv` *(planned; not committed)*

One row per population time series. Missing values are written as `NULL`. Only the columns used by the scripts are listed.

| Variable | Type | Description | Units / allowed values |
|---|---|---|---|
| `ID` | integer | LPD record ID | e.g. 2910, 28210, 3328 |
| `Binomial` | text | Scientific name with underscores | e.g. `Haliaeetus_leucocephalus` |
| `Common_name` | text | Common species name | e.g. Bald eagle |
| `Location` | text | Area the series covers | free text |
| `Country` | text | Main country listed | country name |
| `All_countries` | text | All countries the series covers | comma-separated country names |
| `Units` | text | What the yearly values measure | free text |
| `Citation` | text | Original data source | free text |
| `1950` ... `2022` | number | Value for that year | in `Units`; `NULL` = no data |

### Long-format series (LPD records and USFWS flocks)

The LPD file is `DATA/final/lpd_series.csv` *(planned; not committed)*; the USFWS flock file is `DATA/final/usfws_condor_flocks.csv` *(planned; committed)*. Both share these columns; the USFWS file adds `source_detail`.

| Variable | Type | Description | Units / allowed values |
|---|---|---|---|
| `species` | text | Common species name | Bald eagle, Peregrine falcon, California condor |
| `ID` | text | Series identifier | `2910`, `28210`, `3328`, `USFWS-CA-WILD`, `USFWS-AZUT-WILD`, `USFWS-CA-WILD-DEATHS`, `USFWS-AZUT-WILD-DEATHS` |
| `location` | text | Area the series covers | free text |
| `units` | text | What `count` measures | free text (see Data Summary) |
| `year` | integer | Year of the observation (USFWS: as of Dec 31) | 1970-2025 |
| `count` | number | Observed value | index value, number of birds, or number of deaths, per `units`; >= 0 |
| `log_count` | number | Natural log of `count` | ln(count); blank when `count` = 0 |
| `source` | text | Dataset or report the value came from | e.g. Living Planet Database 2026.1 |
| `zero_count` | boolean | `count` equals 0 (log undefined) | True / False |
| `outlier_flag` | boolean | Single-year spike flagged for sensitivity analysis | True only for bald eagle 2009 |
| `source_detail` | text | *(USFWS file only)* Report, page, figure quoted, and URL | free text |

### Model-ready files

`DATA/final/lpd_model_ready.csv` *(planned; not committed)* and `DATA/final/condor_model_ready.csv` *(planned; committed)* contain the columns above plus:

| Variable | Type | Description | Units / allowed values |
|---|---|---|---|
| `breakpoint` | integer | Year of the conservation event for this series | 2007 (bald eagle), 1999 (peregrine), 2019 (condor flocks) |
| `time` | integer | Years since the first year of this series | 0, 1, 2, ... |
| `after` | integer | Year is on or after the breakpoint | 0 = before, 1 = from the breakpoint year on |
| `time_after` | integer | Years since the breakpoint | 0 before and in the breakpoint year, then 1, 2, ... |
| `flock` | integer | *(condor only)* Which flock | 1 = California, 0 = Arizona/Utah |
| `flock_time` | integer | *(condor only)* `flock` x `time` | 0 for Arizona/Utah |
| `flock_after` | integer | *(condor only)* `flock` x `after` | 0 or 1 |
| `flock_time_after` | integer | *(condor only)* `flock` x `time_after` | 0 for Arizona/Utah |

## Explanatory Plots

> **Placeholder:** at least two explanatory plots will be added to `DATA/plots/` and embedded here (planned: the raw time series for each species, and the coverage of the condor flock counts by year). They will carry the LPD citation where they show LPD data.
