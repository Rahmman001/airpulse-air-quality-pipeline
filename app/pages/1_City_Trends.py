"""City-level historical trend view."""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.data import load_hourly_trend, load_locations, load_pollutants  # noqa: E402

st.set_page_config(page_title="AirPulse — City Trends", page_icon="📈", layout="wide")
st.title("📈 City Trends")
st.caption("Drill into a specific location and pollutant to see how AQI has moved over time.")

locations = load_locations()
pollutants = load_pollutants()

if locations.empty or pollutants.empty:
    st.warning("No data available yet — run the pipeline first (see the README).")
    st.stop()

col1, col2 = st.columns(2)
location_name = col1.selectbox("Location", sorted(locations["location_name"].dropna().unique()))
pollutant_name = col2.selectbox("Pollutant", sorted(pollutants["pollutant_display_name"].dropna().unique()))

location_row = locations[locations["location_name"] == location_name].iloc[0]
pollutant_row = pollutants[pollutants["pollutant_display_name"] == pollutant_name].iloc[0]

trend = load_hourly_trend(
    location_key=location_row["location_key"], pollutant_key=pollutant_row["pollutant_key"]
)

if trend.empty:
    st.info(f"No {pollutant_name} readings for {location_name} in the data currently loaded.")
    st.stop()

st.subheader(f"{pollutant_name} — {location_name}")

# EPA breakpoint reference lines, so the person can see at a glance which
# risk-tier band the trend is sitting in, not just a bare number.
threshold_lines = (
    alt.Chart(
        pd.DataFrame(
            {
                "aqi": [50, 100, 150, 200, 300],
                "tier": [
                    "Good/Moderate",
                    "Moderate/USG",
                    "USG/Unhealthy",
                    "Unhealthy/Very Unhealthy",
                    "Very Unhealthy/Hazardous",
                ],
            }
        )
    )
    .mark_rule(strokeDash=[4, 4], color="#888", opacity=0.6)
    .encode(y="aqi:Q")
)

aqi_line = (
    alt.Chart(trend)
    .mark_line(point=True, color="#2b6cb0")
    .encode(
        x=alt.X("measured_at_utc:T", title="Time (UTC)"),
        y=alt.Y("aqi:Q", title="AQI"),
        tooltip=["measured_at_utc:T", "aqi:Q", "risk_tier:N", "raw_value:Q"],
    )
)

st.altair_chart((threshold_lines + aqi_line).properties(height=350), use_container_width=True)

st.subheader("Recent readings")
display_cols = trend[["measured_at_utc", "raw_value", "value_ugm3", "aqi", "risk_tier"]].sort_values(
    "measured_at_utc", ascending=False
)
st.dataframe(
    display_cols.rename(
        columns={
            "measured_at_utc": "Time (UTC)",
            "raw_value": "Raw value",
            "value_ugm3": "µg/m³ (normalized)",
            "aqi": "AQI",
            "risk_tier": "Risk tier",
        }
    ),
    hide_index=True,
    width="stretch",
)
