"""Load the raw motor portfolio CSV into DuckDB as a `policies` table.

Run from the repo root:
    python -m sql.load                       # data/raw/motor_portfolio.csv
    python -m sql.load --csv tests/fixtures/policies_sample.csv   # SYNTHETIC fixture

Writes data/claims.duckdb (git-ignored). The table is the raw file as-is:
no renames, no filters. Cleaning rules live in the queries so each one is
visible where it is used.
"""

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "raw" / "motor_portfolio.csv"
DEFAULT_DB = ROOT / "data" / "claims.duckdb"
FIXTURE_CSV = ROOT / "tests" / "fixtures" / "policies_sample.csv"

# Every column the SQL queries, dbt models and src/ code read. Checked on
# load so a renamed column fails here with a clear message, not deep in a query.
REQUIRED_COLUMNS = [
    "insured_id", "year", "policy_status", "policy_type", "business_type",
    "payment_frequency", "bonus_score", "driver_age", "age_driving_licence",
    "vehicle_age", "vehicle_brand", "fuel_type", "vehicle_value", "seats",
    "power_to_weight_ratio", "municipality_type", "circulation_area",
    "total_exposure", "total_premium", "total_claims",
]


def is_synthetic(csv_path: Path) -> bool:
    return Path(csv_path).resolve() == FIXTURE_CSV.resolve()


def load(csv_path: Path = DEFAULT_CSV, db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    """(Re)create the policies table from csv_path and return an open connection."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}\nDownload it (see README) or pass --csv.")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(
        "CREATE OR REPLACE TABLE policies AS "
        "SELECT * FROM read_csv(?, delim = ';', header = true, nullstr = ['', 'NA'])",
        [str(csv_path)],
    )
    columns = [row[0] for row in con.execute("DESCRIBE policies").fetchall()]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        con.close()
        sys.exit(f"{csv_path} is missing expected columns: {missing}")

    # Remember where the data came from, so run_all.py can tell real results
    # from synthetic ones.
    con.execute(
        "CREATE OR REPLACE TABLE load_info AS "
        "SELECT ? AS source_csv, ? AS is_synthetic, now() AS loaded_at, "
        "(SELECT count(*) FROM policies) AS n_rows",
        [str(csv_path), is_synthetic(csv_path)],
    )
    return con


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="raw CSV (semicolon-delimited)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="DuckDB file to write")
    args = parser.parse_args()

    con = load(args.csv, args.db)
    n_rows = con.execute("SELECT count(*) FROM policies").fetchone()[0]
    label = " (SYNTHETIC fixture)" if is_synthetic(args.csv) else ""
    print(f"Loaded {n_rows:,} rows from {args.csv}{label} into {args.db} as `policies`\n")
    for name, dtype, *_ in con.execute("DESCRIBE policies").fetchall():
        print(f"  {name:<24} {dtype}")
    con.close()


if __name__ == "__main__":
    main()
