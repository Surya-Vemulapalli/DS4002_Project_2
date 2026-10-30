"""Combine the cleaned per-species files into one consolidated long CSV.

Inputs:  DATA/bald_eagle_cleaned.csv (from 02_prepare_data.py)
         DATA/peregrine_falcon_28210_cleaned.csv (initial data file)
         DATA/california_condor_long.csv (initial data file)
Outputs: DATA/birds_consolidated.csv (all three species, one row per series-year)

Every row keeps its record ID and location, so separate series (different
units, locations or sources) stay distinguishable and are never merged.
"""

from pathlib import Path

import pandas as pd

from helpers import COLUMNS, LPD_SOURCE, add_log_count

# All inputs and the output live in DATA/, relative to the repository's top folder.
DATA_DIR = Path(__file__).parent.parent / "DATA"

# Bald eagle and peregrine falcon files already share the same layout.
eagle = pd.read_csv(DATA_DIR / "bald_eagle_cleaned.csv")
peregrine = pd.read_csv(DATA_DIR / "peregrine_falcon_28210_cleaned.csv")
for df in (eagle, peregrine):
    df["source"] = LPD_SOURCE

# The condor file uses different column names and mixes the LPD record (3328)
# with USFWS population counts, so rename its columns to match.
condor = pd.read_csv(DATA_DIR / "california_condor_long.csv").rename(columns={
    "Year": "year",
    "Series": "location",
    "Value": "count",
    "Units": "units",
    "Source": "source",
})
condor["species"] = "California condor"  # the condor file has no species column

# Stack the three species into one long table. IDs become text, because they
# mix LPD numbers (2910) and USFWS labels (USFWS-GLOBAL-WILD).
combined = pd.concat([eagle, peregrine, condor], ignore_index=True)
combined["ID"] = combined["ID"].astype(str)
# Recompute log_count for every series (replacing any values in the input
# files) so the same per-series rule is used throughout.
combined = add_log_count(combined)[COLUMNS].sort_values(["species", "ID", "year"])

# Save, then print each series' log_count range and which transform it used,
# as a quick check that zero-count series got log(count + 1).
out_path = DATA_DIR / "birds_consolidated.csv"
combined.to_csv(out_path, index=False)
print(f"Saved {len(combined)} rows to {out_path}\n")
print(combined.groupby(["species", "ID", "log_transform"])["log_count"].agg(["min", "max", "count"]))
