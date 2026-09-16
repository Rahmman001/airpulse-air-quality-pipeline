"""
AirPulse - Modern Decoupled FastAPI Analytical Serving Engine.
Serves REST API endpoints for operational metrics, map locations, trends, and alerts.
Mounts and serves the compiled frontend static bundle when available.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.data import (  # noqa: E402
    clear_cache,
    data_source_label,
    load_hourly_trend,
    load_latest_city_aqi,
    load_locations,
    load_locations_without_recent_aqi,
    load_pollutants,
    pipeline_freshness,
)
from app.utils.risk_tiers import RISK_TIER_COLORS_HEX  # noqa: E402

app = FastAPI(
    title="AirPulse API",
    description="Operational Air Quality Risk Intelligence API for Meridian Logistics",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

MIN_AQI_BY_TIER: dict[str, int] = {
    "All": 0,
    "Good": 0,
    "Moderate": 51,
    "Unhealthy for Sensitive Groups": 101,
    "Unhealthy": 151,
    "Very Unhealthy": 201,
    "Hazardous": 301,
}


def _sanitize_for_json(obj: Any) -> Any:
    if isinstance(obj, float):
        import math

        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to JSON-safe list of dicts, replacing NaNs and formatting timestamps."""
    if df.empty:
        return []
    clean_df = df.copy()
    for col in clean_df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        clean_df[col] = clean_df[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    for col in clean_df.select_dtypes(include=["object"]).columns:
        clean_df[col] = clean_df[col].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else x
        )
    records = clean_df.to_dict(orient="records")
    return _sanitize_for_json(records)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Health check endpoint indicating active storage backend and server status."""
    return {
        "status": "healthy",
        "storage_backend": data_source_label(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/api/v1/cache/clear")
def clear_api_cache(request: Request) -> dict[str, str]:
    """Clear all in-memory query caches (internal/localhost only)."""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=403, detail="Localhost access only")
    clear_cache()
    return {"status": "cache_cleared"}


@app.get("/api/v1/kpis")
def get_kpis() -> dict[str, Any]:
    """Top-line operational KPIs for dispatchers."""
    latest = load_latest_city_aqi()
    locations = load_locations()
    freshness = pipeline_freshness()

    latest_date = freshness["latest_date"]
    latest_date_str = (
        str(latest_date.date()) if hasattr(latest_date, "date") else str(latest_date or "—")
    )
    latest_time_raw = freshness.get("latest_time")
    latest_time_str = ""
    if latest_time_raw:
        try:
            latest_time_str = pd.to_datetime(latest_time_raw).strftime("%H:%M UTC")
        except Exception:
            latest_time_str = str(latest_time_raw)

    if latest.empty:
        return {
            "locations_monitored": len(locations) if not locations.empty else 0,
            "worst_current_reading": None,
            "hazardous_zones_count": 0,
            "latest_data_date": latest_date_str,
            "latest_data_time": latest_time_str,
            "data_source_label": data_source_label(),
        }

    valid_latest = latest.dropna(subset=["avg_aqi"])
    if valid_latest.empty:
        worst_reading = None
    else:
        worst_row = valid_latest.sort_values("avg_aqi", ascending=False).iloc[0]
        worst_reading = {
            "location_key": str(worst_row["location_key"]),
            "location_name": str(worst_row["location_name"]),
            "country_name": str(worst_row["country_name"]),
            "parameter_name": str(worst_row["parameter_name"]),
            "avg_aqi": round(float(worst_row["avg_aqi"]), 1),
            "risk_tier": str(worst_row["risk_tier"]),
        }

    hazardous_count = int(latest[latest["avg_aqi"] > 150]["location_key"].nunique())

    return {
        "locations_monitored": len(locations) if not locations.empty else int(latest["location_key"].nunique()),
        "worst_current_reading": worst_reading,
        "hazardous_zones_count": hazardous_count,
        "latest_data_date": latest_date_str,
        "latest_data_time": latest_time_str,
        "data_source_label": data_source_label(),
    }


@app.get("/api/v1/locations")
def get_locations() -> list[dict[str, Any]]:
    """Monitored location points with lat/lon and metadata."""
    locations = load_locations()
    return _df_to_records(locations)


@app.get("/api/v1/locations/unmonitored")
def get_unmonitored_locations() -> list[dict[str, Any]]:
    """Locations currently missing recent AQI data."""
    missing = load_locations_without_recent_aqi()
    return _df_to_records(missing)


@app.get("/api/v1/pollutants")
def get_pollutants() -> list[dict[str, Any]]:
    """Supported AQI pollutants."""
    pollutants = load_pollutants()
    return _df_to_records(pollutants)


@app.get("/api/v1/aqi/latest")
def get_latest_aqi() -> list[dict[str, Any]]:
    """Latest daily average AQI per location and pollutant."""
    latest = load_latest_city_aqi()
    return _df_to_records(latest)


@app.get("/api/v1/aqi/map")
def get_map_stations() -> list[dict[str, Any]]:
    """One aggregated circle per city with its average AQI, station count, centroid coordinates, and peak pollutant."""
    latest = load_latest_city_aqi()
    if latest.empty:
        return []

    df = latest.copy()
    if "city_name" not in df.columns or df["city_name"].isna().all():
        df["city_name"] = df["location_name"]
    else:
        df["city_name"] = df["city_name"].fillna(df["location_name"])

    def _get_tier(aqi: float) -> str:
        if aqi <= 50:
            return "Good"
        if aqi <= 100:
            return "Moderate"
        if aqi <= 150:
            return "Unhealthy for Sensitive Groups"
        if aqi <= 200:
            return "Unhealthy"
        if aqi <= 300:
            return "Very Unhealthy"
        return "Hazardous"

    city_records: list[dict[str, Any]] = []
    for (cc, raw_city), grp in df.groupby(["country_code", "city_name"]):
        city = "Manesar" if raw_city == "Sector-2 IMT" else str(raw_city)
        stations_count = int(grp["location_key"].nunique())
        mean_lat = float(grp["latitude"].mean())
        mean_lon = float(grp["longitude"].mean())

        # Calculate city average AQI per pollutant to find primary pollutant
        pollutant_stats = []
        for p_key, p_grp in grp.groupby("parameter_name"):
            valid_city_avg = p_grp["city_avg_aqi"].dropna()
            if not valid_city_avg.empty:
                p_aqi = float(valid_city_avg.iloc[0])
            else:
                p_aqi = float(p_grp["avg_aqi"].mean())
            pollutant_stats.append({
                "parameter_name": p_key,
                "pollutant_display_name": p_grp["pollutant_display_name"].iloc[0] if "pollutant_display_name" in p_grp.columns else p_key.upper(),
                "aqi": p_aqi,
                "top_location_key": p_grp.sort_values("avg_aqi", ascending=False)["location_key"].iloc[0],
            })

        pollutant_stats.sort(key=lambda x: x["aqi"], reverse=True)
        top_p = pollutant_stats[0]

        city_aqi = round(top_p["aqi"], 1)
        tier = _get_tier(city_aqi)

        city_records.append({
            "location_key": str(top_p["top_location_key"]),
            "city_name": city,
            "location_name": f"{city} ({stations_count} stations)" if stations_count > 1 else city,
            "country_code": str(cc),
            "country_name": str(grp["country_name"].iloc[0]),
            "latitude": round(mean_lat, 5),
            "longitude": round(mean_lon, 5),
            "parameter_name": str(top_p["parameter_name"]),
            "pollutant_display_name": str(top_p["pollutant_display_name"]),
            "avg_aqi": city_aqi,
            "city_avg_aqi": city_aqi,
            "city_stations_count": stations_count,
            "risk_tier": tier,
            "color_hex": RISK_TIER_COLORS_HEX.get(tier, "#00e400"),
            "radius": min(35, max(10, int(city_aqi / 8))),
        })

    # Sort descending by AQI
    city_records.sort(key=lambda r: r["avg_aqi"], reverse=True)
    return city_records


@app.get("/api/v1/aqi/trends")
def get_trends(
    location_key: str = Query(..., description="Location unique key"),
    pollutant_key: str = Query(..., description="Pollutant unique key"),
) -> list[dict[str, Any]]:
    """Hourly time-series trend readings for a specific location and pollutant."""
    trend = load_hourly_trend(location_key=location_key, pollutant_key=pollutant_key)
    return _df_to_records(trend)


@app.get("/api/v1/alerts")
def get_alerts(
    min_tier: str = Query(
        "Unhealthy",
        description="Risk tier classification: All, Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous",
    ),
) -> dict[str, Any]:
    """Operational alert feed filtered by risk tier classification or All."""
    if min_tier not in MIN_AQI_BY_TIER:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_tier '{min_tier}'. Must be one of: {list(MIN_AQI_BY_TIER.keys())}",
        )

    threshold = MIN_AQI_BY_TIER[min_tier]
    latest = load_latest_city_aqi()
    if latest.empty:
        return {
            "min_tier": min_tier,
            "threshold_aqi": threshold,
            "alert_count": 0,
            "alerts": [],
        }

    if min_tier == "All":
        alerts_df = latest.sort_values("avg_aqi", ascending=False).copy()
    else:
        alerts_df = (
            latest[latest["risk_tier"] == min_tier]
            .sort_values("avg_aqi", ascending=False)
            .copy()
        )

    alerts_records = _df_to_records(alerts_df)
    for item in alerts_records:
        item["color_hex"] = RISK_TIER_COLORS_HEX.get(item.get("risk_tier", "Good"), "#00e400")

    return {
        "min_tier": min_tier,
        "threshold_aqi": threshold,
        "alert_count": len(alerts_records),
        "alerts": alerts_records,
    }


@app.get("/api/v1/alerts/export")
def export_alerts_csv(
    min_tier: str = Query("Unhealthy", description="Risk tier classification threshold"),
) -> Response:
    """Download alerts as a UTF-8 encoded CSV file."""
    if min_tier not in MIN_AQI_BY_TIER:
        raise HTTPException(status_code=400, detail="Invalid risk tier")

    threshold = MIN_AQI_BY_TIER[min_tier]
    latest = load_latest_city_aqi()
    if latest.empty:
        csv_content = "location_name,country_name,parameter_name,avg_aqi,risk_tier,reading_count,flagged_reading_count\n"
    else:
        if min_tier == "All":
            filtered = latest.sort_values("avg_aqi", ascending=False).copy()
        else:
            filtered = latest[latest["risk_tier"] == min_tier].sort_values("avg_aqi", ascending=False).copy()

        export_cols = [
            "location_name",
            "country_name",
            "parameter_name",
            "avg_aqi",
            "risk_tier",
            "reading_count",
            "flagged_reading_count",
        ]
        available_cols = [c for c in export_cols if c in filtered.columns]
        # Sanitize strings to avoid formula injection
        for col in ["location_name", "country_name", "parameter_name", "risk_tier"]:
            if col in filtered.columns:
                filtered[col] = filtered[col].astype(str).apply(
                    lambda x: f"'{x}" if x.startswith(("=", "+", "-", "@")) else x
                )
        csv_content = filtered[available_cols].to_csv(index=False)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=airpulse_alerts.csv"},
    )


# ---------------------------------------------------------------------------
# Geodesic Logistics Corridors
# ---------------------------------------------------------------------------
def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def _interpolate_great_circle(
    lat1: float, lon1: float, lat2: float, lon2: float, num_points: int = 40
) -> list[dict[str, float]]:
    phi1, lambda1 = math.radians(lat1), math.radians(lon1)
    phi2, lambda2 = math.radians(lat2), math.radians(lon2)

    delta_phi = phi2 - phi1
    delta_lambda = lambda2 - lambda1
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    d = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    if d < 1e-6:
        return [{"lat": round(lat1, 4), "lon": round(lon1, 4)}]

    points: list[dict[str, float]] = []
    for i in range(num_points + 1):
        f = i / float(num_points)
        a_f = math.sin((1.0 - f) * d) / math.sin(d)
        b_f = math.sin(f * d) / math.sin(d)
        x = a_f * math.cos(phi1) * math.cos(lambda1) + b_f * math.cos(phi2) * math.cos(lambda2)
        y = a_f * math.cos(phi1) * math.sin(lambda1) + b_f * math.cos(phi2) * math.sin(lambda2)
        z = a_f * math.sin(phi1) + b_f * math.sin(phi2)

        pt_lat = math.atan2(z, math.sqrt(x**2 + y**2))
        pt_lon = math.atan2(y, x)
        points.append(
            {"lat": round(math.degrees(pt_lat), 4), "lon": round(math.degrees(pt_lon), 4)}
        )
    return points


def _resolve_hub(
    key: str, locations_df: pd.DataFrame, latest_aqi_df: pd.DataFrame
) -> dict[str, Any] | None:
    """Resolves a hub by location_key, location_id, or name, retrieving coordinates and peak AQI telemetry."""
    match = pd.DataFrame()
    if not locations_df.empty:
        match = locations_df[
            (locations_df["location_key"] == key)
            | (locations_df["location_id"].astype(str) == str(key))
            | (locations_df["location_name"].str.lower() == key.lower())
        ]
    if match.empty and not latest_aqi_df.empty:
        match = latest_aqi_df[
            (latest_aqi_df["location_key"] == key)
            | (latest_aqi_df["location_id"].astype(str) == str(key))
            | (latest_aqi_df["location_name"].str.lower() == key.lower())
        ]
    if match.empty:
        return None

    row = match.iloc[0]
    loc_id = row.get("location_id")
    loc_key = str(row.get("location_key", key))

    # Look up peak AQI telemetry
    aqi_match = pd.DataFrame()
    if not latest_aqi_df.empty:
        aqi_match = latest_aqi_df[
            (latest_aqi_df["location_id"] == loc_id)
            | (latest_aqi_df["location_key"] == loc_key)
        ].sort_values("avg_aqi", ascending=False)

    if not aqi_match.empty:
        aqi_row = aqi_match.iloc[0]
        aqi_val = round(float(aqi_row.get("avg_aqi") or 0.0), 1)
        tier = str(aqi_row.get("risk_tier", "Good"))
        param = str(aqi_row.get("parameter_name", "pm25"))
    else:
        aqi_val = 0.0
        tier = "Unmonitored"
        param = "unmonitored"

    lat = float(row.get("latitude") or 0.0)
    lon = float(row.get("longitude") or 0.0)

    return {
        "location_key": loc_key,
        "location_name": str(row.get("location_name", "Unknown Hub")),
        "country_name": str(row.get("country_name", "")),
        "country_code": str(row.get("country_code", "")),
        "latitude": lat,
        "longitude": lon,
        "parameter_name": param,
        "avg_aqi": aqi_val,
        "risk_tier": tier,
        "color_hex": RISK_TIER_COLORS_HEX.get(tier, "#94A3B8"),
    }


@app.get("/api/v1/corridors/risk")
def get_corridor_risk(
    origin_key: str = Query(..., description="Origin hub unique key"),
    destination_key: str = Query(..., description="Destination hub unique key"),
) -> dict[str, Any]:
    """Calculates route risk, distance, great-circle waypoints, and automated advisories."""
    locations_df = load_locations()
    latest_df = load_latest_city_aqi()

    origin = _resolve_hub(origin_key, locations_df, latest_df)
    if not origin:
        raise HTTPException(status_code=404, detail=f"Origin hub '{origin_key}' not found")

    dest = _resolve_hub(destination_key, locations_df, latest_df)
    if not dest:
        raise HTTPException(status_code=404, detail=f"Destination hub '{destination_key}' not found")

    lat1, lon1 = origin["latitude"], origin["longitude"]
    lat2, lon2 = dest["latitude"], dest["longitude"]

    dist_km = round(_haversine_distance_km(lat1, lon1, lat2, lon2), 1)
    dist_nm = round(dist_km * 0.539957, 1)

    aqi1 = origin["avg_aqi"]
    aqi2 = dest["avg_aqi"]
    tier1 = origin["risk_tier"]
    tier2 = dest["risk_tier"]

    # Handle missing telemetry: don't let unmonitored terminals falsely drag risk down to 0
    if tier1 == "Unmonitored" and tier2 == "Unmonitored":
        corridor_score = 0.0
        overall_status = "Telemetry Unavailable"
        risk_level = "Unmonitored"
        status_color = "#94A3B8"
    elif tier1 == "Unmonitored":
        corridor_score = aqi2
    elif tier2 == "Unmonitored":
        corridor_score = aqi1
    else:
        corridor_score = round(0.3 * aqi1 + 0.5 * aqi2 + 0.2 * max(aqi1, aqi2), 1)

    if tier1 != "Unmonitored" or tier2 != "Unmonitored":
        if corridor_score <= 50:
            overall_status = "Optimal Flight Conditions"
            risk_level = "Low"
            status_color = "#059669"
        elif corridor_score <= 100:
            overall_status = "Moderate Transit Risk"
            risk_level = "Moderate"
            status_color = "#D97706"
        elif corridor_score <= 150:
            overall_status = "Elevated Chokepoint Advisory"
            risk_level = "Elevated"
            status_color = "#EA580C"
        elif corridor_score <= 200:
            overall_status = "High Operational Impact"
            risk_level = "High"
            status_color = "#DC2626"
        else:
            overall_status = "Severe Terminal Disruption Alert"
            risk_level = "Critical"
            status_color = "#991B1B"

    # Actionable operational recommendations
    recommendations = []
    if tier1 == "Unmonitored" and tier2 == "Unmonitored":
        recommendations.append("Both route terminals are unmonitored. Local atmospheric telemetry is currently unavailable.")
    elif tier1 == "Unmonitored":
        recommendations.append(f"Origin terminal '{origin['location_name']}' is offline; corridor exposure estimated from destination.")
    elif tier2 == "Unmonitored":
        recommendations.append(f"Destination terminal '{dest['location_name']}' is offline; corridor exposure estimated from origin.")
    if origin["risk_tier"] == "Unmonitored":
        recommendations.append(
            f"Coverage Notice: Departure terminal '{origin['location_name']}' is currently unmonitored; verify local regional advisory."
        )
    if dest["risk_tier"] == "Unmonitored":
        recommendations.append(
            f"Coverage Notice: Arrival terminal '{dest['location_name']}' is currently unmonitored; verify local regional advisory."
        )
    if aqi2 > 150 or aqi1 > 150:
        recommendations.append("Cal/OSHA Title 8 §5141.1 Directive: Mandate N95 respirator PPE for outdoor cargo ramp and tarmac operations.")
    if aqi2 > 200:
        recommendations.append("Aircraft Maintenance (Boeing/Airbus AMM Guidance): Trigger Environmental Control (ECS) cabin HEPA filter inspection upon arrival.")
    if max(aqi1, aqi2) > 175:
        recommendations.append("CAT II/III Low-Visibility SOP: Anticipate ground turnaround delays (+30 to 45 mins) due to reduced ramp maneuvering visibility.")
    if 100 < aqi2 <= 150:
        recommendations.append("Workforce Health Protocol: Activate sensitive-group ramp crew rotation intervals (max 2h outdoor exposure).")
    if not recommendations:
        recommendations.append("Standard dispatch parameters: No environmental operational restrictions along flight path.")

    waypoints = _interpolate_great_circle(lat1, lon1, lat2, lon2, num_points=40)

    return {
        "origin": origin,
        "destination": dest,
        "distance_km": dist_km,
        "distance_nm": dist_nm,
        "corridor_risk_score": corridor_score,
        "overall_status": overall_status,
        "risk_level": risk_level,
        "status_color": status_color,
        "recommendations": recommendations,
        "waypoints": waypoints,
    }


# ---------------------------------------------------------------------------
# Static SPA Mounting (Production Mode)
# ---------------------------------------------------------------------------
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> Response:
        # Avoid intercepting API routes
        if full_path.startswith("api/") or full_path == "docs" or full_path == "openapi.json":
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
