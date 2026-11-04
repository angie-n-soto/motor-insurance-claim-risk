# dbt star schema (DuckDB)

A [dbt](https://docs.getdbt.com/) project that models the raw motor portfolio into a star schema
in DuckDB: one fact table at the policy-year grain and four dimensions, with data tests.
It reads the semicolon-delimited CSV directly (no separate load step) through
[dbt-duckdb](https://github.com/duckdb/dbt-duckdb).

## Star schema

```mermaid
erDiagram
    fct_policy_year }o--|| dim_driver  : driver_key
    fct_policy_year }o--|| dim_policy  : policy_key
    fct_policy_year }o--|| dim_vehicle : vehicle_key
    fct_policy_year }o--|| dim_year    : year

    fct_policy_year {
        varchar policy_year_id PK "insured_id-year"
        varchar driver_key FK
        varchar policy_key FK
        varchar vehicle_key FK
        int     year FK
        int     driver_age
        varchar driver_age_band
        int     licence_age
        int     years_licensed
        varchar prev_year_claim "yes / no / no_history"
        varchar policy_status "reporting only, not a feature"
        double  total_exposure
        double  total_premium
        int     total_claims
        int     has_claim
        double  premium_per_exposure
    }
    dim_driver {
        varchar driver_key PK "insured_id"
        int     approx_birth_year
        int     latest_licence_age
        int     first_year
        int     last_year
        int     policy_years
        int     years_with_claim
    }
    dim_policy {
        varchar policy_key PK "hash"
        varchar policy_type
        varchar business_type
        varchar payment_frequency
        varchar bonus_score
        varchar municipality_type
        varchar circulation_area
    }
    dim_vehicle {
        varchar vehicle_key PK "hash"
        varchar vehicle_brand
        varchar brand_group "top 15 in train years, else OTHER"
        varchar fuel_type "D / G / missing"
        int     seats
        double  vehicle_value
        varchar value_band
        double  power_to_weight_ratio
    }
    dim_year {
        int     year PK
        varchar model_split "train / test"
        boolean is_test_year
    }
```

| Model | Grain | Notes |
|---|---|---|
| `stg_policies` (view) | insured × year | Typed and renamed (`vehicle_age` → `years_licensed`, `age_driving_licence` → `licence_age`); licence age < 16 → null; missing fuel type → `missing`; exact duplicate (insured, year) rows removed (none expected in the real file; sql query 09 counts them). |
| `fct_policy_year` | insured × year, exposure > 0 | Same population as `src/clean.py`. `prev_year_claim` uses only the immediately preceding year, like the model feature. |
| `dim_driver` | insured | Stable attributes; age and years licensed change yearly, so they stay on the fact. |
| `dim_policy` | policy-terms combination | Small "junk" dimension of policy codes and rating territory, with readable labels. |
| `dim_vehicle` | vehicle profile | The data has no vehicle id, so the key hashes the vehicle attributes. `brand_group` matches the model's top-15 brand grouping. |
| `dim_year` | year | Train (2022–23) / test (2024) split. |

**Tests** (`models/*/schema.yml`, `tests/`): `not_null` and `unique` on every key,
`relationships` from each fact foreign key to its dimension, `accepted_values` on the category
codes, `prev_year_claim`, `has_claim` and the year split, and two singular tests (exposure in
(0, 1], at most 16 brand groups). Accepted values for `policy_status` are a guess, so that test only warns.

## How to run

dbt has its own pinned requirements, so it gets its own virtualenv:

```bash
python -m venv .venv-dbt
.venv-dbt\Scripts\activate          # macOS/Linux: source .venv-dbt/bin/activate
pip install -r requirements-dbt.txt
cd dbt
dbt build                           # SYNTHETIC fixture (default)
```

On the real data (PowerShell; on macOS/Linux use `MOTOR_CSV_PATH=... dbt build`):

```powershell
$env:MOTOR_CSV_PATH = "../data/raw/motor_portfolio.csv"
dbt build
```

| Environment variable | Default | Used in |
|---|---|---|
| `MOTOR_CSV_PATH` | `../tests/fixtures/policies_sample.csv` (SYNTHETIC) | `models/staging/sources.yml` |
| `DBT_DUCKDB_PATH` | `target/motor_dbt.duckdb` | `profiles.yml` |

Paths are relative to the `dbt/` folder. `profiles.yml` lives in this folder, so dbt finds it when
run from here. Both the database and `target/` are git-ignored.

`dbt docs generate && dbt docs serve` opens a browsable lineage graph of the models.

CI runs `dbt build` on the synthetic fixture on every push (see `.github/workflows/ci.yml`).
