-- Q13. Are segments priced to their risk?
-- Business question (pricing): does each segment's premium cover what it costs?
-- Fixes the first-look caveat in Q03 by measuring risk per year of exposure and
-- by money, not just "had a claim":
--   claim frequency = claims / exposure-years (annualised, so short policies
--                     don't look safer than they are)
--   loss ratio      = incurred claim cost / earned premium (premiums in this file
--                     are earned, pro-rated by exposure; see PROJECT_PLAN.md)
-- A loss ratio well above the portfolio's means the segment is under-priced.
-- Caveat: incurred amounts for recent claims may still develop (reserves change),
-- so treat 2024 loss ratios as early estimates.
-- Technique: CTEs, CROSS JOIN to portfolio totals, ratios, RANK(), NTILE-free banding.
WITH segment AS (
    SELECT
        policy_type,
        bonus_score,
        count(*)                                   AS policies,
        sum(total_exposure)                        AS exposure,
        sum(total_premium)                         AS premium,
        sum(total_claims)                          AS claims,
        sum(total_incurred)                        AS incurred
    FROM policies
    WHERE total_exposure > 0
    GROUP BY policy_type, bonus_score
),
portfolio AS (
    SELECT
        sum(total_claims) / sum(total_exposure)    AS frequency,
        sum(total_incurred) / sum(total_premium)   AS loss_ratio,
        sum(total_premium) / sum(total_exposure)   AS premium_per_exposure
    FROM policies
    WHERE total_exposure > 0
)
SELECT
    s.policy_type,
    s.bonus_score,
    s.policies,
    round(s.exposure, 1)                                         AS exposure_years,
    round(s.premium / s.exposure, 2)                             AS premium_per_exposure,
    round(s.claims / s.exposure, 4)                              AS claims_per_exposure_year,
    round(s.incurred / nullif(s.claims, 0), 2)                   AS cost_per_claim,
    round(s.incurred / s.premium, 3)                             AS loss_ratio,
    round((s.premium / s.exposure) / p.premium_per_exposure, 2)  AS price_index,
    round((s.claims / s.exposure) / p.frequency, 2)              AS frequency_index,
    round((s.incurred / s.premium) / p.loss_ratio, 2)            AS loss_ratio_index,
    RANK() OVER (ORDER BY s.incurred / s.premium DESC)           AS loss_ratio_rank
FROM segment AS s
CROSS JOIN portfolio AS p
WHERE s.exposure >= 0.005 * (SELECT sum(total_exposure) FROM policies)
ORDER BY loss_ratio DESC;
