from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from benchmarking.connect import DuckDBConfig, connect_to_db
from benchmarking.core import (
    RunOutcome,
    TimeBenchmark,
    TimeBenchmarkResult,
    ValueBenchmark,
    ValueBenchmarkResult,
    print_time_result,
    print_value_result,
    run_time_benchmark,
    run_value_benchmark,
)

TABLE_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_.]+)", re.IGNORECASE)
IDENT_PATTERN = re.compile(r"[A-Za-z0-9_.]+")


def _default_trajectory_id_source_table() -> str:
    cellstring_schema = os.getenv("CELLSTRING_SCHEMA", "db_design1_v3")
    return os.getenv("TRAJECTORY_ID_SOURCE_TABLE", f"{cellstring_schema}.trajectory_cs")


def _default_stop_id_source_table() -> str:
    cellstring_schema = os.getenv("CELLSTRING_SCHEMA", "db_design1_v3")
    return os.getenv("STOP_ID_SOURCE_TABLE", f"{cellstring_schema}.stop_cs")


def _default_region_id_source_table() -> str:
    cellstring_schema = os.getenv("CELLSTRING_SCHEMA", "db_design1_v3")
    return os.getenv("REGION_ID_SOURCE_TABLE", f"{cellstring_schema}.region_cs")


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


def _benchmark_filters() -> List[str]:
    csv = os.getenv("BENCHMARKS", "").strip()
    if not csv:
        return []
    return [name.strip() for name in csv.split(",") if name.strip()]


def _normalize_filter_token(token: str) -> str:
    normalized = token.strip().strip('"').strip("'").lower()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized


def _is_benchmark_type_match(benchmark_name: str, type_token: str) -> bool:
    type_prefixes = {
        "temporal-range": "Temporal range query",
        "spatial-range": "Spatial range query",
        "spatio-temporal-range": "Spatio-temporal range query",
        "passage-query": "Passage query",
        "spatio-temporal-join": "Spatio-temporal join",
    }
    prefix = type_prefixes.get(type_token)
    return bool(prefix and benchmark_name.startswith(prefix))


def _resolve_run_plan_filters(
    run_plan: List[object], filters: List[str]
) -> List[object]:
    if not filters:
        return run_plan

    normalized_filters = {_normalize_filter_token(item) for item in filters}
    explicit_name_filters = set(filters)

    selected = []
    for bench in run_plan:
        bench_name = getattr(bench, "name", "")
        bench_name_normalized = _normalize_filter_token(bench_name)
        matches_type = any(
            _is_benchmark_type_match(bench_name, filter_token)
            for filter_token in normalized_filters
        )
        matches_name = (
            bench_name in explicit_name_filters
            or bench_name_normalized in normalized_filters
        )
        if matches_type or matches_name:
            selected.append(bench)
    return selected


def _cache_state() -> str:
    state = os.getenv("CACHE_STATE", "warm").strip().lower()
    return state if state in {"warm", "cold"} else "warm"


def _serialize_run_outcome(run: RunOutcome) -> Dict[str, Any]:
    if run.samples:
        return {
            "exec_ms_med": run.exec_ms_med,
            "samples": run.samples,
        }
    return {"exec_ms_med": run.exec_ms_med}


def _serialize_time_result(result: TimeBenchmarkResult) -> Dict[str, Any]:
    return {
        "st": _serialize_run_outcome(result.st),
        "cst": _serialize_run_outcome(result.cst),
        "false_positives": result.false_positives,
        "false_negatives": result.false_negatives,
        "per_region_results": {
            str(region_id): {
                label: _serialize_run_outcome(run) for label, run in runs.items()
            }
            for region_id, runs in result.per_region_results.items()
        },
        "result_counts": result.result_counts,
    }


def _serialize_value_result(result: ValueBenchmarkResult) -> Dict[str, Any]:
    if result.rows:
        return {
            "median_values": result.median_values,
            "rows": result.rows,
        }
    return {"median_values": result.median_values}


def _collect_tables(*sql_statements: str) -> List[str]:
    tables = set()
    for sql in sql_statements:
        if sql:
            tables.update(TABLE_PATTERN.findall(sql))
    return sorted(tables)


def _collect_tables_from_benchmark(benchmark: object) -> List[str]:
    if isinstance(benchmark, TimeBenchmark):
        return _collect_tables(benchmark.st_sql, benchmark.cst_sql)
    if isinstance(benchmark, ValueBenchmark):
        return _collect_tables(benchmark.sql)
    return []


