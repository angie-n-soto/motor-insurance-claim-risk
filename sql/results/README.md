# sql/results/

This folder holds one CSV per query in [`../queries/`](../queries/), written by
`python -m sql.run_all` **on the real data** (`data/raw/motor_portfolio.csv`).

It is empty on purpose until that run happens: the raw Mendeley file is not in
the repo, and numbers computed on the synthetic test fixture are not results.
`run_all.py` refuses to write synthetic output here; when the database was
loaded from `tests/fixtures/policies_sample.csv`, it writes to the git-ignored
`data/processed/sql_results_synthetic/` instead.

To fill it:

```bash
python -m sql.load            # data/raw/motor_portfolio.csv -> data/claims.duckdb
python -m sql.export_scores   # 2024 predictions -> scores table (query 07)
python -m sql.run_all         # writes sql/results/01_...csv to 10_...csv
```

The CSVs are small aggregates (no row-level data), so they are safe to commit.
