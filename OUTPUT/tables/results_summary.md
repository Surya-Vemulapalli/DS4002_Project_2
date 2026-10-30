# Results Summary

Created by `SCRIPTS/12_results_table.py` from the tables in `OUTPUT/tables/`.

## Segmented regression (interrupted time series)

| Model | Event | n | R2 | Adj. R2 | Durbin-Watson | Standard errors | Level change | Level p | Slope change per year | Slope p | Growth since event | Bootstrap 95% lower bound | 20% goal met |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Bald eagle (all years) | Delisting (2007) | 53 | 0.985 | 0.984 | 0.43 | Newey-West, 3 lags | -13.4% | 0.0158 * | -3.15% | < 0.0001 * | +21.1% | +5.2% | No |
| 2. Bald eagle (no 2009 outlier) | Delisting (2007) | 52 | 0.985 | 0.985 | 0.34 | Newey-West, 3 lags | -15.5% | 0.0051 * | -2.94% | < 0.0001 * | +25.1% | +7.5% | No |
| 3. Peregrine falcon | Delisting (1999) | 53 | 0.992 | 0.991 | 0.15 | Newey-West, 3 lags | +12.7% | 0.0539 | -0.95% | 0.0236 * | +155.9% | +126.0% | Yes |
| 4. California condor, CA flock alone | CA lead ban (2019) | 6 | 0.995 | 0.989 | 2.97 | OLS (too few points for Newey-West) | -6.6% | 0.1898 | -2.57% | 0.0781 | +20.7% | +14.1% | No |
| 5. California condor, CA vs AZ/UT | CA lead ban (2019) | 20 | 0.976 | 0.963 | AZ/UT 1.78; CA 2.97 | HC3 | -24.1% (CA - AZ/UT) | 0.1512 | +0.89% (CA - AZ/UT) | 0.8545 | - | - | - |

Changes are percentages on the original scale. p-values are from two-sided t-tests; \* = significant at alpha = 0.05. The 20% goal is met when the one-sided bootstrap 95% lower bound on growth since the event is above 20%. Model 5 tests whether California's changes at 2019 differ from Arizona/Utah's (no 20% test). Model 4 has only 6 points, so treat it with caution.

## All significance tests for the segmented regression models

| Model | Standard errors | df | Durbin-Watson | Pre-event growth (time) | Level change (after) | Slope change (time_after) | CA vs AZ/UT starting level (flock) | CA vs AZ/UT pre-2019 growth (flock_time) | Lead ban: level effect, CA - AZ/UT (flock_after) | Lead ban: slope effect, CA - AZ/UT (flock_time_after) | 20% growth goal (bootstrap) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Bald eagle (all years) | Newey-West, 3 lags | 49 | 0.43 (autocorrelation) | +4.58%/yr (t = 18.15, p < 0.0001 *) | -13.4% (t = -2.50, p = 0.0158 *) | -3.15%/yr (t = -10.50, p < 0.0001 *) | - | - | - | - | +21.1%, 95% lower bound +5.2% (p = 0.4619): not met |
| 2. Bald eagle (no 2009 outlier) | Newey-West, 3 lags | 48 | 0.34 (autocorrelation) | +4.58%/yr (t = 18.15, p < 0.0001 *) | -15.5% (t = -2.93, p = 0.0051 *) | -2.94%/yr (t = -10.56, p < 0.0001 *) | - | - | - | - | +25.1%, 95% lower bound +7.5% (p = 0.3241): not met |
| 3. Peregrine falcon | Newey-West, 3 lags | 49 | 0.15 (autocorrelation) | +5.17%/yr (t = 12.92, p < 0.0001 *) | +12.7% (t = 1.98, p = 0.0539) | -0.95%/yr (t = -2.34, p = 0.0236 *) | - | - | - | - | +155.9%, 95% lower bound +126.0% (p = 0.0002 *): met |
| 4. California condor, CA flock alone | OLS (too few points for Newey-West) | 2 | 2.97 (too few points to judge) | +5.91%/yr (t = 10.49, p = 0.0090 *) | -6.6% (t = -1.95, p = 0.1898) | -2.57%/yr (t = -3.37, p = 0.0781) | - | - | - | - | +20.7%, 95% lower bound +14.1% (p = 0.4173): not met |
| 5. California condor, CA vs AZ/UT | HC3 | 12 | AZ/UT 1.78; CA 2.97 (per flock) | +2.48%/yr (t = 2.88, p = 0.0137 *) | +22.9% (t = 2.20, p = 0.0477 *) | -3.43%/yr (t = -1.45, p = 0.1723) | +77.0% (t = 3.70, p = 0.0031 *) | +3.35%/yr (t = 0.94, p = 0.3682) | -24.1% (t = -1.53, p = 0.1512) | +0.89%/yr (t = 0.19, p = 0.8545) | - |

