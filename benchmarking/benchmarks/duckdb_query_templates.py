from benchmarking.core import TimeBenchmark, ValueBenchmark

# Replace these template queries with your real LineString and CellString queries.
ST_SQL_TEMPLATE = """
SELECT 1 AS trajectory_id
WHERE 1 = 1;
"""

CST_SQL_TEMPLATE = """
SELECT 1 AS trajectory_id
WHERE 1 = 1;
"""

VALUE_SQL_TEMPLATE = """
SELECT 0.0 AS value;
"""

DUCKDB_TEMPLATE_BENCHMARKS = [
    TimeBenchmark(
        name="Template benchmark: LineString vs CellString",
        st_sql=ST_SQL_TEMPLATE,
        cst_sql=CST_SQL_TEMPLATE,
        repeats=3,
    ),
    ValueBenchmark(
        name="Template benchmark: Value query",
        sql=VALUE_SQL_TEMPLATE,
    ),
]

