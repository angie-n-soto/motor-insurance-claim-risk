-- One row per combination of policy terms and rating territory
-- (a "junk" dimension: small, low-cardinality attributes kept together).

select distinct
    {{ policy_key() }}                       as policy_key,
    policy_type,
    case policy_type
        when 'TP'     then 'third-party only'
        when 'TPG'    then 'third-party + glass'
        when 'CC'     then 'third-party + extras'
        when 'COMP_E' then 'comprehensive with excess'
        when 'COMP_N' then 'comprehensive, no excess'
    end                                      as policy_type_label,
    business_type,
    case business_type when 'NB' then 'new business' when 'P' then 'existing portfolio' end
                                             as business_type_label,
    payment_frequency,
    case payment_frequency when 'A' then 'annual' when 'S' then 'semiannual' when 'Q' then 'quarterly' end
                                             as payment_frequency_label,
    bonus_score,
    municipality_type,
    case municipality_type when 'I' then 'inland' when 'C' then 'coastal' when 'IS' then 'islands' end
                                             as municipality_type_label,
    circulation_area,
    case circulation_area when 'U' then 'urban' when 'R' then 'rural' end
                                             as circulation_area_label
from {{ ref('stg_policies') }}
