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

95% prediction intervals: from the regression for linear and exponential
models, and from a residual bootstrap for the logistic model.

Outputs go to data/results/ (git-ignored).
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
# Import OLS directly rather than statsmodels.api: the full api also loads
# time-series extensions that this machine's Application Control blocks.
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

ROOT = Path(__file__).parent
LPD_PATH = ROOT / "data" / "lpd_series.csv"
FLOCKS_PATH = ROOT / "data_external" / "usfws_condor_flocks.csv"
OUT_DIR = ROOT / "data" / "results"
PLOT_DIR = OUT_DIR / "plots"
MODEL_DIR = OUT_DIR / "forecast_models"

FORECAST_YEARS = np.array([2028.0, 2035.0])
TEST_FRACTION = 0.2      # last 20% of years held out (eagle, peregrine)
N_BOOT = 2000            # bootstrap resamples for logistic intervals
K_MAX_MULTIPLE = 50      # upper bound on K as a multiple of the largest count
SEED = 42

warnings.filterwarnings("ignore", category=OptimizeWarning)


def design(years: np.ndarray) -> np.ndarray:
    """Intercept + year column for statsmodels."""
    return add_constant(np.asarray(years, dtype=float), has_constant="add")


class Linear:
    name = "Linear"

    def fit(self, years, counts):
        self.res = OLS(counts, design(years)).fit()
        return self

    def predict(self, years):
        return np.asarray(self.res.predict(design(years)))

    def interval(self, years):
        f = self.res.get_prediction(design(years)).summary_frame(alpha=0.05)
        return f["mean"].values, f["obs_ci_lower"].values, f["obs_ci_upper"].values

    def params(self):
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
        return {"a_intercept": self.res.params[0], "b_slope_per_year": self.res.params[1]}


class Exponential:
    name = "Exponential"

    def fit(self, years, counts):
        self.res = OLS(np.log(counts), design(years)).fit()
        self.s2 = self.res.scale  # residual variance on the log scale
        return self

    def predict(self, years):
        # Log-normal mean: exp(mu + sigma^2 / 2).
        return np.exp(np.asarray(self.res.predict(design(years))) + self.s2 / 2)

    def interval(self, years):
        f = self.res.get_prediction(design(years)).summary_frame(alpha=0.05)
        return (np.exp(f["mean"].values + self.s2 / 2),
                np.exp(f["obs_ci_lower"].values), np.exp(f["obs_ci_upper"].values))

    def params(self):
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
        return {"a_intercept_log": self.res.params[0], "b_slope_log": self.res.params[1],
                "sigma2_log_residual_variance": self.s2,
                "growth_pct_per_year": np.expm1(self.res.params[1]) * 100}


def logistic_curve(t, K, r, t0):
    return K / (1 + np.exp(-r * (t - t0)))


class Logistic:
    name = "Logistic"

    def _fit_curve(self, years, counts, p0):
        top = counts.max()
        bounds = ([0.5 * top, 1e-4, years.min() - 100],
                  [K_MAX_MULTIPLE * top, 2.0, years.max() + 100])
        popt, _ = curve_fit(logistic_curve, years, counts, p0=p0,
                            bounds=bounds, maxfev=20000)
        return popt

    def fit(self, years, counts):
        self.years = np.asarray(years, dtype=float)
        self.counts = np.asarray(counts, dtype=float)
        p0 = [1.5 * self.counts.max(), 0.1, np.median(self.years)]
        self.popt = self._fit_curve(self.years, self.counts, p0)
        self.resid = self.counts - logistic_curve(self.years, *self.popt)
        return self

    def predict(self, years):
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
        "created_by": "forecast_models.py",
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


