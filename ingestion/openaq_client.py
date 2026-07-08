"""
A thin, defensive client for the OpenAQ v3 API.

This handles the three things that make OpenAQ a genuinely non-trivial
ingestion source rather than "just call requests.get":

  1. Pagination, where `meta.found` can be an int, a string like ">100", or
     null -- so it can never be trusted as a hard stop condition.
  2. A published, enforced rate limit (60/min, 2,000/hour) surfaced via
     response headers, which we proactively respect instead of hoping we
     never hit a 429.
  3. Transient failures (429 / 5xx) that should be retried with exponential
     backoff, versus permanent failures (404, malformed request) that
     should fail fast and loud.

Docs: https://docs.openaq.org/api
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Iterator, Optional

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openaq.org"


class OpenAQAPIError(Exception):
    """Raised for non-retryable HTTP errors (4xx other than 429)."""


class OpenAQRateLimitError(Exception):
    """Raised internally so tenacity can retry a 429 with backoff."""


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout, OpenAQRateLimitError),
    )


class OpenAQClient:
    """A minimal, paginated, retrying client for OpenAQ v3."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        min_seconds_between_requests: float = 1.05,  # keeps steady-state usage under 60/min
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No OpenAQ API key found. Set OPENAQ_API_KEY in your environment "
                "or .env file, or pass api_key= explicitly. Get a free key "
                "(no credit card) at https://explore.openaq.org/register"
            )
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key})
        self._min_seconds_between_requests = min_seconds_between_requests
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Low-level request handling
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Proactively pace requests so we rarely trigger a 429 in the first place."""
        elapsed = time.monotonic() - self._last_request_time
        wait = self._min_seconds_between_requests - elapsed
        if wait > 0:
            time.sleep(wait)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict:
        self._throttle()
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, timeout=30)
        self._last_request_time = time.monotonic()

        # React to the published rate-limit headers before we ever get a 429.
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
            reset_seconds = int(response.headers.get("x-ratelimit-reset", 5))
            logger.info(
                "Approaching OpenAQ rate limit (remaining=%s); sleeping %ss",
                remaining,
                reset_seconds,
            )
            time.sleep(reset_seconds)

        if response.status_code == 429:
            reset_seconds = int(response.headers.get("x-ratelimit-reset", 10))
            logger.warning("Rate limited by OpenAQ; backing off %ss", reset_seconds)
            time.sleep(reset_seconds)
            raise OpenAQRateLimitError(f"429 from {url}")

        if response.status_code >= 500:
            raise OpenAQRateLimitError(f"{response.status_code} (server error) from {url}")

        if response.status_code >= 400:
            raise OpenAQAPIError(f"{response.status_code} from {url}: {response.text[:500]}")

        return response.json()

    # ------------------------------------------------------------------
    # Generic pagination
    # ------------------------------------------------------------------

    def _paginate(self, path: str, params: dict[str, Any], limit: int = 100) -> Iterator[dict]:
        """
        Yield individual `results` records across all pages of a list endpoint.

        We deliberately do NOT use `meta.found` as the stop condition, since
        it's documented as int | string | null and OpenAQ returns a value
        like '>100' once an exact count gets expensive to compute. The only
        reliable signal is a page coming back shorter than the requested
        `limit`.
        """
        page = 1
        query = {**params, "limit": limit}
        while True:
            query["page"] = page
            payload = self._get(path, params=query)
            results = payload.get("results", [])
            for record in results:
                yield record

            if len(results) < limit:
                return
            page += 1

    # ------------------------------------------------------------------
    # Public resource methods
    # ------------------------------------------------------------------

    def get_locations(
        self,
        countries_id: Optional[int] = None,
        iso: Optional[str] = None,
        bbox: Optional[str] = None,
        limit: int = 100,
    ) -> Iterator[dict]:
        """Paginated generator over GET /v3/locations."""
        params: dict[str, Any] = {}
        if countries_id is not None:
            params["countries_id"] = countries_id
        if iso is not None:
            params["iso"] = iso
        if bbox is not None:
            params["bbox"] = bbox
        yield from self._paginate("/v3/locations", params, limit=limit)

    def get_sensors_for_location(self, location_id: int, limit: int = 100) -> Iterator[dict]:
        """Paginated generator over GET /v3/locations/{id}/sensors."""
        yield from self._paginate(f"/v3/locations/{location_id}/sensors", {}, limit=limit)

    def get_hourly_measurements(
        self,
        sensor_id: int,
        datetime_from: Optional[str] = None,
        datetime_to: Optional[str] = None,
        limit: int = 1000,
    ) -> Iterator[dict]:
        """
        Paginated generator over GET /v3/sensors/{id}/hours.

        `datetime_from` / `datetime_to` should be ISO-8601 strings, e.g.
        '2026-06-01T00:00:00Z'. OpenAQ's own docs recommend always scoping
        this endpoint to a year or less so queries can use database indexes.
        """
        params: dict[str, Any] = {}
        if datetime_from is not None:
            params["datetime_from"] = datetime_from
        if datetime_to is not None:
            params["datetime_to"] = datetime_to
        yield from self._paginate(f"/v3/sensors/{sensor_id}/hours", params, limit=limit)
