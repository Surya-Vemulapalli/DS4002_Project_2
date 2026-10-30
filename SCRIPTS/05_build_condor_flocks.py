"""Iteration 4: build DATA/usfws_condor_flocks.csv.

Annual counts for the California and Arizona/Utah wild condor flocks, typed in
by hand from US Fish and Wildlife Service reports. Every value is listed below
next to the report and page it came from, so it can be checked against the PDF.

Rules:
- Only official copies are used (fws.gov, ecos.fws.gov, the FWS document
  store, and the 2017 report hosted by CDFW). Values found only in copies
  re-hosted by third parties (2018, 2019, 2021-2023 status reports) are left
  out.
- When two official reports disagree, the most recent report is used and the
  other value is noted in source_detail.
- Missing years are left out, never imputed.

USFWS reports are US government works (public domain). DOI asks to be
credited as the source, which the source and source_detail columns do.

Inputs:  none (the values are typed in below, from the USFWS report PDFs)
Outputs: DATA/usfws_condor_flocks.csv (yearly California and Arizona/Utah
         wild flock counts and deaths, with the report and page for each value)
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT_PATH = Path(__file__).parent.parent / "DATA" / "usfws_condor_flocks.csv"

# Reports used (name, URL).
R2025 = ("USFWS California Condor Recovery Program 2025 Annual Population Status",
         "https://www.fws.gov/sites/default/files/documents/2026-02/2025-california-condor-population-status_508-compliant.pdf")
R2024 = ("USFWS California Condor Recovery Program 2024 Annual Population Status",
         "https://www.fws.gov/sites/default/files/documents/2025-03/2024-california-condor-population-status508-compliant.pdf")
R2020 = ("USFWS California Condor Recovery Program 2020 Annual Population Status",
         "https://www.fws.gov/sites/default/files/documents/2020-California-Condor-Population-Status.pdf")
R2017 = ("USFWS California Condor Recovery Program 2017 Annual Population Status",
         "https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=83849")
REV2013 = ("USFWS California Condor 5-Year Review: Summary and Evaluation (June 2013)",
           "https://ecos.fws.gov/docs/five_year_review/doc4163.pdf")

# Series definitions: ID -> (location, units).
SERIES = {
    "USFWS-CA-WILD": (
        "California wild flock (Southern CA + Central CA; excludes Pacific Northwest)",
        "Number of individuals (year-end, Dec 31)"),
    "USFWS-AZUT-WILD": (
        "Arizona/Utah wild flock",
        "Number of individuals (year-end, Dec 31)"),
    "USFWS-CA-WILD-DEATHS": (
        "California wild flock (Southern CA + Central CA)",
        "Deaths in the wild free-flying population during the year"),
    "USFWS-AZUT-WILD-DEATHS": (
        "Arizona/Utah wild flock",
        "Deaths in the wild free-flying population during the year"),
}

AZ_CHART = "p.11 chart 'AZ Lead Death vs Missing in the Wild', Population data labels"

# (ID, year, count, report, where in the report)
VALUES = [
    # ---- California wild flock -------------------------------------------
    ("USFWS-CA-WILD", 2012, 129, REV2013, "p.13 Abundance: '129 were in California' as of Dec 31, 2012"),
    ("USFWS-CA-WILD", 2016, 166, R2017, "p.1 'California 170 (2016=166)'"),
    ("USFWS-CA-WILD", 2017, 170, R2017, "p.1 'California 170' (Southern CA 80 + Central CA 90)"),
    ("USFWS-CA-WILD", 2020, 186, R2020, "p.1 'CA Wild 186' (SOCA 93 + CECA 93)"),
    ("USFWS-CA-WILD", 2024, 214, R2024, "p.1 'CA Wild 214' (Southern CA 101 + Central CA 113)"),
    ("USFWS-CA-WILD", 2025, 216, R2025, "p.1 'CA Wild 216' (Southern CA 99 + Central CA 117)"),

    # ---- Arizona/Utah wild flock -----------------------------------------
    # All years from the 2025 report's chart. Cross-checked against page 1 of
    # the 2017, 2020, 2024 and 2025 reports (all match) and against the 3-year
    # averages on the same page (all match).
    ("USFWS-AZUT-WILD", 2012, 73, R2025, AZ_CHART + "; 2013 5-Year Review p.13 gives 78 for Dec 31, 2012"),
    ("USFWS-AZUT-WILD", 2013, 77, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2014, 76, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2015, 80, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2016, 76, R2025, AZ_CHART + "; matches 2017 report p.1 (2016=76)"),
    ("USFWS-AZUT-WILD", 2017, 82, R2025, AZ_CHART + "; matches 2017 report p.1"),
    ("USFWS-AZUT-WILD", 2018, 88, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2019, 98, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2020, 103, R2025, AZ_CHART + "; matches 2020 report p.1"),
    ("USFWS-AZUT-WILD", 2021, 111, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2022, 117, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2023, 111, R2025, AZ_CHART),
    ("USFWS-AZUT-WILD", 2024, 89, R2025, AZ_CHART + "; matches 2024 report p.1"),
    ("USFWS-AZUT-WILD", 2025, 98, R2025, "p.1 'AZ/UT Wild 98'; matches " + AZ_CHART),

    # ---- Deaths, California wild flock (secondary outcome) ----------------
    ("USFWS-CA-WILD-DEATHS", 2017, 13, R2017, "p.3 '2017 Mortalities in the free-flying population: California 13'"),
    ("USFWS-CA-WILD-DEATHS", 2019, 12, R2020, "p.2 'CA 34 (2019=12)'"),
    ("USFWS-CA-WILD-DEATHS", 2020, 34, R2020, "p.2 'CA 34' (SOCA 9, CECA 25; includes 9 Dolan Fire deaths)"),
    ("USFWS-CA-WILD-DEATHS", 2023, 22, R2025, "p.3 'Wild CA 13 (2024=16; 2023=22)'; 2024 report p.3 gives 2023=13"),
    ("USFWS-CA-WILD-DEATHS", 2024, 16, R2025, "p.3 'Wild CA 13 (2024=16; 2023=22)'; 2024 report p.3 gives 8"),
    ("USFWS-CA-WILD-DEATHS", 2025, 13, R2025, "p.3 'Wild CA 13'"),

    # ---- Deaths, Arizona/Utah wild flock (secondary outcome) --------------
    ("USFWS-AZUT-WILD-DEATHS", 2017, 3, R2017, "p.3 'Arizona/Utah 3'"),
    ("USFWS-AZUT-WILD-DEATHS", 2020, 7, R2020, "p.2 'AZ/UT 7'"),
    ("USFWS-AZUT-WILD-DEATHS", 2023, 34, R2025, "p.3 'AZ/UT 8 (2024=25; 2023=34)'; includes 21 HPAI deaths; 2024 report p.3 gives 2023=30"),
    ("USFWS-AZUT-WILD-DEATHS", 2024, 25, R2025, "p.3 'AZ/UT 8 (2024=25; 2023=34)'; matches 2024 report p.3"),
    ("USFWS-AZUT-WILD-DEATHS", 2025, 8, R2025, "p.3 'AZ/UT 8'"),
]


def build() -> pd.DataFrame:
    """Turn VALUES into one long table (one row per series and year), with the
    same columns as the other cleaned files plus source_detail."""
    rows = []
    for record_id, year, count, (report, url), where in VALUES:
        location, units = SERIES[record_id]  # look up the series' description
        rows.append({
            "species": "California condor",
            "ID": record_id,
            "location": location,
            "units": units,
            "year": year,
            "count": float(count),
            "source": report,
            "source_detail": f"{report}, {where}. {url}",
        })
    df = pd.DataFrame(rows)

    # Same derived columns as usfws_condor.csv.
    df["log_count"] = np.log(df["count"].where(df["count"] > 0))
    df["zero_count"] = df["count"] == 0
    df["outlier_flag"] = False

    # Safety checks before saving.
    assert not df.duplicated(["ID", "year"]).any(), "Duplicate ID-year rows"
    assert df["source_detail"].str.len().gt(0).all(), "Missing source_detail"
    assert (df["count"] > 0).all(), "Unexpected zero or negative count"

    cols = ["species", "ID", "location", "units", "year", "count", "log_count",
            "source", "zero_count", "outlier_flag", "source_detail"]
    return df[cols].sort_values(["ID", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    flocks = build()
    flocks.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(flocks)} rows to {OUT_PATH}\n")

    # Coverage report: years found and gaps for each series. Gaps are counted
    # from when each wild flock began (California releases 1992, Arizona 1996),
    # to show which years have no official count.
    expected_start = {"USFWS-CA-WILD": 1992, "USFWS-AZUT-WILD": 1996}
    for record_id, s in flocks.groupby("ID"):
        years = sorted(s["year"])
        start = expected_start.get(record_id, years[0])
        gaps = [y for y in range(start, years[-1] + 1) if y not in years]
        print(f"{record_id}: {len(years)} years {years}")
        print(f"  gaps since {start}: {gaps}\n")
