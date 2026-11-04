-- Q3. Are segments priced to risk? Premium per year of exposure vs claim rate.
-- Technique: CTEs, ratios to the portfolio average, RANK() on each side.
-- A segment whose risk_index is well above its price_index is under-priced
-- for claim occurrence (premiums price claim COST too, so this is a first look).
WITH segment AS (
    SELECT
        policy_type,
        bonus_score,
        count(*)                                                  AS policies,
        sum(total_exposure)                                       AS exposure,
        sum(total_premium) / sum(total_exposure)                  AS premium_per_exposure,
        avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END)     AS claim_rate
    FROM policies
    WHERE total_exposure > 0
    GROUP BY policy_type, bonus_score
),
portfolio AS (
    SELECT
        sum(total_premium) / sum(total_exposure)                  AS premium_per_exposure,
        avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END)     AS claim_rate
    FROM policies
    WHERE total_exposure > 0
)
SELECT
    s.policy_type,
    s.bonus_score,
    s.policies,
    round(s.exposure, 1)                                          AS exposure_years,
    round(s.premium_per_exposure, 2)                              AS premium_per_exposure,
    round(s.claim_rate, 4)                                        AS claim_rate,
    round(s.premium_per_exposure / p.premium_per_exposure, 2)     AS price_index,
    round(s.claim_rate / p.claim_rate, 2)                         AS risk_index,
    RANK() OVER (ORDER BY s.premium_per_exposure DESC)            AS price_rank,
    RANK() OVER (ORDER BY s.claim_rate DESC)                      AS risk_rank
FROM segment AS s
CROSS JOIN portfolio AS p
WHERE s.exposure >= 0.005 * (SELECT sum(total_exposure) FROM policies)
ORDER BY risk_index DESC;
