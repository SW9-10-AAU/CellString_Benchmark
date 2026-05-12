# CellString Benchmark (DuckDB)

This repository benchmarks `LineString` vs `CellString` query variants in DuckDB.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `.env` values for your Linux server paths:
- `DUCKDB_PATH`: path to the `.duckdb` database file.
- `LINESTRING_SCHEMA`: schema for LineString/PostGIS-derived tables (default `p10`).
- `CELLSTRING_SCHEMA`: schema for the current CellString design under test (for example `db_design1_v3`).
- `TRAJECTORY_ID_SOURCE_TABLE`, `STOP_ID_SOURCE_TABLE`, `AREA_ID_SOURCE_TABLE`: source ID tables.
- `DUCKDB_THREADS`, `DUCKDB_THREAD_SCALING`, `RUN_LABEL`, `CACHE_STATE`: run behavior.
- `BENCHMARKS`: optional comma-separated benchmark names to run only a subset.

The runner assumes a fixed CellString column layout using `cell_z21`.

## Benchmark Design Rules

- Baseline comparisons must use `DUCKDB_THREADS=1`.
- Run a second scaling pass with `DUCKDB_THREAD_SCALING=1,2,4,8,16` (or server core count).
- Report cold and warm runs separately.

## Cold vs Warm Runs (Linux)

Cold run (drop OS page cache before each run):

```bash
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
python -m benchmarking.main
```

Warm run:

```bash
python -m benchmarking.main
```

## Running Benchmarks

All runner settings are loaded from `.env`.

Single run command:

```bash
python -m benchmarking.main
```

Single-thread baseline:

```bash
DUCKDB_THREADS=1 DUCKDB_THREAD_SCALING= python -m benchmarking.main
```

Thread scaling benchmark:

```bash
DUCKDB_THREADS=1 DUCKDB_THREAD_SCALING=1,2,4,8,16 python -m benchmarking.main
```

Run only the temporal range benchmarks:

```bash
BENCHMARKS="Temporal range query (1 day),Temporal range query (1 week),Temporal range query (1 month)" python -m benchmarking.main
```

The runner writes JSON reports to `benchmarking/benchmark_results/`.

## Adding Your Queries

Use `benchmarking/benchmarks/duckdb_query_templates.py` as the starting point and register them in `benchmarking/benchmarks/__init__.py` via `RUN_PLAN`.

Parameter style for DuckDB is `?` (not `%s`).

## ~~Graphs~~ - DEPRECATED

Set `DEFAULT_REPORT_JSON` in `benchmarking/graphs/graph_generation.py` if you want a fixed JSON file without passing it on the command line. Leave it as `None` to auto-pick the newest report.

```bash
python -m benchmarking.graphs.graph_generation
python -m benchmarking.graphs.graph_generation benchmarking/benchmark_results/run_xxxxxxxx_xxxxxx.json
python -m benchmarking.graphs.graph_generation --benchmark="Template benchmark: LineString vs CellString"
python -m benchmarking.graphs.graph_generation --plot=exec_time_bars
python -m benchmarking.graphs.graph_generation --plot=cell_count_exec_time
python -m benchmarking.graphs.graph_generation --plot=spatio_temporal_range_facets
python -m benchmarking.graphs.graph_generation --plot=spatial_range_dual_axis
python -m benchmarking.graphs.graph_generation --plot=temporal_range_grouped
python -m benchmarking.graphs.graph_generation --plot=spatial_range_dual_axis --threads=1,40
python -m benchmarking.graphs.graph_generation --plot=spatial_range_dual_axis --threads=1,40 --traffic=high
python -m benchmarking.graphs.graph_generation --plot=spatial_range_dual_axis --threads=1,40 --traffic=low
```

`spatio_temporal_range_facets` creates a 3-panel grouped bar chart for `1 day`, `1 week`, and `1 month` windows. Each panel uses area size (`Small`, `Medium`, `Large`) on the x-axis and median execution time on the y-axis.

`temporal_range_grouped` creates one grouped bar chart with `1 day`, `1 week`, and `1 month` on the x-axis. Inside each window group, bars are ordered by thread then series (`LineString`, `CellString`) to mirror the spatial-range comparison style.

`spatial_range_dual_axis` creates grouped stacked bars for area size (`Small`, `Medium`, `Large`) where the solid segment is low-traffic median (`area_id` 4/5/6) and the textured segment above it extends to the high-traffic median (`area_id` 1/2/3). Use `--threads=` to limit the shown thread runs (for example `--threads=1,40`).

For a less cluttered spatial chart, use `--traffic=high` or `--traffic=low` to render only one traffic class. If `--traffic=` is passed multiple times, the last value is used.

