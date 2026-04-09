from benchmarking.core import ValueBenchmark
from benchmarking.table_config import TRAJECTORY_CS_TABLE, TRAJECTORY_LS_TABLE

def _build_sql(cellstring_table: str) -> str:
    return f"""
WITH cs AS (
    SELECT trajectory_id, list(cell_z21) AS cells
    FROM {cellstring_table}
    GROUP BY trajectory_id
),
WITH containment AS (
    SELECT
        ls.trajectory_id,
        NOT ST_Contains(CST_AsMultiPolygon(cs.cells, 21), ls.geom) AS violation
    FROM {TRAJECTORY_LS_TABLE} ls
    JOIN cs
        ON ls.trajectory_id = cs.trajectory_id
    WHERE ls.trajectory_id IN (SELECT UNNEST(?))
)
SELECT
    'not_contained_pct' AS label,
    100.0 * CAST(SUM(CASE WHEN violation THEN 1 ELSE 0 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS value
FROM containment;
"""


LINESTRING_CONTAINMENT_BENCHMARK = ValueBenchmark(
    name="LineString containment vs CellString",
    sql=_build_sql(TRAJECTORY_CS_TABLE),
    with_trajectory_ids=True,
)
