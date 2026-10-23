"""Data checks for the segmented regression project (no modelling here)."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
LPD_PATH = ROOT / "DATA" / "lpd_series.csv"
USFWS_PATH = ROOT / "DATA" / "usfws_condor.csv"
FLOCKS_PATH = ROOT / "DATA" / "usfws_condor_flocks.csv"

# Iteration 5: condor series chosen for the analysis, with their role.
# USFWS global wild / captive / total series are deliberately not used.
SELECTED_CONDOR = {
    "USFWS-CA-WILD": ("modelled", FLOCKS_PATH),      # covered by 2019 CA lead ban
    "USFWS-AZUT-WILD": ("comparison", FLOCKS_PATH),  # voluntary lead program only
    "3328": ("descriptive only", LPD_PATH),          # CA collapse, 1982-1993
}
EXCLUDED_CONDOR = ["USFWS-GLOBAL-WILD", "USFWS-GLOBAL-CAPTIVE", "USFWS-GLOBAL-TOTAL"]


def load_all() -> pd.DataFrame:
    """Read both cleaned files (LPD and USFWS) into one table for checking."""
    return pd.concat(
        [pd.read_csv(p, dtype={"ID": str}) for p in (LPD_PATH, USFWS_PATH)],
        ignore_index=True,
    )


def check_lpd_series() -> pd.DataFrame:
    """Iteration 1: check bald eagle (2910) and peregrine falcon (28210).

    Each series should have exactly one row per year from 1970 to 2022,
    no duplicate species-year rows, and no missing count or log_count.
    """
    lpd = pd.read_csv(LPD_PATH, dtype={"ID": str})
    expected_years = set(range(1970, 2023))

    results = []
    for record_id in ["2910", "28210"]:
        s = lpd[lpd["ID"] == record_id]
        years = set(s["year"])
        results.append({
            "species": s["species"].iloc[0],
            "ID": record_id,
            "rows": len(s),
            "first_year": s["year"].min(),
            "last_year": s["year"].max(),
            "missing_years": sorted(expected_years - years) or "none",
            "extra_years": sorted(years - expected_years) or "none",
            "duplicate_species_years": int(s.duplicated(["species", "year"]).sum()),
            "missing_count": int(s["count"].isna().sum()),
            "missing_log_count": int(s["log_count"].isna().sum()),
        })
    return pd.DataFrame(results)


def check_log_transform() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Iteration 2: verify log_count against count, row by row.

    Rows with count > 0 must have log_count == ln(count) (not ln(count + 1))
    and zero_count == False. Rows with count == 0 must have a blank
    log_count and zero_count == True.
    """
    data = load_all()
    positive = data["count"] > 0

    # Recompute both candidate transforms ourselves rather than trusting
    # 04_clean_data.py. isclose allows for floating-point rounding.
    matches_ln = np.isclose(data["log_count"], np.log(data["count"].where(positive)))
    matches_ln1p = np.isclose(data["log_count"], np.log1p(data["count"]))
    data = data.assign(matches_ln=matches_ln, matches_ln1p=matches_ln1p)

    results = []
    for (species, record_id), s in data.groupby(["species", "ID"]):
        pos = s[s["count"] > 0]
        zero = s[s["count"] == 0]
        results.append({
            "species": species,
            "ID": record_id,
            "rows_count>0": len(pos),
            "not_ln(count)": int((~pos["matches_ln"]).sum()),
            "equals_ln(count+1)": int(pos["matches_ln1p"].sum()),
            "zero_count_wrongly_True": int(pos["zero_count"].sum()),
            "rows_count==0": len(zero),
            "zero_log_not_blank": int(zero["log_count"].notna().sum()),
            "zero_count_wrongly_False": int((~zero["zero_count"]).sum()),
        })

    zero_rows = data.loc[data["count"] == 0,
                         ["species", "ID", "year", "count", "log_count", "zero_count"]]
    return pd.DataFrame(results), zero_rows


def check_outlier_flag() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Iteration 3: show bald eagle 2008-2010 and every flagged row."""
    data = load_all()
    cols = ["species", "ID", "year", "count", "outlier_flag"]
    eagle = data[(data["ID"] == "2910") & data["year"].between(2008, 2010)][cols]
    flagged = data[data["outlier_flag"]][cols]
    return eagle, flagged


def check_condor_selection() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Iteration 5: summarise the selected condor series.

    Growth rates are changes in ln(count) per year between consecutive
    observed years: (ln(count_t) - ln(count_prev)) / (year_t - year_prev),
    because some years are missing. Steps involving a zero count are
    skipped since ln(0) is undefined.
    """
    assert not set(SELECTED_CONDOR) & set(EXCLUDED_CONDOR), "Excluded series selected"

    summary, growth_rows = [], []
    for record_id, (role, path) in SELECTED_CONDOR.items():
        s = pd.read_csv(path, dtype={"ID": str})
        s = s[s["ID"] == record_id].sort_values("year")

        # Per-year log growth between consecutive observed years.
        g = s[["year", "count", "log_count"]].copy()
        g["prev_year"] = g["year"].shift()
        g["prev_count"] = g["count"].shift()
        g["log_growth_per_year"] = g["log_count"].diff() / g["year"].diff()
        g = g.dropna(subset=["log_growth_per_year"])
        g.insert(0, "ID", record_id)
        growth_rows.append(g)

        steepest = g.loc[g["log_growth_per_year"].abs().idxmax()]
        summary.append({
            "ID": record_id,
            "role": role,
            "first_year": s["year"].min(),
            "last_year": s["year"].max(),
            "n_years": len(s),
            "min_count": s["count"].min(),
            "steepest_step": f"{int(steepest['prev_year'])}->{int(steepest['year'])}",
            "steepest_log_growth": round(steepest["log_growth_per_year"], 3),
        })

    growth = pd.concat(growth_rows, ignore_index=True)
    growth["prev_year"] = growth["prev_year"].astype(int)
    return pd.DataFrame(summary), growth.round(3)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    print("Iteration 1: LPD bird series\n")
    print(check_lpd_series().to_string(index=False))

    print("\nIteration 2: log transform\n")
    summary, zero_rows = check_log_transform()
    print(summary.to_string(index=False))
    print("\nRows with count == 0:\n")
    print(zero_rows.to_string(index=False))

    print("\nIteration 3: outlier flag\n")
    eagle, flagged = check_outlier_flag()
    print("Bald eagle 2008-2010:")
    print(eagle.to_string(index=False))
    print(f"\nAll flagged rows ({len(flagged)}):")
    print(flagged.to_string(index=False))

    print("\nIteration 5: selected condor series\n")
    selection, growth = check_condor_selection()
    print(selection.to_string(index=False))
    print("\nLog growth per year between consecutive observed years:\n")
    print(growth.to_string(index=False))