Each test cell shows the estimate as a percentage change, then t = coefficient / standard error (log scale) and the two-sided p-value; \* = significant at alpha = 0.05. A dash means the test does not apply to that model. Durbin-Watson is a rule-of-thumb check (about 2 = no autocorrelation), so it has no p-value. In model 5, the time, after and time_after columns describe the Arizona/Utah flock; the lead-ban effect is flock_after and flock_time_after. The 20% goal is met when the one-sided bootstrap 95% lower bound is above 20%.

## Forecasts

| Series | Best model | Test | MAE | MAPE | RMSE | 95% PI coverage (test) | 95% PI check | 2028 forecast (95% PI) | 2035 forecast (95% PI) |
|---|---|---|---|---|---|---|---|---|---|
| Bald eagle | Logistic | Holdout 2012-2022 | 0.00842 | 2.4% | 0.0103 | 11/11 (100%) | Passed | 0.380 (0.363-0.403) | 0.392 (0.373-0.417) |
| Peregrine falcon | Logistic | Holdout 2012-2022 | 0.000811 | 3.2% | 0.00103 | 10/11 (91%) | Passed | 0.0331 (0.0323-0.0343) | 0.0378 (0.0365-0.0395) |
| California condor, CA wild flock | Linear | Leave-one-out (6 points) | 5.34 | 3.4% | 6.57 | 5/6 (83%) | Passed | 239 (222-256) | 285 (262-307) |
| California condor, AZ/UT wild flock | Linear | Leave-one-out (14 points) | 8.26 | 8.6% | 10.6 | 13/14 (93%) | Passed | 118 (93-143) | 138 (106-169) |

The best model has the lowest test RMSE. Bald eagle and peregrine falcon values are Breeding Bird Survey abundance indices, not bird counts; condor values are numbers of wild birds. PI = prediction interval. 95% PI coverage is how many held-out values fell inside their 95% prediction interval, built without seeing them; about 95% should. The check fails only if coverage is significantly below 95% (one-sided binomial test, p < 0.05), because with 6-14 test points a single miss is expected.

## Year-by-year projections from the best models

| Year | Bald eagle (Logistic) | Peregrine falcon (Logistic) | California condor, CA wild flock (Linear) | California condor, AZ/UT wild flock (Linear) |
|---|---|---|---|---|
| 2023 | 0.369 (0.351-0.396) | 0.0293 (0.0286-0.0303) | - | - |
| 2024 | 0.371 (0.354-0.391) | 0.0301 (0.0294-0.0311) | - | - |
| 2025 | 0.374 (0.356-0.396) | 0.0309 (0.0301-0.0319) | - | - |
| 2026 | 0.376 (0.359-0.399) | 0.0316 (0.0309-0.0327) | 226 (210-242) | 112 (88-136) |
| 2027 | 0.378 (0.362-0.402) | 0.0324 (0.0315-0.0336) | 232 (216-249) | 115 (91-140) |
| 2028 | 0.380 (0.363-0.403) | 0.0331 (0.0323-0.0343) | 239 (222-256) | 118 (93-143) |
| 2029 | 0.382 (0.364-0.408) | 0.0338 (0.0330-0.0350) | 246 (228-263) | 121 (95-147) |
| 2030 | 0.384 (0.366-0.413) | 0.0345 (0.0336-0.0358) | 252 (234-270) | 124 (97-151) |
| 2031 | 0.386 (0.367-0.411) | 0.0352 (0.0342-0.0365) | 259 (240-278) | 126 (99-154) |
| 2032 | 0.387 (0.369-0.411) | 0.0359 (0.0348-0.0373) | 265 (245-285) | 129 (101-158) |
| 2033 | 0.389 (0.371-0.413) | 0.0365 (0.0354-0.0381) | 272 (251-292) | 132 (103-162) |
| 2034 | 0.390 (0.371-0.420) | 0.0372 (0.0359-0.0388) | 278 (257-300) | 135 (104-165) |
| 2035 | 0.392 (0.373-0.417) | 0.0378 (0.0365-0.0395) | 285 (262-307) | 138 (106-169) |