def holdout_scores(model_cls, years, counts):
    """Train on earlier years, test on the last TEST_FRACTION of years."""
    n_test = int(np.ceil(TEST_FRACTION * len(years)))
    model = model_cls().fit(years[:-n_test], counts[:-n_test])
    predicted = model.predict(years[-n_test:])
    test_span = f"{int(years[-n_test])}-{int(years[-1])}"
    return score(counts[-n_test:], predicted), test_span


def loocv_scores(model_cls, years, counts):
    """Leave each observation out once, predict it from the rest."""
    actual, predicted = [], []
    for i in range(len(years)):
        keep = np.arange(len(years)) != i
        model = model_cls().fit(years[keep], counts[keep])
        actual.append(counts[i])
        predicted.append(model.predict(years[i:i + 1])[0])
    return score(actual, predicted), "leave-one-out"


def load_series(record_id: str, path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ID": str})
    return df[df["ID"] == record_id].sort_values("year").reset_index(drop=True)


def run():
    comparison, forecasts, params, fits, saved = [], [], [], {}, []
    for record_id, label, path, model_classes, method in SERIES:
        s = load_series(record_id, path)
        years = s["year"].to_numpy(dtype=float)
        counts = s["count"].to_numpy(dtype=float)

        # 1. Compare models.
        scores = {}
        for cls in model_classes:
            sc, detail = (holdout_scores if method == "holdout" else loocv_scores)(cls, years, counts)
            scores[cls.name] = sc["rmse"]
            comparison.append({"ID": record_id, "series": label, "model": cls.name,
                               "method": method, "test": detail, "n_obs": len(years),
                               **sc})
        best = min(scores, key=scores.get)  # best model is chosen by RMSE

        # 2. Refit on all years and forecast.
        fits[record_id] = {"label": label, "data": s, "models": {}}
        for cls in model_classes:
            model = cls().fit(years, counts)
            mean, low, high = model.interval(FORECAST_YEARS)
            fits[record_id]["models"][cls.name] = (model, mean, low, high)
            for y, m, lo, hi in zip(FORECAST_YEARS, mean, low, high):
                forecasts.append({"ID": record_id, "series": label, "model": cls.name,
                                  "year": int(y), "forecast": m, "pi_low": lo, "pi_high": hi,
                                  "last_data_year": int(years[-1]),
                                  "years_ahead": int(y - years[-1]),
                                  "best_model": cls.name == best})
            params.append({"ID": record_id, "series": label, "model": cls.name, **model.params()})
            saved.extend(save_forecast_model(record_id, label, model, cls.name == best, years))

    comparison = pd.DataFrame(comparison)
    comparison["best"] = comparison.groupby("ID")["rmse"].transform("min") == comparison["rmse"]
    comparison["best_mae"] = comparison.groupby("ID")["mae"].transform("min") == comparison["mae"]
    comparison["best_mape"] = comparison.groupby("ID")["mape_pct"].transform("min") == comparison["mape_pct"]
    return comparison, pd.DataFrame(forecasts), pd.DataFrame(params), fits, saved


# ---- Plots -------------------------------------------------------------
COLORS = {"Linear": "#2a78d6", "Exponential": "#eb6834", "Logistic": "#1baf7a"}
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
})


def draw_series(ax, fit, best, ylabel):
    s = fit["data"]
    first, last = s["year"].min(), s["year"].max()
    grid = np.arange(first, FORECAST_YEARS[-1] + 0.01, 0.25)
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
    comparison, forecasts, params, fits, saved = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(OUT_DIR / "forecast_comparison.csv", index=False)
    forecasts.to_csv(OUT_DIR / "forecasts.csv", index=False)
    params.to_csv(OUT_DIR / "forecast_parameters.csv", index=False)
    plot_all(fits, comparison)
    plot_metric_comparison(comparison)

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
    print(f"\nSaved results and plots to {OUT_DIR.relative_to(ROOT)}")
    print(f"Saved {len(saved)} forecasting model files to {MODEL_DIR.relative_to(ROOT)}:")
    for path in saved:
        print(f"  {path.name}")
