-- One row per insured per year, typed and renamed. No rows are dropped here
-- except exact (insured_id, year) duplicates; the zero-exposure filter is
-- applied in fct_policy_year so the data-quality picture stays visible.

with source as (

    select * from {{ source('raw', 'motor_portfolio') }}

),

renamed as (

    select
        cast(insured_id as varchar) || '-' || cast(year as varchar)  as policy_year_id,
        cast(insured_id as varchar)                                  as insured_id,
        cast(year as integer)                                        as year,

        -- policy terms
        cast(policy_type as varchar)                                 as policy_type,
        cast(business_type as varchar)                               as business_type,
        cast(payment_frequency as varchar)                           as payment_frequency,
        cast(bonus_score as varchar)                                 as bonus_score,
        -- recorded "at the time of analysis", i.e. after the year: reporting only, never a feature
        cast(policy_status as varchar)                               as policy_status,
        cast(municipality_type as varchar)                           as municipality_type,
        cast(circulation_area as varchar)                            as circulation_area,

        -- driver. EDA findings 1-2: vehicle_age is really years licensed and
        -- age_driving_licence is the age when licensed. Under 16 = data error -> null.
        cast(driver_age as integer)                                  as driver_age,
        case
            when age_driving_licence < {{ var('min_licence_age') }} then null
            else cast(age_driving_licence as integer)
        end                                                          as licence_age,
        cast(vehicle_age as integer)                                 as years_licensed,

        -- vehicle. Missing fuel type carries signal, so it is its own category.
        cast(vehicle_brand as varchar)                               as vehicle_brand,
        coalesce(cast(fuel_type as varchar), 'missing')              as fuel_type,
        cast(vehicle_value as double)                                as vehicle_value,
        cast(seats as integer)                                       as seats,
        cast(power_to_weight_ratio as double)                        as power_to_weight_ratio,

        -- measures
        cast(total_exposure as double)                               as total_exposure,
        cast(total_premium as double)                                as total_premium,
        cast(total_claims as integer)                                as total_claims,
        case when total_claims > 0 then 1 else 0 end                 as has_claim,
        (total_exposure = 0)                                         as is_zero_exposure

    from source

),

deduplicated as (

    -- The real file has no duplicate (insured_id, year) pairs (sql query 09 confirmed 0),
    -- so this should be a no-op there. It keeps policy_year_id unique if a duplicate ever appears
    -- (the synthetic fixture plants one on purpose).
    select *
    from renamed
    qualify row_number() over (
        partition by insured_id, year
        order by total_exposure desc, total_premium desc
    ) = 1

)

select * from deduplicated
