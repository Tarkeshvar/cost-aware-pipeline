import pandas as pd
import pytest

from ai_summary import OllamaProvider, SummaryProvider, get_summary, load_stats
from generate_data import generate
from pipeline_duckdb import run_duckdb
from pipeline_pandas import run_pandas

HEADER = "order_id,customer_id,product_id,quantity,amount,order_ts,status\n"
IMPLEMENTATIONS = [run_pandas, run_duckdb]


def write_csv(tmp_path, rows):
    path = tmp_path / "orders.csv"
    path.write_text(HEADER + "\n".join(rows) + "\n")
    return path


@pytest.mark.parametrize("run", IMPLEMENTATIONS)
def test_duplicates_are_removed(tmp_path, run):
    path = write_csv(
        tmp_path,
        [
            "1,10,5,2,100.0,2026-01-01 10:00:00,completed",
            "1,10,5,2,100.0,2026-01-01 10:00:00,completed",
            "2,11,5,1,40.0,2026-01-01 11:00:00,completed",
        ],
    )
    daily, stats = run(str(path))
    assert stats["rows_in"] == 3
    assert stats["rows_out"] == 2
    assert int(daily.loc[0, "orders"]) == 2


@pytest.mark.parametrize("run", IMPLEMENTATIONS)
def test_bad_rows_are_rejected(tmp_path, run):
    path = write_csv(
        tmp_path,
        [
            "1,10,5,2,100.0,2026-01-01 10:00:00,completed",
            "2,,5,1,50.0,2026-01-01 11:00:00,completed",
            "3,11,5,1,-20.0,2026-01-02 09:00:00,completed",
            "4,12,5,1,0.0,2026-01-02 09:30:00,completed",
            "5,13,5,1,30.0,2026-01-02 10:00:00,cancelled",
        ],
    )
    daily, stats = run(str(path))
    assert stats["rows_out"] == 2
    assert list(daily["order_date"]) == ["2026-01-01", "2026-01-02"]
    assert float(daily.loc[0, "revenue"]) == 100.0
    assert int(daily.loc[1, "cancelled"]) == 1
    assert float(daily.loc[1, "revenue"]) == 0.0


def test_pandas_and_duckdb_give_same_result(tmp_path):
    path = tmp_path / "orders.csv"
    generate(5000).to_csv(path, index=False)
    a, sa = run_pandas(str(path))
    b, sb = run_duckdb(str(path))
    assert sa == sb
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


@pytest.mark.parametrize("run", IMPLEMENTATIONS)
def test_rerun_gives_same_result(tmp_path, run):
    path = tmp_path / "orders.csv"
    generate(2000).to_csv(path, index=False)
    first, s1 = run(str(path))
    second, s2 = run(str(path))
    assert s1 == s2
    pd.testing.assert_frame_equal(first, second)


def test_duckdb_rerun_on_same_database_file(tmp_path):
    path = tmp_path / "orders.csv"
    generate(2000).to_csv(path, index=False)
    db = str(tmp_path / "pipeline.duckdb")
    first, _ = run_duckdb(str(path), db)
    second, _ = run_duckdb(str(path), db)
    pd.testing.assert_frame_equal(first, second)


@pytest.mark.parametrize("run", IMPLEMENTATIONS)
def test_edge_case_all_rows_invalid(tmp_path, run):
    path = write_csv(
        tmp_path,
        [
            "1,,5,1,50.0,2026-01-01 11:00:00,completed",
            "2,11,5,1,-20.0,2026-01-02 09:00:00,completed",
        ],
    )
    daily, stats = run(str(path))
    assert stats["rows_in"] == 2
    assert stats["rows_out"] == 0
    assert len(daily) == 0


class BrokenProvider(SummaryProvider):
    name = "broken"

    def summarize(self, stats):
        raise RuntimeError("model crashed")


def make_stats(tmp_path):
    metrics = tmp_path / "metrics.csv"
    pd.DataFrame(
        {
            "input_rows": [1000, 1000, 1000, 1000],
            "implementation": ["pandas", "pandas", "duckdb", "duckdb"],
            "seconds": [2.0, 4.0, 1.0, 1.0],
            "peak_mem_mb": [100.0, 100.0, 150.0, 150.0],
        }
    ).to_csv(metrics, index=False)
    return load_stats(str(metrics))


def test_ai_failure_falls_back_to_rule_based(tmp_path):
    text, source = get_summary(make_stats(tmp_path), BrokenProvider())
    assert "fallback" in source
    assert "3.00s" in text
    assert "3.0x" in text


def test_unreachable_ollama_falls_back(tmp_path):
    provider = OllamaProvider(url="http://127.0.0.1:9", timeout=2)
    text, source = get_summary(make_stats(tmp_path), provider)
    assert "fallback" in source
    assert len(text) > 0