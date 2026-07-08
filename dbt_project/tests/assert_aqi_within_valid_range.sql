-- AQI is defined on a 0-500 scale by construction (the EPA breakpoint table
-- tops out at 500 and calculate_aqi() clamps anything above the last
-- breakpoint to exactly 500). A value outside this range means a bug in
-- the breakpoint macro, not a data issue -- worth failing loudly on.
select *
from {{ ref('fact_air_quality_hourly') }}
where aqi is not null
  and (aqi < 0 or aqi > 500)
