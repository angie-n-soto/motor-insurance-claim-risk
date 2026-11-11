-- Q11. Which customers renew, and which ones leave?
-- Business question (retention): of the customers insured in 2022 or 2023,
-- who comes back the next year, and which segments leave most often?
-- "Left" = the insured has no policy row the following year. On the real file
-- this matches policy_status = 'C' (cancelled) exactly for 2022-2023.
-- 2024 is excluded because its "next year" is not in the data.
-- Technique: LEAD() per insured, CASE WHEN bands, GROUPING SETS for several
-- segment cuts in one pass, comparison to the overall rate with a window over the
-- whole result.
WITH history AS (
    SELECT
        insured_id,
        year,
        payment_frequency,
        policy_type,
        bonus_score,
        business_type,
        CASE
            WHEN driver_age < 25 THEN '18-24'
            WHEN driver_age < 35 THEN '25-34'
            WHEN driver_age < 45 THEN '35-44'
            WHEN driver_age < 55 THEN '45-54'
            WHEN driver_age < 65 THEN '55-64'
            ELSE '65+'
        END                                                        AS age_band,
        CASE WHEN total_claims > 0 THEN 'claim' ELSE 'no claim' END AS claim_this_year,
        LEAD(year) OVER (PARTITION BY insured_id ORDER BY year)    AS next_year
    FROM policies
),
cohort AS (
    SELECT *, CASE WHEN next_year = year + 1 THEN 1 ELSE 0 END AS renewed
    FROM history
    WHERE year < 2024
),
cuts AS (
    SELECT
        CASE
            WHEN GROUPING(payment_frequency) = 0 THEN 'payment_frequency'
            WHEN GROUPING(policy_type) = 0       THEN 'policy_type'
            WHEN GROUPING(bonus_score) = 0       THEN 'bonus_score'
            WHEN GROUPING(business_type) = 0     THEN 'business_type'
            WHEN GROUPING(age_band) = 0          THEN 'driver_age_band'
            WHEN GROUPING(claim_this_year) = 0   THEN 'claim_this_year'
            ELSE 'all'
        END                                                        AS segment_type,
        coalesce(payment_frequency, policy_type, bonus_score, business_type,
                 age_band, claim_this_year, 'all')                 AS segment,
        count(*)                                                   AS customers,
        avg(renewed)                                               AS renewal_rate
    FROM cohort
    GROUP BY GROUPING SETS (
        (), (payment_frequency), (policy_type), (bonus_score),
        (business_type), (age_band), (claim_this_year)
    )
)
SELECT
    segment_type,
    segment,
    customers,
    round(renewal_rate, 4)                                         AS renewal_rate,
    round(1 - renewal_rate, 4)                                     AS leave_rate,
    round((1 - renewal_rate)
          / max(CASE WHEN segment_type = 'all' THEN 1 - renewal_rate END) OVER (), 2)
                                                                   AS leave_index
FROM cuts
-- keep segments with at least 0.5% of the cohort, so tiny groups don't top the list
WHERE customers >= 0.005 * (SELECT count(*) FROM cohort)
ORDER BY segment_type = 'all' DESC, segment_type, leave_rate DESC;
