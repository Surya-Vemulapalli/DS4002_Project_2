"""Step 2: reshape the chosen LPD records into one long (year, count) series
per species and save them to data/ (which is git-ignored)."""

from pathlib import Path

import numpy as np
import pandas as pd

from load_data import SPECIES, load_lpd, year_columns

# One record per species, chosen in Step 1. Using a single record ID per
# species guarantees we never mix different units or locations.
CHOSEN_IDS = {
    # US + Canada index, 1970-2022. The only bald eagle series that reaches
    # recent years; no US-only record goes past 2002.
    "Bald eagle": 2910,
    "California condor": 3328,  # California, number of individuals
    "Peregrine falcon": 6005,   # Colville River area, Alaska, breeding pairs
}

OUTPUT_PATH = Path(__file__).parent / "data" / "birds_cleaned.csv"
EAGLE_PATH = Path(__file__).parent / "data" / "bald_eagle_cleaned.csv"


def prepare_series() -> pd.DataFrame:
    """Return a long table with columns: species, ID, location, units, year, count."""
    # Look records up by ID in the full database rather than the US-only
    # subset, because the bald eagle record also covers Canada.
    birds = load_lpd()
    years = year_columns(birds)

    series = []
    for species, record_id in CHOSEN_IDS.items():
        rec = birds.loc[birds["ID"] == record_id]
        # Sanity check: the ID must exist and belong to the expected species.
        assert len(rec) == 1, f"Expected exactly one row for ID {record_id}"
        assert SPECIES[rec["Binomial"].iloc[0]] == species

        # Wide -> long: one row per year, then drop years with no count.
        long = rec.melt(
            id_vars=["ID", "Location", "Units"],
            value_vars=years,
            var_name="year",
            value_name="count",
        ).dropna(subset=["count"])
        long["year"] = long["year"].str.lstrip("X").astype(int)
        long["species"] = species
        series.append(long)

    out = pd.concat(series, ignore_index=True)
    out = out.rename(columns={"Location": "location", "Units": "units"})

    # log(count + 1): the condor series has zero wild birds in 1987-1991 and
    # log(0) is undefined. Applied to every species so all models are fitted
    # on the same scale.
    out["log_count"] = np.log1p(out["count"])

    cols = ["species", "ID", "location", "units", "year", "count", "log_count"]
    return out[cols].sort_values(["species", "year"])


if __name__ == "__main__":
    data = prepare_series()
    data.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(data)} rows to {OUTPUT_PATH}")

    # Separate file with just the bald eagle series.
    eagle = data[data["species"] == "Bald eagle"]
    eagle.to_csv(EAGLE_PATH, index=False)
    print(f"Saved {len(eagle)} rows to {EAGLE_PATH}\n")

    # Quick look at each series, including gaps and zeros (log(0) is undefined).
    for species, grp in data.groupby("species"):
        gaps = grp["year"].diff().gt(1).sum()
        zeros = (grp["count"] <= 0).sum()
        print(f"{species}: {len(grp)} years, {gaps} gaps, {zeros} zero/negative counts")
        print(grp[["year", "count", "log_count"]].round(3).to_string(index=False), "\n")
