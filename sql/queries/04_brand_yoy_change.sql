-- Q4. Year-over-year change in claim rate for the 15 biggest vehicle brands.
-- Technique: CTEs + LAG() OVER (PARTITION BY ... ORDER BY ...), DENSE_RANK().
WITH brand_size AS (
    SELECT
        vehicle_brand,
        DENSE_RANK() OVER (ORDER BY count(*) DESC, vehicle_brand) AS size_rank
    FROM policies
    WHERE total_exposure > 0
    GROUP BY vehicle_brand
),
brand_year AS (
    SELECT
        p.vehicle_brand,
        p.year,
        count(*)                                                AS policies,
        avg(CASE WHEN p.total_claims > 0 THEN 1.0 ELSE 0.0 END) AS claim_rate
    FROM policies AS p
    JOIN brand_size AS b USING (vehicle_brand)
    WHERE p.total_exposure > 0
      AND b.size_rank <= 15
    GROUP BY p.vehicle_brand, p.year
)
SELECT
    vehicle_brand,
    year,
    policies,
    round(claim_rate, 4)                                                     AS claim_rate,
    round(LAG(claim_rate) OVER (PARTITION BY vehicle_brand ORDER BY year), 4) AS prev_year_claim_rate,
    round(claim_rate - LAG(claim_rate) OVER (PARTITION BY vehicle_brand ORDER BY year), 4)
                                                                             AS change_pts
FROM brand_year
ORDER BY vehicle_brand, year;
