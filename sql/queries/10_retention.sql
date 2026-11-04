-- Q10. Retention: of the insureds present in 2022, what share are still
-- insured in 2023, in 2024, and in both?
-- Technique: one CTE per year + LEFT JOIN (a NULL on the right = not renewed).
WITH y2022 AS (SELECT DISTINCT insured_id FROM policies WHERE year = 2022),
     y2023 AS (SELECT DISTINCT insured_id FROM policies WHERE year = 2023),
     y2024 AS (SELECT DISTINCT insured_id FROM policies WHERE year = 2024),
cohort AS (
    SELECT
        c.insured_id,
        a.insured_id IS NOT NULL AS in_2023,
        b.insured_id IS NOT NULL AS in_2024
    FROM y2022 AS c
    LEFT JOIN y2023 AS a ON a.insured_id = c.insured_id
    LEFT JOIN y2024 AS b ON b.insured_id = c.insured_id
)
SELECT
    count(*)                                                              AS cohort_2022,
    sum(CASE WHEN in_2023 THEN 1 ELSE 0 END)::BIGINT                              AS renewed_2023,
    sum(CASE WHEN in_2024 THEN 1 ELSE 0 END)::BIGINT                              AS present_2024,
    sum(CASE WHEN in_2023 AND in_2024 THEN 1 ELSE 0 END)::BIGINT                  AS renewed_both,
    round(avg(CASE WHEN in_2023 THEN 1.0 ELSE 0.0 END), 4)                AS retention_2023,
    round(avg(CASE WHEN in_2024 THEN 1.0 ELSE 0.0 END), 4)                AS share_present_2024,
    round(avg(CASE WHEN in_2023 AND in_2024 THEN 1.0 ELSE 0.0 END), 4)    AS retention_both_years
FROM cohort;
