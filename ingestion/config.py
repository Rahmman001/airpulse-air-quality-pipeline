"""Project-wide ingestion configuration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# A manageable slice of the world so a full pipeline run finishes in minutes,
# not hours, during development. Extend freely once the pipeline is proven out.
TARGET_COUNTRY_ISO_CODES = [
    "IN", "US", "GB", "FR", "AU", "JP", "DE", "CA", "CH", "NL",
    "SE", "NO", "DK", "BE", "ES", "AE", "NZ", "SG", "KR", "IE",
    "AT", "FI", "IL", "CZ", "TW", "HK", "MY", "IT", "SA", "LU",
]

# How far back to pull hourly measurements on each run. 3 days (72 hours)
# covers 48h trend charts with reporting margin while keeping each sensor
# to a single OpenAQ API page.
MEASUREMENT_LOOKBACK_DAYS = 3

# Country-specific location caps for scheduled refreshes (calibrated for 8-9 min run).
COUNTRY_LOCATION_LIMITS = {
    "IN": 75,
    "US": 35,
    "GB": 15,
    "DE": 15,
    "AU": 15,
    "CA": 12,
    "CH": 10,
    "FR": 8,
    "JP": 8,
    "NL": 8,
    "ES": 8,
    "SE": 6,
    "NO": 6,
    "DK": 6,
    "BE": 6,
    "AE": 6,
    "NZ": 6,
    "SG": 5,
    "KR": 5,
    "IT": 5,
    "IE": 4,
    "AT": 4,
    "FI": 4,
    "IL": 4,
    "CZ": 4,
    "TW": 4,
    "HK": 4,
    "MY": 4,
    "SA": 4,
    "LU": 3,
}

# 10 working stations for India; up to 5 active stations or less for the Top 100 global cities
CITY_FALLBACK_STATIONS_BY_COUNTRY = {
    "IN": 10,
}

# Oxford Economics Top 100 Global Cities + Major Indian Metros
IMPORTANT_CITIES_BY_COUNTRY = {
    "IN": {
        "Delhi": ["delhi", "new delhi", "noida", "gurugram", "ghaziabad", "faridabad"],
        "Mumbai": ["mumbai", "navi mumbai", "thane", "kalyan"],
        "Kolkata": ["kolkata", "howrah"],
        "Bengaluru": ["bengaluru", "bangalore"],
        "Chennai": ["chennai", "alandur"],
        "Hyderabad": ["hyderabad", "secunderabad"],
        "Pune": ["pune", "pcmc"],
        "Ahmedabad": ["ahmedabad"],
    },
    "US": {
        "New York": ["new york", "nyc", "manhattan", "brooklyn", "queens", "bronx"],
        "San Jose": ["san jose"],
        "Seattle": ["seattle"],
        "Boston": ["boston", "cambridge"],
        "San Francisco": ["san francisco", "oakland"],
        "Los Angeles": ["los angeles", "la", "pasadena", "long beach"],
        "Washington, DC": ["washington", "dc", "arlington"],
        "Dallas": ["dallas", "fort worth"],
        "Chicago": ["chicago"],
        "Denver": ["denver"],
        "Atlanta": ["atlanta"],
        "Houston": ["houston"],
        "Philadelphia": ["philadelphia"],
        "Minneapolis": ["minneapolis", "st. paul"],
        "San Diego": ["san diego"],
        "Phoenix": ["phoenix"],
        "Miami": ["miami"],
        "Austin": ["austin"],
        "Portland": ["portland"],
        "Salt Lake City": ["salt lake"],
        "Nashville": ["nashville"],
        "Baltimore": ["baltimore"],
        "Madison": ["madison"],
        "Charlotte": ["charlotte"],
        "Raleigh": ["raleigh"],
        "Riverside": ["riverside"],
        "Columbus": ["columbus"],
        "Detroit": ["detroit"],
        "Providence": ["providence"],
        "Richmond": ["richmond"],
        "Orlando": ["orlando"],
        "Tampa": ["tampa"],
        "Las Vegas": ["las vegas"],
        "Omaha": ["omaha"],
    },
    "GB": {
        "London": ["london", "westminster", "camden", "greenwich"],
        "Edinburgh": ["edinburgh"],
        "Bristol": ["bristol"],
        "Leeds": ["leeds"],
        "Cambridge": ["cambridge"],
        "Glasgow": ["glasgow"],
        "Manchester": ["manchester"],
    },
    "FR": {
        "Paris": ["paris"],
        "Lyon": ["lyon"],
    },
    "AU": {
        "Melbourne": ["melbourne"],
        "Sydney": ["sydney"],
        "Brisbane": ["brisbane"],
        "Perth": ["perth"],
        "Canberra": ["canberra"],
        "Adelaide": ["adelaide"],
        "Gold Coast": ["gold coast"],
    },
    "JP": {
        "Tokyo": ["tokyo", "shinjuku"],
        "Osaka-Kyoto": ["osaka", "kyoto"],
    },
    "DE": {
        "Munich": ["munich", "münchen"],
        "Berlin": ["berlin", "potsdam"],
        "Hamburg": ["hamburg"],
        "Frankfurt am Main": ["frankfurt"],
        "Dusseldorf": ["dusseldorf", "düsseldorf"],
    },
    "CA": {
        "Toronto": ["toronto"],
        "Vancouver": ["vancouver"],
        "Montreal": ["montreal", "montréal"],
        "Calgary": ["calgary"],
        "Ottawa-Gatineau": ["ottawa", "gatineau"],
    },
    "CH": {
        "Zurich": ["zurich", "zürich"],
        "Geneva": ["geneva", "genève"],
        "Basel": ["basel"],
        "Bern": ["bern"],
        "Lausanne": ["lausanne"],
    },
    "NL": {
        "Amsterdam": ["amsterdam"],
        "Rotterdam": ["rotterdam"],
        "The Hague": ["hague", "den haag"],
        "Eindhoven": ["eindhoven"],
    },
    "SE": {
        "Stockholm": ["stockholm"],
        "Gothenburg": ["gothenburg", "göteborg"],
        "Malmo": ["malmo", "malmö"],
    },
    "NO": {
        "Oslo": ["oslo"],
        "Bergen": ["bergen"],
    },
    "DK": {
        "Copenhagen": ["copenhagen", "københavn"],
        "Aarhus": ["aarhus", "århus"],
    },
    "BE": {
        "Brussels": ["brussels", "bruxelles"],
        "Antwerp": ["antwerp", "antwerpen"],
        "Gent": ["gent", "ghent"],
    },
    "ES": {
        "Madrid": ["madrid"],
        "Barcelona": ["barcelona"],
    },
    "AE": {
        "Dubai": ["dubai"],
        "Abu Dhabi": ["abu dhabi"],
    },
    "NZ": {
        "Wellington": ["wellington"],
        "Auckland": ["auckland"],
    },
    "SG": {"Singapore": ["singapore"]},
    "KR": {"Seoul": ["seoul", "gangnam"]},
    "IE": {"Dublin": ["dublin"]},
    "AT": {"Vienna": ["vienna", "wien"]},
    "FI": {"Helsinki": ["helsinki"]},
    "IL": {"Tel Aviv": ["tel aviv"]},
    "CZ": {"Prague": ["prague", "praha"]},
    "TW": {"Taipei": ["taipei"]},
    "HK": {"Hong Kong": ["hong kong"]},
    "MY": {"Kuala Lumpur": ["kuala lumpur"]},
    "IT": {"Milan": ["milan", "milano"]},
    "SA": {"Riyadh": ["riyadh"]},
    "LU": {"Luxembourg": ["luxembourg"]},
}

# Major metropolitan coordinates (latitude, longitude, radius_km).
# Stations within radius_km are recognized as serving the metro area even
# if their station name omits the city name or references a local street.
MAJOR_METRO_COORDINATES = {
    "IN": {
        "Delhi": (28.6139, 77.2090, 45.0),
        "Mumbai": (19.0760, 72.8777, 40.0),
        "Kolkata": (22.5726, 88.3639, 35.0),
        "Bengaluru": (12.9716, 77.5946, 35.0),
        "Chennai": (13.0827, 80.2707, 35.0),
        "Hyderabad": (17.3850, 78.4867, 35.0),
    },
    "US": {
        "New York": (40.7128, -74.0060, 45.0),
        "Los Angeles": (34.0522, -118.2437, 50.0),
        "Chicago": (41.8781, -87.6298, 40.0),
        "Houston": (29.7604, -95.3698, 40.0),
        "Phoenix": (33.4484, -112.0740, 40.0),
        "San Francisco": (37.7749, -122.4194, 45.0),
    },
    "GB": {
        "London": (51.5074, -0.1278, 40.0),
        "Birmingham": (52.4862, -1.8904, 30.0),
        "Manchester": (53.4808, -2.2426, 30.0),
        "Glasgow": (55.8642, -4.2518, 30.0),
    },
    "DE": {
        "Berlin": (52.5200, 13.4050, 35.0),
        "Munich": (48.1351, 11.5820, 35.0),
        "Frankfurt": (50.1109, 8.6821, 30.0),
        "Hamburg": (53.5511, 9.9937, 35.0),
        "Cologne": (50.9375, 6.9603, 30.0),
    },
    "PL": {
        "Warsaw": (52.2297, 21.0122, 35.0),
        "Krakow": (50.0647, 19.9450, 30.0),
        "Wroclaw": (51.1079, 17.0385, 30.0),
    },
    "MX": {
        "Mexico City": (19.4326, -99.1332, 45.0),
        "Guadalajara": (20.6597, -103.3496, 35.0),
        "Monterrey": (25.6866, -100.3161, 35.0),
    },
    "TH": {
        "Bangkok": (13.7563, 100.5018, 45.0),
        "Chiang Mai": (18.7883, 98.9853, 30.0),
    },
    "NG": {
        "Lagos": (6.5244, 3.3792, 40.0),
        "Abuja": (9.0765, 7.3986, 35.0),
        "Kano": (12.0022, 8.5920, 30.0),
    },
}
