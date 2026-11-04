"""Run every query in sql/queries/ and save each result as a CSV.

Run from the repo root, after python -m sql.load and python -m sql.export_scores:
    python -m sql.run_all

Results go to sql/results/<query name>.csv. If the database was loaded from
the SYNTHETIC test fixture, results go to data/processed/sql_results_synthetic/
instead (git-ignored), so made-up numbers never land in sql/results/.
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = ROOT / "sql" / "queries"
RESULTS_DIR = ROOT / "sql" / "results"
SYNTHETIC_RESULTS_DIR = ROOT / "data" / "processed" / "sql_results_synthetic"
DEFAULT_DB = ROOT / "data" / "claims.duckdb"


def query_files() -> list[Path]:
    return sorted(QUERY_DIR.glob("*.sql"))


def run_query(con: duckdb.DuckDBPyConnection, path: Path) -> pd.DataFrame:
    return con.execute(path.read_text(encoding="utf-8")).df()


def run_all(db_path: Path = DEFAULT_DB, out_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "scores" not in tables:
            raise SystemExit("No `scores` table: run python -m sql.export_scores first (query 07 needs it).")
        synthetic = bool(con.execute("SELECT is_synthetic FROM load_info").fetchone()[0])
        if out_dir is None:
            out_dir = SYNTHETIC_RESULTS_DIR if synthetic else RESULTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        for path in query_files():
            df = run_query(con, path)
            df.to_csv(out_dir / f"{path.stem}.csv", index=False)
            results[path.stem] = df
            print(f"{path.stem:<40} {len(df):>4} rows")
    finally:
        con.close()
    label = "SYNTHETIC data" if synthetic else "real data"
    print(f"\nWrote {len(results)} result files ({label}) to {out_dir}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=None, help="output folder (default: see docstring)")
    args = parser.parse_args()
    run_all(args.db, args.out)


if __name__ == "__main__":
    main()
