"""
Tests for the AirPulse FastAPI backend serving layer.
Validates all analytical endpoints using FastAPI's TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "storage_backend" in data
    assert "timestamp" in data


def test_kpis_endpoint(client):
    response = client.get("/api/v1/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "locations_monitored" in data
    assert "worst_current_reading" in data
    assert "hazardous_zones_count" in data
    assert "latest_data_date" in data
    assert "data_source_label" in data


def test_locations_endpoint(client):
    response = client.get("/api/v1/locations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_unmonitored_locations_endpoint(client):
    response = client.get("/api/v1/locations/unmonitored")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_pollutants_endpoint(client):
    response = client.get("/api/v1/pollutants")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_aqi_latest_endpoint(client):
    response = client.get("/api/v1/aqi/latest")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_map_stations_endpoint(client):
    response = client.get("/api/v1/aqi/map")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for station in data:
        assert "color_hex" in station
        assert "radius" in station
        assert "avg_aqi" in station


def test_alerts_endpoint_default(client):
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["min_tier"] == "Unhealthy"
    assert data["threshold_aqi"] == 151
    assert "alert_count" in data
    assert isinstance(data["alerts"], list)


def test_alerts_endpoint_custom_tier(client):
    response = client.get("/api/v1/alerts?min_tier=Moderate")
    assert response.status_code == 200
    data = response.json()
    assert data["min_tier"] == "Moderate"
    assert data["threshold_aqi"] == 51


def test_alerts_endpoint_invalid_tier(client):
    response = client.get("/api/v1/alerts?min_tier=NonExistentTier")
    assert response.status_code == 400


def test_alerts_export_csv(client):
    response = client.get("/api/v1/alerts/export?min_tier=Moderate")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Content-Disposition" in response.headers
    assert "attachment; filename=airpulse_alerts.csv" in response.headers["Content-Disposition"]
    assert "location_name" in response.text


def test_trends_endpoint_query(client):
    response = client.get("/api/v1/aqi/trends?location_key=loc_test&pollutant_key=pm25")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_trends_endpoint_missing_params(client):
    response = client.get("/api/v1/aqi/trends")
    assert response.status_code == 422


def test_alerts_endpoint_exact_tier_filtering(client):
    response = client.get("/api/v1/alerts?min_tier=Good")
    assert response.status_code == 200
    data = response.json()
    assert data["min_tier"] == "Good"
    for alert in data["alerts"]:
        assert alert["risk_tier"] == "Good"


def test_alerts_endpoint_all_tier(client):
    response = client.get("/api/v1/alerts?min_tier=All")
    assert response.status_code == 200
    data = response.json()
    assert data["min_tier"] == "All"
    assert data["alert_count"] == len(data["alerts"])


def test_spa_index_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower()
    assert "AtmosRoute" in response.text or "AirPulse" in response.text


def test_corridor_risk_valid(client):
    locations = client.get("/api/v1/locations").json()
    assert len(locations) >= 2
    origin_key = locations[0]["location_key"]
    dest_key = locations[1]["location_key"]

    response = client.get(
        f"/api/v1/corridors/risk?origin_key={origin_key}&destination_key={dest_key}"
    )
    assert response.status_code == 200
    data = response.json()
    assert "distance_km" in data
    assert "distance_nm" in data
    assert "corridor_risk_score" in data
    assert "overall_status" in data
    assert "risk_level" in data
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0
    assert "waypoints" in data
    assert len(data["waypoints"]) > 10
    assert "origin" in data
    assert "destination" in data


def test_corridor_risk_invalid_hub(client):
    response = client.get(
        "/api/v1/corridors/risk?origin_key=nonexistent_1&destination_key=nonexistent_2"
    )
    assert response.status_code == 404


def test_corridor_risk_missing_params(client):
    response = client.get("/api/v1/corridors/risk")
    assert response.status_code == 422



