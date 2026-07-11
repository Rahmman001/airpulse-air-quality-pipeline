"""
AirPulse — Global Air Quality Risk Intelligence Platform.

Main entry point. Run with:
    streamlit run app/streamlit_app.py

This is the landing page: the business narrative, top-line KPIs, and the
global map. City-level trend drill-down and the ops alert list are
separate pages (Streamlit's `pages/` convention puts them in the sidebar
automatically).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.data import (  # noqa: E402
    data_source_label,
    load_latest_city_aqi,
    load_locations,
    load_locations_without_recent_aqi,
    pipeline_freshness,
)
from app.utils.risk_tiers import (  # noqa: E402
    RISK_TIER_COLORS_HEX,
    RISK_TIER_COLORS_RGB,
    RISK_TIER_ORDER,
)

st.set_page_config(
    page_title="AirPulse — Air Quality Risk Intelligence",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 AirPulse — Global Air Quality Risk Intelligence")
st.caption(
    "Built for Meridian Logistics' operations team: which delivery zones have hazardous air quality "
    "right now, and where is it trending worse? Data from [OpenAQ](https://openaq.org), refreshed "
    "on a schedule by the Dagster-orchestrated pipeline behind this dashboard."
)

latest = load_latest_city_aqi()
locations = load_locations()
locations_without_recent_aqi = load_locations_without_recent_aqi()

if latest.empty:
    if not locations.empty:
        st.warning("Monitoring locations are loaded, but no recent AQI readings are available yet.")
        st.subheader("Locations without recent AQI data")
        st.dataframe(
            locations_without_recent_aqi.rename(
                columns={
                    "location_name": "Location",
                    "country_name": "Country",
                    "country_code": "Country code",
                    "data_status": "Status",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(f"Data source: {data_source_label()}.")
        st.stop()

    st.warning(
        "No data available yet. Run the pipeline first: `python -m ingestion.extract_locations`, "
        "`python -m ingestion.extract_measurements`, `python -m warehouse.load_raw`, then `dbt build` "
        "(or materialize everything from the Dagster UI) -- see the README for the full sequence."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Top-line KPIs
# ---------------------------------------------------------------------------
worst_row = latest.loc[latest["avg_aqi"].idxmax()]
num_hazardous_or_worse = latest[latest["avg_aqi"] > 150]["location_key"].nunique()
freshness = pipeline_freshness()

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Locations monitored", len(locations) if not locations.empty else latest["location_key"].nunique()
)
col2.metric(
    "Worst current reading",
    f"{worst_row['avg_aqi']:.0f} AQI",
    help=f"{worst_row['location_name']}, {worst_row['parameter_name']}",
)
col3.metric(
    "Zones needing attention",
    num_hazardous_or_worse,
    help="Locations with any pollutant averaging above 150 AQI (Unhealthy or worse)",
)
col4.metric("Data through", str(freshness["latest_date"]) if freshness["latest_date"] else "—")

st.divider()

# ---------------------------------------------------------------------------
# Global map
# ---------------------------------------------------------------------------
st.subheader("Current air quality risk by location")

# One marker per location -- worst pollutant's AQI at that location, since
# that's the one that actually determines the risk tier a person on the
# ground would experience.
map_df = latest.sort_values("avg_aqi", ascending=False).drop_duplicates(subset=["location_key"]).copy()
map_df["risk_tier"] = pd.cut(
    map_df["avg_aqi"],
    bins=[-1, 50, 100, 150, 200, 300, 10_000],
    labels=RISK_TIER_ORDER,
).astype(
    str
)  # plain string, not Categorical -- .map() with list-valued
# dicts (RGB triples) breaks specifically on Categorical columns, since
# pandas' categorical .map() internally requires hashable mapped values.
map_df["color"] = map_df["risk_tier"].map(RISK_TIER_COLORS_RGB)
map_df["radius"] = 15_000 + (map_df["avg_aqi"].clip(upper=300) * 400)

if map_df["latitude"].notna().any():
    view_state = pdk.ViewState(
        latitude=float(map_df["latitude"].mean()),
        longitude=float(map_df["longitude"].mean()),
        zoom=1.5,
        pitch=0,
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.75,
        stroked=True,
        get_line_color=[0, 0, 0, 80],
        line_width_min_pixels=1,
    )
    tooltip = {
        "html": "<b>{location_name}</b> ({country_name})<br/>"
        "Worst pollutant: {parameter_name}<br/>"
        "AQI: {avg_aqi} — {risk_tier}",
        "style": {"backgroundColor": "#1f2933", "color": "white"},
    }
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))
else:
    st.info("No coordinate data available to plot.")

# Legend
legend_cols = st.columns(len(RISK_TIER_ORDER))
for col, tier in zip(legend_cols, RISK_TIER_ORDER):
    col.markdown(
        f'<span style="color:{RISK_TIER_COLORS_HEX[tier]}; font-size:1.4em;">●</span> {tier}',
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
st.subheader("Today's most polluted locations")
leaderboard = (
    map_df[["location_name", "country_name", "parameter_name", "avg_aqi", "risk_tier"]]
    .head(10)
    .rename(
        columns={
            "location_name": "Location",
            "country_name": "Country",
            "parameter_name": "Worst pollutant",
            "avg_aqi": "AQI",
            "risk_tier": "Risk tier",
        }
    )
)
st.dataframe(leaderboard, hide_index=True, width="stretch")

if not locations_without_recent_aqi.empty:
    st.divider()
    st.subheader("Locations without recent AQI data")
    missing_display = locations_without_recent_aqi[
        ["location_name", "country_name", "country_code", "data_status"]
    ].rename(
        columns={
            "location_name": "Location",
            "country_name": "Country",
            "country_code": "Country code",
            "data_status": "Status",
        }
    )
    st.dataframe(missing_display, hide_index=True, width="stretch")

st.caption(
    f"Data source: {data_source_label()}. See the **City Trends** page for historical detail on any "
    "location, or **Alerts** for the full operational watch list."
)
