-- Regression test for a real bug found while building this project: a null
-- source value (a sensor gap/outage) was silently computing as AQI=500
-- ("Hazardous") because `NULL <= x` is NULL, not true, in SQL, so it fell
-- through every breakpoint bracket to the catch-all `else 500`. A range
-- check alone (0-500) can't catch this, since 500 is technically a valid
-- AQI value -- this test encodes the actual invariant: a missing raw
-- reading must produce a missing AQI, never a fabricated one.
select *
from {{ ref('fact_air_quality_hourly') }}
where raw_value is null
  and aqi is not null
