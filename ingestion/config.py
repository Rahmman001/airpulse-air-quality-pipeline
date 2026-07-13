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

# Keep a small backup set for important cities, so one quiet station does not
# make the city disappear from the dashboard.
CITY_FALLBACK_STATIONS_BY_COUNTRY = {
    "IN": 2,
}

# Target cities to prefer when selecting a bounded slice of locations. OpenAQ
# still returns stations, but this keeps the project intent city-based.
IMPORTANT_CITIES_BY_COUNTRY = {
    "IN": {
        "Delhi": ["delhi", "new delhi"],
        "Mumbai": ["mumbai"],
        "Kolkata": ["kolkata"],
        "Bengaluru": ["bengaluru", "bangalore"],
        "Chennai": ["chennai"],
        "Hyderabad": ["hyderabad"],
        "Pune": ["pune"],
        "Ahmedabad": ["ahmedabad"],
    },
}
