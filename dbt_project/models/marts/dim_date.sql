-- A standard calendar spine dimension. Static range rather than derived
-- from the data's min/max dates -- simpler, and a date dimension is meant
-- to exist independently of whatever happens to be loaded right now.
with date_spine as (

    select unnest(generate_series(date '2020-01-01', date '2031-01-01', interval 1 day)) as date_day

)

select
    date_day,
    md5(cast(date_day as varchar))  as date_key,
    extract(year from date_day)     as year,
    extract(month from date_day)    as month,
    extract(day from date_day)      as day_of_month,
    extract(dow from date_day)      as day_of_week,
    strftime(date_day, '%A')        as day_name,
    strftime(date_day, '%B')        as month_name,
    extract(quarter from date_day)  as quarter,
    extract(dow from date_day) in (0, 6) as is_weekend

from date_spine
