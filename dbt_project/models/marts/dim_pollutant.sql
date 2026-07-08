with distinct_pollutants as (

    select distinct
        parameter_id,
        parameter_name,
        parameter_units

    from {{ ref('stg_openaq__measurements') }}
    where parameter_id is not null

)

select
    md5(cast(parameter_id as varchar)) as pollutant_key,
    parameter_id,
    parameter_name,
    parameter_units,
    case parameter_name
        when 'pm25' then 'PM2.5'
        when 'pm10' then 'PM10'
        when 'o3'   then 'Ozone'
        when 'no2'  then 'Nitrogen Dioxide'
        when 'so2'  then 'Sulfur Dioxide'
        when 'co'   then 'Carbon Monoxide'
        else upper(substr(parameter_name, 1, 1)) || substr(parameter_name, 2)
    end as pollutant_display_name,
    parameter_name in ('pm25', 'pm10', 'o3', 'no2', 'so2', 'co') as has_aqi_support

from distinct_pollutants
