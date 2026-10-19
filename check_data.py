"""Data checks for the segmented regression project (no modelling here)."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
LPD_PATH = ROOT / "data" / "lpd_series.csv"


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


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print("Iteration 1: LPD bird series\n")
    print(check_lpd_series().to_string(index=False))
