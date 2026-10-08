import sys
from pathlib import Path

import duckdb

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def run_duckdb(csv_path, db_path=":memory:"):
    con = duckdb.connect(db_path)
    csv_sql = Path(csv_path).resolve().as_posix()
    for name in ("01_raw.sql", "02_clean.sql", "03_daily.sql"):
        sql = (SQL_DIR / name).read_text().replace("{csv_path}", csv_sql)
        con.execute(sql)

    rows_in = con.execute("SELECT COUNT(*) FROM raw_orders").fetchone()[0]
    rows_out = con.execute("SELECT COUNT(*) FROM clean_orders").fetchone()[0]
    daily = con.execute("SELECT * FROM daily_sales ORDER BY order_date").df()
    con.close()
    return daily, {"rows_in": rows_in, "rows_out": rows_out}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/orders.csv"
    result, stats = run_duckdb(path)
    print(stats)
    print(result.head())
    print(f"days: {len(result)}")