"""Fit segmented regression (interrupted time series) models.

Inputs:  DATA/model_ready_lpd.csv     (bald eagle 2910, peregrine falcon 28210)
         DATA/model_ready_condor.csv  (California and Arizona/Utah wild flocks)
Outputs: OUTPUT/tables/coefficients.csv   one row per model coefficient
         OUTPUT/tables/model_summary.csv  fit statistics, one row per model
         OUTPUT/tables/fitted_values.csv  fitted values and residuals per year
         OUTPUT/models/model_*.pickle     the fitted models (read by 09 and 11)

Outcome: log_count = ln(count), so exp(coef) - 1 is a proportional change.
- time:       yearly growth before the breakpoint
- after:      immediate level change at the breakpoint
- time_after: change in yearly growth after the breakpoint

Standard errors are chosen here, once, and saved with each model, so that
11_significance_tests.py reports exactly the same standard errors and p-values:
- two stacked flocks (model 5): HC3 (robust to unequal variance between flocks)
- fewer than 10 residual degrees of freedom: plain OLS (too few points to
  estimate autocorrelation)
- Durbin-Watson outside 1.5-2.5 (autocorrelated residuals): Newey-West (HAC)
- otherwise: plain OLS
All p-values and confidence intervals use the t-distribution (use_t=True).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.stattools import durbin_watson

# File locations, relative to the repository's top folder.
ROOT = Path(__file__).parent.parent
LPD_PATH = ROOT / "DATA" / "model_ready_lpd.csv"
CONDOR_PATH = ROOT / "DATA" / "model_ready_condor.csv"
OUT_DIR = ROOT / "OUTPUT" / "tables"
MODEL_DIR = ROOT / "OUTPUT" / "models"

# Single-series model: a straight line in log_count before the breakpoint,
# plus a jump (after) and a change in slope (time_after) at the breakpoint.
ITS_FORMULA = "log_count ~ time + after + time_after"
# Comparative ITS: flock and flock_time let CA and AZ/UT have different
# starting levels and pre-2019 growth; flock_after and flock_time_after test
# whether CA's change at 2019 differs from AZ/UT's. In this model `after` and
# `time_after` are the Arizona/Utah (comparison) flock's changes, not CA's.
CITS_FORMULA = ("log_count ~ time + flock + flock_time"
                " + after + time_after + flock_after + flock_time_after")

# Rule-of-thumb Durbin-Watson range for "no strong autocorrelation" (about 2
# means none; well below 2 means consecutive years move together).
DW_LOW, DW_HIGH = 1.5, 2.5
MIN_DF_FOR_HAC = 10  # below this, too few points to estimate autocorrelation


def hac_lags(n: int) -> int:
    """Newey-West lag length, floor(4 * (n / 100) ** (2 / 9)): 3 for n = 52-53."""
    return max(1, int(np.floor(4 * (n / 100) ** (2 / 9))))


def fit(name: str, formula: str, data: pd.DataFrame, two_flocks: bool = False) -> dict:
    """Fit one OLS model and choose its standard errors (see the module docstring).

    use_t=True takes p-values and confidence intervals from the t-distribution
    (not the normal), which is safer with these small samples.
    """
    model = smf.ols(formula, data)
    # Plain OLS first: needed for its residuals, to run the Durbin-Watson test.
    ols = model.fit(use_t=True)

    if two_flocks:
        # Two separate series stacked together: autocorrelation cannot be
        # estimated across them, but their variances may differ, so use HC3.
        result, cov = model.fit(cov_type="HC3", use_t=True), "HC3"
    elif ols.df_resid < MIN_DF_FOR_HAC:
        result, cov = ols, "OLS"
    elif not DW_LOW <= durbin_watson(ols.resid) <= DW_HIGH:
        # Autocorrelated residuals make plain OLS standard errors too small;
        # Newey-West widens them. HAC needs rows in time order (true here).
        lags = hac_lags(int(ols.nobs))
        result = model.fit(cov_type="HAC", cov_kwds={"maxlags": lags}, use_t=True)
        cov = "HAC"
    else:
        result, cov = ols, "OLS"
    return {"name": name, "result": result, "data": data, "cov": cov}


def tidy(model: dict) -> pd.DataFrame:
    """Coefficient table for one model: estimate, standard error, p-value and
    95% confidence interval for every term."""
    r = model["result"]
    ci = r.conf_int()  # 95% intervals, from the t-distribution
    return pd.DataFrame({
        "model": model["name"],
        "term": r.params.index,
        "coef": r.params.values,
        "std_err": r.bse.values,
        "p_value": r.pvalues.values,
        "ci_low": ci[0].values,
        "ci_high": ci[1].values,
        # Proportional effect on the original scale, e.g. 0.05 = +5%.
        "pct_effect": np.expm1(r.params.values) * 100,
    })


def summarise(model: dict) -> dict:
    """One row of fit statistics for one model."""
    r = model["result"]
    d = model["data"]
    if "flock" in r.model.exog_names:
        # Two flocks stacked in one model: test each flock's residuals on
        # their own, since stacked residuals mix two separate time series.
        dws = {g: durbin_watson(r.resid[d["flock"] == g]) for g in (0, 1)}
        dw = f"AZ/UT {dws[0]:.3f}; CA {dws[1]:.3f}"
    else:
        dw = durbin_watson(r.resid)
    return {
        "model": model["name"],
        "n": int(r.nobs),
        "params": len(r.params),
        "df_resid": int(r.df_resid),  # data points minus parameters
        "r_squared": r.rsquared,
        "adj_r_squared": r.rsquared_adj,
        "durbin_watson": dw,
        "std_errors": model["cov"],
    }


def fitted_table(model: dict) -> pd.DataFrame:
    """Observed and fitted values for every year used by one model."""
    d = model["data"]
    r = model["result"]
    keep = ["species", "ID", "year", "count", "log_count", "outlier_flag"]
    out = d[keep].copy()
    out.insert(0, "model", model["name"])
    out["fitted_log"] = r.fittedvalues.values
    out["fitted_count"] = np.exp(out["fitted_log"])  # back to the original scale
    out["residual_log"] = r.resid.values
    return out


def save_models(models: list[dict]) -> list[Path]:
    """Save each fitted model with statsmodels' .save() (a pickle file).

    The saved models keep their data and their standard-error settings, so
    they can be reloaded and used for .summary(), .predict() or
    .get_prediction() without refitting:

        from statsmodels.regression.linear_model import OLSResults
        model = OLSResults.load("OUTPUT/models/model_1_bald_eagle_all_years.pickle")

    Only load pickle files you created yourself: loading a pickle can run code.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for m in models:
        # "1 Bald eagle (all years)" -> "model_1_bald_eagle_all_years.pickle"
        slug = "".join(c if c.isalnum() else "_" for c in m["name"].lower())
        slug = "_".join(part for part in slug.split("_") if part)
        path = MODEL_DIR / f"model_{slug}.pickle"
        m["result"].save(str(path))
        paths.append(path)
    return paths


