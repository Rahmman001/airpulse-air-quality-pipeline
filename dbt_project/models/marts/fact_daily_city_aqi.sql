-- Pre-aggregated daily rollup so the Streamlit dashboard never has to scan
-- raw hourly data on every page load. This is the table the dashboard's
-- map, leaderboard, and trend views query directly.
with hourly as (

    select * from {{ ref('fact_air_quality_hourly') }}

),

locations as (

    select location_key, location_id, location_name, country_code, country_name, latitude, longitude
    from {{ ref('dim_location') }}
    where is_current

),

pollutants as (

    select pollutant_key, parameter_name, pollutant_display_name
    from {{ ref('dim_pollutant') }}

)

select
    h.measured_date,
    l.location_key,
    l.location_id,
    l.location_name,
    l.country_code,
    l.country_name,
    l.latitude,
    l.longitude,
    p.pollutant_key,
    p.parameter_name,
    p.pollutant_display_name,
    avg(h.aqi)                                     as avg_aqi,
    max(h.aqi)                                      as max_aqi,
    avg(h.value_ugm3)                               as avg_value_ugm3,
    count(*)                                        as reading_count,
    sum(case when h.has_flags then 1 else 0 end)    as flagged_reading_count

from hourly h
join locations l on h.location_key = l.location_key
join pollutants p on h.pollutant_key = p.pollutant_key
where h.aqi is not null
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
