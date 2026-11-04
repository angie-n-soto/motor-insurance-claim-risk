-- At most top_n_brands named brands plus OTHER, as in src/clean.py.
select count(distinct brand_group) as n_groups
from {{ ref('dim_vehicle') }}
having count(distinct brand_group) > {{ var('top_n_brands') }} + 1