def _write_json_report(payload: dict, run_started_at: datetime) -> Path:
    output_dir = Path("benchmarking/benchmark_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"run_{run_started_at.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved run report to {path}")
    return path


def _fetch_random_ids(
    conn, table_name: str, id_column: str, sample_size: int
) -> List[int]:
    if sample_size <= 0:
        return []
    if not IDENT_PATTERN.fullmatch(table_name) or not IDENT_PATTERN.fullmatch(
        id_column
    ):
        raise ValueError(
            f"Unsafe identifier(s): table={table_name}, column={id_column}"
        )
    rows = conn.execute(
        f"SELECT {id_column} FROM {table_name} ORDER BY random() LIMIT ?",
        [sample_size],
    ).fetchall()
    return [int(row[0]) for row in rows]


def _get_region_ids(conn, region_table: str) -> List[int]:
    try:
        rows = conn.execute(
            f"SELECT DISTINCT region_id FROM {region_table} ORDER BY region_id"
        ).fetchall()
    except Exception:
        return []
    return [int(row[0]) for row in rows]


def main() -> None:
    load_dotenv()
    cellstring_schema = os.getenv("CELLSTRING_SCHEMA", "db_design1_v3")
    from benchmarking.benchmarks import RUN_PLAN

    run_started_at = datetime.now(timezone.utc)

    duckdb_path = os.getenv("DUCKDB_PATH", "cellstring.duckdb")
    threads = max(1, _env_int("DUCKDB_THREADS", 1))
    trajectory_id_source_table = _default_trajectory_id_source_table()
    trajectory_id_column = os.getenv("TRAJECTORY_ID_COLUMN", "trajectory_id")
    trajectory_sample_size = _env_int("TRAJECTORY_SAMPLE_SIZE", 400)
    stop_id_source_table = _default_stop_id_source_table()
    stop_id_column = os.getenv("STOP_ID_COLUMN", "stop_id")
    stop_sample_size = _env_int("STOP_SAMPLE_SIZE", 400)
    region_id_source_table = _default_region_id_source_table()
    run_label = os.getenv("RUN_LABEL", "local")
    cache_state = _cache_state()
    thread_counts = _thread_plan()

    if not RUN_PLAN:
        print(
            "RUN_PLAN is empty. Add benchmark definitions in benchmarking/benchmarks and rerun."
        )
        return

    benchmark_filters = _benchmark_filters()
    if benchmark_filters:
        run_plan = _resolve_run_plan_filters(RUN_PLAN, benchmark_filters)
        if not run_plan:
            print("No benchmarks matched BENCHMARKS in .env.")
            print(
                "Valid type filters: temporal-range, spatial-range, spatio-temporal-range, passage-query, spatio-temporal-join"
            )
            print("Available benchmarks:")
            for bench in RUN_PLAN:
                print(f"- {bench.name}")
            return
    else:
        run_plan = RUN_PLAN

    conn = connect_to_db(DuckDBConfig(db_path=duckdb_path, threads=threads))
    try:
        trajectory_ids = _fetch_random_ids(
            conn,
            trajectory_id_source_table,
            trajectory_id_column,
            trajectory_sample_size,
        )
        
        trajectory_cardinalities: Dict[str, int] = {}
        trajectory_lengths: Dict[str, float] = {}
        if trajectory_ids:
            try:
                placeholders = ", ".join(["?"] * len(trajectory_ids))
                # Cardinality from CellString
                cs_rows = conn.execute(
                    f"SELECT trajectory_id, COUNT(*) FROM {trajectory_id_source_table} WHERE trajectory_id IN ({placeholders}) GROUP BY trajectory_id",
                    trajectory_ids
                ).fetchall()
                for r in cs_rows:
                    if r[1] is not None:
                        trajectory_cardinalities[str(int(r[0]))] = int(r[1])
                
                # Length from LineString
                ls_table = os.getenv("TRAJECTORY_LS_TABLE", "p10_ls.trajectory_ls")
                ls_rows = conn.execute(
                    f"SELECT trajectory_id, ST_Length(geom) / 1000.0 FROM {ls_table} WHERE trajectory_id IN ({placeholders})",
                    trajectory_ids
                ).fetchall()
                for r in ls_rows:
                    if r[1] is not None:
                        trajectory_lengths[str(int(r[0]))] = float(r[1])
            except Exception as e:
                print(f"Warning: Failed to fetch trajectory metadata: {e}")

        stop_ids = _fetch_random_ids(
            conn, stop_id_source_table, stop_id_column, stop_sample_size
        )
        benchmark_outputs: List[Dict[str, object]] = []

        for thread_count in thread_counts:
            conn.execute(f"PRAGMA threads={thread_count}")
            print(f"\n=== Running benchmarks with PRAGMA threads={thread_count} ===")

            for benchmark in run_plan:
                bench_instance = benchmark
                if (
                    isinstance(bench_instance, TimeBenchmark)
                    and bench_instance.use_region_ids
                    and not bench_instance.region_ids
                ):
                    bench_instance = replace(
                        bench_instance,
                        region_ids=_get_region_ids(conn, region_id_source_table),
                    )

                print(f"\nRunning benchmark: {bench_instance.name}")
                tables_used = _collect_tables_from_benchmark(bench_instance)

                if isinstance(bench_instance, TimeBenchmark):
                    result = run_time_benchmark(
                        conn,
                        bench_instance,
                        trajectory_ids=trajectory_ids,
                        stop_ids=stop_ids,
                    )
                    print_time_result(result)
                    serialized = _serialize_time_result(result)
                    benchmark_type = "time"
                elif isinstance(bench_instance, ValueBenchmark):
                    result = run_value_benchmark(
                        conn,
                        bench_instance,
                        trajectory_ids=trajectory_ids,
                        stop_ids=stop_ids,
                    )
                    print_value_result(result)
                    serialized = _serialize_value_result(result)
                    benchmark_type = "value"
                else:
                    continue

                benchmark_outputs.append(
                    {
                        "name": bench_instance.name,
                        "benchmark_type": benchmark_type,
                        "tables_used": tables_used,
                        "thread_count": thread_count,
                        "result": serialized,
                    }
                )

        report = {
            "meta": {
                "run_started_at": run_started_at.isoformat(),
                "run_label": run_label,
                "cache_state": cache_state,
                "db_backend": "duckdb",
                "duckdb_path": duckdb_path,
                "linestring_schema": os.getenv("LINESTRING_SCHEMA", "p10"),
                "cellstring_schema": cellstring_schema,
                "thread_plan": thread_counts,
                "trajectory_count": len(trajectory_ids),
                "trajectory_ids": trajectory_ids,
                "trajectory_cardinalities": trajectory_cardinalities,
                "trajectory_lengths": trajectory_lengths,
                "stop_count": len(stop_ids),
                "stop_ids": stop_ids,
                "cold_run_note": "For cold runs on Linux: sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches",
            },
            "benchmarks": benchmark_outputs,
        }
        _write_json_report(report, run_started_at)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
