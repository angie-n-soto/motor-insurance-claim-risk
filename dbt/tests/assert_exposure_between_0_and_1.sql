-- Exposure is a fraction of a year. Rows outside (0, 1] in the fact table
-- would break every per-exposure rate. Warn only: the EDA counted rows with
-- exposure > 1 but the real count isn't recorded in this repo.
{{ config(severity='warn') }}

select policy_year_id, total_exposure
from {{ ref('fct_policy_year') }}
where total_exposure <= 0 or total_exposure > 1
