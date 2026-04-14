from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class TimeBenchmark:
    name: str
    st_sql: str
    cst_sql: str
    params: Tuple[Any, ...] = tuple()
    st_setup_sql: str = ""
    cst_setup_sql: str = ""
    st_setup_params: Tuple[Any, ...] = tuple()
    cst_setup_params: Tuple[Any, ...] = tuple()
    repeats: int = 5
    with_trajectory_ids: bool = False
    with_stop_ids: bool = False
    area_ids: List[int] = field(default_factory=list)
    use_area_ids: bool = False


@dataclass(frozen=True)
class ValueBenchmark:
    name: str
    sql: str
    with_trajectory_ids: bool = False
    with_stop_ids: bool = False
    iterate_trajectory_ids: bool = False
    iterate_stop_ids: bool = False
    params: Tuple[Any, ...] = tuple()
    capture_rows: bool = False
    row_field_names: Optional[List[str]] = None


@dataclass
class RunOutcome:
    exec_ms_med: float
    rows: List[Tuple]
    samples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TimeBenchmarkResult:
    name: str
    st: RunOutcome
    cst: RunOutcome
    false_positives: int
    false_negatives: int
    per_area_results: Dict[int, Dict[str, RunOutcome]] = field(default_factory=dict)
    result_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class ValueBenchmarkResult:
    name: str
    median_values: Dict[str, float]
    rows: List[Dict[str, Any]] = field(default_factory=list)


def _reset_connection(cur) -> None:
    # Keep settings deterministic between benchmark runs.
    cur.execute("PRAGMA enable_progress_bar=false")


def _execute_with_timing(
    cur,
    sql: str,
    params: Sequence[Any],
    *,
    setup_sql: str = "",
    setup_params: Sequence[Any] = tuple(),
) -> Tuple[List[Tuple], float]:
    if setup_sql:
        _reset_connection(cur)
        _run_setup_sql(cur, setup_sql, setup_params)
    _reset_connection(cur)
    start = time.perf_counter()
    cur.execute(sql, params)
    rows = cur.fetchall()
    return rows, (time.perf_counter() - start) * 1000.0


def _run_setup_sql(cur, setup_sql: str, setup_params: Sequence[Any]) -> None:
    statements = [stmt.strip() for stmt in setup_sql.split(";") if stmt.strip()]
    if not statements:
        return

    params_list = list(setup_params)
    param_index = 0
    for statement in statements:
        placeholders = statement.count("?")
        statement_params: Sequence[Any] = tuple()
        if placeholders:
            end_index = param_index + placeholders
            if end_index > len(params_list):
                raise ValueError(
                    "setup_sql placeholders exceed provided setup_params "
                    f"(needed at least {end_index}, got {len(params_list)})"
                )
            statement_params = tuple(params_list[param_index:end_index])
            param_index = end_index
        cur.execute(statement, statement_params)

    if param_index != len(params_list):
        raise ValueError(
            "setup_params has unused values for setup_sql "
            f"(used {param_index}, provided {len(params_list)})"
        )


def _warmup(
    cur,
    sql: str,
    params: Sequence[Any],
    *,
    setup_sql: str = "",
    setup_params: Sequence[Any] = tuple(),
) -> None:
    _execute_with_timing(
        cur,
        sql,
        params,
        setup_sql=setup_sql,
        setup_params=setup_params,
    )


def _median_or_zero(values: Iterable[float]) -> float:
    values = list(values)
    return round(median(values), 3) if values else 0.0


def _normalize_row_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_mapping(
    row: Sequence[Any], field_names: Optional[List[str]]
) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    if field_names:
        for idx, name in enumerate(field_names):
            if idx < len(row):
                mapping[name] = _normalize_row_value(row[idx])
        return mapping
    for idx, value in enumerate(row):
        mapping[f"col{idx}"] = _normalize_row_value(value)
    return mapping


def _aggregate_runs(runs: List[RunOutcome], rows: List[Tuple]) -> RunOutcome:
    return RunOutcome(
        exec_ms_med=_median_or_zero(r.exec_ms_med for r in runs),
        rows=rows,
        samples=[sample for run in runs for sample in run.samples],
    )


def _keyset(rows: Iterable[Tuple]) -> set:
    return {r[0] for r in rows}


