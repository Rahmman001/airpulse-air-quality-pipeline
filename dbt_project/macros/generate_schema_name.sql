{#
  dbt's default behavior for a custom +schema config is to prefix it with
  the target schema, e.g. `+schema: mart` becomes `dev_mart`. That's the
  right default for a shared warehouse where many devs point at the same
  database, but for a single-file local DuckDB warehouse it just adds noise.
  This is the standard override recipe from dbt's own docs for "I want my
  schema name to be exactly what I typed."
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
