from benchmarking.core import ValueBenchmark
from benchmarking.table_config import AREA_CS_TABLE, TRAJECTORY_CS_TABLE

TRAJECTORY_TABLE = TRAJECTORY_CS_TABLE

SQL_TEMPLATE = f"""
WITH area AS (
    SELECT
        list(cell_z21) AS cells,
        CAST(? AS INTEGER) AS area_id
    FROM {AREA_CS_TABLE}
    WHERE area_id = ?
)
SELECT
    area.area_id,
    coverage.mmsi,
    coverage.coverage_percent
FROM area
CROSS JOIN LATERAL CST_Coverage_ByMMSI(
    '{TRAJECTORY_TABLE}',
    21,
    area.cells
) AS coverage
ORDER BY coverage.coverage_percent DESC;
"""


def build_area_coverage_benchmark(area_id: int) -> ValueBenchmark:
    return ValueBenchmark(
        name=f"MMSI Coverage - Area {area_id}",
        sql=SQL_TEMPLATE,
        params=(area_id, area_id),
        capture_rows=True,
        row_field_names=["area_id", "mmsi", "coverage_percent"],
    )


AREA_MMSI_COVERAGE_BENCHMARKS = [build_area_coverage_benchmark(area_id) for area_id in (2, 3)]

