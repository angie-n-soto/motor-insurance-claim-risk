{# Surrogate keys shared by the dimension and the fact table, so both hash
   exactly the same columns. NULLs become '~' so they still produce a key. #}

{% macro _hash(columns) -%}
    md5({%- for c in columns %}coalesce(cast({{ c }} as varchar), '~'){% if not loop.last %} || '|' || {% endif %}{%- endfor %})
{%- endmacro %}

{% macro vehicle_key() -%}
    {{ _hash(['vehicle_brand', 'fuel_type', 'seats', 'vehicle_value', 'power_to_weight_ratio']) }}
{%- endmacro %}

{% macro policy_key() -%}
    {{ _hash(['policy_type', 'business_type', 'payment_frequency', 'bonus_score',
              'municipality_type', 'circulation_area']) }}
{%- endmacro %}
