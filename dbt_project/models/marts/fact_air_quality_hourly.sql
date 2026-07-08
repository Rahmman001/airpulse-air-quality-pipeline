-- Grain: one row per (sensor, hour). This is the atomic fact table --
-- fact_daily_city_aqi below rolls this up for fast dashboard queries.
--
-- Known simplification worth calling out explicitly: joining to the
-- *current* version of dim_location (is_current = true) rather than the
-- version that was actually valid at measured_at_utc. For true point-in-time
-- correctness against an SCD2 dimension, you'd join on
-- measured_at_utc between valid_from and coalesce(valid_to, '9999-12-31').
-- Location metadata changes are rare and this project's history is short,
-- so the practical difference is close to zero -- but it's a real
-- simplification, not an oversight, and a great thing to walk through in
-- an interview if asked how SCD2 dimensions should really be joined.
with measurements as (

    select * from {{ ref('int_measurements_aqi') }}

),

current_locations as (

    select location_id, location_key
    from {{ ref('dim_location') }}
    where is_current

),

pollutants as (

    select parameter_id, pollutant_key
    from {{ ref('dim_pollutant') }}

)

select
    md5(cast(m.sensor_id as varchar) || '|' || cast(m.measured_at_utc as varchar)) as measurement_key,
    m.sensor_id,
    l.location_key,
    p.pollutant_key,
    m.measured_at_utc,
    date_trunc('day', m.measured_at_utc) as measured_date,
    m.value                              as raw_value,
    m.parameter_units                    as raw_units,
    m.value_ugm3,
    m.aqi,
    case
        when m.aqi is null       then null
        when m.aqi <= 50         then 'Good'
        when m.aqi <= 100        then 'Moderate'
        when m.aqi <= 150        then 'Unhealthy for Sensitive Groups'
        when m.aqi <= 200        then 'Unhealthy'
        when m.aqi <= 300        then 'Very Unhealthy'
        else 'Hazardous'
    end as risk_tier,
    m.has_flags,
    m.percent_coverage

from measurements m
left join current_locations l on m.location_id = l.location_id
left join pollutants p on m.parameter_id = p.parameter_id
