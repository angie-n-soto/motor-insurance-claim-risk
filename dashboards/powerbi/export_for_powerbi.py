"""Export the dbt star schema (and the model's 2024 scores) as CSVs for Power BI.

Run from the repo root, after `dbt build` (and, for the decile page,
python -m sql.load + python -m sql.export_scores):

    python dashboards/powerbi/export_for_powerbi.py

Reads:
  dbt/target/motor_dbt.duckdb   fct_policy_year, dim_driver, dim_policy, dim_vehicle, dim_year
  data/claims.duckdb            scores (optional; skipped with a message if missing)

Writes one CSV per table to dashboards/powerbi/data/ (git-ignored: it is
row-level data). If the dbt build read the SYNTHETIC fixture, it writes to
dashboards/powerbi/data_synthetic/ instead and says so in SOURCE.txt.
"""

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DBT_DB = ROOT / "dbt" / "target" / "motor_dbt.duckdb"
DEFAULT_SCORES_DB = ROOT / "data" / "claims.duckdb"
OUT_REAL = ROOT / "dashboards" / "powerbi" / "data"
OUT_SYNTHETIC = ROOT / "dashboards" / "powerbi" / "data_synthetic"

STAR_TABLES = ["fct_policy_year", "dim_driver", "dim_policy", "dim_vehicle", "dim_year"]

# Deciles are computed here (same NTILE rule as sql/queries/07_decile_lift.sql)
# so Power BI only has to aggregate. policy_year_id matches fct_policy_year.
SCORES_SQL = """
SELECT
    CAST(insured_id AS VARCHAR) || '-' || CAST(year AS VARCHAR) AS policy_year_id,
    year,
    predicted_probability,
    has_claim,
    NTILE(10) OVER (ORDER BY predicted_probability, insured_id, year) AS decile
FROM scores_db.scores
"""


def _copy(con: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    con.execute(f"COPY ({query}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
    return con.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]


def export(
    dbt_db: Path = DEFAULT_DBT_DB,
    scores_db: Path | None = DEFAULT_SCORES_DB,
    out_dir: Path | None = None,
) -> dict[str, int]:
    if not Path(dbt_db).exists():
        raise SystemExit(f"{dbt_db} not found: run `dbt build` in dbt/ first.")
    con = duckdb.connect(str(dbt_db), read_only=True)
    try:
        source_csv, synthetic = con.execute(
            "SELECT source_csv, is_synthetic FROM meta_source"
        ).fetchone()
        if out_dir is None:
            out_dir = OUT_SYNTHETIC if synthetic else OUT_REAL
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        counts = {t: _copy(con, f"SELECT * FROM {t}", out_dir / f"{t}.csv") for t in STAR_TABLES}

        if scores_db is not None and Path(scores_db).exists():
            con.execute(f"ATTACH '{Path(scores_db).as_posix()}' AS scores_db (READ_ONLY)")
            has_scores = con.execute(
                "SELECT count(*) FROM duckdb_tables() "
                "WHERE database_name = 'scores_db' AND table_name = 'scores'"
            ).fetchone()[0]
            if has_scores:
                counts["fct_scores"] = _copy(con, SCORES_SQL, out_dir / "fct_scores.csv")
        if "fct_scores" not in counts:
            print("No scores table found: skipped fct_scores.csv "
                  "(run python -m sql.load and python -m sql.export_scores for the decile page).")
    finally:
        con.close()

    label = "SYNTHETIC (tests/fixtures/policies_sample.csv), not real results" if synthetic else "real data"
    lines = [f"Data: {label}", f"dbt source CSV: {source_csv}", ""]
    lines += [f"{name}.csv: {n:,} rows" for name, n in counts.items()]
    (out_dir / "SOURCE.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {len(counts)} CSVs to {out_dir}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dbt-db", type=Path, default=DEFAULT_DBT_DB)
    parser.add_argument("--scores-db", type=Path, default=DEFAULT_SCORES_DB)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    export(args.dbt_db, args.scores_db, args.out)


if __name__ == "__main__":
    main()
