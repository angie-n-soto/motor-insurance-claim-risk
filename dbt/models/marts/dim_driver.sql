-- One row per insured (the policyholder / main driver).
-- Attributes that change every year (age, years licensed) stay on the fact table.

with policy_years as (

    select * from {{ ref('stg_policies') }}

),

latest as (

    select *
    from policy_years
    qualify row_number() over (partition by insured_id order by year desc) = 1

)

select
    l.insured_id                                    as driver_key,
    l.insured_id,
    l.year - l.driver_age                           as approx_birth_year,
    l.licence_age                                   as latest_licence_age,
    agg.first_year,
    agg.last_year,
    agg.policy_years,
    agg.years_with_claim
from latest as l
join (
    select
        insured_id,
        min(year)        as first_year,
        max(year)        as last_year,
        count(*)         as policy_years,
        sum(has_claim)   as years_with_claim
    from policy_years
    group by insured_id
) as agg using (insured_id)
