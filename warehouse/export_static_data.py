"""
AirPulse Static Data Exporter for Jamstack / Cloudflare Pages.
Exports DuckDB marts and analytical telemetry as pre-computed JSON snapshots
into frontend/public/data/ for zero-cost, high-speed static edge deployment.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ingestion.config import PROJECT_ROOT
from app.api.main import (
    get_kpis,
    get_locations,
    get_unmonitored_locations,
    get_pollutants,
    get_map_stations,
    get_latest_aqi,
    get_alerts,
    MIN_AQI_BY_TIER,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DATA_OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "data"


def export_all() -> None:
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Exporting static analytical datasets to: %s", DATA_OUTPUT_DIR)

    # 1. KPIs
    kpis = get_kpis()
    _save_json("kpis.json", kpis)

    # 2. Locations
    locations = get_locations()
    _save_json("locations.json", locations)

    # 3. Unmonitored Locations
    unmonitored = get_unmonitored_locations()
    _save_json("unmonitored.json", unmonitored)

    # 4. Pollutants
    pollutants = get_pollutants()
    _save_json("pollutants.json", pollutants)

    # 5. Map Stations (with radius and risk colors)
    map_stations = get_map_stations()
    _save_json("map_stations.json", map_stations)

    # 6. Latest Daily AQI
    latest_aqi = get_latest_aqi()
    _save_json("latest_aqi.json", latest_aqi)

    # 7. Alerts for each risk tier threshold
    alerts_by_tier: dict[str, Any] = {}
    for tier in MIN_AQI_BY_TIER:
        alerts_by_tier[tier] = get_alerts(min_tier=tier)
    _save_json("alerts.json", alerts_by_tier)

    # 8. Pre-computed Hourly Trends map: {location_key}_{pollutant_key} -> trend points
    from app.utils.data import _query
    from app.api.main import _df_to_records

    trend_rows = _query("""
        SELECT location_key, pollutant_key, measured_at_utc, aqi, raw_value, value_ugm3, risk_tier
        FROM mart.fact_air_quality_hourly
        ORDER BY location_key, pollutant_key, measured_at_utc
    """)
    trends_index: dict[str, list[dict[str, Any]]] = {}
    if not trend_rows.empty:
        records = _df_to_records(trend_rows)
        for r in records:
            key = f"{r.pop('location_key')}_{r.pop('pollutant_key')}"
            trends_index.setdefault(key, []).append(r)

    _save_json("trends.json", trends_index)
    logger.info("Pre-computed %d location-pollutant trend series.", len(trends_index))

    logger.info(
        "Static analytical snapshot export complete! All datasets written to %s",
        DATA_OUTPUT_DIR,
    )


def _save_json(filename: str, data: Any) -> None:
    from app.api.main import _sanitize_for_json

    filepath = DATA_OUTPUT_DIR / filename
    sanitized = _sanitize_for_json(data)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, ensure_ascii=False, indent=2, allow_nan=False)
    size_kb = filepath.stat().st_size / 1024
    logger.info("  ✓ %-18s (%.1f KB)", filename, size_kb)


if __name__ == "__main__":
    export_all()
