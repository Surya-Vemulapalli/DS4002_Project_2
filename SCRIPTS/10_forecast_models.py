"""Forecast populations for 2028 and 2035 and compare growth models.

Models (all fitted on every observed year of each series):
- Linear:      count = a + b * year
- Exponential: ln(count) = a + b * year, back-transformed as
               exp(prediction + sigma^2 / 2) (log-normal mean correction)
- Logistic:    count = K / (1 + exp(-r * (year - t0))), via scipy curve_fit
               (bald eagle and peregrine only; the condor series are too
               short and release-driven for a reliable carrying capacity)

Comparison (MAE, MAPE and RMSE, all on the original count scale):
- Bald eagle, peregrine: time-based holdout, train on earlier years and test
  on the last 20% of years. No random splits.
- Condor flocks: leave-one-out cross-validation (LOOCV), since the series are
  too short for a holdout.
- MAE  = mean(|actual - predicted|)
  MAPE = mean(|actual - predicted| / |actual|) * 100   (percent)
  RMSE = sqrt(mean((actual - predicted)^2))
- The "best" model (used to flag forecasts and label plots) is still chosen
  by RMSE. best_mae and best_mape columns show the winner under each metric.
- 95% prediction-interval check: for every held-out point, a 95% interval is
  built from the training data only, and the share of actual values inside
  is reported (pi_covered / pi_n). About 95% should fall inside; the check
  fails only if coverage is significantly below 95% (one-sided binomial test,
  pi_binom_p < 0.05), because a single miss among 6-14 points is expected.

95% prediction intervals: from the regression for linear and exponential
models, and from a residual bootstrap for the logistic model.

Every model is also projected for each year from the year after its last
data point through 2035 (forecast_projections_yearly.csv); the 2028 and 2035
forecasts in forecasts.csv are taken from that same projection.

Inputs:  DATA/lpd_series.csv (bald eagle 2910, peregrine falcon 28210;
         from 04_clean_data.py)
         DATA/usfws_condor_flocks.csv (California and Arizona/Utah wild flocks;
         from 05_build_condor_flocks.py)
Outputs: OUTPUT/tables/forecast_comparison.csv  test errors (MAE, MAPE, RMSE)
                                                and 95% PI coverage, per model
         OUTPUT/tables/forecasts.csv            2028 and 2035 forecasts with
                                                95% prediction intervals
         OUTPUT/tables/forecast_projections_yearly.csv  every year to 2035
         OUTPUT/tables/forecast_parameters.csv  fitted parameters per model
         OUTPUT/figures/forecast_bald_eagle.png, forecast_peregrine_falcon.png,
         forecast_condor_flocks.png, model_comparison_metrics.png
         OUTPUT/models/forecast/forecast_<series>_<model>.pickle and .json
"""

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning, curve_fit
from scipy.stats import binom
# Import OLS directly rather than statsmodels.api: the full api also loads
# time-series extensions that this machine's Application Control blocks.
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

ROOT = Path(__file__).parent.parent
LPD_PATH = ROOT / "DATA" / "lpd_series.csv"
FLOCKS_PATH = ROOT / "DATA" / "usfws_condor_flocks.csv"
OUT_DIR = ROOT / "OUTPUT" / "tables"
PLOT_DIR = ROOT / "OUTPUT" / "figures"
MODEL_DIR = ROOT / "OUTPUT" / "models" / "forecast"

FORECAST_YEARS = np.array([2028.0, 2035.0])
TEST_FRACTION = 0.2      # last 20% of years held out (eagle, peregrine)
N_BOOT = 2000            # bootstrap resamples for logistic intervals
K_MAX_MULTIPLE = 50      # upper bound on K as a multiple of the largest count
SEED = 42
PI_LEVEL = 0.95          # nominal coverage of the prediction intervals
PI_CHECK_ALPHA = 0.05    # coverage check fails if significantly below PI_LEVEL

warnings.filterwarnings("ignore", category=OptimizeWarning)


def design(years: np.ndarray) -> np.ndarray:
    """Intercept + year column for statsmodels."""
    return add_constant(np.asarray(years, dtype=float), has_constant="add")


# Each model class has the same methods, so run() can treat them alike:
#   fit(years, counts)  fit the model and return itself
#   predict(years)      point forecasts on the original count scale
#   interval(years)     (forecast, 95% PI low, 95% PI high) for each year
#   params()            key parameters for forecast_parameters.csv
#   save() / to_dict()  what is written to OUTPUT/models/forecast/


