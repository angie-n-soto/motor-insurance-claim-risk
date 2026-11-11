-- Q12. Does a claim this year predict a claim next year, and does a second
-- claim year raise the risk again?
-- Business question (repeat risk): for 2024 customers who were also insured in
-- BOTH 2022 and 2023, how does the 2024 claim rate change with the number of
-- earlier years that had a claim (0, 1 or 2)?
-- Q05 answers the one-year version for every year; this adds the two-year streak.
-- Technique: two LAG() offsets over each insured's history, a CASE filter for an
-- unbroken 3-year run, relative risk vs the clean-history group via a window.
WITH valid AS (
    SELECT insured_id, year, CASE WHEN total_claims > 0 THEN 1 ELSE 0 END AS has_claim
    FROM policies
    WHERE total_exposure > 0
),
history AS (
    SELECT
        insured_id,
        year,
        has_claim,
        LAG(year, 1)      OVER w AS year_1,
        LAG(year, 2)      OVER w AS year_2,
        LAG(has_claim, 1) OVER w AS claim_1,
        LAG(has_claim, 2) OVER w AS claim_2
    FROM valid
    WINDOW w AS (PARTITION BY insured_id ORDER BY year)
),
streak AS (
    SELECT claim_1 + claim_2 AS prior_claim_years, has_claim
    FROM history
    WHERE year = 2024 AND year_1 = 2023 AND year_2 = 2022
),
grouped AS (
    SELECT prior_claim_years, count(*) AS customers, avg(has_claim) AS claim_rate_2024
    FROM streak
    GROUP BY prior_claim_years
)
SELECT
    prior_claim_years,
    customers,
    round(claim_rate_2024, 4)                                       AS claim_rate_2024,
    round(claim_rate_2024
          / max(CASE WHEN prior_claim_years = 0 THEN claim_rate_2024 END) OVER (), 2)
                                                                    AS relative_risk
FROM grouped
ORDER BY prior_claim_years;
