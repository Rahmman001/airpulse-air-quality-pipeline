{#
  EPA's AQI formula is a piecewise-linear interpolation between published
  breakpoints:

      AQI = (AQI_hi - AQI_lo) / (Conc_hi - Conc_lo) * (Conc - Conc_lo) + AQI_lo

  applied within whichever breakpoint bracket the concentration falls into.
  Breakpoints below are the standard EPA tables for PM2.5/PM10 (ug/m3) and
  O3/NO2/SO2/CO (ppm, converted internally to the ppb some tables are
  published in).

  Two honest simplifications worth stating up front, both good interview
  talking points:
    1. EPA AQI is technically defined over specific averaging windows (24-hr
       for PM, 8-hr for O3, 1-hr for NO2/SO2/CO at high concentrations).
       This macro applies the breakpoint math directly to each hourly
       reading -- an "instantaneous AQI approximation," not a
       regulatory-grade figure. A real implementation would compute rolling
       windows first (a good "if I had more time" answer).
    2. Input must already be in the unit each pollutant's table expects
       (ug/m3 for PM, ppm for gases) -- see convert_to_epa_aqi_units() in
       convert_units.sql, which is what feeds this macro in
       int_measurements_aqi.sql.
#}
{% macro calculate_aqi(parameter_name_column, value_column) %}
    case
        -- IMPORTANT: NULL <= X evaluates to NULL (not true) in SQL, so
        -- without this explicit guard, a null reading (a real, expected
        -- case -- sensor outages happen) would fall through every WHEN
        -- branch below and land on the final `else 500`, silently reporting
        -- a missing reading as the single worst possible AQI value. Caught
        -- by actually inspecting output rows, not by the range test (500 is
        -- a valid value, so a range check alone can't catch this class of
        -- bug) -- a good example of why eyeballing real output still
        -- matters even when every automated test is green.
        when {{ value_column }} is null then null

        -- PM2.5, µg/m³, 24-hr breakpoints (EPA)
        when {{ parameter_name_column }} = 'pm25' then
            case
                when {{ value_column }} <= 12.0  then round(({{ value_column }} - 0.0)   * (50.0  - 0.0)   / (12.0  - 0.0)   + 0.0,   0)
                when {{ value_column }} <= 35.4  then round(({{ value_column }} - 12.1)  * (100.0 - 51.0)  / (35.4  - 12.1)  + 51.0,  0)
                when {{ value_column }} <= 55.4  then round(({{ value_column }} - 35.5)  * (150.0 - 101.0) / (55.4  - 35.5)  + 101.0, 0)
                when {{ value_column }} <= 150.4 then round(({{ value_column }} - 55.5)  * (200.0 - 151.0) / (150.4 - 55.5)  + 151.0, 0)
                when {{ value_column }} <= 250.4 then round(({{ value_column }} - 150.5) * (300.0 - 201.0) / (250.4 - 150.5) + 201.0, 0)
                when {{ value_column }} <= 350.4 then round(({{ value_column }} - 250.5) * (400.0 - 301.0) / (350.4 - 250.5) + 301.0, 0)
                when {{ value_column }} <= 500.4 then round(({{ value_column }} - 350.5) * (500.0 - 401.0) / (500.4 - 350.5) + 401.0, 0)
                else 500
            end

        -- PM10, µg/m³, 24-hr breakpoints (EPA)
        when {{ parameter_name_column }} = 'pm10' then
            case
                when {{ value_column }} <= 54  then round(({{ value_column }} - 0)   * (50.0  - 0.0)   / (54  - 0)   + 0.0,   0)
                when {{ value_column }} <= 154 then round(({{ value_column }} - 55)  * (100.0 - 51.0)  / (154 - 55)  + 51.0,  0)
                when {{ value_column }} <= 254 then round(({{ value_column }} - 155) * (150.0 - 101.0) / (254 - 155) + 101.0, 0)
                when {{ value_column }} <= 354 then round(({{ value_column }} - 255) * (200.0 - 151.0) / (354 - 255) + 151.0, 0)
                when {{ value_column }} <= 424 then round(({{ value_column }} - 355) * (300.0 - 201.0) / (424 - 355) + 201.0, 0)
                when {{ value_column }} <= 504 then round(({{ value_column }} - 425) * (400.0 - 301.0) / (504 - 425) + 301.0, 0)
                when {{ value_column }} <= 604 then round(({{ value_column }} - 505) * (500.0 - 401.0) / (604 - 505) + 401.0, 0)
                else 500
            end

        -- O3, ppm, 8-hr breakpoints (EPA) applied to the hourly reading
        when {{ parameter_name_column }} = 'o3' then
            case
                when {{ value_column }} <= 0.054 then round(({{ value_column }} - 0.000) * (50.0  - 0.0)   / (0.054 - 0.000) + 0.0,   0)
                when {{ value_column }} <= 0.070 then round(({{ value_column }} - 0.055) * (100.0 - 51.0)  / (0.070 - 0.055) + 51.0,  0)
                when {{ value_column }} <= 0.085 then round(({{ value_column }} - 0.071) * (150.0 - 101.0) / (0.085 - 0.071) + 101.0, 0)
                when {{ value_column }} <= 0.105 then round(({{ value_column }} - 0.086) * (200.0 - 151.0) / (0.105 - 0.086) + 151.0, 0)
                when {{ value_column }} <= 0.200 then round(({{ value_column }} - 0.106) * (300.0 - 201.0) / (0.200 - 0.106) + 201.0, 0)
                else 500
            end

        -- NO2, ppm input converted to ppb for the EPA table (1-hr breakpoints)
        when {{ parameter_name_column }} = 'no2' then
            case
                when {{ value_column }} * 1000 <= 53   then round(({{ value_column }} * 1000 - 0)    * (50.0  - 0.0)   / (53   - 0)    + 0.0,   0)
                when {{ value_column }} * 1000 <= 100  then round(({{ value_column }} * 1000 - 54)   * (100.0 - 51.0)  / (100  - 54)   + 51.0,  0)
                when {{ value_column }} * 1000 <= 360  then round(({{ value_column }} * 1000 - 101)  * (150.0 - 101.0) / (360  - 101)  + 101.0, 0)
                when {{ value_column }} * 1000 <= 649  then round(({{ value_column }} * 1000 - 361)  * (200.0 - 151.0) / (649  - 361)  + 151.0, 0)
                when {{ value_column }} * 1000 <= 1249 then round(({{ value_column }} * 1000 - 650)  * (300.0 - 201.0) / (1249 - 650)  + 201.0, 0)
                else 500
            end

        -- SO2, ppm input converted to ppb for the EPA table (1-hr breakpoints)
        when {{ parameter_name_column }} = 'so2' then
            case
                when {{ value_column }} * 1000 <= 35  then round(({{ value_column }} * 1000 - 0)   * (50.0  - 0.0)   / (35  - 0)   + 0.0,   0)
                when {{ value_column }} * 1000 <= 75  then round(({{ value_column }} * 1000 - 36)  * (100.0 - 51.0)  / (75  - 36)  + 51.0,  0)
                when {{ value_column }} * 1000 <= 185 then round(({{ value_column }} * 1000 - 76)  * (150.0 - 101.0) / (185 - 76)  + 101.0, 0)
                when {{ value_column }} * 1000 <= 304 then round(({{ value_column }} * 1000 - 186) * (200.0 - 151.0) / (304 - 186) + 151.0, 0)
                else 500
            end

        -- CO, ppm, 8-hr breakpoints (EPA) applied to the hourly reading
        when {{ parameter_name_column }} = 'co' then
            case
                when {{ value_column }} <= 4.4  then round(({{ value_column }} - 0.0)  * (50.0  - 0.0)   / (4.4  - 0.0)  + 0.0,   0)
                when {{ value_column }} <= 9.4  then round(({{ value_column }} - 4.5)  * (100.0 - 51.0)  / (9.4  - 4.5)  + 51.0,  0)
                when {{ value_column }} <= 12.4 then round(({{ value_column }} - 9.5)  * (150.0 - 101.0) / (12.4 - 9.5)  + 101.0, 0)
                when {{ value_column }} <= 15.4 then round(({{ value_column }} - 12.5) * (200.0 - 151.0) / (15.4 - 12.5) + 151.0, 0)
                else 500
            end

        else null
    end
{% endmacro %}
