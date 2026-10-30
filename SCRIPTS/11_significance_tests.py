"""
Significance tests for the five interrupted time series (segmented regression) models.

For each model:
  - R-squared and adjusted R-squared
  - Durbin-Watson test on the residuals
  - The standard errors chosen by 08_fit_models.py (Newey-West when
    autocorrelation is present), read from the saved model, so every p-value
    here matches OUTPUT/tables/coefficients.csv
  - Two-sided t-tests (alpha = 0.05) on the level change (`after`)
    and slope change (`time_after`)
  - One-sided test of the 20% growth goal: did the population grow more than
    20% between the intervention year and the last year of data? The test uses
    a bootstrap one-sided 95% confidence interval; the goal is met when its
    lower bound is above 20%. Series with autocorrelated residuals (the ones
    given Newey-West SEs) use a moving-block bootstrap so that runs of
    correlated years stay together; the others resample single residuals.
    The analytic t-based bound and p-value are also saved, for comparison.
For model 5 (CA vs AZ/UT), it tests whether California's post-2019 level and
slope changes differ from Arizona/Utah's (`flock_after`, `flock_time_after`).

Usage: run 08_fit_models.py first, then from the repository's top folder run
    python SCRIPTS/11_significance_tests.py
It reads the model .pickle files in OUTPUT/models/. Output prints to the
screen and is saved to OUTPUT/tables/significance_test_results.csv.
Requires: pip install statsmodels pandas numpy scipy
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.stattools import durbin_watson

ROOT = Path(__file__).parent.parent
MODEL_DIR = ROOT / "OUTPUT" / "models"
OUT_PATH = ROOT / "OUTPUT" / "tables" / "significance_test_results.csv"

ALPHA = 0.05
THRESHOLD = 0.20
LOG_THRESHOLD = np.log(1 + THRESHOLD)

N_BOOT = 5000  # bootstrap resamples for the 20% growth test
SEED = 42      # fixed seed so the bootstrap gives the same result every run

# First year of each series (time = 0), used to turn `time` back into calendar years
START_YEAR = {"bald_eagle": 1970, "peregrine": 1970, "condor": 2012}


def load(path):
    # Loaded inside a function: statsmodels formula models need a calling frame
    with open(path, "rb") as f:
        return pickle.load(f)


def start_year(path):
    return next(y for k, y in START_YEAR.items() if k in path)


def se_label(res, small):
    """Describe the standard errors a saved model was fitted with by 08_fit_models.py."""
    if res.cov_type == "HAC":
        return f"Newey-West, {res.cov_kwds['maxlags']} lags"
    if res.cov_type == "HC3":
        return "HC3"
    return "OLS (too few points for Newey-West)" if small else "OLS"


def one_sided(res, c):
    """H1: c'beta > ln(1.2). Returns estimate, one-sided 95% lower bound, p."""
    est = float(c @ res.params.values)
    se = float(np.sqrt(c @ res.cov_params().values @ c))
    df = res.df_resid
    p = 1 - stats.t.cdf((est - LOG_THRESHOLD) / se, df)
    lb = est - stats.t.ppf(1 - ALPHA, df) * se
    return np.expm1(est), np.expm1(lb), p


def block_length(n):
    """Moving-block length for autocorrelated series: about n^(1/3) years
    (4 for the 52-53 year bird indices)."""
    return max(2, round(n ** (1 / 3)))


