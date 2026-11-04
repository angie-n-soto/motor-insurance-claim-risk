-- Fact table: one row per insured per year with exposure > 0 (the same
-- population src/clean.py models). Grain: policy_year_id.

with policy_years as (

    select *
    from {{ ref('stg_policies') }}
    where not is_zero_exposure

),

with_history as (

    -- prev_year_claim exactly as in src/clean.py: only the immediately
    -- preceding year counts; a gap or a first year means no_history.
    select
        *,
        lag(year)      over (partition by insured_id order by year) as _prev_year,
        lag(has_claim) over (partition by insured_id order by year) as _prev_has_claim
    from policy_years

)

select
    policy_year_id,
    insured_id                                         as driver_key,
    year,
    {{ policy_key() }}                                 as policy_key,
    {{ vehicle_key() }}                                as vehicle_key,

    -- snapshot attributes (change every year)
    driver_age,
    case
        when driver_age is null then 'unknown'
        when driver_age < 25 then '18-24'
        when driver_age < 35 then '25-34'
        when driver_age < 45 then '35-44'
        when driver_age < 55 then '45-54'
        when driver_age < 65 then '55-64'
        else '65+'
    end                                                as driver_age_band,
    licence_age,
    years_licensed,
    case
        when _prev_year is distinct from year - 1 then 'no_history'
        when _prev_has_claim = 1 then 'yes'
        else 'no'
    end                                                as prev_year_claim,
    policy_status,

    -- measures
    total_exposure,
    total_premium,
    total_claims,
    has_claim,
    total_premium / total_exposure                     as premium_per_exposure

from with_history