Each cell is the projection with its 95% prediction interval in brackets, from the best model for that series (lowest test RMSE), refitted on all years. Projections start the year after each series' last data point (2022 for the bird indices, 2025 for the condor flocks). Bald eagle and peregrine falcon values are Breeding Bird Survey indices, not bird counts; condor values are numbers of wild birds. Intervals widen the further ahead the projection goes.

## Forecast model errors (all models)

| Series | Model | Test | Data points | MAE | RMSE | MAPE | 95% PI coverage (test) | 95% PI check | Best model (lowest RMSE) |
|---|---|---|---|---|---|---|---|---|---|
| Bald eagle | Linear | Holdout 2012-2022 | 53 | 0.0188 | 0.0220 | 5.4% | 9/11 (82%) | Passed | No |
| Bald eagle | Exponential | Holdout 2012-2022 | 53 | 0.154 | 0.163 | 43.9% | 0/11 (0%) | Failed | No |
| Bald eagle | Logistic | Holdout 2012-2022 | 53 | 0.00842 (lowest) | 0.0103 (lowest) | 2.4% (lowest) | 11/11 (100%) | Passed | Yes |
| Peregrine falcon | Linear | Holdout 2012-2022 | 53 | 0.00514 | 0.00530 | 20.8% | 1/11 (9%) | Failed | No |
| Peregrine falcon | Exponential | Holdout 2012-2022 | 53 | 0.00348 | 0.00409 | 13.6% | 9/11 (82%) | Passed | No |
| Peregrine falcon | Logistic | Holdout 2012-2022 | 53 | 0.000811 (lowest) | 0.00103 (lowest) | 3.2% (lowest) | 10/11 (91%) | Passed | Yes |
| California condor, CA wild flock | Linear | Leave-one-out | 6 | 5.34 (lowest) | 6.57 (lowest) | 3.4% (lowest) | 5/6 (83%) | Passed | Yes |
| California condor, CA wild flock | Exponential | Leave-one-out | 6 | 8.12 | 9.98 | 5.0% | 5/6 (83%) | Passed | No |
| California condor, AZ/UT wild flock | Linear | Leave-one-out | 14 | 8.26 (lowest) | 10.6 (lowest) | 8.6% (lowest) | 13/14 (93%) | Passed | Yes |
| California condor, AZ/UT wild flock | Exponential | Leave-one-out | 14 | 8.50 | 11.0 | 8.8% | 13/14 (93%) | Passed | No |

Errors are on the original scale (index values for the bald eagle and peregrine falcon, numbers of birds for the condor flocks); MAPE is in percent, so it can be compared across series. Bald eagle and peregrine falcon models were trained on 1970-2011 and tested on 2012-2022; the short condor series use leave-one-out cross-validation instead. The 95% PI check is explained under Forecasts.

## 2028 and 2035 predictions from every forecasting model

| Series | Model | 2028 forecast | 2028 95% PI | 2035 forecast | 2035 95% PI |
|---|---|---|---|---|---|
| Bald eagle | Linear | 0.426 | 0.401-0.451 | 0.471 | 0.446-0.497 |
| Bald eagle | Exponential | 0.590 | 0.436-0.783 | 0.752 | 0.552-1.00 |
| Bald eagle | Logistic (best) | 0.380 | 0.363-0.403 | 0.392 | 0.373-0.417 |
| Peregrine falcon | Linear | 0.0280 | 0.0237-0.0323 | 0.0316 | 0.0272-0.0359 |
| Peregrine falcon | Exponential | 0.0440 | 0.0368-0.0523 | 0.0624 | 0.0519-0.0744 |
| Peregrine falcon | Logistic (best) | 0.0331 | 0.0323-0.0343 | 0.0378 | 0.0365-0.0395 |
| California condor, CA wild flock | Linear (best) | 239 | 222-256 | 285 | 262-307 |
| California condor, CA wild flock | Exponential | 250 | 213-292 | 325 | 263-401 |
| California condor, AZ/UT wild flock | Linear (best) | 118 | 93-143 | 138 | 106-169 |
| California condor, AZ/UT wild flock | Exponential | 122 | 93-157 | 152 | 109-209 |

Logistic models were fitted only for the bald eagle and peregrine falcon; the condor series are too short for a reliable carrying capacity.

Data: ZSL/WWF 2026. Living Planet Database 2026.1 <www.livingplanetindex.org/data_portal>; USFWS California Condor Recovery Program annual population status reports.
