"""Clean data/birds_consolidated.csv and split it by source.

Outputs:
- data/lpd_series.csv: Living Planet Database rows (records 2910, 28210,
  3328). LPD data cannot be redistributed, so this stays in the git-ignored
  data/ folder.
- data_external/usfws_condor.csv: USFWS condor rows. US government work
  (public domain), so this can be committed.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
INPUT_PATH = ROOT / "data" / "birds_consolidated.csv"
LPD_PATH = ROOT / "data" / "lpd_series.csv"
USFWS_PATH = ROOT / "data_external" / "usfws_condor.csv"

LPD_IDS = ["2910", "28210", "3328"]
COLUMNS = ["species", "ID", "location", "units", "year", "count",
           "log_count", "source", "zero_count"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute log_count as ln(count) and flag zero counts."""
    df = df.copy()
    df["ID"] = df["ID"].astype(str)
    df["year"] = df["year"].astype(int)

    # Zero counts (condor 3328, 1987-1991) have no defined log, so leave
    # log_count blank (NaN) and mark them with zero_count instead.
    df["zero_count"] = df["count"] == 0
    df["log_count"] = np.log(df["count"].where(df["count"] > 0))

    return df[COLUMNS].sort_values(["species", "ID", "year"]).reset_index(drop=True)


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
