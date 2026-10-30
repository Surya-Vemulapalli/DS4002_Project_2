# DS4002 Project 2: Birds of Prey Population Recovery

This project asks whether major conservation actions changed the population trends of three North American birds of prey: the bald eagle (delisted in 2007), the peregrine falcon (delisted in 1999), and the California condor (California's 2019 lead ammunition ban). Each series is analysed with segmented regression (interrupted time series), tested for significance, and forecast to 2028 and 2035 with linear, exponential and logistic growth models.

## Repository Contents

| Item | Contents |
|---|---|
| `README.md` | This orientation file. |
| `LICENSE.md` | MIT license for the project's code and documentation. |
| `SCRIPTS/` | Python scripts, numbered in the order they are run, plus shared helpers (`helpers.py`). |
| `DATA/` | Initial data, intermediate and analysis-ready (final) datasets, metadata (`DATA/README.md`), and explanatory plots. |
| `OUTPUT/` | Results: figures, tables, and the saved fitted models. |

## Section 1: Software and Platform

- **Software:** Python 3.14 (tested with 3.14.3).
- **Add-on packages:**

  | Package | Version used | Used for |
  |---|---|---|
  | pandas | 3.0.6 | Reading, reshaping and saving data |
  | numpy | 2.5.3 | Log transforms and numeric work |
  | statsmodels | 0.15.0 | Segmented regression, Durbin-Watson, robust standard errors |
  | scipy | 1.18.1 | Logistic curve fitting and one-sided t-tests |
  | matplotlib | 3.11.2 | All plots |

  Install them with:

  ```
  pip install pandas numpy statsmodels scipy matplotlib
  ```

- **Platform:** Windows 11. The scripts build file paths with `pathlib`, so they should also run on macOS and Linux.

## Section 2: Map of the Documentation

```
DS4002_Project_2/
├── README.md
├── LICENSE.md
├── SCRIPTS/
│   ├── helpers.py                  Shared functions and constants (imported, not run)
│   ├── 01_explore.py               Lists every US LPD record for the three species
│   ├── 02_prepare_data.py          Reshapes the chosen LPD records to long format
│   ├── 03_combine_data.py          Combines the per-species files into one CSV
│   ├── 04_clean_data.py            Cleans the combined file and splits it by source
│   ├── 05_build_condor_flocks.py   Builds the USFWS California and Arizona/Utah flock counts
│   ├── 06_check_data.py            Data checks and the explanatory plots
│   ├── 07_make_model_vars.py       Adds the segmented-regression variables
│   ├── 08_fit_models.py            Fits the five segmented-regression models
│   ├── 09_plot_models.py           Plots observed data with fitted lines
│   ├── 10_forecast_models.py       Forecasts to 2028 and 2035; compares models (MAE, MAPE, RMSE)
│   ├── 11_significance_tests.py    t-tests on the level and slope changes; bootstrap 20% growth test
│   └── 12_results_table.py         Summary tables of the main results
├── DATA/
│   ├── README.md                   Metadata: summary, provenance, license, ethics, data dictionary, plots
│   ├── LPD_public.csv              Initial: Living Planet Database 2026.1 (NOT included; download it, see step 3)
│   ├── peregrine_falcon_28210_cleaned.csv   Initial: peregrine falcon series (LPD 28210)
│   ├── california_condor_long.csv  Initial: condor series (LPD 3328 and USFWS 2025 report)
│   ├── birds_cleaned.csv           Intermediate (from 02)
│   ├── bald_eagle_cleaned.csv      Intermediate (from 02)
│   ├── birds_consolidated.csv      Intermediate (from 03)
│   ├── lpd_series.csv              Final LPD series (from 04)
│   ├── usfws_condor.csv            Final USFWS global condor series (from 04)
│   ├── usfws_condor_flocks.csv     Final USFWS flock counts (from 05)
│   ├── model_ready_lpd.csv         Analysis-ready LPD data (from 07)
│   ├── model_ready_condor.csv      Analysis-ready condor flock data (from 07)
│   ├── plots/
│   │   ├── lpd_population_indices_1970_2022.png
│   │   └── condor_population_by_series.png
│   ├── raw/, intermediate/, final/ (empty placeholders)
└── OUTPUT/
    ├── figures/
    │   ├── bald_eagle.png, peregrine_falcon.png, condor_flocks.png, condor_1982_1993.png   (from 09)
    │   └── forecast_bald_eagle.png, forecast_peregrine_falcon.png,
    │       forecast_condor_flocks.png, model_comparison_metrics.png                        (from 10)
    ├── tables/
    │   ├── coefficients.csv, model_summary.csv, fitted_values.csv                          (from 08)
    │   ├── forecasts.csv, forecast_comparison.csv, forecast_parameters.csv,
    │   │   forecast_projections_yearly.csv                                                 (from 10)
    │   ├── significance_test_results.csv                                                   (from 11)
    │   └── results_summary.md, results_summary_segmented_regression.csv,
    │       results_summary_significance_tests.csv,
    │       results_summary_forecasts.csv, results_summary_forecast_errors.csv,
    │       results_summary_projections_best_models.csv,
    │       results_summary_forecasts_all_models.csv                                        (from 12)
    └── models/
        ├── model_1_bald_eagle_all_years.pickle ... model_5_condor_ca_vs_az_ut.pickle        (from 08)
        └── forecast/   forecast_<series>_<model>.pickle and .json                           (from 10)
```

## Section 3: Instructions for Reproducing the Results

1. **Get the code.** Clone this repository, or download it as a ZIP from GitHub and unzip it.
2. **Install the software.** Install Python 3.14 from [python.org](https://www.python.org/downloads/), then open a terminal and run:
   ```
   pip install pandas numpy statsmodels scipy matplotlib
   ```
3. **Download the raw Living Planet Database file.** It is not included in this repository, because its data use policy does not allow publishing it in its original format.
   1. Go to the [LPI Data Portal](https://www.livingplanetindex.org/data_portal).
   2. Register with your name and email, describe how you will use the data, and accept the data use policy.
   3. Download the public dataset (version 2026.1) as a CSV.
   4. Rename it to `LPD_public.csv` and save it in the `DATA/` folder, so its path is `DATA/LPD_public.csv`.

   The other two initial files, `DATA/peregrine_falcon_28210_cleaned.csv` and `DATA/california_condor_long.csv`, are already in the repository.
4. **Open a terminal in the repository's top folder** (the folder that contains `README.md`). Every command below is run from there.
5. **Run the numbered scripts in order.** Each one reads the files written by the ones before it.
   ```
   python SCRIPTS/01_explore.py
   python SCRIPTS/02_prepare_data.py
   python SCRIPTS/03_combine_data.py
   python SCRIPTS/04_clean_data.py
   python SCRIPTS/05_build_condor_flocks.py
   python SCRIPTS/06_check_data.py
   python SCRIPTS/07_make_model_vars.py
   python SCRIPTS/08_fit_models.py
   python SCRIPTS/09_plot_models.py
   python SCRIPTS/10_forecast_models.py
   ```
   What each step produces:
   - Step 01 only prints a table of candidate LPD records (used to choose IDs 2910, 28210 and 3328).
   - Steps 02-05 write the intermediate and final datasets in `DATA/`.
   - Step 06 prints the data checks and saves the two explanatory plots to `DATA/plots/`.
   - Step 07 writes `DATA/model_ready_lpd.csv` and `DATA/model_ready_condor.csv`.
   - Step 08 fits the five segmented-regression models, saves them to `OUTPUT/models/`, and writes the coefficient, summary and fitted-value tables to `OUTPUT/tables/`. In model 5 (California vs. Arizona/Utah), `after` and `time_after` are the Arizona/Utah flock's changes at 2019; the lead-ban comparison is `flock_after` and `flock_time_after` (how California's changes differ from Arizona/Utah's).
   - Step 09 saves the fitted-model plots to `OUTPUT/figures/`.
   - Step 10 compares the forecasting models on held-out data (MAE, RMSE, MAPE, and how many held-out values fall inside their 95% prediction intervals), saves the forecast models to `OUTPUT/models/forecast/`, the forecast tables to `OUTPUT/tables/`, and the forecast and model-comparison plots to `OUTPUT/figures/`.
6. **Run the significance tests and build the results tables:**
   ```
   python SCRIPTS/11_significance_tests.py
   python SCRIPTS/12_results_table.py
   ```
   This prints R-squared, the Durbin-Watson test, the two-sided t-tests on the level and slope changes, and the one-sided bootstrap test of the 20% growth goal for each model, and saves them to `OUTPUT/tables/significance_test_results.csv`. Step 12 then collects the main results into `OUTPUT/tables/results_summary.md` (easiest to read on GitHub) and two CSV versions.
7. **Check the results.** Compare your files in `OUTPUT/` with the ones in this repository. The tables and models should match exactly.

## References

[1] ZSL/WWF, "Living Planet Database 2026.1," Living Planet Index. [Online]. Available: https://www.livingplanetindex.org/data_portal. Accessed: Oct. 15, 2026.

[2] J. A. Hostetler, J. R. Sauer, J. E. Hines, D. Ziolkowski, and M. Lutmerding, "The North American Breeding Bird Survey, Analysis Results 1966-2022," U.S. Geological Survey data release, 2023, doi: 10.5066/P9IU1UZ6.

[3] U.S. Fish and Wildlife Service, "California Condor Recovery Program 2025 Annual Population Status," 2026. [Online]. Available: https://www.fws.gov/sites/default/files/documents/2026-02/2025-california-condor-population-status_508-compliant.pdf

[4] Project TIER, "TIER Protocol 4.0." [Online]. Available: https://www.projecttier.org/tier-protocol/protocol-4-0/
