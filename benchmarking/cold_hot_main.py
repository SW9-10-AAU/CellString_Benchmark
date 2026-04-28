"""Standalone runner for cold vs hot benchmark.

Usage:
    sudo python -m benchmarking.cold_hot_main

Clears the Linux filesystem page cache before the first (cold) run of each
query, then records the minimum of two subsequent (hot) runs.  Produces a
JSON report under benchmarking/benchmark_results/cold_hot_run_<ts>.json.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from dotenv import load_dotenv

from benchmarking.connect import DuckDBConfig, connect_to_db
from benchmarking.core import (
    ColdHotBenchmarkResult,
    TimeBenchmark,
    print_cold_hot_result,
    run_cold_hot_benchmark,
)

TABLE_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_.]+)", re.IGNORECASE)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer in {name}: {raw}") from exc


def _thread_plan() -> List[int]:
    scaling = os.getenv("DUCKDB_THREAD_SCALING", "").strip()
    base_threads = max(1, _env_int("DUCKDB_THREADS", 1))
    if not scaling:
        return [base_threads]
    counts: List[int] = []
    for item in scaling.split(","):
        value = item.strip()
        if not value:
            continue
        counts.append(max(1, int(value)))
    return counts or [base_threads]


def _cold_hot_filters() -> List[str]:
    csv = os.getenv("COLD_HOT_BENCHMARKS", "").strip()
    if not csv:
        return []
    return [name.strip() for name in csv.split(",") if name.strip()]


def _normalize_filter_token(token: str) -> str:
    normalized = token.strip().strip('"').strip("'").lower()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized


def _resolve_filters(
    benchmarks: List[TimeBenchmark], filters: List[str]
) -> List[TimeBenchmark]:
    if not filters:
        return benchmarks
    normalized_filters = {_normalize_filter_token(f) for f in filters}
    explicit_names = set(filters)
    selected = []
    for bench in benchmarks:
        name_norm = _normalize_filter_token(bench.name)
        if bench.name in explicit_names or name_norm in normalized_filters:
            selected.append(bench)
    return selected


def _collect_tables(*sql_statements: str) -> List[str]:
    tables = set()
    for sql in sql_statements:
        if sql:
            tables.update(TABLE_PATTERN.findall(sql))
    return sorted(tables)


def _make_conn_factory(
    duckdb_path: str, threads: int
) -> Callable[[], Any]:
    """Return a callable that creates a fully initialised DuckDB connection."""

    def _factory():
        return connect_to_db(DuckDBConfig(db_path=duckdb_path, threads=threads))

    return _factory


def _serialize_cold_hot_result(result: ColdHotBenchmarkResult) -> Dict[str, Any]:
    return {
        "st": {
            "cold_ms": result.st.cold_ms,
            "hot_ms": result.st.hot_ms,
            "all_runs_ms": result.st.all_runs_ms,
        },
        "cst": {
            "cold_ms": result.cst.cold_ms,
            "hot_ms": result.cst.hot_ms,
            "all_runs_ms": result.cst.all_runs_ms,
        },
        "result_counts": result.result_counts,
    }


def _write_json_report(payload: dict, run_started_at: datetime) -> Path:
    output_dir = Path("benchmarking/benchmark_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"cold_hot_run_{run_started_at.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved cold/hot report to {path}")
    return path


def main() -> None:
    load_dotenv()

    from benchmarking.benchmarks.cold_hot_benchmark import COLD_HOT_BENCHMARKS

    run_started_at = datetime.now(timezone.utc)

    duckdb_path = os.getenv("DUCKDB_PATH", "cellstring.duckdb")
    thread_counts = _thread_plan()
    run_label = os.getenv("RUN_LABEL", "local")

    filters = _cold_hot_filters()
    benchmarks = _resolve_filters(COLD_HOT_BENCHMARKS, filters)

    if not benchmarks:
        print("No cold/hot benchmarks to run.")
        if filters:
            print("Available benchmarks:")
            for b in COLD_HOT_BENCHMARKS:
                print(f"  - {b.name}")
        return

    print(f"Cold/hot benchmark run — {len(benchmarks)} benchmark(s)")
    print(f"Thread plan: {thread_counts}")
    print(f"DB path: {duckdb_path}\n")

    benchmark_outputs: List[Dict[str, Any]] = []

    for thread_count in thread_counts:
        conn_factory = _make_conn_factory(duckdb_path, thread_count)
        print(f"\n=== threads={thread_count} ===")

        for benchmark in benchmarks:
            print(f"\nRunning: {benchmark.name}")
            tables_used = _collect_tables(
                benchmark.st_sql,
                benchmark.cst_sql,
                benchmark.st_setup_sql,
                benchmark.cst_setup_sql,
            )

            result = run_cold_hot_benchmark(conn_factory, benchmark)
            print_cold_hot_result(result)

            benchmark_outputs.append(
                {
                    "name": result.name,
                    "benchmark_type": "cold_hot",
                    "tables_used": tables_used,
                    "thread_count": thread_count,
                    "result": _serialize_cold_hot_result(result),
                }
            )

    report = {
        "meta": {
            "run_started_at": run_started_at.isoformat(),
            "run_label": run_label,
            "benchmark_type": "cold_hot",
            "db_backend": "duckdb",
            "duckdb_path": duckdb_path,
            "linestring_schema": os.getenv("LINESTRING_SCHEMA", "p10"),
            "cellstring_schema": os.getenv("CELLSTRING_SCHEMA", "db_design1_v3"),
            "thread_plan": thread_counts,
        },
        "benchmarks": benchmark_outputs,
    }
    _write_json_report(report, run_started_at)


if __name__ == "__main__":
    main()
