"""
Pydantic models for OpenAQ v3 API responses.

These mirror the response shapes documented at https://docs.openaq.org/api
(pulled directly from the docs, not guessed) so that ingestion fails loudly
and early if OpenAQ ever changes their schema -- rather than silently landing
malformed data into the bronze layer where it's much more expensive to catch.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


class DatetimeObject(BaseModel):
    utc: datetime
    local: datetime


class Coordinates(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CountryBase(BaseModel):
    id: Optional[int] = None
    code: str
    name: str


class EntityBase(BaseModel):
    id: int
    name: str


class ParameterBase(BaseModel):
    id: int
    name: str
    units: str
    displayName: Optional[str] = None


class InstrumentBase(BaseModel):
    id: int
    name: str


class SensorBase(BaseModel):
    id: int
    name: str
    parameter: ParameterBase


class LocationLicense(BaseModel):
    id: int
    name: str
    attribution: dict
    dateFrom: Optional[date] = None
    dateTo: Optional[date] = None


# ---------------------------------------------------------------------------
# GET /v3/locations  and  GET /v3/locations/{id}
# ---------------------------------------------------------------------------


class Location(BaseModel):
    id: int
    name: Optional[str] = None
    locality: Optional[str] = None
    timezone: str
    country: CountryBase
    owner: EntityBase
    provider: EntityBase
    isMobile: bool
    isMonitor: bool
    instruments: list[InstrumentBase] = Field(default_factory=list)
    sensors: list[SensorBase] = Field(default_factory=list)
    coordinates: Coordinates
    licenses: Optional[list[LocationLicense]] = None
    bounds: list[float] = Field(default_factory=list)
    distance: Optional[float] = None
    datetimeFirst: Optional[DatetimeObject] = None
    datetimeLast: Optional[DatetimeObject] = None


# ---------------------------------------------------------------------------
# GET /v3/sensors/{id}/hours  (precomputed hourly measurements)
# ---------------------------------------------------------------------------


class FlagInfo(BaseModel):
    hasFlags: bool


class Period(BaseModel):
    """
    datetimeFrom is required, unlike the optional fields on Coverage/Summary
    below: a measurement without a real timestamp isn't optional metadata,
    it's an unusable record, and we want pydantic to reject it loudly at
    the ingestion boundary rather than silently producing a null
    measured_at_utc three layers downstream in dbt.
    """

    label: Optional[str] = None
    interval: Optional[str] = None
    datetimeFrom: DatetimeObject
    datetimeTo: Optional[DatetimeObject] = None


class Summary(BaseModel):
    min: Optional[float] = None
    q02: Optional[float] = None
    q25: Optional[float] = None
    median: Optional[float] = None
    q75: Optional[float] = None
    q98: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    sd: Optional[float] = None


class Coverage(BaseModel):
    """All-Optional for the same reason documented on Period above."""

    expectedCount: Optional[int] = None
    expectedInterval: Optional[str] = None
    observedCount: Optional[int] = None
    observedInterval: Optional[str] = None
    percentComplete: Optional[float] = None
    percentCoverage: Optional[float] = None
    datetimeFrom: Optional[DatetimeObject] = None
    datetimeTo: Optional[DatetimeObject] = None


class HourlyData(BaseModel):
    value: Optional[float] = None
    flagInfo: FlagInfo
    parameter: ParameterBase
    # Required -- see Period's docstring above for why this one doesn't get
    # a safe default the way coverage/summary do below.
    period: Period
    coordinates: Optional[Coordinates] = None
    # default_factory (not `= None`) is deliberate: this guarantees `summary`
    # / `coverage` are ALWAYS serialized as objects, even when every
    # sub-field inside is null. Without this, pandas' json_normalize only
    # flattens a nested field into `coverage__subfield` columns when at
    # least one row in the ingestion batch has it populated as a real dict
    # -- a batch where every row's coverage is legitimately absent (some
    # OpenAQ providers don't report coverage stats at all) produces a flat
    # `coverage` column instead, and any downstream
    # `coverage__percentCoverage` reference in dbt breaks with a real
    # "column not found" error. This happened for real while building
    # Phase 4's orchestration tests -- see tests/test_orchestration.py.
    summary: Summary = Field(default_factory=Summary)
    coverage: Coverage = Field(default_factory=Coverage)


# ---------------------------------------------------------------------------
# The {meta, results} envelope every OpenAQ v3 list endpoint returns
# ---------------------------------------------------------------------------


class Meta(BaseModel):
    name: str = "openaq-api"
    website: str = "/"
    page: int = 1
    limit: int = 100
    # Documented as int | string | null -- OpenAQ returns a string like
    # ">100" once the exact count gets expensive to compute, so pagination
    # logic must never treat this as a reliable stopping condition.
    found: Optional[Union[int, str]] = None


class LocationsResponse(BaseModel):
    meta: Meta
    results: list[Location]


class HourlyDataResponse(BaseModel):
    meta: Meta
    results: list[HourlyData]
