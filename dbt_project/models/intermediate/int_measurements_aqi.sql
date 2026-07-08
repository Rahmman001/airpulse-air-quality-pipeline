-- Compute AQI per (sensor, hour) reading. AQI breakpoint tables are
-- unit-specific per pollutant (ug/m3 for particulates, ppm for gases), so
-- we normalize into *those* units first -- separately from the ug/m3
-- display normalization upstream, since the two conversions serve different
-- purposes and shouldn't be conflated in one column.
with normalized as (

    select * from {{ ref('int_measurements_unit_normalized') }}

),

epa_units as (

    select
        *,
        {{ convert_to_epa_aqi_units('value', 'parameter_units', 'parameter_name') }} as value_epa_units

    from normalized

)

select
    *,
    {{ calculate_aqi('parameter_name', 'value_epa_units') }} as aqi

from epa_units
