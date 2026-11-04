-- Q1. What are the claim rate and exposure in each year?
-- Technique: GROUP BY with basic aggregates.
-- Zero-exposure rows are excluded, as in src/clean.py (they could not claim).
SELECT
    year,
    count(*)                                                   AS policies,
    count(DISTINCT insured_id)                                 AS insureds,
    round(sum(total_exposure), 1)                              AS exposure_years,
    sum(CASE WHEN total_claims > 0 THEN 1 ELSE 0 END)::BIGINT          AS policies_with_claim,
    round(avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END), 4) AS claim_rate,
    -- claims per year of cover: the actuarial "frequency"
    round(sum(total_claims) / sum(total_exposure), 4)          AS claims_per_exposure_year
FROM policies
WHERE total_exposure > 0
GROUP BY year
ORDER BY year;
