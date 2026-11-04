-- One row per policy year, with the train/test split used by the model.

select distinct
    year,
    case when year >= {{ var('test_year') }} then 'test' else 'train' end as model_split,
    (year >= {{ var('test_year') }})                                      as is_test_year
from {{ ref('stg_policies') }}
