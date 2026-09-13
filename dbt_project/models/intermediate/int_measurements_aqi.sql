-- Compute AQI and normalized display units (ug/m3) per (sensor, hour) reading.
with measurements as (

    select * from {{ ref('stg_openaq__measurements') }}

),

epa_units as (

    select
        *,
        {{ convert_to_ugm3('value', 'parameter_units', 'parameter_name') }} as value_ugm3,
        {{ convert_to_epa_aqi_units('value', 'parameter_units', 'parameter_name') }} as value_epa_units

    from measurements

)

select
    *,
    {{ calculate_aqi('parameter_name', 'value_epa_units') }} as aqi

from epa_units