class Linear:
    """Straight-line growth: the same number of birds (or index units) added
    every year. Fitted by ordinary least squares on the counts."""
    name = "Linear"

    def fit(self, years, counts):
        """Fit count = a + b * year."""
        self.res = OLS(counts, design(years)).fit()
        return self

    def predict(self, years):
        """Point forecasts: a + b * year."""
        return np.asarray(self.res.predict(design(years)))

    def interval(self, years):
        """95% prediction intervals from the regression: they cover a single
        new observation (obs_ci), not just the fitted line."""
        f = self.res.get_prediction(design(years)).summary_frame(alpha=0.05)
        return f["mean"].values, f["obs_ci_lower"].values, f["obs_ci_upper"].values

    def params(self):
        """Yearly change in the count."""
        return {"slope_per_year": self.res.params[1]}

    formula = "count = a + b * year"
    how_to_predict = ("Load the .pickle with OLSResults.load(); "
                      "forecast = model.predict([[1, year]]).")

    def save(self, stem: Path) -> list[Path]:
        """Save the fitted statsmodels results as a pickle."""
        path = stem.with_suffix(".pickle")
        self.res.save(str(path))
        return [path]

    def to_dict(self):
        """Parameters for the JSON summary."""
        return {"a_intercept": self.res.params[0], "b_slope_per_year": self.res.params[1]}


class Exponential:
    """Constant percentage growth every year. Fitted as a straight line on
    ln(count), then converted back to the count scale."""
    name = "Exponential"

    def fit(self, years, counts):
        """Fit ln(count) = a + b * year (needs counts above zero)."""
        self.res = OLS(np.log(counts), design(years)).fit()
        self.s2 = self.res.scale  # residual variance on the log scale
        return self

    def predict(self, years):
        """Point forecasts on the count scale. exp() of the log-scale line gives
        the median; adding sigma^2 / 2 gives the mean (log-normal correction)."""
        return np.exp(np.asarray(self.res.predict(design(years))) + self.s2 / 2)

    def interval(self, years):
        """95% prediction intervals on the log scale, converted back with exp(),
        so they are wider above the forecast than below it."""
        f = self.res.get_prediction(design(years)).summary_frame(alpha=0.05)
        return (np.exp(f["mean"].values + self.s2 / 2),
                np.exp(f["obs_ci_lower"].values), np.exp(f["obs_ci_upper"].values))

    def params(self):
        """Yearly growth rate in percent: (e^b - 1) * 100."""
        return {"growth_pct_per_year": np.expm1(self.res.params[1]) * 100}

    formula = "ln(count) = a + b * year"
    how_to_predict = ("Load the .pickle with OLSResults.load(); "
                      "forecast = exp(model.predict([[1, year]]) + model.scale / 2) "
                      "(log-normal mean back-transformation).")

    def save(self, stem: Path) -> list[Path]:
        """Save the fitted statsmodels results (log scale) as a pickle."""
        path = stem.with_suffix(".pickle")
        self.res.save(str(path))
        return [path]

    def to_dict(self):
        """Parameters for the JSON summary."""
        return {"a_intercept_log": self.res.params[0], "b_slope_log": self.res.params[1],
                "sigma2_log_residual_variance": self.s2,
                "growth_pct_per_year": np.expm1(self.res.params[1]) * 100}


def logistic_curve(t, K, r, t0):
    """S-shaped growth: K is the ceiling (carrying capacity), r the growth rate
    and t0 the year of fastest growth (where the curve is at K / 2)."""
    return K / (1 + np.exp(-r * (t - t0)))


