"""Collect the main results into summary tables (no new analysis here).

Inputs:  OUTPUT/tables/coefficients.csv, model_summary.csv (from 08_fit_models.py)
         OUTPUT/tables/forecast_comparison.csv, forecasts.csv,
         forecast_projections_yearly.csv (from 10_forecast_models.py)
         OUTPUT/tables/significance_test_results.csv (from 11_significance_tests.py)
Outputs (all in OUTPUT/tables/):
- results_summary_segmented_regression.csv: one row per segmented-regression
  model: fit (R-squared, Durbin-Watson), level and slope changes with their
  two-sided t-test p-values, and the bootstrap test of the 20% growth goal.
- results_summary_forecasts.csv: one row per series: the chosen forecasting
  model, its test errors (MAE, MAPE, RMSE) and the 2028 and 2035 forecasts
  with 95% prediction intervals.
- results_summary_significance_tests.csv: every significance test for each
  segmented-regression model: one row per model and one column per test
  (Durbin-Watson, a t-test per coefficient, and the bootstrap 20% test).
- results_summary_forecast_errors.csv: test errors (MAE, RMSE, MAPE) for
  every forecasting model, with the lowest value per series marked.
- results_summary_projections_best_models.csv: year-by-year projections
  (with 95% prediction intervals) from each series' best model, through 2035.
- results_summary_forecasts_all_models.csv: the 2028 and 2035 predictions
  from every forecasting model (linear, exponential, logistic), not only the best.
- results_summary.md: all six tables, formatted for reading on GitHub.

Run 08_fit_models.py, 10_forecast_models.py and 11_significance_tests.py first.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
TABLE_DIR = ROOT / "OUTPUT" / "tables"
ALPHA = 0.05

# Readable names for the saved model files used by 11_significance_tests.py.
MODEL_LABELS = {
    "model_1_bald_eagle_all_years.pickle": "1. Bald eagle (all years)",
    "model_2_bald_eagle_no_2009_outlier.pickle": "2. Bald eagle (no 2009 outlier)",
    "model_3_peregrine_falcon.pickle": "3. Peregrine falcon",
    "model_4_condor_ca_flock_alone.pickle": "4. California condor, CA flock alone",
    "model_5_condor_ca_vs_az_ut.pickle": "5. California condor, CA vs AZ/UT",
}
EVENTS = {2007: "Delisting (2007)", 1999: "Delisting (1999)", 2019: "CA lead ban (2019)"}


def pct(value, digits=1, sign=True):
    """Format a percentage, or a dash when it does not apply."""
    if pd.isna(value):
        return "-"
    return f"{value:+.{digits}f}%" if sign else f"{value:.{digits}f}%"


def p_text(p):
    """p-value with a star when significant at alpha = 0.05."""
    if pd.isna(p):
        return "-"
    text = "< 0.0001" if p < 0.0001 else f"{p:.4f}"
    return f"{text} *" if p < ALPHA else text


def p_cell(p):
    """'p = 0.0158 *' or 'p < 0.0001 *' for use inside a table cell."""
    text = p_text(p)
    return f"p {text}" if text.startswith("<") else f"p = {text}"


def number(x):
    """Index values are small (e.g. 0.42); bird counts are whole numbers."""
    # '#' keeps trailing zeros, so 1.003 shows as 1.00 rather than 1.
    return f"{x:.0f}" if abs(x) >= 10 else f"{x:#.3g}"


def error(x):
    """Error metrics always keep 3 significant digits (10.6 vs 11.0), so
    close values are never shown as a tie."""
    return f"{x:#.3g}"


def segmented_regression_table() -> pd.DataFrame:
    """One row per segmented-regression model: fit statistics, the level and
    slope changes with their p-values, and the 20% growth test."""
    sig = pd.read_csv(TABLE_DIR / "significance_test_results.csv")
    # Unrounded % effects from 08_fit_models.py. significance_test_results.csv
    # stores them rounded to 2 decimals, and rounding again can be off by 0.1.
    coefs = pd.read_csv(TABLE_DIR / "coefficients.csv").set_index(["model", "term"])["pct_effect"]
    model_names = {f: name for name, f in SIG_FILES.items()}
    rows = []
    for _, r in sig.iterrows():
        comparison = r["model"].startswith("model_5")
        name = model_names[r["model"]]
        level_term, slope_term = ("flock_after", "flock_time_after") if comparison else ("after", "time_after")
        r["level_change_pct"] = coefs[(name, level_term)]
        r["slope_change_pct_per_yr"] = coefs[(name, slope_term)]
        rows.append({
            "Model": MODEL_LABELS.get(r["model"], r["model"]),
            "Event": EVENTS.get(r["intervention_year"], r["intervention_year"]),
            "n": r["n"],
            "R2": r["r2"],
            "Adj. R2": r["adj_r2"],
            "Durbin-Watson": r["durbin_watson"],
            "Standard errors": r["se_type"],
            # Model 5 reports how California's changes differ from Arizona/Utah's.
            "Level change": pct(r["level_change_pct"]) + (" (CA - AZ/UT)" if comparison else ""),
            "Level p": p_text(r["level_p"]),
            "Slope change per year": pct(r["slope_change_pct_per_yr"], 2) + (" (CA - AZ/UT)" if comparison else ""),
            "Slope p": p_text(r["slope_p"]),
            "Growth since event": pct(r["growth_since_pct"]),
            "Bootstrap 95% lower bound": pct(r["growth_lower_bound_pct"]),
            "20% goal met": "-" if pd.isna(r["meets_20pct"]) else ("Yes" if r["meets_20pct"] else "No"),
        })
    return pd.DataFrame(rows)


# One column per test. Model 5 stacks the two condor flocks, so in that row the
# `time`, `after` and `time_after` columns describe Arizona/Utah, and the flock_*
# columns are California minus Arizona/Utah (the lead-ban comparison).
TEST_COLUMNS = {
    "time": "Pre-event growth (time)",
    "after": "Level change (after)",
    "time_after": "Slope change (time_after)",
    "flock": "CA vs AZ/UT starting level (flock)",
    "flock_time": "CA vs AZ/UT pre-2019 growth (flock_time)",
    "flock_after": "Lead ban: level effect, CA - AZ/UT (flock_after)",
    "flock_time_after": "Lead ban: slope effect, CA - AZ/UT (flock_time_after)",
}
SIG_FILES = {  # 08_fit_models.py model names -> 11_significance_tests.py model files
    "1 Bald eagle (all years)": "model_1_bald_eagle_all_years.pickle",
    "2 Bald eagle (no 2009 outlier)": "model_2_bald_eagle_no_2009_outlier.pickle",
    "3 Peregrine falcon": "model_3_peregrine_falcon.pickle",
    "4 Condor CA flock alone": "model_4_condor_ca_flock_alone.pickle",
    "5 Condor CA vs AZ/UT": "model_5_condor_ca_vs_az_ut.pickle",
}


def significance_tests_table() -> pd.DataFrame:
    """Every significance test for each segmented-regression model, one row per
    model and one column per test: the Durbin-Watson check, a two-sided t-test
    for every coefficient except the intercept, and (models 1-4) the one-sided
    bootstrap test of the 20% goal. A dash means the test does not apply."""
    coefs = pd.read_csv(TABLE_DIR / "coefficients.csv")
    summary = pd.read_csv(TABLE_DIR / "model_summary.csv").set_index("model")
    sig = pd.read_csv(TABLE_DIR / "significance_test_results.csv").set_index("model")
    rows = []
    for name, sig_file in SIG_FILES.items():
        s = sig.loc[sig_file]
        row = {"Model": MODEL_LABELS[sig_file],
               "Standard errors": s["se_type"],
               "df": int(summary.loc[name, "df_resid"])}

        # Durbin-Watson: a rule-of-thumb check (about 2 = no autocorrelation;
        # outside 1.5-2.5 = autocorrelation), so it has no p-value.
        dw = s["durbin_watson"]
        if name.startswith("5"):
            row["Durbin-Watson"] = f"{dw} (per flock)"
        elif s["n"] < 14:
            row["Durbin-Watson"] = f"{dw} (too few points to judge)"
        elif not 1.5 <= float(dw) <= 2.5:
            row["Durbin-Watson"] = f"{dw} (autocorrelation)"
        else:
            row["Durbin-Watson"] = f"{dw} (no strong autocorrelation)"

        # Two-sided t-tests (alpha = 0.05), t = coef / SE: "estimate (t, p)".
        row.update({col: "-" for col in TEST_COLUMNS.values()})
        for _, c in coefs[coefs["model"] == name].iterrows():
            if c["term"] == "Intercept":
                continue
            per_year = "time" in c["term"]
            estimate = pct(c["pct_effect"], 2 if per_year else 1) + ("/yr" if per_year else "")
            row[TEST_COLUMNS[c["term"]]] = (f"{estimate} (t = {c['coef'] / c['std_err']:.2f}, "
                                            f"{p_cell(c['p_value'])})")

        # One-sided bootstrap test of the 20% goal (single-series models only).
        if pd.isna(s["growth_lower_bound_pct"]):
            row["20% growth goal (bootstrap)"] = "-"
        else:
            row["20% growth goal (bootstrap)"] = (
                f"{pct(s['growth_since_pct'])}, 95% lower bound {pct(s['growth_lower_bound_pct'])} "
                f"({p_cell(s['growth_p_one_sided'])}): "
                + ("met" if s["meets_20pct"] else "not met"))
        rows.append(row)
    return pd.DataFrame(rows)


def forecast_table() -> pd.DataFrame:
    """One row per series for its best forecasting model: test errors, 95% PI
    coverage, and the 2028 and 2035 forecasts with prediction intervals."""
    comp = pd.read_csv(TABLE_DIR / "forecast_comparison.csv", dtype={"ID": str})
    fc = pd.read_csv(TABLE_DIR / "forecasts.csv", dtype={"ID": str})
    rows = []
    for _, r in comp[comp["best"]].iterrows():
        f = fc[(fc["ID"] == r["ID"]) & (fc["model"] == r["model"])].set_index("year")
        row = {
            "Series": r["series"],
            "Best model": r["model"],
            "Test": "Holdout 2012-2022" if r["method"] == "holdout" else f"Leave-one-out ({r['n_obs']} points)",
            "MAE": error(r["mae"]),
            "MAPE": pct(r["mape_pct"], 1, sign=False),
            "RMSE": error(r["rmse"]),
            "95% PI coverage (test)": pi_coverage(r),
            "95% PI check": "Passed" if r["pi_check_passed"] else "Failed",
        }
        for year in (2028, 2035):
            row[f"{year} forecast (95% PI)"] = (f"{number(f.loc[year, 'forecast'])} "
                                                f"({number(f.loc[year, 'pi_low'])}-{number(f.loc[year, 'pi_high'])})")
        rows.append(row)
    return pd.DataFrame(rows)


def pi_coverage(r) -> str:
    """How many held-out values fell inside their 95% prediction interval,
    e.g. '10/11 (91%)', from 10_forecast_models.py."""
    return f"{int(r['pi_covered'])}/{int(r['pi_n'])} ({r['pi_coverage_pct']:.0f}%)"


def forecast_errors_table() -> pd.DataFrame:
    """Test errors (MAE, RMSE, MAPE) for every forecasting model, with the
    lowest value for each series and metric marked."""
    comp = pd.read_csv(TABLE_DIR / "forecast_comparison.csv", dtype={"ID": str})
    rows = []
    for _, r in comp.iterrows():
        lowest = comp[comp["ID"] == r["ID"]][["mae", "rmse", "mape_pct"]].min()
        mark = lambda m: " (lowest)" if r[m] == lowest[m] else ""
        rows.append({
            "Series": r["series"],
            "Model": r["model"],
            "Test": "Holdout 2012-2022" if r["method"] == "holdout" else "Leave-one-out",
            "Data points": r["n_obs"],
            "MAE": error(r["mae"]) + mark("mae"),
            "RMSE": error(r["rmse"]) + mark("rmse"),
            "MAPE": pct(r["mape_pct"], 1, sign=False) + mark("mape_pct"),
            "95% PI coverage (test)": pi_coverage(r),
            "95% PI check": "Passed" if r["pi_check_passed"] else "Failed",
            "Best model (lowest RMSE)": "Yes" if r["best"] else "No",
        })
    return pd.DataFrame(rows)


def best_model_projections_table() -> pd.DataFrame:
    """Year-by-year projections from each series' best model, one row per
    year and one column per series: 'projection (95% PI low-high)'."""
    proj = pd.read_csv(TABLE_DIR / "forecast_projections_yearly.csv", dtype={"ID": str})
    proj = proj[proj["best_model"]]
    table = pd.DataFrame({"Year": sorted(proj["year"].unique())})
    for (series, model), d in proj.groupby(["series", "model"], sort=False):
        cells = {int(r["year"]): f"{number(r['projection'])} ({number(r['pi_low'])}-{number(r['pi_high'])})"
                 for _, r in d.iterrows()}
        # A dash for years before the series' own projections start
        # (the condor data run to 2025, the bird indices only to 2022).
        table[f"{series} ({model})"] = [cells.get(y, "-") for y in table["Year"]]
    return table


def all_forecasts_table() -> pd.DataFrame:
    """2028 and 2035 predictions from every forecasting model, best or not."""
    comp = pd.read_csv(TABLE_DIR / "forecast_comparison.csv", dtype={"ID": str})
    fc = pd.read_csv(TABLE_DIR / "forecasts.csv", dtype={"ID": str})
    rows = []
    for _, r in comp.iterrows():
        f = fc[(fc["ID"] == r["ID"]) & (fc["model"] == r["model"])].set_index("year")
        row = {"Series": r["series"], "Model": r["model"] + (" (best)" if r["best"] else "")}
        for year in (2028, 2035):
            row[f"{year} forecast"] = number(f.loc[year, "forecast"])
            row[f"{year} 95% PI"] = f"{number(f.loc[year, 'pi_low'])}-{number(f.loc[year, 'pi_high'])}"
        rows.append(row)
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    """Plain markdown table (avoids needing the optional 'tabulate' package)."""
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


if __name__ == "__main__":
    seg = segmented_regression_table()
    tests = significance_tests_table()
    tests.to_csv(TABLE_DIR / "results_summary_significance_tests.csv", index=False)
    fcast = forecast_table()
    errors = forecast_errors_table()
    all_fc = all_forecasts_table()
    projections = best_model_projections_table()
    projections.to_csv(TABLE_DIR / "results_summary_projections_best_models.csv", index=False)
    errors.to_csv(TABLE_DIR / "results_summary_forecast_errors.csv", index=False)
    seg.to_csv(TABLE_DIR / "results_summary_segmented_regression.csv", index=False)
    fcast.to_csv(TABLE_DIR / "results_summary_forecasts.csv", index=False)
    all_fc.to_csv(TABLE_DIR / "results_summary_forecasts_all_models.csv", index=False)

    md = "\n\n".join([
        "# Results Summary",
        "Created by `SCRIPTS/12_results_table.py` from the tables in `OUTPUT/tables/`.",
        "## Segmented regression (interrupted time series)",
        to_markdown(seg),
        "Changes are percentages on the original scale. p-values are from two-sided t-tests; "
        "\\* = significant at alpha = 0.05. The 20% goal is met when the one-sided bootstrap 95% lower "
        "bound on growth since the event is above 20%. Model 5 tests whether California's changes at "
        "2019 differ from Arizona/Utah's (no 20% test). Model 4 has only 6 points, so treat it with caution.",
        "## All significance tests for the segmented regression models",
        to_markdown(tests),
        "Each test cell shows the estimate as a percentage change, then t = coefficient / standard "
        "error (log scale) and the two-sided p-value; \\* = significant at alpha = 0.05. A dash means "
        "the test does not apply to that model. Durbin-Watson is a rule-of-thumb check (about 2 = no "
        "autocorrelation), so it has no p-value. In model 5, the time, after and time_after columns "
        "describe the Arizona/Utah flock; the lead-ban effect is flock_after and flock_time_after. "
        "The 20% goal is met when the one-sided bootstrap 95% lower bound is above 20%.",
        "## Forecasts",
        to_markdown(fcast),
        "The best model has the lowest test RMSE. Bald eagle and peregrine falcon values are Breeding "
        "Bird Survey abundance indices, not bird counts; condor values are numbers of wild birds. "
        "PI = prediction interval. 95% PI coverage is how many held-out values fell inside their 95% "
        "prediction interval, built without seeing them; about 95% should. The check fails only if "
        "coverage is significantly below 95% (one-sided binomial test, p < 0.05), because with 6-14 "
        "test points a single miss is expected.",
        "## Year-by-year projections from the best models",
        to_markdown(projections),
        "Each cell is the projection with its 95% prediction interval in brackets, from the best model "
        "for that series (lowest test RMSE), refitted on all years. Projections start the year after "
        "each series' last data point (2022 for the bird indices, 2025 for the condor flocks). Bald "
        "eagle and peregrine falcon values are Breeding Bird Survey indices, not bird counts; condor "
        "values are numbers of wild birds. Intervals widen the further ahead the projection goes.",
        "## Forecast model errors (all models)",
        to_markdown(errors),
        "Errors are on the original scale (index values for the bald eagle and peregrine falcon, "
        "numbers of birds for the condor flocks); MAPE is in percent, so it can be compared across "
        "series. Bald eagle and peregrine falcon models were trained on 1970-2011 and tested on "
        "2012-2022; the short condor series use leave-one-out cross-validation instead. "
        "The 95% PI check is explained under Forecasts.",
        "## 2028 and 2035 predictions from every forecasting model",
        to_markdown(all_fc),
        "Logistic models were fitted only for the bald eagle and peregrine falcon; the condor "
        "series are too short for a reliable carrying capacity.",
        "Data: ZSL/WWF 2026. Living Planet Database 2026.1 <www.livingplanetindex.org/data_portal>; "
        "USFWS California Condor Recovery Program annual population status reports.",
    ]) + "\n"
    (TABLE_DIR / "results_summary.md").write_text(md, encoding="utf-8")

    pd.set_option("display.width", 250, "display.max_columns", 20)
    print(seg.to_string(index=False))
    print()
    print(tests.to_string(index=False))
    print()
    print(fcast.to_string(index=False))
    print()
    print(errors.to_string(index=False))
    print()
    print(all_fc.to_string(index=False))
    print(f"\nSaved results_summary_segmented_regression.csv, results_summary_significance_tests.csv, "
          f"results_summary_forecasts.csv, "
          f"results_summary_forecast_errors.csv, results_summary_forecasts_all_models.csv "
          f"and results_summary.md to "
          f"{TABLE_DIR.relative_to(ROOT)}")
