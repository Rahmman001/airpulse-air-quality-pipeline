-- Flatten the nested `sensors` array from stg_openaq__locations into one row
-- per sensor. This is the actual "handle nested JSON" step promised in the
-- project's README -- OpenAQ nests an arbitrary-length array of sensors
-- inside each location payload, and UNNEST is how DuckDB (and most modern
-- SQL engines) turn that into relational rows.
with locations as (

    select * from {{ ref('stg_openaq__locations') }}

),

unnested as (

    select
        location_id,
        location_name,
        country_code,
        latitude,
        longitude,
        timezone,
        unnest(sensors) as sensor

    from locations
    where sensors is not null and len(sensors) > 0

)

select
    sensor.id                  as sensor_id,
    location_id,
    location_name,
    country_code,
    latitude,
    longitude,
    timezone,
    sensor.parameter.id        as parameter_id,
    sensor.parameter.name      as parameter_name,
    sensor.parameter.units     as parameter_units

from unnested
