{#
  Locations get recalibrated, renamed, or physically moved over time -- this
  snapshot tracks that history rather than overwriting it, using dbt's
  'check' strategy (compare the listed columns run-over-run; when any of
  them differ, close out the old row with dbt_valid_to and insert a new
  current row with dbt_valid_from). This is what makes dim_location a real
  Type 2 slowly-changing dimension instead of a table that just reflects
  "whatever the API said most recently."

  Run with `dbt snapshot` -- this does NOT run automatically as part of
  `dbt run`, which is a common gotcha worth knowing.
#}
{% snapshot dim_location_snapshot %}

{{
    config(
        target_schema='mart',
        unique_key='location_id',
        strategy='check',
        check_cols=[
            'location_name', 'country_code', 'country_name',
            'latitude', 'longitude', 'timezone',
            'is_mobile', 'is_monitor', 'provider_name',
        ],
    )
}}

select * from {{ ref('stg_openaq__locations') }}

{% endsnapshot %}