if __name__ == "__main__":
    # Load the model-ready data (made by 07_make_model_vars.py), in time order.
    lpd = pd.read_csv(LPD_PATH, dtype={"ID": str}).sort_values(["ID", "year"])
    condor = pd.read_csv(CONDOR_PATH, dtype={"ID": str}).sort_values(["ID", "year"])

    # One data frame per modelled series.
    eagle = lpd[lpd["ID"] == "2910"].reset_index(drop=True)
    peregrine = lpd[lpd["ID"] == "28210"].reset_index(drop=True)
    ca = condor[condor["ID"] == "USFWS-CA-WILD"].reset_index(drop=True)

    models = [
        fit("1 Bald eagle (all years)", ITS_FORMULA, eagle),
        # Sensitivity check: the same model without the flagged 2009 spike.
        fit("2 Bald eagle (no 2009 outlier)", ITS_FORMULA,
            eagle[~eagle["outlier_flag"]].reset_index(drop=True)),
        fit("3 Peregrine falcon", ITS_FORMULA, peregrine),
        # 6 points, 4 parameters: shown for transparency only.
        fit("4 Condor CA flock alone", ITS_FORMULA, ca),
        # Both flocks in one model, to compare CA (lead ban) with AZ/UT.
        fit("5 Condor CA vs AZ/UT", CITS_FORMULA, condor.reset_index(drop=True), two_flocks=True),
    ]

    # Build and save the three tables, then the fitted models themselves.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coefs = pd.concat([tidy(m) for m in models], ignore_index=True)
    summary = pd.DataFrame([summarise(m) for m in models])
    fitted = pd.concat([fitted_table(m) for m in models], ignore_index=True)
    coefs.to_csv(OUT_DIR / "coefficients.csv", index=False)
    summary.to_csv(OUT_DIR / "model_summary.csv", index=False)
    fitted.to_csv(OUT_DIR / "fitted_values.csv", index=False)
    saved = save_models(models)

    # Print the results to the screen.
    pd.set_option("display.width", 200)
    print("Model summary:\n")
    print(summary.round(3).to_string(index=False))
    print("\nCoefficients:\n")
    for name, c in coefs.groupby("model", sort=False):
        print(name)
        print(c.drop(columns="model").round(4).to_string(index=False), "\n")
    print(f"Saved results to {OUT_DIR}")
    print("Saved models:")
    for path in saved:
        print(f"  {path.relative_to(ROOT)}")
