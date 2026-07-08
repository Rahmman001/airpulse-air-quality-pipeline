-- A singular test passes when this query returns ZERO rows.
-- A negative concentration is physically impossible -- a sensor reporting
-- one indicates a calibration fault or a unit-conversion bug, either of
-- which we want to know about loudly rather than silently averaging in.
select *
from {{ ref('fact_air_quality_hourly') }}
where raw_value < 0
