# Data source:
# ZSL/WWF 2026. Living Planet Database 2026.1
# <www.livingplanetindex.org/data_portal>. Downloaded on 10/15/2026.
"""Load the Living Planet Database (LPD) and pull out the three bird species."""

from pathlib import Path

import pandas as pd

# Path relative to this script, so the project works on any machine.
DATA_PATH = Path(__file__).parent / "data" / "LPD_public.csv"

# Species of interest: scientific name (as written in the "Binomial" column)
# mapped to its common name.
SPECIES = {
    "Gymnogyps_californianus": "California condor",
    "Haliaeetus_leucocephalus": "Bald eagle",
    "Falco_peregrinus": "Peregrine falcon",
}


def load_lpd(path: Path = DATA_PATH) -> pd.DataFrame:
    """Read the raw LPD CSV, treating "NULL" as a missing value."""
    if not path.exists():
        raise FileNotFoundError(
            f"LPI data not found at {path}. Download the public dataset from "
            "https://www.livingplanetindex.org/data_portal and save it as "
            "data/LPD_public.csv inside the project folder."
        )
    # latin-1 avoids decode errors from accented characters in citations.
    return pd.read_csv(path, encoding="latin-1", na_values=["NULL"], low_memory=False)


def year_columns(df: pd.DataFrame) -> list[str]:
    """Return the yearly count columns (e.g. "1950" ... "2022").

    Some versions of the file prefix years with "X", so allow for that.
    """
    return [c for c in df.columns if c.lstrip("X").isdigit()]


def load_species(path: Path = DATA_PATH) -> pd.DataFrame:
    """Return only the US records for the three study species.

    Filter on "All_countries" rather than "Country": some records (e.g. ID
    2910) list Country as "United States" but actually span the US and Canada.
    """
    df = load_lpd(path)
    mask = df["Binomial"].isin(SPECIES) & (df["All_countries"] == "United States")
    return df.loc[mask].copy()
