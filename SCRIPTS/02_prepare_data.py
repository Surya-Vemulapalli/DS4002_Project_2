"""Step 2: reshape the chosen LPD records into one long (year, count) series
per species and save them to DATA/."""

from pathlib import Path

import pandas as pd

from helpers import (COLUMNS, LPD_SOURCE, SPECIES, add_log_count, load_lpd,
                     year_columns)

# One record per species, chosen in Step 1. Using a single record ID per
# species guarantees we never mix different units or locations.
CHOSEN_IDS = {
    # US + Canada index, 1970-2022. The only bald eagle series that reaches
    # recent years; no US-only record goes past 2002.
    "Bald eagle": 2910,
    "California condor": 3328,  # California, number of individuals
    # North America (US + Canada) index, 1970-2022. Same Breeding Bird Survey
    # analysis and units as the bald eagle record, so the two are comparable.
    "Peregrine falcon": 28210,
}

OUTPUT_PATH = Path(__file__).parent.parent / "DATA" / "birds_cleaned.csv"
EAGLE_PATH = Path(__file__).parent.parent / "DATA" / "bald_eagle_cleaned.csv"

# Condor counts from the USFWS 2025 Annual Population Status report (not part
# of the LPD), already in long format in this file alongside LPD record 3328.
CONDOR_PATH = Path(__file__).parent.parent / "DATA" / "california_condor_long.csv"

def load_usfws_condor() -> pd.DataFrame:
    """Return the USFWS condor series, renamed to match the LPD columns.

    Each USFWS series keeps its own ID (e.g. USFWS-GLOBAL-WILD) so it is never
    merged with LPD record 3328, which covers a different area.
    """
    condor = pd.read_csv(CONDOR_PATH).rename(columns={
        "Year": "year",
        "Series": "location",
        "Value": "count",
        "Units": "units",
        "Source": "source",
    })
    # Rows for record 3328 come from the LPD itself, so skip them here.
    condor = condor[condor["ID"].astype(str).str.startswith("USFWS")].copy()
    condor["species"] = "California condor"
    return condor


def prepare_series() -> pd.DataFrame:
    """Return a long table with columns: species, ID, location, units, year,
    count, log_count, source."""
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
    out["source"] = LPD_SOURCE

    # Add the USFWS condor series. IDs become strings since they mix numbers
    # (LPD) and text (USFWS).
    out = pd.concat([out, load_usfws_condor()], ignore_index=True)
    out["ID"] = out["ID"].astype(str)

    out = add_log_count(out)
    return out[COLUMNS].sort_values(["species", "ID", "year"])


if __name__ == "__main__":
    data = prepare_series()
    data.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(data)} rows to {OUTPUT_PATH}")

    # Separate file with just the bald eagle series.
    eagle = data[data["species"] == "Bald eagle"]
    eagle.to_csv(EAGLE_PATH, index=False)
    print(f"Saved {len(eagle)} rows to {EAGLE_PATH}\n")

    # Quick look at each series, including gaps and zeros (log(0) is undefined).
    # Summarise per series (species + ID), not per species, since the condor
    # now has several separate series.
    for (species, record_id), grp in data.groupby(["species", "ID"]):
        gaps = grp["year"].diff().gt(1).sum()
        zeros = (grp["count"] <= 0).sum()
        print(f"{species} [{record_id}]: {len(grp)} years "
              f"({grp['year'].min()}-{grp['year'].max()}), "
              f"{gaps} gaps, {zeros} zero/negative counts")
