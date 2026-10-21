"""
Significance tests for the five interrupted time series (segmented regression) models.

For each model:
  - R-squared and adjusted R-squared
  - Durbin-Watson test on the residuals
  - Newey-West (HAC) standard errors when autocorrelation is present
  - Two-sided t-tests (alpha = 0.05) on the level change (`after`)
    and slope change (`time_after`)
  - One-sided test of the 20% growth goal: did the population grow more than
    20% between the intervention year and the last year of data?
For model 5 (CA vs AZ/UT), it tests whether California's post-2019 level and
slope changes differ from Arizona/Utah's (`flock_after`, `flock_time_after`).

Usage: put this file next to the .pickle files and run
    python significance_tests.py
Output prints to the screen and is saved to significance_test_results.csv.
Requires: pip install statsmodels pandas numpy scipy
"""

import glob
import pickle

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.stattools import durbin_watson

ALPHA = 0.05
THRESHOLD = 0.20
LOG_THRESHOLD = np.log(1 + THRESHOLD)

# First year of each series (time = 0), used to turn `time` back into calendar years
START_YEAR = {"bald_eagle": 1970, "peregrine": 1970, "condor": 2012}


def load(path):
    # Loaded inside a function: statsmodels formula models need a calling frame
    with open(path, "rb") as f:
        return pickle.load(f)


def start_year(path):
    return next(y for k, y in START_YEAR.items() if k in path)


def hac_lags(n):
    return max(1, int(np.floor(4 * (n / 100) ** (2 / 9))))


def one_sided(res, c):
    """H1: c'beta > ln(1.2). Returns estimate, one-sided 95% lower bound, p."""
    est = float(c @ res.params.values)
    se = float(np.sqrt(c @ res.cov_params().values @ c))
    df = res.df_resid
    p = 1 - stats.t.cdf((est - LOG_THRESHOLD) / se, df)
    lb = est - stats.t.ppf(1 - ALPHA, df) * se
    return np.expm1(est), np.expm1(lb), p


def flag(p):
    return "SIGNIFICANT" if p < ALPHA else "not significant"


def main():
    rows = []
    for path in sorted(glob.glob("*.pickle")):
        saved = load(path)
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
            # Heteroskedasticity-robust SEs (HC3), as the model was saved with;
            # HAC doesn't apply to two stacked series with gaps
            final = model.fit(cov_type="HC3", use_t=True)
            print("SEs: HC3 (heteroskedasticity-robust)")
            print(final.summary().tables[1])
            for term, label in (("flock_after", "Difference in level change (CA minus AZ/UT)"),
                                ("flock_time_after", "Difference in slope change (CA minus AZ/UT)")):
                b, p = final.params[term], final.pvalues[term]
                unit = " per year" if "time" in term else ""
                print(f"  {label}: {np.expm1(b):+.1%}{unit}  (p = {p:.4f}, two-sided)  {flag(p)}")
            rows.append({
                "model": path, "intervention_year": 2019, "n": n, "resid_df": int(ols.df_resid),
                "r2": round(ols.rsquared, 3), "adj_r2": round(ols.rsquared_adj, 3),
                "durbin_watson": f"AZ/UT {dws[0]:.2f}; CA {dws[1]:.2f}", "se_type": "HC3",
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
        if small:
            final, se_type = ols, "OLS (too few points for Newey-West)"
        elif not 1.5 <= dw <= 2.5:
            lags = hac_lags(n)
            final = model.fit(cov_type="HAC", cov_kwds={"maxlags": lags}, use_t=True)
            se_type = f"Newey-West, {lags} lags"
        else:
            final, se_type = ols, "OLS"
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
        growth, growth_lb, p_growth = one_sided(final, c_growth)

        # Effect relative to the pre-intervention trend continuing
        c_eff = np.array([0, 0, 1, last["time_after"]])
        effect = np.expm1(float(c_eff @ final.params.values))

        print(f"\n  Intervention year: {year0}   last year: {int(y0 + last['time'])}")
        print(f"  Level change: {np.expm1(b_lvl):+.1%}  (p = {p_lvl:.4f}, two-sided)  {flag(p_lvl)}")
        print(f"  Slope change: {np.expm1(b_slp):+.2%} per year  (p = {p_slp:.4f}, two-sided)  {flag(p_slp)}")
        print(f"  Pre-intervention growth: {np.expm1(final.params['time']):+.2%} per year;"
              f" after: {np.expm1(final.params['time'] + b_slp):+.2%} per year")
        print(f"  Growth since {year0}: {growth:+.1%}  (one-sided 95% lower bound {growth_lb:+.1%},"
              f" p = {p_growth:.4f})  -> 20% goal {'MET' if growth_lb > THRESHOLD else 'NOT met'}")
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
            "vs_pretrend_pct": round(100 * effect, 1),
        })

    pd.DataFrame(rows).to_csv("significance_test_results.csv", index=False)
    print("\nSaved significance_test_results.csv")


if __name__ == "__main__":
    main()
