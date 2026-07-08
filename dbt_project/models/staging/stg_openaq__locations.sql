-- Clean, rename, and type-cast raw location metadata. The `sensors` array
-- stays nested here (deliberately) -- it's flattened out one level down in
-- stg_openaq__sensors, keeping "one location per row" and "one sensor per
-- row" as two separate, single-purpose models rather than one model doing
-- both jobs.
with source as (

    select * from {{ source('raw', 'locations') }}

),

renamed as (

    select
        id                        as location_id,
        name                      as location_name,
        locality,
        timezone,
        country__code              as country_code,
        country__name              as country_name,
        provider__name             as provider_name,
        owner__name                as owner_name,
        "isMobile"                 as is_mobile,
        "isMonitor"                as is_monitor,
        coordinates__latitude      as latitude,
        coordinates__longitude     as longitude,
        try_cast("datetimeFirst__utc" as timestamp) as first_reading_at_utc,
        try_cast("datetimeLast__utc" as timestamp)  as last_reading_at_utc,
        _ingested_iso              as ingested_iso,
        ingest_date,
        sensors

    from source

),

deduped as (

    -- A location can appear in more than one ingest_date partition (it's
    -- re-pulled every run). Keep the most recently ingested version of each
    -- location -- this is also what makes this model a safe input to the
    -- dim_location snapshot, which needs exactly one current row per
    -- location_id to track changes correctly.
    select
        *,
        row_number() over (
            partition by location_id
            order by ingest_date desc
        ) as _row_num

    from renamed

)

select * exclude (_row_num)
from deduped
where _row_num = 1
