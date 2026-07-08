"""Operational alert panel -- the page that answers the business question this whole project exists for."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.data import load_latest_city_aqi  # noqa: E402
from app.utils.risk_tiers import RISK_TIER_ORDER  # noqa: E402

st.set_page_config(page_title="AirPulse — Alerts", page_icon="🚨", layout="wide")
st.title("🚨 Operational Alerts")
st.caption(
    "Locations currently at Unhealthy or worse for any monitored pollutant — the action list for "
    "deciding where to shift delivery schedules or require indoor handoffs."
)

latest = load_latest_city_aqi()
if latest.empty:
    st.warning("No data available yet — run the pipeline first (see the README).")
    st.stop()

min_tier = st.select_slider(
    "Minimum risk tier to show",
    options=RISK_TIER_ORDER,
    value="Unhealthy",
)
min_aqi_by_tier = {
    "Good": 0,
    "Moderate": 51,
    "Unhealthy for Sensitive Groups": 101,
    "Unhealthy": 151,
    "Very Unhealthy": 201,
    "Hazardous": 301,
}
threshold = min_aqi_by_tier[min_tier]

alerts = (
    latest[latest["avg_aqi"] >= threshold]
    .sort_values("avg_aqi", ascending=False)[
        [
            "location_name",
            "country_name",
            "parameter_name",
            "avg_aqi",
            "reading_count",
            "flagged_reading_count",
        ]
    ]
    .rename(
        columns={
            "location_name": "Location",
            "country_name": "Country",
            "parameter_name": "Pollutant",
            "avg_aqi": "AQI",
            "reading_count": "Readings today",
            "flagged_reading_count": "Flagged readings",
        }
    )
)

st.metric(f"Locations at {min_tier} or worse", len(alerts))

if alerts.empty:
    st.success(f"No locations currently at {min_tier} or worse. 🎉")
else:
    st.dataframe(alerts, hide_index=True, width="stretch")
    st.download_button(
        "Download as CSV",
        data=alerts.to_csv(index=False).encode("utf-8"),
        file_name="airpulse_alerts.csv",
        mime="text/csv",
    )
