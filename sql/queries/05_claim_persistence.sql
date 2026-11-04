-- Q5. Does a claim in year N predict a claim in year N+1?
-- Technique: LAG() over each insured's history (PARTITION BY insured_id ORDER BY year).
-- Mirrors the prev_year_claim feature in src/clean.py: only the IMMEDIATELY
-- preceding year counts. If the previous row is two years back (a gap), the
-- insured has no history for this purpose. Results are split train/test the
-- same way as reports/RESULTS.md (train = 2022-2023, test = 2024).
WITH valid AS (
    -- the lag is computed after the zero-exposure filter, exactly like clean.py
    SELECT insured_id, year, CASE WHEN total_claims > 0 THEN 1 ELSE 0 END AS has_claim
    FROM policies
    WHERE total_exposure > 0
),
history AS (
    SELECT
        insured_id,
        year,
        has_claim,
        LAG(year)      OVER (PARTITION BY insured_id ORDER BY year) AS prev_year,
        LAG(has_claim) OVER (PARTITION BY insured_id ORDER BY year) AS prev_has_claim
    FROM valid
),
labelled AS (
    SELECT
        CASE WHEN year < 2024 THEN 'train' ELSE 'test' END AS split,
        CASE
            WHEN prev_year IS DISTINCT FROM year - 1 THEN 'no_history'
            WHEN prev_has_claim = 1 THEN 'yes'
            ELSE 'no'
        END AS prev_year_claim,
        has_claim
    FROM history
)
SELECT
    split,
    prev_year_claim,
    count(*)                  AS policies,
    round(avg(has_claim), 4)  AS claim_rate
FROM labelled
GROUP BY split, prev_year_claim
ORDER BY split DESC, prev_year_claim;
