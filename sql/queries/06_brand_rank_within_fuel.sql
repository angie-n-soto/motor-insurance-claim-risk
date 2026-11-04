-- Q6. Within each fuel type, which brands have the highest claim rate?
-- Technique: RANK() and DENSE_RANK() with PARTITION BY.
-- Brands need at least 0.5% of all policies to be ranked (relative threshold,
-- so the query also runs on the small synthetic fixture).
WITH brand_fuel AS (
    SELECT
        coalesce(fuel_type, 'missing')                           AS fuel_type,
        vehicle_brand,
        count(*)                                                 AS policies,
        avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END)    AS claim_rate
    FROM policies
    WHERE total_exposure > 0
    GROUP BY 1, 2
    HAVING count(*) >= 0.005 * (SELECT count(*) FROM policies)
)
SELECT
    fuel_type,
    vehicle_brand,
    policies,
    round(claim_rate, 4)                                                    AS claim_rate,
    RANK()       OVER (PARTITION BY fuel_type ORDER BY claim_rate DESC)     AS rank_in_fuel,
    DENSE_RANK() OVER (PARTITION BY fuel_type ORDER BY claim_rate DESC)     AS dense_rank_in_fuel
FROM brand_fuel
QUALIFY rank_in_fuel <= 10
ORDER BY fuel_type, rank_in_fuel, vehicle_brand;
