"""Project-wide ingestion configuration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

# A manageable slice of the world so a full pipeline run finishes in minutes,
# not hours, during development. Extend freely once the pipeline is proven out.
TARGET_COUNTRY_ISO_CODES = ["US", "IN", "GB", "DE", "PL", "MX", "TH", "NG"]

# How far back to pull hourly measurements on each run. Fourteen days keeps
# the hourly endpoint under one API page per sensor while tolerating provider
# reporting delays that would otherwise make active-looking stations vanish
# from the dashboard.
MEASUREMENT_LOOKBACK_DAYS = 14

# Country-specific location caps for scheduled refreshes. India gets a
# larger cap so the dashboard has better coverage for major cities while the
# global per-country limit stays small enough for quick runs.
COUNTRY_LOCATION_LIMITS = {
    "IN": 20,
}

# City names to prefer when selecting a bounded slice of locations. OpenAQ
# station names vary by provider, so these are simple case-insensitive
# substrings matched against name/locality/country fields.
IMPORTANT_CITY_KEYWORDS_BY_COUNTRY = {
    "IN": [
        "delhi",
        "new delhi",
        "mumbai",
        "kolkata",
        "bengaluru",
        "bangalore",
        "chennai",
        "hyderabad",
        "pune",
        "ahmedabad",
    ],
}
