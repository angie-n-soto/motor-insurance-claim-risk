-- Q8. Running totals of exposure and claims by driver-age band.
-- Technique: CASE WHEN bands + SUM() OVER (ORDER BY ...) running totals.
-- Shows how much of the portfolio's exposure and claims sit in younger bands.
WITH banded AS (
    SELECT
        CASE
            WHEN driver_age IS NULL THEN NULL
            WHEN driver_age < 25 THEN 1
            WHEN driver_age < 35 THEN 2
            WHEN driver_age < 45 THEN 3
            WHEN driver_age < 55 THEN 4
            WHEN driver_age < 65 THEN 5
            ELSE 6
        END AS band_order,
        total_exposure,
        total_claims
    FROM policies
    WHERE total_exposure > 0
),
by_band AS (
    SELECT
        band_order,
        CASE band_order
            WHEN 1 THEN '18-24' WHEN 2 THEN '25-34' WHEN 3 THEN '35-44'
            WHEN 4 THEN '45-54' WHEN 5 THEN '55-64' WHEN 6 THEN '65+'
        END                                       AS age_band,
        count(*)                                  AS policies,
        sum(total_exposure)                       AS exposure,
        sum(total_claims)::BIGINT                 AS claims
    FROM banded
    WHERE band_order IS NOT NULL
    GROUP BY band_order
)
SELECT
    age_band,
    policies,
    round(exposure, 1)                                                     AS exposure_years,
    claims,
    round(claims / exposure, 4)                                            AS claims_per_exposure_year,
    round(SUM(exposure) OVER (ORDER BY band_order), 1)                     AS running_exposure,
    SUM(claims) OVER (ORDER BY band_order)::BIGINT                         AS running_claims,
    round(SUM(exposure) OVER (ORDER BY band_order) / SUM(exposure) OVER (), 4) AS cumulative_exposure_share,
    round(SUM(claims) OVER (ORDER BY band_order) / SUM(claims) OVER (), 4)     AS cumulative_claims_share
FROM by_band
ORDER BY band_order;