def bootstrap_growth(res, c, block):
    """Residual bootstrap of the growth c'beta (log scale) for H1: c'beta > ln(1.2).

    Each resample keeps the fitted line and adds residuals drawn with
    replacement, then refits the regression on the same design. block = 1
    draws single residuals; block > 1 draws runs of `block` consecutive
    residuals (moving-block bootstrap), which keeps year-to-year correlation.
    Residuals are centred and scaled by sqrt(n / (n - p)), because fitted OLS
    residuals are smaller on average than the true errors.

    Returns the one-sided 95% lower bound (5th percentile, as % growth) and
    the bootstrap p-value: the share of resamples with growth <= 20%.
    """
    X = res.model.exog
    fitted = res.fittedvalues.values
    n, p = X.shape
    resid = (res.resid.values - res.resid.values.mean()) * np.sqrt(n / (n - p))

    rng = np.random.default_rng(SEED)
    n_blocks = int(np.ceil(n / block))
    est = np.empty(N_BOOT)
    for b in range(N_BOOT):
        # Random block starts, joined and trimmed back to n residuals.
        starts = rng.integers(0, n - block + 1, n_blocks)
        e = np.concatenate([resid[s:s + block] for s in starts])[:n]
        beta = np.linalg.lstsq(X, fitted + e, rcond=None)[0]
        est[b] = c @ beta

    lower = np.expm1(np.percentile(est, 100 * ALPHA))
    p = (np.sum(est <= LOG_THRESHOLD) + 1) / (N_BOOT + 1)
    return lower, p


def flag(p):
    return "SIGNIFICANT" if p < ALPHA else "not significant"


