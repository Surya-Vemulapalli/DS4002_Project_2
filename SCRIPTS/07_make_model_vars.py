"""Iteration 6: add segmented-regression variables to each modelled series.

For every series (computed within that series):
- time:       years since the series' first year
- after:      0 before the breakpoint, 1 from the breakpoint year on
- time_after: years since the breakpoint (0 before it, and 0 in the
              breakpoint year itself)

For the condor flock comparison (comparative interrupted time series):
- flock:            1 = California, 0 = Arizona/Utah
- flock_time:       flock * time
- flock_after:      flock * after
- flock_time_after: flock * time_after

No models are fitted here.

Inputs:  DATA/lpd_series.csv (from 04_clean_data.py)
         DATA/usfws_condor_flocks.csv (from 05_build_condor_flocks.py)
Outputs: DATA/model_ready_lpd.csv    (bald eagle and peregrine, with the variables above)
         DATA/model_ready_condor.csv (CA and AZ/UT wild flocks, with the flock terms)
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
LPD_PATH = ROOT / "DATA" / "lpd_series.csv"
FLOCKS_PATH = ROOT / "DATA" / "usfws_condor_flocks.csv"
LPD_OUT = ROOT / "DATA" / "model_ready_lpd.csv"
CONDOR_OUT = ROOT / "DATA" / "model_ready_condor.csv"

# Breakpoint year for each modelled series (record ID -> year).
BREAKPOINTS = {
    "2910": 2007,             # Bald eagle: removed from endangered species list
    "28210": 1999,            # Peregrine falcon: removed from endangered species list
    # Both condor flocks: California statewide lead ammunition ban, in effect
    # July 1, 2019. USFWS counts are year-end, so 2019 is coded after = 1.
    "USFWS-CA-WILD": 2019,
    "USFWS-AZUT-WILD": 2019,
}


def add_segment_vars(df: pd.DataFrame) -> pd.DataFrame:
    """Add time, after and time_after, computed separately for each series."""
    parts = []
    for record_id, s in df.groupby("ID"):
        s = s.sort_values("year").copy()
        bp = BREAKPOINTS[record_id]
        s["breakpoint"] = bp
        s["time"] = s["year"] - s["year"].min()
        s["after"] = (s["year"] >= bp).astype(int)
        s["time_after"] = (s["year"] - bp).clip(lower=0) * s["after"]

        # Safety checks: unique years, after switches 0 -> 1 exactly once,
        # and time_after is 0 whenever after is 0.
        assert not s["year"].duplicated().any(), f"Duplicate years in {record_id}"
        assert s["after"].diff().fillna(0).isin([0, 1]).all(), f"after not monotone in {record_id}"
        assert s["after"].iloc[0] == 0 and s["after"].iloc[-1] == 1, f"No pre/post data in {record_id}"
        assert (s.loc[s["after"] == 0, "time_after"] == 0).all()
        parts.append(s)
    return pd.concat(parts, ignore_index=True)


def build_lpd() -> pd.DataFrame:
    lpd = pd.read_csv(LPD_PATH, dtype={"ID": str})
    lpd = lpd[lpd["ID"].isin(["2910", "28210"])]
    return add_segment_vars(lpd)


def build_condor() -> pd.DataFrame:
    flocks = pd.read_csv(FLOCKS_PATH, dtype={"ID": str})
    # Population series only; the *-DEATHS rows are a separate outcome.
    flocks = flocks[flocks["ID"].isin(["USFWS-CA-WILD", "USFWS-AZUT-WILD"])]
    condor = add_segment_vars(flocks)

    # Comparison terms for one comparative interrupted time series model.
    condor["flock"] = (condor["ID"] == "USFWS-CA-WILD").astype(int)
    # flock_time lets CA and AZ/UT have different growth before 2019.
    condor["flock_time"] = condor["flock"] * condor["time"]
    condor["flock_after"] = condor["flock"] * condor["after"]
    condor["flock_time_after"] = condor["flock"] * condor["time_after"]
    return condor


if __name__ == "__main__":
    lpd = build_lpd()
    condor = build_condor()
    lpd.to_csv(LPD_OUT, index=False)
    condor.to_csv(CONDOR_OUT, index=False)
    print(f"Saved {len(lpd)} rows to {LPD_OUT}")
    print(f"Saved {len(condor)} rows to {CONDOR_OUT}\n")

    # Show rows around each breakpoint so the coding can be checked.
    pd.set_option("display.width", 200)
    base = ["ID", "year", "count", "time", "after", "time_after"]
    for record_id, s in lpd.groupby("ID"):
        bp = BREAKPOINTS[record_id]
        print(f"{s['species'].iloc[0]} ({record_id}), breakpoint {bp}:")
        print(s[s["year"].between(bp - 2, bp + 2)][base].to_string(index=False), "\n")

    print("Condor flocks, breakpoint 2019 (all CA rows; AZ/UT 2017-2021):")
    near = condor[(condor["flock"] == 1) | condor["year"].between(2017, 2021)]
    cols = base + ["flock", "flock_time", "flock_after", "flock_time_after"]
    print(near[cols].sort_values(["flock", "year"], ascending=[False, True]).to_string(index=False))
