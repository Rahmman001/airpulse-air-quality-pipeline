"""
Unit tests for ingestion.openaq_client.

These run entirely offline against mocked HTTP responses. The sandboxed
dev/CI environment for this project has no network path to api.openaq.org --
and more importantly, a well-designed ingestion client shouldn't need a live
external API to prove its pagination/retry logic is correct.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from ingestion.openaq_client import OpenAQAPIError, OpenAQClient


def make_response(status_code: int, json_body: dict, headers: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.headers = headers or {}
    resp.text = str(json_body)
    return resp


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Never actually sleep in tests, regardless of which code path triggers it."""
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)


@pytest.fixture
def client():
    return OpenAQClient(api_key="test-key", min_seconds_between_requests=0)


def test_missing_api_key_raises_value_error(monkeypatch):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenAQClient(api_key=None)


def test_pagination_stops_on_short_final_page(client):
    """Pages of 2, 2, then 1 record (limit=2) should yield 5 total and stop after page 3."""
    page1 = {"meta": {"page": 1, "limit": 2, "found": 5}, "results": [{"id": 1}, {"id": 2}]}
    page2 = {"meta": {"page": 2, "limit": 2, "found": 5}, "results": [{"id": 3}, {"id": 4}]}
    page3 = {"meta": {"page": 3, "limit": 2, "found": 5}, "results": [{"id": 5}]}

    mock_responses = [make_response(200, page1), make_response(200, page2), make_response(200, page3)]
    with patch.object(client.session, "get", side_effect=mock_responses) as mock_get:
        records = list(client._paginate("/v3/locations", {}, limit=2))

    assert [r["id"] for r in records] == [1, 2, 3, 4, 5]
    assert mock_get.call_count == 3


def test_found_as_string_does_not_break_pagination(client):
    """OpenAQ sometimes returns meta.found as '>100' -- pagination must not rely on it."""
    page1 = {"meta": {"page": 1, "limit": 2, "found": ">2"}, "results": [{"id": 1}, {"id": 2}]}
    page2 = {"meta": {"page": 2, "limit": 2, "found": ">2"}, "results": [{"id": 3}]}

    mock_responses = [make_response(200, page1), make_response(200, page2)]
    with patch.object(client.session, "get", side_effect=mock_responses):
        records = list(client._paginate("/v3/locations", {}, limit=2))

    assert [r["id"] for r in records] == [1, 2, 3]


def test_found_as_null_does_not_break_pagination(client):
    """`found` can also be null -- same guarantee as the string case."""
    page1 = {"meta": {"page": 1, "limit": 2, "found": None}, "results": [{"id": 1}, {"id": 2}]}
    page2 = {"meta": {"page": 2, "limit": 2, "found": None}, "results": []}

    mock_responses = [make_response(200, page1), make_response(200, page2)]
    with patch.object(client.session, "get", side_effect=mock_responses):
        records = list(client._paginate("/v3/locations", {}, limit=2))

    assert [r["id"] for r in records] == [1, 2]


def test_retries_after_429_then_succeeds(client):
    rate_limited = make_response(429, {}, headers={"x-ratelimit-reset": "1"})
    ok = make_response(200, {"meta": {"page": 1, "limit": 100, "found": 1}, "results": [{"id": 42}]})

    with patch.object(client.session, "get", side_effect=[rate_limited, ok]) as mock_get:
        payload = client._get("/v3/locations", params={})

    assert payload["results"][0]["id"] == 42
    assert mock_get.call_count == 2


def test_retries_after_server_error_then_succeeds(client):
    server_error = make_response(503, {})
    ok = make_response(200, {"meta": {"page": 1, "limit": 100, "found": 1}, "results": [{"id": 7}]})

    with patch.object(client.session, "get", side_effect=[server_error, ok]) as mock_get:
        payload = client._get("/v3/locations", params={})

    assert payload["results"][0]["id"] == 7
    assert mock_get.call_count == 2


def test_persistent_client_error_raises_without_retrying_forever(client):
    not_found = make_response(404, {"detail": "not found"})
    with patch.object(client.session, "get", side_effect=[not_found]) as mock_get:
        with pytest.raises(OpenAQAPIError):
            client._get("/v3/locations/999999999")
    # A 404 is not retryable -- it should fail on the first attempt, not burn
    # through all 5 retry attempts.
    assert mock_get.call_count == 1


def test_throttles_when_rate_limit_nearly_exhausted(client, monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))

    low_remaining = make_response(
        200,
        {"meta": {"page": 1, "limit": 100, "found": 0}, "results": []},
        headers={"x-ratelimit-remaining": "1", "x-ratelimit-reset": "3"},
    )
    with patch.object(client.session, "get", side_effect=[low_remaining]):
        client._get("/v3/locations", params={})

    assert 3 in sleep_calls


def test_get_locations_paginated_generator_returns_raw_dicts(client):
    location = {"id": 8118, "name": "New Delhi"}
    page = {"meta": {"page": 1, "limit": 100, "found": 1}, "results": [location]}
    with patch.object(client.session, "get", side_effect=[make_response(200, page)]):
        results = list(client.get_locations(iso="IN"))

    assert results == [location]


def test_get_hourly_measurements_passes_datetime_params(client):
    page = {"meta": {"page": 1, "limit": 1000, "found": 0}, "results": []}
    with patch.object(client.session, "get", side_effect=[make_response(200, page)]) as mock_get:
        list(client.get_hourly_measurements(sensor_id=123, datetime_from="2026-06-01T00:00:00Z"))

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["datetime_from"] == "2026-06-01T00:00:00Z"
    assert mock_get.call_args.args[0].endswith("/v3/sensors/123/hours")