class Logistic:
    """Growth that slows as the population approaches a ceiling (K). Fitted by
    non-linear least squares; used for the bald eagle and peregrine only."""
    name = "Logistic"

    def _fit_curve(self, years, counts, p0):
        """Fit K, r and t0, starting from p0. The bounds keep the fit sensible:
        K between half and K_MAX_MULTIPLE times the largest count, r between
        0.0001 and 2, and t0 within 100 years of the data."""
        top = counts.max()
        bounds = ([0.5 * top, 1e-4, years.min() - 100],
                  [K_MAX_MULTIPLE * top, 2.0, years.max() + 100])
        popt, _ = curve_fit(logistic_curve, years, counts, p0=p0,
                            bounds=bounds, maxfev=20000)
        return popt

    def fit(self, years, counts):
        """Fit the curve and keep the residuals for the bootstrap intervals."""
        self.years = np.asarray(years, dtype=float)
        self.counts = np.asarray(counts, dtype=float)
        # Starting guess: ceiling 50% above the largest count, moderate growth,
        # fastest growth in the middle of the data.
        p0 = [1.5 * self.counts.max(), 0.1, np.median(self.years)]
        self.popt = self._fit_curve(self.years, self.counts, p0)
        self.resid = self.counts - logistic_curve(self.years, *self.popt)
        return self

    def predict(self, years):
        """Point forecasts from the fitted curve."""
        return logistic_curve(np.asarray(years, dtype=float), *self.popt)

    def interval(self, years):
        """Residual bootstrap: refit on fitted + resampled residuals, then
        add a resampled residual to each forecast (prediction interval)."""
        rng = np.random.default_rng(SEED)
        years = np.asarray(years, dtype=float)
        fitted = logistic_curve(self.years, *self.popt)
        sims = []
        for _ in range(N_BOOT):
            y_b = fitted + rng.choice(self.resid, size=len(fitted), replace=True)
            try:
                p_b = self._fit_curve(self.years, y_b, self.popt)
            except RuntimeError:
                continue  # skip the rare resample that does not converge
            sims.append(logistic_curve(years, *p_b) + rng.choice(self.resid, size=len(years)))
        sims = np.array(sims)
        self.n_boot_ok = len(sims)
        return self.predict(years), np.percentile(sims, 2.5, axis=0), np.percentile(sims, 97.5, axis=0)

    def params(self):
        """K, r and t0, and whether K hit its upper bound (a sign the data do
        not show a ceiling yet, so K is not reliable)."""
        K, r, t0 = self.popt
        return {"K": K, "r": r, "t0": t0,
                "K_at_upper_bound": bool(np.isclose(K, K_MAX_MULTIPLE * self.counts.max(), rtol=1e-3))}

    formula = "count = K / (1 + exp(-r * (year - t0)))"
    how_to_predict = ("forecast = K / (1 + exp(-r * (year - t0))) using the K, r, t0 "
                      "in 'parameters'. Prediction intervals: residual bootstrap using "
                      "'training_years', 'training_counts' and 'residuals' (see Logistic.interval).")

    def save(self, stem: Path) -> list[Path]:
        """No separate object file: everything needed is in the JSON summary,
        which is also safer to load than a pickle."""
        return []

    def to_dict(self):
        """Parameters plus the training data and residuals, which are needed to
        recreate the bootstrap prediction intervals."""
        K, r, t0 = self.popt
        return {"K": K, "r": r, "t0": t0,
                "training_years": self.years.tolist(),
                "training_counts": self.counts.tolist(),
                "residuals": self.resid.tolist(),
                "bootstrap": {"n_resamples": N_BOOT, "seed": SEED,
                              "K_bounds_multiple_of_max_count": [0.5, K_MAX_MULTIPLE]}}


