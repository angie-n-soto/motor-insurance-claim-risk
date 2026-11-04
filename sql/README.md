# SQL analyses (DuckDB)

Ten business questions about the motor portfolio, answered in SQL on
[DuckDB](https://duckdb.org/) (an in-process database that reads the CSV directly; no server).

Answers live in [`results/`](results/) as CSVs once the queries have been run on the
real data (see [results/README.md](results/README.md)). The raw file is not committed,
so nothing in this folder contains row-level data.

## How to run

From the repo root, with the virtualenv active (`pip install -r requirements.txt`):

```bash
python -m sql.load            # data/raw/motor_portfolio.csv -> data/claims.duckdb, table `policies`
python -m sql.export_scores   # scores the 2024 test year with models/claim_model.joblib -> table `scores`
python -m sql.run_all         # runs queries/*.sql in order -> results/*.csv
```

- `load.py --csv PATH` loads a different file (for example the synthetic fixture,
  `tests/fixtures/policies_sample.csv`). It checks that every column the queries use is present.
- `run_all.py` sends results from the synthetic fixture to the git-ignored
  `data/processed/sql_results_synthetic/`, never to `results/`.
- To open the database yourself: `duckdb data/claims.duckdb` (DuckDB CLI) or
  `python -c "import duckdb; print(duckdb.connect('data/claims.duckdb').sql('FROM policies LIMIT 5'))"`.
- CI runs every query against the synthetic fixture (`tests/test_sql.py`): that checks the SQL
  works, not what the real numbers are.

**Column notes.** `policies` is the raw file unchanged, so it uses the raw names:
`vehicle_age` actually holds *years licensed* and `age_driving_licence` holds the *age* when
licensed (findings 1–2 in [PROJECT_PLAN.md](../PROJECT_PLAN.md)). Most queries exclude
zero-exposure rows, as `src/clean.py` does. A "claim" means `total_claims > 0`.
There is no loss-ratio query: the code in this repo never reads a claim-cost column by name,
so its exact name is unconfirmed (see [PRACTICE.md](PRACTICE.md) for an optional extra).

## The questions

| # | File | Business question | Technique |
|---|---|---|---|
| 1 | [01_claim_rate_by_year.sql](queries/01_claim_rate_by_year.sql) | What are the claim rate and exposure in each year? | `GROUP BY`, aggregates, `CASE WHEN` |
| 2 | [02_policy_type_by_payment_frequency.sql](queries/02_policy_type_by_payment_frequency.sql) | How does claim rate vary by policy type × payment frequency? | Two-column `GROUP BY`, `HAVING` minimum exposure (subquery) |
| 3 | [03_price_vs_risk_by_segment.sql](queries/03_price_vs_risk_by_segment.sql) | Are segments (policy type × bonus score) priced to risk? | CTEs, `CROSS JOIN` to portfolio averages, `RANK()` |
| 4 | [04_brand_yoy_change.sql](queries/04_brand_yoy_change.sql) | How did each big brand's claim rate change year over year? | CTEs, `DENSE_RANK()`, `LAG() OVER (PARTITION BY … ORDER BY …)` |
| 5 | [05_claim_persistence.sql](queries/05_claim_persistence.sql) | Does a claim in year N predict a claim in N+1? | `LAG()` per insured, gap handling with `IS DISTINCT FROM` |
| 6 | [06_brand_rank_within_fuel.sql](queries/06_brand_rank_within_fuel.sql) | Within each fuel type, which brands claim most? | `RANK()` vs `DENSE_RANK()` with `PARTITION BY`, `QUALIFY` |
| 7 | [07_decile_lift.sql](queries/07_decile_lift.sql) | Does the model's ranking separate risky from safe policies? | `NTILE(10)`, lift vs average |
| 8 | [08_running_totals_by_age_band.sql](queries/08_running_totals_by_age_band.sql) | How do exposure and claims accumulate across driver-age bands? | `CASE WHEN` bands, running `SUM() OVER (ORDER BY …)`, `SUM() OVER ()` |
| 9 | [09_data_quality_checks.sql](queries/09_data_quality_checks.sql) | Is the raw data clean? Duplicates, impossible values, nulls | `CASE WHEN` counts, window `count(*)` for duplicates, `UNPIVOT` |
| 10 | [10_retention.sql](queries/10_retention.sql) | What share of 2022 insureds renew in 2023 and 2024? | Year CTEs + `LEFT JOIN` (NULL = not renewed) |

## What the real run should reproduce

Some numbers are already known from the Python pipeline on the real data
([reports/RESULTS.md](../reports/RESULTS.md), [PROJECT_PLAN.md](../PROJECT_PLAN.md)).
After `run_all.py` on the real file, check:

- **Q1:** claim rate 13.0% (2022) → 14.0% (2023) → 15.1% (2024).
- **Q5:** train yes 24.5% / no 17.4% / no_history 11.2%; test yes 25.5% / no 17.3% / no_history 9.5%.
- **Q7:** decile 10 ≈ 33.9% and decile 1 ≈ 2.4% (small differences are possible: `NTILE` breaks
  ties by id, `pandas.qcut` by row order).
- **Q9:** 49 zero-exposure rows, 57 licence ages under 16, and (expected) 0 duplicate (insured_id, year) rows: the EDA notebook
  checks this, but its output isn't committed, so treat this one as unconfirmed until you run it;
  missing `fuel_type` 1,287 and `vehicle_value` 513.

If a number doesn't match, that's a bug in the SQL (or in the earlier Python): worth finding before
quoting either.

## Answers

_To fill in after running on the real data:_ for each question, paste the small table from
`results/NN_*.csv` and add one sentence on what it means for an underwriter.
