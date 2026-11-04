-- Q7. Decile lift: claim rate per decile of the model's predicted probability.
-- Technique: NTILE(10) window, then GROUP BY decile; lift vs the average.
-- Needs the `scores` table (python -m sql.export_scores): 2024 test-year
-- predictions from models/claim_model.joblib. Decile 10 = riskiest.
WITH ranked AS (
    SELECT
        predicted_probability,
        has_claim,
        -- tie-break on the ids so the deciles are reproducible
        NTILE(10) OVER (ORDER BY predicted_probability, insured_id, year) AS decile
    FROM scores
),
overall AS (
    SELECT avg(has_claim) AS claim_rate FROM scores
)
SELECT
    r.decile,
    count(*)                                         AS policies,
    round(avg(r.predicted_probability), 4)           AS mean_predicted,
    round(avg(r.has_claim), 4)                       AS claim_rate,
    round(avg(r.has_claim) / o.claim_rate, 2)        AS lift
FROM ranked AS r
CROSS JOIN overall AS o
GROUP BY r.decile, o.claim_rate
ORDER BY r.decile;