def save_forecast_model(record_id: str, label: str, model, is_best: bool,
                        years: np.ndarray) -> list[Path]:
    """Save one refitted forecasting model: an object file where available
    (pickle) plus a readable JSON summary with everything needed to use it."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in record_id.lower())
    stem = MODEL_DIR / f"forecast_{slug}_{model.name.lower()}"
    paths = model.save(stem)
    summary = {
        "series_id": record_id,
        "series": label,
        "model": model.name,
        "best_model": bool(is_best),
        "formula": model.formula,
        "fitted_on_years": [int(years.min()), int(years.max())],
        "n_obs": int(len(years)),
        "parameters": model.to_dict(),
        "how_to_predict": model.how_to_predict,
        "object_file": paths[0].name if paths else None,
        "created_by": "10_forecast_models.py",
    }
    json_path = stem.with_suffix(".json")
    # default=float converts numpy numbers so json can write them.
    json_path.write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    return paths + [json_path]


# (ID, label, data file, models, comparison method)
SERIES = [
    ("2910", "Bald eagle", LPD_PATH, [Linear, Exponential, Logistic], "holdout"),
    ("28210", "Peregrine falcon", LPD_PATH, [Linear, Exponential, Logistic], "holdout"),
    ("USFWS-CA-WILD", "California condor, CA wild flock", FLOCKS_PATH, [Linear, Exponential], "loocv"),
    ("USFWS-AZUT-WILD", "California condor, AZ/UT wild flock", FLOCKS_PATH, [Linear, Exponential], "loocv"),
]


# ---- Error metrics -----------------------------------------------------
METRICS = ["mae", "mape_pct", "rmse"]
METRIC_LABELS = {"mae": "MAE", "mape_pct": "MAPE (%)", "rmse": "RMSE"}


def mae(actual, predicted) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def rmse(actual, predicted) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean(np.square(np.asarray(actual) - np.asarray(predicted)))))


def mape(actual, predicted) -> float:
    """Mean absolute percentage error, in percent. Points with actual == 0 are
    skipped because the percentage error is undefined there."""
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    keep = actual != 0
    if not keep.any():
        return float("nan")
    return float(np.mean(np.abs((actual[keep] - predicted[keep]) / actual[keep])) * 100)


def score(actual, predicted) -> dict:
    """All three metrics for one set of held-out points."""
    return {"mae": mae(actual, predicted),
            "mape_pct": mape(actual, predicted),
            "rmse": rmse(actual, predicted)}


def coverage(actual, low, high) -> dict:
    """Check of the 95% prediction intervals on the held-out points: how many
    actual values fell inside their interval, built without seeing them.

    About 95% should. With so few test points (6-14), one miss already drops
    coverage below 95%, so the check uses a one-sided binomial test: it fails
    only if coverage is significantly below 95%, i.e.
    P(this many hits or fewer | n, 0.95) < 0.05. Intervals that are too wide
    (100% coverage) are not penalised by this test.
    """
    actual, low, high = (np.asarray(a, dtype=float) for a in (actual, low, high))
    hits = int(np.sum((actual >= low) & (actual <= high)))
    n = len(actual)
    p = float(binom.cdf(hits, n, PI_LEVEL))
    return {"pi_covered": hits, "pi_n": n, "pi_coverage_pct": 100 * hits / n,
            "pi_binom_p": p, "pi_check_passed": bool(p >= PI_CHECK_ALPHA)}


def holdout_scores(model_cls, years, counts):
    """Train on earlier years, test on the last TEST_FRACTION of years."""
    n_test = int(np.ceil(TEST_FRACTION * len(years)))
    model = model_cls().fit(years[:-n_test], counts[:-n_test])
    predicted = model.predict(years[-n_test:])
    # 95% prediction intervals for the held-out years, from the training fit only.
    _, low, high = model.interval(years[-n_test:])
    test_span = f"{int(years[-n_test])}-{int(years[-1])}"
    return {**score(counts[-n_test:], predicted),
            **coverage(counts[-n_test:], low, high)}, test_span


def loocv_scores(model_cls, years, counts):
    """Leave each observation out once, predict it from the rest."""
    actual, predicted, low, high = [], [], [], []
    for i in range(len(years)):
        keep = np.arange(len(years)) != i
        model = model_cls().fit(years[keep], counts[keep])
        actual.append(counts[i])
        predicted.append(model.predict(years[i:i + 1])[0])
        # 95% prediction interval for the left-out point, from the other points only.
        _, lo, hi = model.interval(years[i:i + 1])
        low.append(lo[0])
        high.append(hi[0])
    return {**score(actual, predicted), **coverage(actual, low, high)}, "leave-one-out"


def load_series(record_id: str, path: Path) -> pd.DataFrame:
    """One series from a cleaned data file, in year order."""
    df = pd.read_csv(path, dtype={"ID": str})
    return df[df["ID"] == record_id].sort_values("year").reset_index(drop=True)


def run():
    """For every series: compare the models on held-out data, pick the best,
    then refit every model on all years and project it to 2035.

    Returns the comparison, forecast, parameter and projection tables, the
    fitted models (for the plots) and the list of saved model files.
    """
    comparison, forecasts, params, fits, saved, projections = [], [], [], {}, [], []
    for record_id, label, path, model_classes, method in SERIES:
        s = load_series(record_id, path)
        # Plain arrays of years and counts, as the model classes expect.
        years = s["year"].to_numpy(dtype=float)
        counts = s["count"].to_numpy(dtype=float)

        # 1. Compare models on data they were not fitted to (holdout for the
        # long bird series, leave-one-out for the short condor series).
        scores = {}
        for cls in model_classes:
            sc, detail = (holdout_scores if method == "holdout" else loocv_scores)(cls, years, counts)
            scores[cls.name] = sc["rmse"]
            comparison.append({"ID": record_id, "series": label, "model": cls.name,
                               "method": method, "test": detail, "n_obs": len(years),
                               **sc})
        best = min(scores, key=scores.get)  # best model is chosen by RMSE

        # 2. Refit on all years and project every year from the year after the
        # last data point through the last forecast year. The 2028 and 2035
        # forecasts are read from this same projection, so they always agree.
        fits[record_id] = {"label": label, "data": s, "models": {}}
        proj_years = np.arange(years[-1] + 1, FORECAST_YEARS[-1] + 1)
        at_forecast_years = np.isin(proj_years, FORECAST_YEARS)
        for cls in model_classes:
            model = cls().fit(years, counts)
            proj_mean, proj_low, proj_high = model.interval(proj_years)
            for y, m, lo, hi in zip(proj_years, proj_mean, proj_low, proj_high):
                projections.append({"ID": record_id, "series": label, "model": cls.name,
                                    "year": int(y), "projection": m, "pi_low": lo, "pi_high": hi,
                                    "best_model": cls.name == best})
            mean, low, high = (a[at_forecast_years] for a in (proj_mean, proj_low, proj_high))
            fits[record_id]["models"][cls.name] = (model, mean, low, high)
            for y, m, lo, hi in zip(FORECAST_YEARS, mean, low, high):
                forecasts.append({"ID": record_id, "series": label, "model": cls.name,
                                  "year": int(y), "forecast": m, "pi_low": lo, "pi_high": hi,
                                  "last_data_year": int(years[-1]),
                                  "years_ahead": int(y - years[-1]),
                                  "best_model": cls.name == best})
            # Keep the fitted parameters and save the model itself.
            params.append({"ID": record_id, "series": label, "model": cls.name, **model.params()})
            saved.extend(save_forecast_model(record_id, label, model, cls.name == best, years))

    # Mark the lowest-error model per series under each metric. "best" (RMSE)
    # is the one used for the forecasts; MAE and MAPE are shown for comparison.
    comparison = pd.DataFrame(comparison)
    comparison["best"] = comparison.groupby("ID")["rmse"].transform("min") == comparison["rmse"]
    comparison["best_mae"] = comparison.groupby("ID")["mae"].transform("min") == comparison["mae"]
    comparison["best_mape"] = comparison.groupby("ID")["mape_pct"].transform("min") == comparison["mape_pct"]
    return (comparison, pd.DataFrame(forecasts), pd.DataFrame(params), fits, saved,
            pd.DataFrame(projections))


# ---- Plots -------------------------------------------------------------
# One colour per model, used in every forecast plot, plus the shared chart style.
COLORS = {"Linear": "#2a78d6", "Exponential": "#eb6834", "Logistic": "#1baf7a"}
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
})


def draw_series(ax, fit, best, ylabel):
    """One forecast panel: the observed data, each model's fitted curve
    extended to 2035, and the 2028 and 2035 forecasts with 95% prediction
    intervals (whiskers). A vertical line marks where the data end."""
    s = fit["data"]
    first, last = s["year"].min(), s["year"].max()
    grid = np.arange(first, FORECAST_YEARS[-1] + 0.01, 0.25)  # smooth x values for the curves
    names = list(fit["models"])
    for i, (name, (model, mean, low, high)) in enumerate(fit["models"].items()):
        tag = " (best)" if name == best else ""
        ax.plot(grid, model.predict(grid), color=COLORS[name], lw=2, label=f"{name}{tag}")
        # Forecast whiskers, offset slightly so the models don't overlap.
        x = FORECAST_YEARS + (i - (len(names) - 1) / 2) * 0.45
        ax.errorbar(x, mean, yerr=[mean - low, high - mean], fmt="o", color=COLORS[name],
                    ms=5, capsize=3, lw=1.4, mec=SURFACE, mew=0.7)
    ax.plot(s["year"], s["count"], "o", color=INK_2, ms=5, mec=SURFACE, mew=0.7,
            label="Observed", zorder=4)
    ax.axvline(last, color=MUTED, lw=1, zorder=1)
    ax.text(last, 1.01, " forecast", transform=ax.get_xaxis_transform(),
            color=INK_2, fontsize=9, va="bottom")
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)


def plot_all(fits, comparison):
    """Save the forecast plots: one each for the bald eagle and peregrine
    falcon, and one with both condor flocks side by side."""
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    best = comparison[comparison["best"]].set_index("ID")["model"]

    for record_id, fname, ylabel, source in [
        ("2910", "forecast_bald_eagle.png", "Abundance index",
         "BBS relative abundance index, US + Canada (LPD record 2910)"),
        ("28210", "forecast_peregrine_falcon.png", "Abundance index",
         "BBS relative abundance index, North America (LPD record 28210)"),
    ]:
        fig, ax = plt.subplots(figsize=(8, 4.8))
        draw_series(ax, fits[record_id], best[record_id], ylabel)
        ax.legend(loc="upper left", fontsize=9)
        fig.suptitle(f"{fits[record_id]['label']}: forecasts for 2028 and 2035",
                     x=0.06, ha="left", fontsize=13, fontweight="bold")
        ax.set_title(f"{source}. Whiskers: 95% prediction intervals.",
                     loc="left", fontsize=9.5, color=INK_2, pad=20)
        fig.tight_layout()
        fig.savefig(PLOT_DIR / fname, dpi=200)
        plt.close(fig)

    # Condor flocks: small multiples, each with its own y-axis.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, record_id, title in [(axes[0], "USFWS-CA-WILD", "California wild flock (6 counts)"),
                                 (axes[1], "USFWS-AZUT-WILD", "Arizona/Utah wild flock (14 counts)")]:
        draw_series(ax, fits[record_id], best[record_id], "Wild birds")
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=18)
        ax.legend(loc="upper left", fontsize=8.5)
    fig.suptitle("California condor wild flocks: forecasts for 2028 and 2035",
                 x=0.04, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.04, 0.89, "Year-end counts, USFWS annual population status reports. "
             "Whiskers: 95% prediction intervals. Each flock modelled separately.",
             fontsize=9.5, color=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(PLOT_DIR / "forecast_condor_flocks.png", dpi=200)
    plt.close(fig)


def plot_metric_comparison(comparison):
    """One row per series, one column per metric, one bar per model.
    Each panel has its own y-axis because the series are on different scales.
    The lowest bar in each panel (the best model for that metric) is outlined."""
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    series_ids = list(dict.fromkeys(comparison["ID"]))
    fig, axes = plt.subplots(len(series_ids), len(METRICS),
                             figsize=(11, 2.8 * len(series_ids)), squeeze=False)
    for r, record_id in enumerate(series_ids):
        d = comparison[comparison["ID"] == record_id].reset_index(drop=True)
        method = d["method"].iloc[0]
        for c, metric in enumerate(METRICS):
            ax = axes[r][c]
            bars = ax.bar(d["model"], d[metric], color=[COLORS[m] for m in d["model"]], width=0.6)
            winner = int(d[metric].idxmin())
            bars[winner].set_edgecolor(INK)
            bars[winner].set_linewidth(2)
            for b, v in zip(bars, d[metric]):
                ax.annotate(f"{v:.3g}", (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=8, color=INK_2)
            ax.set_ylim(top=d[metric].max() * 1.18)
            ax.grid(axis="x", visible=False)
            if r == 0:
                ax.set_title(METRIC_LABELS[metric], loc="left", fontsize=11, fontweight="bold")
            if c == 0:
                ax.set_ylabel(f"{d['series'].iloc[0]}\n({method})", fontsize=8.5)
    fig.suptitle("Model comparison: MAE, MAPE and RMSE (lower is better, outlined bar = best)",
                 x=0.03, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(PLOT_DIR / "model_comparison_metrics.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    # Fit, compare and forecast, then save the tables and plots.
    comparison, forecasts, params, fits, saved, projections = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(OUT_DIR / "forecast_comparison.csv", index=False)
    forecasts.to_csv(OUT_DIR / "forecasts.csv", index=False)
    projections.to_csv(OUT_DIR / "forecast_projections_yearly.csv", index=False)
    params.to_csv(OUT_DIR / "forecast_parameters.csv", index=False)
    plot_all(fits, comparison)
    plot_metric_comparison(comparison)

    # Print the results to the screen.
    pd.set_option("display.width", 220)
    print("Model comparison (MAE, MAPE %, RMSE on the count scale):\n")
    print(comparison.round(5).to_string(index=False))
    print("\nForecasts (95% prediction intervals):\n")
    print(forecasts.round(4).to_string(index=False))
    print("\nParameters:\n")
    print(params.round(4).to_string(index=False))
    for record_id, fit in fits.items():
        if "Logistic" in fit["models"]:
            print(f"Logistic bootstrap fits that converged ({record_id}): "
                  f"{fit['models']['Logistic'][0].n_boot_ok}/{N_BOOT}")
    print(f"\nSaved tables to {OUT_DIR.relative_to(ROOT)} and plots to {PLOT_DIR.relative_to(ROOT)}")
    print(f"Saved {len(saved)} forecasting model files to {MODEL_DIR.relative_to(ROOT)}:")
    for path in saved:
        print(f"  {path.name}")
