-- Q2. How does the claim rate vary by policy type x payment frequency?
-- Technique: GROUP BY two columns + HAVING (minimum-exposure filter).
-- Cells with less than 1% of total exposure are dropped: their rates are noise.
-- The threshold is relative so the same query works on the full data and on
-- the small synthetic test fixture.
SELECT
    policy_type,
    payment_frequency,
    count(*)                                                    AS policies,
    round(sum(total_exposure), 1)                               AS exposure_years,
    round(avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END), 4) AS claim_rate
FROM policies
WHERE total_exposure > 0
GROUP BY policy_type, payment_frequency
HAVING sum(total_exposure) >= 0.01 * (SELECT sum(total_exposure) FROM policies)
ORDER BY claim_rate DESC;
