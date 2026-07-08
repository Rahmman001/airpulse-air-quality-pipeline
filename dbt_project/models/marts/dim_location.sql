-- Friendly wrapper around the SCD2 snapshot: renames dbt's snapshot
-- metadata columns to something a dashboard query doesn't have to know is
-- snapshot-specific, and adds an is_current flag for the common case of
-- "just give me the latest version of every location."
with snapshot as (

    select * from {{ ref('dim_location_snapshot') }}

)

select
    md5(cast(location_id as varchar) || '|' || cast(dbt_valid_from as varchar)) as location_key,
    location_id,
    location_name,
    country_code,
    country_name,
    latitude,
    longitude,
    timezone,
    provider_name,
    is_mobile,
    is_monitor,
    dbt_valid_from                as valid_from,
    dbt_valid_to                  as valid_to,
    (dbt_valid_to is null)        as is_current

from snapshot
