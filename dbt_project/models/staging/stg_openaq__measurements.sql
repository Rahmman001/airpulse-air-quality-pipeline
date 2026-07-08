-- Clean, rename, type-cast, and deduplicate raw hourly measurements.
with source as (

    select * from {{ source('raw', 'measurements') }}

),

renamed as (

    select
        sensor_id,
        location_id,
        value,
        "flagInfo__hasFlags"        as has_flags,
        parameter__id                as parameter_id,
        parameter__name              as parameter_name,
        parameter__units             as parameter_units,
        try_cast("period__datetimeFrom__utc" as timestamp) as measured_at_utc,
        "coverage__percentCoverage"  as percent_coverage,
        summary__avg                 as summary_avg,
        ingest_date

    from source
    -- A record with no valid measurement period is unusable downstream --
    -- drop it here rather than letting a null timestamp silently propagate
    -- into every model built on top of this one.
    where try_cast("period__datetimeFrom__utc" as timestamp) is not null

),

deduped as (

    -- Overlapping lookback windows mean the same (sensor, hour) reading can
    -- legitimately appear in more than one bronze ingest_date partition.
    -- Raw stays raw (no dedup there, by design -- see warehouse/load_raw.py);
    -- this is where we collapse to one row per real-world business key,
    -- keeping the most recently ingested copy of each.
    select
        *,
        row_number() over (
            partition by sensor_id, measured_at_utc
            order by ingest_date desc
        ) as _row_num

    from renamed

)

select * exclude (_row_num)
from deduped
where _row_num = 1
