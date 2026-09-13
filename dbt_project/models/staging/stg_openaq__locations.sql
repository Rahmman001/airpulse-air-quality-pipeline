-- Clean, rename, and type-cast raw location metadata.
with source as (

    select * from {{ source('raw', 'locations') }}

),

renamed as (

    select
        id                        as location_id,
        name                      as location_name,
        case
            when lower(name) like '%delhi%' or lower(name) like '%noida%' or lower(name) like '%gurugram%' or lower(name) like '%ghaziabad%' or lower(name) like '%faridabad%' then 'Delhi'
            when lower(name) like '%mumbai%' or lower(name) like '%thane%' or lower(name) like '%airoli%' or lower(name) like '%kalyan%' then 'Mumbai'
            when lower(name) like '%bengaluru%' or lower(name) like '%bangalore%' or lower(name) like '%peenya%' then 'Bengaluru'
            when lower(name) like '%kolkata%' or lower(name) like '%howrah%' then 'Kolkata'
            when lower(name) like '%chennai%' or lower(name) like '%manali%' or lower(name) like '%alandur%' then 'Chennai'
            when lower(name) like '%hyderabad%' or lower(name) like '%secunderabad%' or lower(name) like '%bollaram%' then 'Hyderabad'
            when lower(name) like '%pune%' or lower(name) like '%pcmc%' then 'Pune'
            when lower(name) like '%ahmedabad%' then 'Ahmedabad'
            when lower(name) like '%london%' or lower(name) like '%westminster%' then 'London'
            when lower(name) like '%new york%' or lower(name) like '%queens%' or lower(name) like '%manhattan%' or lower(name) like '%brooklyn%' then 'New York'
            when lower(name) like '%los angeles%' then 'Los Angeles'
            when lower(name) like '%chicago%' then 'Chicago'
            when lower(name) like '%houston%' then 'Houston'
            when lower(name) like '%phoenix%' then 'Phoenix'
            when lower(name) like '%san francisco%' then 'San Francisco'
            when lower(name) like '%berlin%' then 'Berlin'
            when lower(name) like '%tokyo%' then 'Tokyo'
            when lower(name) like '%singapore%' then 'Singapore'
            when lower(name) like '%dubai%' then 'Dubai'
            when lower(name) like '%bangkok%' then 'Bangkok'
            when lower(name) like '%paris%' then 'Paris'
            else coalesce(nullif(trim(try_cast(locality as varchar)), ''), split_part(name, ',', 1))
        end                       as city_name,
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
