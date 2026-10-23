"""Plot observed data and fitted segmented regression lines.

Fitted lines come from the models saved by fit_models.py
(data/results/models/). The pre- and post-breakpoint segments are drawn
separately so the fitted line breaks at the breakpoint. Modelled series use a
log y-axis, because the models are fitted to ln(count): straight lines on the
chart are the model's straight segments.

Plots are saved to data/results/plots/ (git-ignored), since most of them show
LPD data, which must not be committed.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, LogLocator, MaxNLocator
from statsmodels.regression.linear_model import OLSResults

ROOT = Path(__file__).parent
LPD_PATH = ROOT / "data" / "model_ready_lpd.csv"
LPD_RAW_PATH = ROOT / "data" / "lpd_series.csv"
CONDOR_PATH = ROOT / "data_external" / "model_ready_condor.csv"
MODEL_DIR = ROOT / "data" / "results" / "models"
PLOT_DIR = ROOT / "data" / "results" / "plots"

# Colours (validated categorical slots 1-2 plus chart ink, light mode).
BLUE, ORANGE = "#2a78d6", "#eb6834"
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "legend.frameon": False,
})


def load_model(name: str) -> OLSResults:
    return OLSResults.load(str(MODEL_DIR / f"{name}.pickle"))


def segment_frame(years: np.ndarray, first_year: int, bp: int, flock: int | None = None) -> pd.DataFrame:
    """Build model variables for arbitrary (fractional) years."""
    d = pd.DataFrame({"year": years})
    d["time"] = d["year"] - first_year
    d["after"] = (d["year"] >= bp).astype(int)
    d["time_after"] = (d["year"] - bp).clip(lower=0) * d["after"]
    if flock is not None:
        d["flock"] = flock
        d["flock_time"] = flock * d["time"]
        d["flock_after"] = flock * d["after"]
        d["flock_time_after"] = flock * d["time_after"]
    return d


def plot_fitted(ax, model, first_year, last_year, bp, color, label, flock=None, lw=2.0):
    """Draw the fitted line as two separate segments, split at the breakpoint."""
    for start, end, lab in [(first_year, bp - 1e-6, label), (bp, last_year, None)]:
        years = np.linspace(start, end, 200)
        pred = model.predict(segment_frame(years, first_year, bp, flock))
        ax.plot(years, np.exp(pred), color=color, lw=lw, label=lab, solid_capstyle="round")


def plot_observed(ax, df, color, label):
    ax.plot(df["year"], df["count"], "o", color=color, ms=5.5, mec=SURFACE, mew=0.7,
            label=label, zorder=3)


def mark_breakpoint(ax, bp, text):
    ax.axvline(bp, color=MUTED, lw=1, zorder=1)
    ax.text(bp, 1.02, f" {text}", transform=ax.get_xaxis_transform(),
            color=INK_2, fontsize=9, ha="left", va="bottom")


def log_axis(ax):
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(subs=[1, 1.5, 2, 3, 5, 7]))
    ax.yaxis.set_minor_locator(LogLocator(subs=[1, 2, 3, 4, 5, 6, 7, 8, 9]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))


def finish(fig, ax, title, subtitle, ylabel, path):
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    fig.suptitle(title, x=0.06, ha="left", fontsize=13, fontweight="bold", color=INK)
    ax.set_title(subtitle, loc="left", fontsize=9.5, color=INK_2, pad=22)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved {path.relative_to(ROOT)}")


def plot_bald_eagle(lpd):
    eagle = lpd[lpd["ID"] == "2910"]
    m_all = load_model("model_1_bald_eagle_all_years")
    m_no = load_model("model_2_bald_eagle_no_2009_outlier")
    first, last, bp = eagle["year"].min(), eagle["year"].max(), 2007

    fig, ax = plt.subplots(figsize=(8, 4.8))
    plot_observed(ax, eagle, INK_2, "Observed index")
    plot_fitted(ax, m_all, first, last, bp, BLUE, "Fitted, all years (model 1)")
    plot_fitted(ax, m_no, first, last, bp, ORANGE, "Fitted, without 2009 (model 2)", lw=1.6)

    # Ring and label the flagged outlier.
    out = eagle[eagle["outlier_flag"]]
    ax.plot(out["year"], out["count"], "o", ms=13, mfc="none", mec=INK, mew=1.2, zorder=4)
    ax.annotate("2009 flagged outlier", (out["year"].iloc[0], out["count"].iloc[0]),
                xytext=(-120, 18), textcoords="offset points", color=INK_2, fontsize=9,
                arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})

    mark_breakpoint(ax, bp, "2007: removed from endangered list")
    log_axis(ax)
    ax.legend(loc="lower right")
    finish(fig, ax, "Bald eagle: growth slowed after 2007 delisting",
           "BBS relative abundance index, US + Canada (LPD record 2910). Log scale.",
           "Abundance index (log scale)", PLOT_DIR / "bald_eagle.png")


def plot_peregrine(lpd):
    pf = lpd[lpd["ID"] == "28210"]
    m = load_model("model_3_peregrine_falcon")
    first, last, bp = pf["year"].min(), pf["year"].max(), 1999

    fig, ax = plt.subplots(figsize=(8, 4.8))
    plot_observed(ax, pf, INK_2, "Observed index")
    plot_fitted(ax, m, first, last, bp, BLUE, "Fitted (model 3)")
    mark_breakpoint(ax, bp, "1999: removed from endangered list")
    log_axis(ax)
    ax.legend(loc="lower right")
    finish(fig, ax, "Peregrine falcon: growth continued after 1999 delisting",
           "BBS relative abundance index, North America (LPD record 28210). Log scale.",
           "Abundance index (log scale)", PLOT_DIR / "peregrine_falcon.png")


def plot_condor_flocks(condor):
    m = load_model("model_5_condor_ca_vs_az_ut")
    first, last, bp = condor["year"].min(), condor["year"].max(), 2019
    ca = condor[condor["flock"] == 1]
    az = condor[condor["flock"] == 0]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    plot_observed(ax, ca, BLUE, "California, observed")
    plot_observed(ax, az, ORANGE, "Arizona/Utah, observed")
    plot_fitted(ax, m, first, last, bp, BLUE, "California, fitted", flock=1)
    plot_fitted(ax, m, first, last, bp, ORANGE, "Arizona/Utah, fitted", flock=0)

    # Direct labels at the series ends.
    for s, color, name in [(ca, BLUE, "California"), (az, ORANGE, "Arizona/Utah")]:
        end = s.sort_values("year").iloc[-1]
        ax.text(end["year"] + 0.25, end["count"], name, color=INK_2, fontsize=9, va="center")

    mark_breakpoint(ax, bp, "2019: CA statewide lead ammunition ban")
    log_axis(ax)
    ax.set_xlim(first - 0.5, last + 2.2)
    ax.legend(loc="upper left", fontsize=8.5)
    ax.text(0.99, 0.02, "Only 6 California counts (2012, 2016, 2017, 2020, 2024, 2025)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5, color=INK_2)
    finish(fig, ax, "California condor wild flocks: no clear change in CA vs AZ/UT after 2019",
           "Year-end wild counts, USFWS annual population status reports. Model 5 fit. Log scale.",
           "Wild birds (log scale)", PLOT_DIR / "condor_flocks.png")


def plot_condor_collapse(lpd_raw):
    c = lpd_raw[lpd_raw["ID"] == "3328"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(c["year"], c["count"], "-", color=BLUE, lw=2, zorder=2)
    plot_observed(ax, c, BLUE, None)
    ax.axvspan(1986.5, 1991.5, color=GRID, alpha=0.6, lw=0, zorder=0)
    ax.text(1989, 12, "All wild birds in captivity\n(0 counted 1987-1991)",
            ha="center", color=INK_2, fontsize=9)
    ax.annotate("Releases begin 1992", (1992, 7), xytext=(-10, 30), textcoords="offset points",
                ha="right", color=INK_2, fontsize=9,
                arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))  # whole birds only
    finish(fig, ax, "California condor collapse, 1982-1993 (descriptive, not modelled)",
           "Wild individuals in California (LPD record 3328).",
           "Wild birds", PLOT_DIR / "condor_1982_1993.png")


if __name__ == "__main__":
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    lpd = pd.read_csv(LPD_PATH, dtype={"ID": str})
    lpd_raw = pd.read_csv(LPD_RAW_PATH, dtype={"ID": str})
    condor = pd.read_csv(CONDOR_PATH, dtype={"ID": str})

    plot_bald_eagle(lpd)
    plot_peregrine(lpd)
    plot_condor_flocks(condor)
    plot_condor_collapse(lpd_raw)
