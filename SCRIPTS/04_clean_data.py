"""Clean DATA/birds_consolidated.csv and split it by source.

Recomputes log_count as ln(count) (blank for zero counts, marked by
zero_count) and flags the bald eagle 2009 outlier (outlier_flag).

Inputs:  DATA/birds_consolidated.csv (from 03_combine_data.py)
Outputs: DATA/lpd_series.csv   (Living Planet Database rows: records 2910,
                                28210 and 3328)
         DATA/usfws_condor.csv (USFWS condor rows: global wild, captive and
                                total series and the 2025 California count;
                                US government work, public domain)
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
INPUT_PATH = ROOT / "DATA" / "birds_consolidated.csv"
LPD_PATH = ROOT / "DATA" / "lpd_series.csv"
USFWS_PATH = ROOT / "DATA" / "usfws_condor.csv"

LPD_IDS = ["2910", "28210", "3328"]
COLUMNS = ["species", "ID", "location", "units", "year", "count",
           "log_count", "source", "zero_count", "outlier_flag"]

# Single-year spikes to flag (not remove), as (record ID, year). Models can
# then be fitted with and without these rows.
OUTLIERS = [
    ("2910", 2009),  # Bald eagle: 0.352, above both 2008 (0.313) and 2010 (0.301)
]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute log_count as ln(count) and flag zero counts."""
    df = df.copy()
    df["ID"] = df["ID"].astype(str)
    df["year"] = df["year"].astype(int)

    # Zero counts (condor 3328, 1987-1991) have no defined log, so leave
    # log_count blank (NaN) and mark them with zero_count instead.
    df["zero_count"] = df["count"] == 0
    df["log_count"] = np.log(df["count"].where(df["count"] > 0))

    df = flag_outliers(df)
    return df[COLUMNS].sort_values(["species", "ID", "year"]).reset_index(drop=True)


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Add outlier_flag: False everywhere, True for the rows in OUTLIERS."""
    df = df.copy()
    df["outlier_flag"] = False
    for record_id, year in OUTLIERS:
        series = df[df["ID"] == record_id].set_index("year")["count"]
        hit = (df["ID"] == record_id) & (df["year"] == year)
        # Safety checks: the row must exist exactly once and really be a
        # spike above both neighbouring years.
        assert hit.sum() == 1, f"Expected one row for {record_id} {year}"
        assert series[year] > series[year - 1] and series[year] > series[year + 1], (
            f"{record_id} {year} is not above both neighbouring years"
        )
        df.loc[hit, "outlier_flag"] = True
    return df


if __name__ == "__main__":
    data = clean(pd.read_csv(INPUT_PATH))

    is_lpd = data["ID"].isin(LPD_IDS)
    lpd = data[is_lpd]
    usfws = data[~is_lpd]
    # Every non-LPD row should be a USFWS row; stop if anything else slipped
    # in, so LPD data can never end up in the committable folder.
    assert usfws["ID"].str.startswith("USFWS").all(), "Unexpected non-USFWS rows"

    USFWS_PATH.parent.mkdir(exist_ok=True)
    lpd.to_csv(LPD_PATH, index=False)
    usfws.to_csv(USFWS_PATH, index=False)
    print(f"Saved {len(lpd)} LPD rows to {LPD_PATH}")
    print(f"Saved {len(usfws)} USFWS rows to {USFWS_PATH}")