def main():
    rows = []
    # Only the segmented-regression models; forecast models are in models/forecast/.
    for model_path in sorted(MODEL_DIR.glob("*.pickle")):
        saved = load(model_path)
        path = model_path.name  # file name, used for labels and the start year
        model = saved.model
        names = list(model.exog_names)
        X = pd.DataFrame(model.exog, columns=names)
        n = int(saved.nobs)
        y0 = start_year(path)

        ols = model.fit(use_t=True)  # plain OLS, for R^2 and Durbin-Watson
        print("=" * 78)
        print(f"{path}   (n = {n}, residual df = {int(ols.df_resid)})")
        print(f"R^2 = {ols.rsquared:.3f}   adj R^2 = {ols.rsquared_adj:.3f}")

        # ---------- Model 5: two flocks in one model ----------
        if "flock" in names:
            # Durbin-Watson within each flock (stacked residuals would mix the two series)
            dws = {g: durbin_watson(ols.resid[X["flock"] == g]) for g in (0, 1)}
            print(f"Durbin-Watson: Arizona/Utah = {dws[0]:.2f}, California = {dws[1]:.2f}")
            # Use the model exactly as 08_fit_models.py fitted it (HC3 for two
            # stacked flocks), so the p-values match coefficients.csv.
            final = saved
            print(f"SEs: {se_label(final, small=False)}")
            print(final.summary().tables[1])
            for term, label in (("flock_after", "Difference in level change (CA minus AZ/UT)"),
                                ("flock_time_after", "Difference in slope change (CA minus AZ/UT)")):
                b, p = final.params[term], final.pvalues[term]
                unit = " per year" if "time" in term else ""
                print(f"  {label}: {np.expm1(b):+.1%}{unit}  (p = {p:.4f}, two-sided)  {flag(p)}")
            rows.append({
                "model": path, "intervention_year": 2019, "n": n, "resid_df": int(ols.df_resid),
                "r2": round(ols.rsquared, 3), "adj_r2": round(ols.rsquared_adj, 3),
                "durbin_watson": f"AZ/UT {dws[0]:.2f}; CA {dws[1]:.2f}",
                "se_type": se_label(final, small=False),
                "level_change_pct": round(100 * np.expm1(final.params["flock_after"]), 2),
                "level_p": round(final.pvalues["flock_after"], 4),
                "slope_change_pct_per_yr": round(100 * np.expm1(final.params["flock_time_after"]), 2),
                "slope_p": round(final.pvalues["flock_time_after"], 4),
                "note": "CA minus AZ/UT difference in post-2019 changes",
            })
            continue

        # ---------- Single-series models (1-4) ----------
        dw = durbin_watson(ols.resid)
        small = ols.df_resid < 10
        # Use the model exactly as 08_fit_models.py fitted it: it already chose
        # the standard errors (Newey-West when Durbin-Watson shows
        # autocorrelation, plain OLS otherwise), so p-values match coefficients.csv.
        final = saved
        se_type = se_label(final, small)
        dw_note = " (unreliable with this few points)" if small else (
            " -> autocorrelation present" if not 1.5 <= dw <= 2.5 else " -> no strong autocorrelation")
        print(f"Durbin-Watson = {dw:.2f}{dw_note}")
        print(f"SEs: {se_type}")
        print(final.summary().tables[1])

        b_lvl, p_lvl = final.params["after"], final.pvalues["after"]
        b_slp, p_slp = final.params["time_after"], final.pvalues["time_after"]

        # Intervention year: first post row's time minus its years-since value
        r0 = X.index[X["after"] > 0][0]
        t0 = X.loc[r0, "time"] - X.loc[r0, "time_after"]
        year0 = int(y0 + t0)
        last = X.iloc[-1]

        # Growth along the fitted post-intervention line, from the intervention
        # year to the last year: (b_time + b_time_after) * (T - t0)
        span = last["time"] - t0
        c_growth = np.array([0, span, 0, span])
        growth, growth_lb_t, p_growth_t = one_sided(final, c_growth)

        # Bootstrap 95% lower bound for the 20% goal. Block bootstrap where the
        # residuals are autocorrelated (Newey-West models), single residuals otherwise.
        block = block_length(n) if se_type.startswith("Newey-West") else 1
        boot_method = f"moving-block bootstrap, block {block}" if block > 1 else "residual bootstrap"
        growth_lb, p_growth = bootstrap_growth(final, c_growth, block)

        # Effect relative to the pre-intervention trend continuing
        c_eff = np.array([0, 0, 1, last["time_after"]])
        effect = np.expm1(float(c_eff @ final.params.values))

        print(f"\n  Intervention year: {year0}   last year: {int(y0 + last['time'])}")
        print(f"  Level change: {np.expm1(b_lvl):+.1%}  (p = {p_lvl:.4f}, two-sided)  {flag(p_lvl)}")
        print(f"  Slope change: {np.expm1(b_slp):+.2%} per year  (p = {p_slp:.4f}, two-sided)  {flag(p_slp)}")
        print(f"  Pre-intervention growth: {np.expm1(final.params['time']):+.2%} per year;"
              f" after: {np.expm1(final.params['time'] + b_slp):+.2%} per year")
        print(f"  Growth since {year0}: {growth:+.1%}  (bootstrap one-sided 95% lower bound"
              f" {growth_lb:+.1%}, p = {p_growth:.4f}; {boot_method}, {N_BOOT} resamples)"
              f"  -> 20% goal {'MET' if growth_lb > THRESHOLD else 'NOT met'}")
        print(f"    for comparison, t-based lower bound {growth_lb_t:+.1%} (p = {p_growth_t:.4f})")
        print(f"  Compared with the pre-{year0} trend continuing: {effect:+.1%}")

        rows.append({
            "model": path, "intervention_year": year0, "n": n, "resid_df": int(ols.df_resid),
            "r2": round(ols.rsquared, 3), "adj_r2": round(ols.rsquared_adj, 3),
            "durbin_watson": round(dw, 2), "se_type": se_type,
            "level_change_pct": round(100 * np.expm1(b_lvl), 2), "level_p": round(p_lvl, 4),
            "slope_change_pct_per_yr": round(100 * np.expm1(b_slp), 2), "slope_p": round(p_slp, 4),
            "growth_pre_pct_per_yr": round(100 * np.expm1(final.params["time"]), 2),
            "growth_post_pct_per_yr": round(100 * np.expm1(final.params["time"] + b_slp), 2),
            "growth_since_pct": round(100 * growth, 1),
            "growth_lower_bound_pct": round(100 * growth_lb, 1),
            "growth_p_one_sided": round(p_growth, 4),
            "meets_20pct": bool(growth_lb > THRESHOLD),
            "bootstrap_method": f"{boot_method}, {N_BOOT} resamples",
            "growth_lower_bound_t_pct": round(100 * growth_lb_t, 1),
            "growth_p_one_sided_t": round(p_growth_t, 4),
            "vs_pretrend_pct": round(100 * effect, 1),
        })

    pd.DataFrame(rows).to_csv(OUT_PATH, index=False)
    print(f"\nSaved {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
