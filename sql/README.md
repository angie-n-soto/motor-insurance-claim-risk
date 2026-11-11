# SQL analyses (DuckDB)

Business questions about a motor insurance portfolio (354,140 policy-years, 2022–2024),
answered in SQL on [DuckDB](https://duckdb.org/) (an in-process database that reads the CSV
directly; no server). Every number below comes from running these queries on the real file;
the result tables are in [`results/`](results/). The raw file is not committed, so nothing in
this folder contains row-level data.

## Findings

Four questions a retention, risk or pricing team would ask, each answered by one or more queries.

### 1. Which customers renew, and which ones leave? ([Q11](queries/11_who_renews.sql), [Q10](queries/10_retention.sql))

Across the 186,007 customer-years in 2022 and 2023, **9.4% did not renew** the next year.
Leaving is concentrated in a few segments:

| Segment | Leave rate | vs average |
|---|---|---|
| Pays quarterly (payment frequency `Q`) | 25.1% | 2.7× |
| Bonus score `B` | 23.0% | 2.4× |
| Policy type `TPG` | 14.5% | 1.5× |
| Driver aged 25–34 | 13.7% | 1.5× |
| Had a claim this year | 11.3% | 1.2× |
| Pays annually (`A`) | 7.8% | 0.8× |
| Driver aged 65+ | 6.7% | 0.7× |
| Comprehensive, no excess (`COMP_N`) | 5.0% | 0.5× |

Quarterly payers leave at about three times the rate of annual payers, which makes payment
frequency the simplest early flag for a retention campaign. Of the 2022 cohort, 75.2% were still
insured in 2024. (In this file a customer with no row the next year always has
`policy_status = 'C'`, so "left" and "cancelled" agree for 2022–2023.) These are descriptive
rates: segments overlap (for example, young drivers may pay quarterly more often), so they show
where to look, not what causes leaving.

### 2. Does a claim this year predict a claim next year? ([Q05](queries/05_claim_persistence.sql), [Q12](queries/12_repeat_claims.sql))

**Yes.** In 2024, customers who claimed in 2023 claimed again **25.5%** of the time, against
**17.3%** for customers with a claim-free 2023 and 9.5% for new customers. The risk keeps
stacking: among the 50,488 customers insured in all three years, the 2024 claim rate was

| Claim years in 2022–2023 | Customers | 2024 claim rate | Relative risk |
|---|---|---|---|
| 0 | 36,410 | 16.2% | 1.0× |
| 1 | 12,496 | 24.5% | 1.5× |
| 2 | 1,582 | 33.6% | 2.1× |

Two claim years in a row roughly double next year's risk, which is why claim history is a
model feature ([`src/clean.py`](../src/clean.py)) and a natural trigger for loss-prevention outreach.

### 3. Are segments priced to their risk? ([Q13](queries/13_pricing_vs_loss.sql), [Q03](queries/03_price_vs_risk_by_segment.sql))

The portfolio paid out **70.3%** of earned premium in claims (loss ratio; 65.6% in 2022 → 74.7% in 2024).
By policy type × bonus score:

| Segment | Premium per exposure-year | Claims per exposure-year | Loss ratio | vs portfolio |
|---|---|---|---|---|
| Comprehensive, no excess (`COMP_N`), bonus `G` | €790 | 1.02 | **95.3%** | 1.36× |
| `CC`, bonus `N` | €560 | 0.34 | 86.4% | 1.23× |
| Comprehensive with excess (`COMP_E`), bonus `G` | €541 | 0.40 | 73.4% | 1.04× |
| `TPG`, bonus `G` | €317 | 0.20 | 67.2% | 0.96× |
| `CC`, bonus `G` | €337 | 0.22 | 62.7% | 0.89× |
| `CC`, bonus `B` | €740 | 0.41 | 60.9% | 0.87× |
| `TP`, bonus `G` | €257 | 0.13 | 56.6% | 0.81× |

`COMP_N` charges 1.9× the average premium but claims 3.3× as often per year of cover, so nearly
all of its premium goes back out as claims: it is the clearest under-priced segment. `TP` has
the lowest loss ratio. (The dataset documents `COMP_N`/`COMP_E`; the other policy-type and
bonus-score codes are left as they appear in the file.)

Q13 measures risk per exposure-year and in money, which fixes the first-look caveat in Q03 (a plain "had a claim" rate makes segments with many short policies look
safer than they are). Incurred amounts on recent claims can still change, so 2024 loss ratios are
early estimates.

### 4. How clean is the data? ([Q09](queries/09_data_quality_checks.sql))

Clean enough to use, with a short list of issues for the cleaning step ([`src/clean.py`](../src/clean.py)):

- 354,140 rows and **0 duplicate** (insured, year) pairs.
- 49 rows with zero exposure (1 of them still records a claim): dropped from rates.
- 57 licence ages under 16 (impossible): set to missing, rows kept.
- Missing values: `fuel_type` 1,287 (0.4%; kept as its own "missing" group, because those rows
  claim more often), `vehicle_value` 513, licence age 2, `vehicle_age` 2.
- One mislabelled column: `vehicle_age` actually holds years licensed (found in the EDA; see
  [PROJECT_PLAN.md](../PROJECT_PLAN.md)).

The SQL checks reproduce the Python pipeline's numbers exactly (claim rate 13.0% → 14.0% → 15.1%
by year; claim persistence 24.5% / 17.4% / 11.2% in training years), so the SQL and Python agree.

### Also in this folder

The model's 2024 scores, ranked into deciles in SQL ([Q07](queries/07_decile_lift.sql)): the
riskiest 10% claimed 33.9% of the time vs 2.4% for the safest 10%.

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
The loss ratio in Q13 uses `total_incurred` (claim cost) over `total_premium` (earned premium).

## All queries

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
| 11 | [11_who_renews.sql](queries/11_who_renews.sql) | Which customer segments renew, and which leave? | `LEAD()` per insured, `GROUPING SETS`, leave index via a window over the result |
| 12 | [12_repeat_claims.sql](queries/12_repeat_claims.sql) | Do two claim years in a row raise next year's risk again? | `LAG(…, 1)` and `LAG(…, 2)` with a named `WINDOW`, relative risk |
| 13 | [13_pricing_vs_loss.sql](queries/13_pricing_vs_loss.sql) | Does each segment's premium cover its claims? | CTEs, `CROSS JOIN` to portfolio totals, loss ratio and frequency indices, `RANK()` |

## Cross-checks against the Python pipeline

Some numbers are already known from the Python pipeline on the real data
([reports/RESULTS.md](../reports/RESULTS.md), [PROJECT_PLAN.md](../PROJECT_PLAN.md)).
After `run_all.py` on the real file, check:

- **Q1:** claim rate 13.0% (2022) → 14.0% (2023) → 15.1% (2024).
- **Q5:** train yes 24.5% / no 17.4% / no_history 11.2%; test yes 25.5% / no 17.3% / no_history 9.5%.
- **Q7:** decile 10 ≈ 33.9% and decile 1 ≈ 2.4% (small differences are possible: `NTILE` breaks
  ties by id, `pandas.qcut` by row order).
- **Q9:** 49 zero-exposure rows, 57 licence ages under 16, 0 duplicate (insured_id, year) rows (confirmed on the real file, 11/5);
  missing `fuel_type` 1,287 and `vehicle_value` 513.

If a number doesn't match, that's a bug in the SQL (or in the earlier Python): worth finding before
quoting either.

## Answers

See [Findings](#findings) at the top. Each result table is in [`results/`](results/), named after its query.
