"""
Schema "contract" tests: validate our pydantic models against real example
payloads taken from https://docs.openaq.org (not synthetic data), so that if
these models pass, we have real confidence the ingestion layer will parse
live API responses correctly.
"""

from __future__ import annotations

from ingestion.schemas import HourlyData, Location, Meta

# Verbatim example from https://docs.openaq.org/using-the-api/quick-start
LOCATION_EXAMPLE = {
    "id": 8118,
    "name": "New Delhi",
    "locality": "India",
    "timezone": "Asia/Kolkata",
    "country": {"id": 9, "code": "IN", "name": "India"},
    "owner": {"id": 4, "name": "Unknown Governmental Organization"},
    "provider": {"id": 119, "name": "AirNow"},
    "isMobile": False,
    "isMonitor": True,
    "instruments": [{"id": 2, "name": "Government Monitor"}],
    "sensors": [
        {
            "id": 23534,
            "name": "pm25 µg/m³",
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
        }
    ],
    "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
    "licenses": [
        {
            "id": 33,
            "name": "US Public Domain",
            "attribution": {"name": "Unknown Governmental Organization", "url": None},
            "dateFrom": "2016-01-30",
            "dateTo": None,
        }
    ],
    "bounds": [77.22445, 28.63576, 77.22445, 28.63576],
    "distance": None,
    "datetimeFirst": {"utc": "2016-11-09T19:00:00Z", "local": "2016-11-10T00:30:00+05:30"},
    "datetimeLast": {"utc": "2024-12-13T14:30:00Z", "local": "2024-12-13T20:00:00+05:30"},
}


def test_location_schema_matches_real_openaq_example():
    location = Location.model_validate(LOCATION_EXAMPLE)
    assert location.id == 8118
    assert location.country.code == "IN"
    assert location.sensors[0].parameter.name == "pm25"
    assert location.coordinates.latitude == 28.63576


def test_location_schema_tolerates_null_optional_fields():
    minimal = dict(LOCATION_EXAMPLE)
    minimal["name"] = None
    minimal["licenses"] = None
    minimal["distance"] = None
    location = Location.model_validate(minimal)
    assert location.name is None
    assert location.licenses is None


def test_hourly_data_schema_matches_documented_shape():
    hourly_example = {
        "value": 12.4,
        "flagInfo": {"hasFlags": False},
        "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
        "period": {
            "label": "1hour",
            "interval": "01:00:00",
            "datetimeFrom": {"utc": "2026-06-01T00:00:00Z", "local": "2026-06-01T05:30:00+05:30"},
            "datetimeTo": {"utc": "2026-06-01T01:00:00Z", "local": "2026-06-01T06:30:00+05:30"},
        },
        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
        "summary": {
            "min": 8.1,
            "q02": 8.2,
            "q25": 10.0,
            "median": 12.0,
            "q75": 14.5,
            "q98": 16.0,
            "max": 16.9,
            "avg": 12.4,
            "sd": 2.1,
        },
        "coverage": {
            "expectedCount": 60,
            "expectedInterval": "01:00:00",
            "observedCount": 58,
            "observedInterval": "00:58:00",
            "percentComplete": 96.7,
            "percentCoverage": 96.7,
            "datetimeFrom": None,
            "datetimeTo": None,
        },
    }
    hourly = HourlyData.model_validate(hourly_example)
    assert hourly.value == 12.4
    assert hourly.parameter.units == "µg/m³"
    assert hourly.coverage.percentComplete == 96.7


def test_hourly_data_tolerates_null_value_for_sensor_gaps():
    """A sensor outage/gap is a real, expected case -- value can be null, but
    period (the hour being reported) is still present: the sensor is
    reporting 'nothing observed this hour', not 'this hour doesn't exist'."""
    hourly = HourlyData.model_validate(
        {
            "value": None,
            "flagInfo": {"hasFlags": True},
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
            "period": {
                "label": "1hour",
                "interval": "01:00:00",
                "datetimeFrom": {"utc": "2026-06-29T01:00:00Z", "local": "2026-06-29T06:30:00+05:30"},
            },
        }
    )
    assert hourly.value is None
    assert hourly.flagInfo.hasFlags is True


def test_hourly_data_defaults_summary_and_coverage_when_absent():
    """
    Regression test for a real bug caught while building Phase 4: summary
    and coverage are legitimately absent for some providers, and the old
    `Optional[...] = None` defaults meant a batch where every row lacked
    them produced a flat `coverage` column instead of `coverage__percentCoverage`
    -- breaking dbt with a "column not found" error the first time a real
    ingestion batch had zero coverage data. summary/coverage must always
    serialize as objects (with null sub-fields), even when entirely absent
    from the source payload.
    """
    hourly = HourlyData.model_validate(
        {
            "value": 10.0,
            "flagInfo": {"hasFlags": False},
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
            "period": {"datetimeFrom": {"utc": "2026-06-29T00:00:00Z", "local": "2026-06-29T00:00:00Z"}},
            # deliberately no "summary" or "coverage" key at all
        }
    )
    dumped = hourly.model_dump(mode="json")
    assert dumped["summary"] == {k: None for k in dumped["summary"]}
    assert dumped["coverage"] == {k: None for k in dumped["coverage"]}
    # crucially: these are dicts, not None -- which is what keeps pandas'
    # json_normalize flattening them into stable `summary__x` / `coverage__x`
    # columns regardless of what a given batch actually contains.
    assert isinstance(dumped["summary"], dict)
    assert isinstance(dumped["coverage"], dict)


def test_meta_found_accepts_int_string_or_null():
    assert Meta.model_validate({"page": 1, "limit": 100, "found": 5000}).found == 5000
    assert Meta.model_validate({"page": 1, "limit": 100, "found": ">100"}).found == ">100"
    assert Meta.model_validate({"page": 1, "limit": 100, "found": None}).found is None
