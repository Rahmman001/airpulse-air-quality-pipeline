"""
Shared risk-tier constants -- the official EPA AQI color scale, used
consistently across the map, trends, and alerts pages so a color always
means the same thing everywhere in the app.
"""

from __future__ import annotations

# Order matters here (best to worst) -- used for sorting and for building
# the legend in a sensible order, not just alphabetically.
RISK_TIER_ORDER = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]

# Official EPA AQI color scale (https://www.airnow.gov/aqi/aqi-basics/).
RISK_TIER_COLORS_HEX = {
    "Good": "#00e400",
    "Moderate": "#ffff00",
    "Unhealthy for Sensitive Groups": "#ff7e00",
    "Unhealthy": "#ff0000",
    "Very Unhealthy": "#8f3f97",
    "Hazardous": "#7e0023",
}


def hex_to_rgb(hex_color: str) -> list[int]:
    hex_color = hex_color.lstrip("#")
    return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]


RISK_TIER_COLORS_RGB = {tier: hex_to_rgb(hex_color) for tier, hex_color in RISK_TIER_COLORS_HEX.items()}

