"""Project-wide ingestion configuration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

# A manageable slice of the world so a full pipeline run finishes in minutes,
# not hours, during development. Extend freely once the pipeline is proven out.
TARGET_COUNTRY_ISO_CODES = ["US", "IN", "GB", "DE", "PL", "MX", "TH", "NG"]

# How far back to pull hourly measurements on each run.
MEASUREMENT_LOOKBACK_DAYS = 3
