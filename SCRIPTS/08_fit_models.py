"""Fit segmented regression (interrupted time series) models.

Outcome: log_count = ln(count), so exp(coef) - 1 is a proportional change.
- time:       yearly growth before the breakpoint
- after:      immediate level change at the breakpoint
- time_after: change in yearly growth after the breakpoint

Tables are written to OUTPUT/tables/ and fitted models to OUTPUT/models/.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.stattools import durbin_watson

ROOT = Path(__file__).parent.parent
LPD_PATH = ROOT / "DATA" / "model_ready_lpd.csv"
CONDOR_PATH = ROOT / "DATA" / "model_ready_condor.csv"
OUT_DIR = ROOT / "OUTPUT" / "tables"
MODEL_DIR = ROOT / "OUTPUT" / "models"

ITS_FORMULA = "log_count ~ time + after + time_after"
# Comparative ITS: flock and flock_time let CA and AZ/UT have different
# starting levels and pre-2019 growth; flock_after and flock_time_after test
# whether CA's change at 2019 differs from AZ/UT's.
CITS_FORMULA = ("log_count ~ time + flock + flock_time"
                " + after + time_after + flock_after + flock_time_after")

# Newey-West lags for the annual BBS index series (n = 52-53):
# floor(4 * (n / 100) ** (2 / 9)) = 3.
HAC_LAGS = 3


def fit(name: str, formula: str, data: pd.DataFrame, cov: str):
    """Fit one OLS model with the chosen standard errors."""
    if cov == "HAC":
        # HAC needs rows in time order with no gaps (true for the BBS series).
        result = smf.ols(formula, data).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    elif cov == "HC3":
        result = smf.ols(formula, data).fit(cov_type="HC3")
    else:
        result = smf.ols(formula, data).fit()
    return {"name": name, "result": result, "data": data, "cov": cov}


def tidy(model: dict) -> pd.DataFrame:
    """Coefficient table for one model."""
    r = model["result"]
    ci = r.conf_int()
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
    r = model["result"]
    return {
        "model": model["name"],
        "n": int(r.nobs),
        "params": len(r.params),
        "df_resid": int(r.df_resid),
        "r_squared": r.rsquared,
        "adj_r_squared": r.rsquared_adj,
        "durbin_watson": durbin_watson(r.resid),
        "std_errors": model["cov"],
    }


def fitted_table(model: dict) -> pd.DataFrame:
    d = model["data"]
    r = model["result"]
    keep = ["species", "ID", "year", "count", "log_count", "outlier_flag"]
    out = d[keep].copy()
    out.insert(0, "model", model["name"])
    out["fitted_log"] = r.fittedvalues.values
    out["fitted_count"] = np.exp(out["fitted_log"])
    out["residual_log"] = r.resid.values
    return out


def save_models(models: list[dict]) -> list[Path]:
    """Save each fitted model with statsmodels' .save() (a pickle file).

    The saved models keep their data, so they can be reloaded and used for
    .summary(), .predict() or .get_prediction() without refitting:

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
    lpd = pd.read_csv(LPD_PATH, dtype={"ID": str}).sort_values(["ID", "year"])
    condor = pd.read_csv(CONDOR_PATH, dtype={"ID": str}).sort_values(["ID", "year"])

    eagle = lpd[lpd["ID"] == "2910"].reset_index(drop=True)
    peregrine = lpd[lpd["ID"] == "28210"].reset_index(drop=True)
    ca = condor[condor["ID"] == "USFWS-CA-WILD"].reset_index(drop=True)

    models = [
        fit("1 Bald eagle (all years)", ITS_FORMULA, eagle, "HAC"),
        fit("2 Bald eagle (no 2009 outlier)", ITS_FORMULA,
            eagle[~eagle["outlier_flag"]].reset_index(drop=True), "HAC"),
        fit("3 Peregrine falcon", ITS_FORMULA, peregrine, "HAC"),
        # 6 points, 4 parameters: shown for transparency only.
        fit("4 Condor CA flock alone", ITS_FORMULA, ca, "OLS"),
        fit("5 Condor CA vs AZ/UT", CITS_FORMULA, condor.reset_index(drop=True), "HC3"),
    ]

    OUT_DIR.mkdir(exist_ok=True)
    coefs = pd.concat([tidy(m) for m in models], ignore_index=True)
    summary = pd.DataFrame([summarise(m) for m in models])
    fitted = pd.concat([fitted_table(m) for m in models], ignore_index=True)
    coefs.to_csv(OUT_DIR / "coefficients.csv", index=False)
    summary.to_csv(OUT_DIR / "model_summary.csv", index=False)
    fitted.to_csv(OUT_DIR / "fitted_values.csv", index=False)
    saved = save_models(models)

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
