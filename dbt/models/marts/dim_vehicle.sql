-- One row per distinct vehicle profile. The data has no vehicle id, so the key
-- is a hash of the vehicle attributes.
-- brand_group mirrors src/clean.py: the top brands by policy count in the
-- TRAIN years only (zero exposure excluded), everything else is OTHER.

with policy_years as (

    select * from {{ ref('stg_policies') }}

),

top_brands as (

    select vehicle_brand
    from policy_years
    where year < {{ var('test_year') }} and not is_zero_exposure
    group by vehicle_brand
    qualify row_number() over (order by count(*) desc, vehicle_brand) <= {{ var('top_n_brands') }}

),

profiles as (

    select distinct
        {{ vehicle_key() }}       as vehicle_key,
        vehicle_brand,
        fuel_type,
        seats,
        vehicle_value,
        power_to_weight_ratio
    from policy_years

)

select
    p.vehicle_key,
    p.vehicle_brand,
    coalesce(t.vehicle_brand, 'OTHER')              as brand_group,
    p.fuel_type,
    case p.fuel_type when 'D' then 'diesel' when 'G' then 'gasoline' else 'not recorded' end
                                                    as fuel_type_label,
    p.seats,
    p.vehicle_value,
    case
        when p.vehicle_value is null then 'unknown'
        when p.vehicle_value < 10000 then '<10k'
        when p.vehicle_value < 20000 then '10-20k'
        when p.vehicle_value < 30000 then '20-30k'
        when p.vehicle_value < 50000 then '30-50k'
        else '50k+'
    end                                             as value_band,
    p.power_to_weight_ratio
from profiles as p
left join top_brands as t using (vehicle_brand)
