# SQL practice set (questions only)

Rewrite each query yourself from a blank editor, then compare with `queries/`.
Time yourself: in a live test you'll have roughly 10–15 minutes per question.

**Setup:** `python -m sql.load` (or `--csv tests/fixtures/policies_sample.csv` for the
synthetic file), then open `data/claims.duckdb` in the DuckDB CLI or a notebook.

**Table:** `policies`, one row per insured per year (2022–2024). Columns you need:
`insured_id, year, policy_type, payment_frequency, bonus_score, driver_age,
age_driving_licence, vehicle_brand, fuel_type, total_exposure, total_premium, total_claims`.
A claim means `total_claims > 0`. Leave out rows with `total_exposure = 0` unless told otherwise.
For Q7 there is also `scores(insured_id, year, predicted_probability, has_claim)`.

Keep a note of which ones you needed help on, and redo those the next day.

| # | Done alone? | Needed help? | Redo date |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |

---

### 1. Claim rate and exposure by year
For each year: number of policies, distinct insureds, total exposure, number of policies
with a claim, claim rate, and claims per year of exposure.

<details><summary>Hint</summary>

`avg(CASE WHEN total_claims > 0 THEN 1.0 ELSE 0.0 END)` is a rate. Why `1.0` and not `1`
(think integer division in other databases)?
</details>

### 2. Policy type × payment frequency
Claim rate for every combination of `policy_type` and `payment_frequency`, keeping only
combinations with at least 1% of the portfolio's total exposure. Sort by claim rate.

<details><summary>Hint</summary>

Filtering on an aggregate goes in `HAVING`, not `WHERE`. The 1% threshold needs the
portfolio total: a scalar subquery works.
</details>

### 3. Are segments priced to risk?
For each `policy_type` × `bonus_score` segment: premium per year of exposure and claim rate,
each divided by the portfolio average (a "price index" and a "risk index"), plus a rank on each.
Which segments have a risk index well above their price index?

<details><summary>Hint</summary>

One CTE for segment numbers, one CTE for the portfolio average, `CROSS JOIN` them.
Premium per exposure is `sum(premium) / sum(exposure)`, not `avg(premium / exposure)`: why?
</details>

### 4. Year-over-year change by brand
For the 15 brands with the most policies: claim rate per year, last year's rate, and the change
in percentage points.

<details><summary>Hint</summary>

Rank brands by size first (`DENSE_RANK() OVER (ORDER BY count(*) DESC)`), then
`LAG(claim_rate) OVER (PARTITION BY vehicle_brand ORDER BY year)`. What does `LAG` return
for the first year?
</details>

### 5. Does a claim predict next year's claim?
Label each policy-year `yes` / `no` / `no_history` by whether the same insured claimed in the
**immediately preceding** year. Give the claim rate per label, separately for 2022–23 and 2024.

<details><summary>Hint</summary>

`LAG(year)` and `LAG(has_claim)` over `PARTITION BY insured_id ORDER BY year`. An insured seen in
2022 and 2024 but not 2023 has no history for 2024: compare the lagged year with `year - 1`.
Apply the zero-exposure filter *before* the window function. Does the order matter?
</details>

### 6. Brands ranked within fuel type
Within each fuel type (missing fuel type as its own group), rank brands by claim rate; brands
need at least 0.5% of all policies. Show `RANK()` and `DENSE_RANK()` side by side, top 10 per fuel.

<details><summary>Hint</summary>

`PARTITION BY fuel_type ORDER BY claim_rate DESC`. `coalesce(fuel_type, 'missing')`.
Filtering on a window result needs `QUALIFY` (DuckDB, Snowflake) or a wrapping subquery
(everywhere else). When do `RANK` and `DENSE_RANK` differ?
</details>

### 7. Decile lift table
Using `scores`: split policies into 10 equal groups by predicted probability (10 = riskiest).
Per decile: policies, mean predicted probability, actual claim rate, and lift vs the overall rate.

<details><summary>Hint</summary>

`NTILE(10) OVER (ORDER BY predicted_probability)`, then `GROUP BY` the decile. Add a tie-breaker
to the `ORDER BY` so the result is reproducible.
</details>

### 8. Running totals by driver-age band
Bands 18–24, 25–34, 35–44, 45–54, 55–64, 65+. Per band: exposure, claims, claims per exposure,
running exposure, running claims, and cumulative shares of each.

<details><summary>Hint</summary>

Build the band with `CASE WHEN` *and* a sort key, aggregate, then
`SUM(exposure) OVER (ORDER BY band_order)` for running totals and `SUM(exposure) OVER ()` for the
grand total.
</details>

### 9. Data-quality checks
In one query: total rows, extra rows from duplicate (insured_id, year) pairs, zero exposure,
exposure outside [0, 1], licence age under 16, licence age above driver age, and nulls in the
key columns. One row per check is easiest to read.

<details><summary>Hint</summary>

`sum(CASE WHEN … THEN 1 ELSE 0 END)` per check. For duplicates, a window
`count(*) OVER (PARTITION BY insured_id, year)` or a `GROUP BY … HAVING count(*) > 1`
subquery. Long format: `UNPIVOT` (DuckDB) or `UNION ALL`.
</details>

### 10. Retention
Of the insureds present in 2022, how many and what share appear in 2023, in 2024, and in both?

<details><summary>Hint</summary>

One CTE of distinct ids per year; `LEFT JOIN` 2023 and 2024 onto 2022. A `NULL` on the right
side means "not there". Why `LEFT JOIN` and not `JOIN`?
</details>

---

### Extra (optional)
- **Loss ratio** by segment, if you confirm the claim-cost column in the raw file
  (it's one of the `*_incurred` columns, probably `total_incurred`): `sum(incurred) / sum(premium)`.
- Rewrite Q5 as a **self-join** (`policies` joined to itself on `insured_id` and `year - 1`)
  instead of `LAG`. Do you get the same counts?
- Rewrite Q9's duplicate check with `GROUP BY … HAVING`.
