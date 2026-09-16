"""
End-to-end tests for the AirPulse unified pipeline runner.
"""

from __future__ import annotations

from warehouse.db import get_connection
from warehouse.pipeline_runner import has_valid_openaq_key, run_pipeline


def test_has_valid_openaq_key_placeholder(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "your-openaq-api-key-here")
    assert not has_valid_openaq_key()


def test_has_valid_openaq_key_real(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "prod-secret-live-token-12345")
    assert has_valid_openaq_key()


def test_run_pipeline_offline_mode():
    counts = run_pipeline(force_mode="offline")

    assert "fact_daily_city_aqi" in counts
    assert "fact_air_quality_hourly" in counts
    assert "dim_location" in counts
    assert "dim_pollutant" in counts

    assert counts["dim_location"] >= 20
    assert counts["fact_air_quality_hourly"] > 1000

    conn = get_connection(read_only=True)
    try:
        # Verify locations span multiple continents
        countries = conn.execute(
            "SELECT DISTINCT country_name FROM mart.dim_location"
        ).fetchall()
        country_set = {c[0] for c in countries}
        assert len(country_set) >= 10
        assert "India" in country_set
        assert "Japan" in country_set
        assert "United States" in country_set
        assert "United Kingdom" in country_set

        # Verify hourly trend data has multiple pollutants
        pollutants = conn.execute(
            "SELECT DISTINCT parameter_name FROM mart.dim_pollutant"
        ).fetchall()
        pollutant_set = {p[0] for p in pollutants}
        assert "pm25" in pollutant_set
        assert "o3" in pollutant_set
        assert "no2" in pollutant_set
    finally:
        conn.close()
