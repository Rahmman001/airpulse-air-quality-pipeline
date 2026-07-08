{#
  OpenAQ aggregates from thousands of independent providers, and gas
  pollutants (O3, NO2, SO2, CO) show up reported in ug/m3, ppm, or ppb
  depending on which provider's equipment produced the reading -- this is
  the real "multi-provider unit inconsistency" problem described in the
  project's business narrative, not a hypothetical one.

  This macro normalizes everything to ug/m3 for *display* purposes (so the
  dashboard can show one consistent unit per pollutant). It uses the
  standard EPA ideal-gas approximation at 25 C / 1 atm:

      ug/m3 = ppm * (molecular_weight / 24.45) * 1000

  This is a simplification -- real conversion depends on the actual
  temperature and pressure at the monitoring station, which OpenAQ doesn't
  provide -- and it's worth being upfront about that in an interview rather
  than presenting it as more precise than it is.
#}
{% macro convert_to_ugm3(value_column, units_column, parameter_column) %}
    case
        when {{ units_column }} = 'µg/m³' then {{ value_column }}
        when {{ units_column }} = 'ppm' and {{ parameter_column }} = 'o3'  then {{ value_column }} * (48.00 / 24.45) * 1000
        when {{ units_column }} = 'ppm' and {{ parameter_column }} = 'no2' then {{ value_column }} * (46.01 / 24.45) * 1000
        when {{ units_column }} = 'ppm' and {{ parameter_column }} = 'so2' then {{ value_column }} * (64.07 / 24.45) * 1000
        when {{ units_column }} = 'ppm' and {{ parameter_column }} = 'co'  then {{ value_column }} * (28.01 / 24.45) * 1000
        when {{ units_column }} = 'ppb' and {{ parameter_column }} = 'o3'  then {{ value_column }} * (48.00 / 24.45)
        when {{ units_column }} = 'ppb' and {{ parameter_column }} = 'no2' then {{ value_column }} * (46.01 / 24.45)
        when {{ units_column }} = 'ppb' and {{ parameter_column }} = 'so2' then {{ value_column }} * (64.07 / 24.45)
        when {{ units_column }} = 'ppb' and {{ parameter_column }} = 'co'  then {{ value_column }} * (28.01 / 24.45)
        else {{ value_column }}
    end
{% endmacro %}

{#
  EPA AQI breakpoint tables are pollutant-specific about units: PM2.5/PM10
  need ug/m3, while the gases need ppm. Since OpenAQ's source data mixes
  units across providers (see convert_to_ugm3 above), we need the inverse
  conversion too -- normalize any input into whatever unit the AQI
  breakpoint table for that specific pollutant actually expects, so
  calculate_aqi() always receives a value in the right unit regardless of
  what unit the original sensor reported in.
#}
{% macro convert_to_epa_aqi_units(value_column, units_column, parameter_column) %}
    case
        when {{ parameter_column }} in ('pm25', 'pm10') then
            case when {{ units_column }} = 'µg/m³' then {{ value_column }} else null end
        when {{ parameter_column }} = 'o3' then
            case
                when {{ units_column }} = 'ppm' then {{ value_column }}
                when {{ units_column }} = 'ppb' then {{ value_column }} / 1000.0
                when {{ units_column }} = 'µg/m³' then {{ value_column }} / ((48.00 / 24.45) * 1000)
                else null
            end
        when {{ parameter_column }} = 'no2' then
            case
                when {{ units_column }} = 'ppm' then {{ value_column }}
                when {{ units_column }} = 'ppb' then {{ value_column }} / 1000.0
                when {{ units_column }} = 'µg/m³' then {{ value_column }} / ((46.01 / 24.45) * 1000)
                else null
            end
        when {{ parameter_column }} = 'so2' then
            case
                when {{ units_column }} = 'ppm' then {{ value_column }}
                when {{ units_column }} = 'ppb' then {{ value_column }} / 1000.0
                when {{ units_column }} = 'µg/m³' then {{ value_column }} / ((64.07 / 24.45) * 1000)
                else null
            end
        when {{ parameter_column }} = 'co' then
            case
                when {{ units_column }} = 'ppm' then {{ value_column }}
                when {{ units_column }} = 'ppb' then {{ value_column }} / 1000.0
                when {{ units_column }} = 'µg/m³' then {{ value_column }} / ((28.01 / 24.45) * 1000)
                else null
            end
        else null
    end
{% endmacro %}
