-- Encodes the exact invariant stg_openaq__measurements' dedup logic is
-- supposed to guarantee: at most one row per (sensor_id, measured_at_utc)
-- after staging. If this ever returns rows, the dedup logic in that model
-- has a bug.
select
    sensor_id,
    measured_at_utc,
    count(*) as row_count
from {{ ref('stg_openaq__measurements') }}
group by 1, 2
having count(*) > 1
