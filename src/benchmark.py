import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import psutil

from generate_data import generate

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "metrics.duckdb"
CSV_OUT = ROOT / "docs" / "metrics.csv"
IMPLEMENTATIONS = ["pandas", "duckdb"]


def worker(impl, csv_path):
    if impl == "pandas":
        from pipeline_pandas import run_pandas as fn
    else:
        from pipeline_duckdb import run_duckdb as fn
    start = time.perf_counter()
    _, stats = fn(csv_path)
    elapsed = time.perf_counter() - start
    print(json.dumps({**stats, "seconds": elapsed}))


def process_memory(ps):
    total = 0
    for p in [ps] + ps.children(recursive=True):
        try:
            info = p.memory_info()
            total += max(info.rss, getattr(info, "peak_wset", 0))
        except psutil.Error:
            pass
    return total


def measure(impl, csv_path):
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", impl, str(csv_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ps = psutil.Process(proc.pid)
    peak = 0
    while proc.poll() is None:
        try:
            peak = max(peak, process_memory(ps))
        except psutil.Error:
            break
        time.sleep(0.01)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(err)
    result = json.loads(out.strip().splitlines()[-1])
    result["peak_mem_mb"] = peak / 1024 / 1024
    return result


def save(rows):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        rows,
        columns=["run_ts", "implementation", "input_rows", "clean_rows", "seconds", "peak_mem_mb", "rows_per_sec"],
    )
    con = duckdb.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            run_ts TIMESTAMP,
            implementation VARCHAR,
            input_rows BIGINT,
            clean_rows BIGINT,
            seconds DOUBLE,
            peak_mem_mb DOUBLE,
            rows_per_sec DOUBLE
        )
        """
    )
    con.execute("INSERT INTO metrics SELECT * FROM df")
    con.execute(f"COPY (SELECT * FROM metrics ORDER BY run_ts) TO '{CSV_OUT.as_posix()}' (HEADER, DELIMITER ',')")
    con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[100_000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()

    if args.worker:
        worker(args.worker[0], args.worker[1])
        return

    rows = []
    for n in args.sizes:
        csv_path = ROOT / "data" / f"orders_{n}.csv"
        if not csv_path.exists():
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            generate(n).to_csv(csv_path, index=False)
        for _ in range(args.repeats):
            for impl in IMPLEMENTATIONS:
                r = measure(impl, csv_path)
                rows.append(
                    (
                        datetime.now(timezone.utc).replace(tzinfo=None),
                        impl,
                        r["rows_in"],
                        r["rows_out"],
                        r["seconds"],
                        r["peak_mem_mb"],
                        r["rows_in"] / r["seconds"],
                    )
                )
                print(f"{impl:7} rows={r['rows_in']:>9} time={r['seconds']:.2f}s mem={r['peak_mem_mb']:.0f}MB")
    save(rows)
    print(f"saved {len(rows)} runs to {CSV_OUT}")


if __name__ == "__main__":
    main()