def _execute_random_or_repeated_queries(
    cur,
    sql: str,
    params: Sequence[Any],
    *,
    repeats: int | None = None,
    trajectory_ids: List[int] | None = None,
    stop_ids: List[int] | None = None,
    sample_label: str | None = None,
    setup_sql: str = "",
    setup_params: Sequence[Any] = tuple(),
) -> RunOutcome:
    if trajectory_ids is not None and not trajectory_ids:
        return RunOutcome(0.0, [])

    exec_times: List[float] = []
    collected_rows: List[Tuple] = []
    sample_records: List[Dict[str, Any]] = []
    base_params: Tuple[Any, ...] = tuple(params)
    run_repeats = repeats or 1

    if trajectory_ids is not None:
        first_params = (trajectory_ids[0],) + base_params
        _warmup(
            cur,
            sql,
            first_params,
            setup_sql=setup_sql,
            setup_params=setup_params,
        )

        for trajectory_id in trajectory_ids:
            current_params = (trajectory_id,) + base_params
            rows, exec_ms = _execute_with_timing(
                cur,
                sql,
                current_params,
                setup_sql=setup_sql,
                setup_params=setup_params,
            )
            exec_times.append(exec_ms)
            collected_rows.extend(rows)
            sample: Dict[str, Any] = {}
            sample["trajectory_id"] = trajectory_id
            sample["exec_ms"] = exec_ms
            if sample_label:
                sample["label"] = sample_label
            sample_records.append(sample)
    elif stop_ids is not None:
        first_params = (stop_ids[0],) + base_params
        _warmup(
            cur,
            sql,
            first_params,
            setup_sql=setup_sql,
            setup_params=setup_params,
        )

        for stop_id in stop_ids:
            current_params = (stop_id,) + base_params
            rows, exec_ms = _execute_with_timing(
                cur,
                sql,
                current_params,
                setup_sql=setup_sql,
                setup_params=setup_params,
            )
            exec_times.append(exec_ms)
            collected_rows.extend(rows)
            sample: Dict[str, Any] = {}
            sample["stop_id"] = stop_id
            sample["exec_ms"] = exec_ms
            if sample_label:
                sample["label"] = sample_label
            sample_records.append(sample)
    else:
        _warmup(
            cur,
            sql,
            base_params,
            setup_sql=setup_sql,
            setup_params=setup_params,
        )
        rows, _ = _execute_with_timing(
            cur,
            sql,
            base_params,
            setup_sql=setup_sql,
            setup_params=setup_params,
        )
        collected_rows = rows
        for _ in range(run_repeats):
            _, exec_ms = _execute_with_timing(
                cur,
                sql,
                base_params,
                setup_sql=setup_sql,
                setup_params=setup_params,
            )
            exec_times.append(exec_ms)

    _reset_connection(cur)
    return RunOutcome(_median_or_zero(exec_times), collected_rows, samples=sample_records)


def run_time_benchmark(
    connection,
    benchmark: TimeBenchmark,
    trajectory_ids: List[int] | None = None,
    stop_ids: List[int] | None = None,
) -> TimeBenchmarkResult:
    per_area_results: Dict[int, Dict[str, RunOutcome]] = {}

    cur = connection.cursor()
    try:
        if benchmark.use_area_ids and benchmark.area_ids:
            st_rows: List[Tuple] = []
            valid_st_runs: List[RunOutcome] = []
            cst_rows: List[Tuple] = []
            valid_cst_runs: List[RunOutcome] = []

            for area_id in benchmark.area_ids:
                area_params = (area_id,) + benchmark.params
                st_run = _execute_random_or_repeated_queries(
                    cur,
                    benchmark.st_sql,
                    area_params,
                    repeats=benchmark.repeats,
                    setup_sql=benchmark.st_setup_sql,
                    setup_params=benchmark.st_setup_params,
                )
                per_area_results[area_id] = {"st": st_run}
                st_rows.extend(st_run.rows)
                valid_st_runs.append(st_run)

                cst_run = _execute_random_or_repeated_queries(
                    cur,
                    benchmark.cst_sql,
                    area_params,
                    repeats=benchmark.repeats,
                    setup_sql=benchmark.cst_setup_sql,
                    setup_params=benchmark.cst_setup_params,
                )
                per_area_results[area_id]["cst"] = cst_run
                cst_rows.extend(cst_run.rows)
                valid_cst_runs.append(cst_run)

            st_out = _aggregate_runs(valid_st_runs, st_rows)
            cst_out = _aggregate_runs(valid_cst_runs, cst_rows)
        elif benchmark.with_trajectory_ids:
            st_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.st_sql,
                benchmark.params,
                trajectory_ids=trajectory_ids,
                sample_label="LineString",
                setup_sql=benchmark.st_setup_sql,
                setup_params=benchmark.st_setup_params,
            )
            cst_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.cst_sql,
                benchmark.params,
                trajectory_ids=trajectory_ids,
                sample_label="CellString",
                setup_sql=benchmark.cst_setup_sql,
                setup_params=benchmark.cst_setup_params,
            )
        elif benchmark.with_stop_ids:
            st_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.st_sql,
                benchmark.params,
                stop_ids=stop_ids,
                setup_sql=benchmark.st_setup_sql,
                setup_params=benchmark.st_setup_params,
            )
            cst_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.cst_sql,
                benchmark.params,
                stop_ids=stop_ids,
                sample_label="CellString",
                setup_sql=benchmark.cst_setup_sql,
                setup_params=benchmark.cst_setup_params,
            )
        else:
            st_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.st_sql,
                benchmark.params,
                repeats=benchmark.repeats,
                setup_sql=benchmark.st_setup_sql,
                setup_params=benchmark.st_setup_params,
            )
            cst_out = _execute_random_or_repeated_queries(
                cur,
                benchmark.cst_sql,
                benchmark.params,
                repeats=benchmark.repeats,
                setup_sql=benchmark.cst_setup_sql,
                setup_params=benchmark.cst_setup_params,
            )

    finally:
        cur.close()

    st_keys = _keyset(st_out.rows)
    cst_keys = _keyset(cst_out.rows)
    false_positives = len(cst_keys - st_keys)
    false_negatives = len(st_keys - cst_keys)
    result_counts: Dict[str, int] = {
        "LineString": len(st_keys),
        "CellString": len(cst_keys),
    }

    return TimeBenchmarkResult(
        benchmark.name,
        st_out,
        cst_out,
        false_positives,
        false_negatives,
        per_area_results,
        result_counts,
    )


