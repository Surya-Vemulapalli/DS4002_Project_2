"""Step 1: list every US record for the three species so we can pick one
time series per species before modelling.

Inputs:  DATA/LPD_public.csv (raw Living Planet Database, read via helpers.py;
         download it first, see DATA/README.md)
Outputs: none saved; prints a table of candidate records (species, ID,
         location, units, first and last year, number of years)
"""

import pandas as pd

from helpers import SPECIES, load_species, year_columns

birds = load_species()
years = year_columns(birds)

rows = []
for _, rec in birds.iterrows():
    # Years that actually have a count for this record.
    observed = [int(y.lstrip("X")) for y in years if pd.notna(rec[y])]
    rows.append({
        "species": SPECIES[rec["Binomial"]],
        "ID": rec["ID"],
        "location": rec["Location"],
        "units": rec["Units"],
        "first_year": min(observed) if observed else None,
        "last_year": max(observed) if observed else None,
        "n_years": len(observed),
    })

summary = pd.DataFrame(rows).sort_values(["species", "n_years"], ascending=[True, False])

pd.set_option("display.width", 250, "display.max_colwidth", 70, "display.max_rows", 200)
print(summary.to_string(index=False))
