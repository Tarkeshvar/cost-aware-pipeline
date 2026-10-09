import argparse
import os
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent

BANNED_WORDS = [
    "faster", "slower", "quicker", "quick", "speed", "more", "less", "fewer", "lower", "higher",
    "better", "worse", "efficient", "efficiency", "cheaper", "bigger", "smaller", "larger",
    "avoid", "never", "not", "don't", "instead",
]
DUCKDB_FOR_TIME = r"duckdb\b.*?\btime\b.*?\bpandas\b.*?\bmemory\b"
PANDAS_FOR_MEMORY = r"pandas\b.*?\bmemory\b.*?\bduckdb\b.*?\btime\b"


def load_stats(csv_path):
    df = pd.read_csv(csv_path)
    med = df.groupby(["input_rows", "implementation"], as_index=False).agg(
        seconds=("seconds", "median"), peak_mem_mb=("peak_mem_mb", "median")
    )
    p = med[med["implementation"] == "pandas"].set_index("input_rows")
    d = med[med["implementation"] == "duckdb"].set_index("input_rows")
    out = pd.DataFrame(
        {
            "pandas_seconds": p["seconds"],
            "duckdb_seconds": d["seconds"],
            "pandas_mem_mb": p["peak_mem_mb"],
            "duckdb_mem_mb": d["peak_mem_mb"],
        }
    ).reset_index()
    out["speedup"] = out["pandas_seconds"] / out["duckdb_seconds"]
    out["memory_ratio"] = out["duckdb_mem_mb"] / out["pandas_mem_mb"]
    return out.round(2)


def facts_text(stats):
    first = stats.iloc[0]
    last = stats.iloc[-1]
    return (
        f"At {int(first['input_rows']):,} rows, pandas took {first['pandas_seconds']:.2f}s and "
        f"DuckDB took {first['duckdb_seconds']:.2f}s. "
        f"At {int(last['input_rows']):,} rows, DuckDB SQL took {last['duckdb_seconds']:.2f}s against "
        f"{last['pandas_seconds']:.2f}s for pandas, a speedup of {last['speedup']:.1f}x. "
        f"DuckDB used {last['duckdb_mem_mb']:.0f} MB of memory against {last['pandas_mem_mb']:.0f} MB "
        f"for pandas, which is {last['memory_ratio']:.2f}x."
    )


def build_prompt(stats):
    return (
        "A data pipeline was built two ways, pandas and DuckDB SQL, and both were measured.\n\n"
        f"{facts_text(stats)}\n\n"
        "Complete these two lines and reply with only the two lines.\n"
        "Choose DuckDB when <a short reason about compute time>\n"
        "Choose pandas when <a short reason about memory>\n\n"
        "Rules: no digits, and no comparison words like faster, slower, more or less.\n"
        "Example:\n"
        "Choose DuckDB when the job runs often and compute time adds up\n"
        "Choose pandas when the machine has little memory"
    )


def parse_advice(text):
    duck = re.search(r"duckdb when\s+(.+?)(?=,?\s*(?:and\s+)?(?:choose\s+)?pandas when|\n|$)", text, re.I)
    pand = re.search(r"pandas when\s+(.+?)(?=\n|$)", text, re.I)
    if not duck or not pand:
        raise ValueError("model reply is not in the expected format")
    duck_part = duck.group(1).strip().rstrip(".,;").strip()
    pand_part = pand.group(1).strip().rstrip(".,;").strip()
    return f"Choose DuckDB when {duck_part}, and choose pandas when {pand_part}."


def check_summary(text):
    lowered = text.lower()
    if any(ch.isdigit() for ch in lowered):
        raise ValueError("summary contains numbers")
    words = set(re.findall(r"[a-z']+", lowered))
    if words & set(BANNED_WORDS):
        raise ValueError("summary uses comparison words")
    if not (re.search(DUCKDB_FOR_TIME, lowered, re.S) or re.search(PANDAS_FOR_MEMORY, lowered, re.S)):
        raise ValueError("summary does not match the measurements")


class SummaryProvider:
    name = "base"

    def summarize(self, stats):
        raise NotImplementedError


class OllamaProvider(SummaryProvider):
    def __init__(self, model=None, url=None, timeout=60):
        self.model = model or os.environ.get("AI_MODEL", "llama3.2")
        self.url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.timeout = timeout
        self.name = f"ollama:{self.model}"

    def summarize(self, stats):
        response = requests.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": build_prompt(stats), "stream": False},
            timeout=self.timeout,
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        if not text:
            raise ValueError("empty response from model")
        return parse_advice(text)


class RuleBasedProvider(SummaryProvider):
    name = "rule-based"

    def summarize(self, stats):
        return (
            f"{facts_text(stats)} "
            "Choose DuckDB when compute time is the main cost, and choose pandas when memory is limited."
        )


def get_summary(stats, provider=None):
    provider = provider or OllamaProvider()
    try:
        advice = provider.summarize(stats)
        check_summary(advice)
        return f"{facts_text(stats)} {advice}", provider.name
    except Exception:
        fallback = RuleBasedProvider()
        return fallback.summarize(stats), f"{fallback.name} (fallback)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default=str(ROOT / "docs" / "metrics.csv"))
    parser.add_argument("--out", default=str(ROOT / "docs" / "summary.md"))
    args = parser.parse_args()

    stats = load_stats(args.metrics)
    text, source = get_summary(stats)
    print(stats.to_string(index=False))
    print()
    print(f"source: {source}")
    print(text)

    Path(args.out).write_text(f"{text}\n\nGenerated by: {source}\n", encoding="utf-8")


if __name__ == "__main__":
    main()