def run_value_benchmark(
    connection,
    bench: ValueBenchmark,
    trajectory_ids: Optional[List[int]] = None,
    stop_ids: Optional[List[int]] = None,
) -> ValueBenchmarkResult:
    trajectory_ids = trajectory_ids or []
    stop_ids = stop_ids or []
    median_values: Dict[str, float] = {}
    rows: List[Dict[str, Any]] = []

    def _collect_value_rows(
        query_rows: List[Tuple], *, numeric_values: List[float]
    ) -> None:
        for row in query_rows:
            if not row:
                continue
            if bench.capture_rows:
                rows.append(_row_to_mapping(row, bench.row_field_names))
            if len(row) == 1:
                try:
                    numeric_values.append(float(row[0]))
                except (TypeError, ValueError):
                    continue
            elif len(row) == 2 and isinstance(row[0], str):
                try:
                    median_values[str(row[0])] = float(row[1])
                except (TypeError, ValueError):
                    continue

    cur = connection.cursor()
    try:
        value_samples: List[float] = []

        if bench.with_trajectory_ids:
            if not trajectory_ids:
                return ValueBenchmarkResult(bench.name, {}, [])
            if bench.iterate_trajectory_ids:
                for trajectory_id in trajectory_ids:
                    cur.execute(bench.sql, (trajectory_id, *bench.params))
                    _collect_value_rows(cur.fetchall(), numeric_values=value_samples)
            else:
                cur.execute(bench.sql, (trajectory_ids, *bench.params))
                _collect_value_rows(cur.fetchall(), numeric_values=value_samples)
            if value_samples:
                median_values["value"] = median(value_samples)
        elif bench.with_stop_ids:
            if not stop_ids:
                return ValueBenchmarkResult(bench.name, {}, [])
            if bench.iterate_stop_ids:
                for stop_id in stop_ids:
                    cur.execute(bench.sql, (stop_id, *bench.params))
                    _collect_value_rows(cur.fetchall(), numeric_values=value_samples)
            else:
                cur.execute(bench.sql, (stop_ids, *bench.params))
                _collect_value_rows(cur.fetchall(), numeric_values=value_samples)
            if value_samples:
                median_values["value"] = median(value_samples)
        else:
            cur.execute(bench.sql, bench.params)
            _collect_value_rows(cur.fetchall(), numeric_values=value_samples)
            if value_samples and "value" not in median_values:
                median_values["value"] = median(value_samples)

    finally:
        cur.close()

    return ValueBenchmarkResult(bench.name, median_values, rows)


def _print_run(label: str, run: RunOutcome, indent: str = "") -> None:
    print(f"{indent}{label}: exec_ms(median)={run.exec_ms_med}")


def print_time_result(result: TimeBenchmarkResult) -> None:
    print(f"\n--- {result.name} ---")
    _print_run("LineString", result.st)
    print("----------------------------")
    _print_run("CellString", result.cst)
    print(f"False positives (CellString \\ LineString): {result.false_positives}")
    print(f"False negatives (LineString \\ CellString): {result.false_negatives}")
    print("----------------------------")
    if result.per_area_results:
        print("Per-area breakdown:")
        for area_id in sorted(result.per_area_results):
            print(f"Area {area_id}:")
            for label, run in result.per_area_results[area_id].items():
                _print_run(f"  {label}", run)
            print("----------------------------")


def print_value_result(result: ValueBenchmarkResult) -> None:
    print(f"\n--- {result.name} ---")
    for label, value in result.median_values.items():
        print(f"{label}: median value = {value:.10f}")
    print("----------------------------")
