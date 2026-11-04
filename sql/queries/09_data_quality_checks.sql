-- Q9. Data-quality checks on the raw table.
-- Technique: CASE WHEN counts in one pass, duplicate detection with a window
-- count, then UNPIVOT into one row per check.
-- On the real file the EDA found 49 zero-exposure rows (the only rows
-- src/clean.py drops) and 57 licence ages under 16. Duplicate (insured_id, year) rows are
-- expected to be 0 (the EDA notebook checks it, but its output is not committed).
WITH flagged AS (
    SELECT
        *,
        count(*) OVER (PARTITION BY insured_id, year) AS rows_for_insured_year
    FROM policies
),
checks AS (
    SELECT
        count(*)                                                               AS total_rows,
        sum(CASE WHEN rows_for_insured_year > 1 THEN 1 ELSE 0 END)::BIGINT
            - count(DISTINCT CASE WHEN rows_for_insured_year > 1
                                  THEN insured_id::VARCHAR || '-' || year::VARCHAR END)
                                                                               AS duplicate_insured_year_rows,
        sum(CASE WHEN total_exposure = 0 THEN 1 ELSE 0 END)::BIGINT                    AS zero_exposure,
        sum(CASE WHEN total_exposure < 0 OR total_exposure > 1 THEN 1 ELSE 0 END)::BIGINT AS exposure_out_of_range,
        sum(CASE WHEN age_driving_licence < 16 THEN 1 ELSE 0 END)::BIGINT              AS licence_age_under_16,
        sum(CASE WHEN age_driving_licence > driver_age THEN 1 ELSE 0 END)::BIGINT      AS licence_age_above_driver_age,
        sum(CASE WHEN total_claims > 0 AND total_exposure = 0 THEN 1 ELSE 0 END)::BIGINT AS claims_without_exposure,
        sum(CASE WHEN total_premium < 0 THEN 1 ELSE 0 END)::BIGINT                     AS negative_premium,
        sum(CASE WHEN insured_id IS NULL THEN 1 ELSE 0 END)::BIGINT                    AS null_insured_id,
        sum(CASE WHEN year IS NULL THEN 1 ELSE 0 END)::BIGINT                          AS null_year,
        sum(CASE WHEN driver_age IS NULL THEN 1 ELSE 0 END)::BIGINT                    AS null_driver_age,
        sum(CASE WHEN age_driving_licence IS NULL THEN 1 ELSE 0 END)::BIGINT           AS null_age_driving_licence,
        sum(CASE WHEN vehicle_age IS NULL THEN 1 ELSE 0 END)::BIGINT                   AS null_vehicle_age,
        sum(CASE WHEN fuel_type IS NULL THEN 1 ELSE 0 END)::BIGINT                     AS null_fuel_type,
        sum(CASE WHEN vehicle_value IS NULL THEN 1 ELSE 0 END)::BIGINT                 AS null_vehicle_value,
        sum(CASE WHEN total_exposure IS NULL THEN 1 ELSE 0 END)::BIGINT                AS null_total_exposure,
        sum(CASE WHEN total_claims IS NULL THEN 1 ELSE 0 END)::BIGINT                  AS null_total_claims
    FROM flagged
)
SELECT check_name, n_rows
FROM (UNPIVOT checks ON COLUMNS(*) INTO NAME check_name VALUE n_rows);
