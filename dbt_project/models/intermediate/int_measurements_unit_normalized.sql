-- Apply display-unit normalization (everything to ug/m3) on top of the
-- cleaned, deduped staging measurements. Kept as a separate model from the
-- AQI calculation below so each transformation step is independently
-- testable and the SQL stays readable -- one job per model.
with measurements as (

    select * from {{ ref('stg_openaq__measurements') }}

)

select
    *,
    {{ convert_to_ugm3('value', 'parameter_units', 'parameter_name') }} as value_ugm3

from measurements
