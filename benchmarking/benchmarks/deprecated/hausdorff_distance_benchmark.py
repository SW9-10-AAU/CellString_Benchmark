from benchmarking.core import ValueBenchmark
from benchmarking.table_config import TRAJECTORY_CS_TABLE, TRAJECTORY_LS_TABLE

SQL = """
WITH cs AS (
    SELECT trajectory_id, list(cell_z21) AS cells
    FROM {trajectory_cs_table}
    GROUP BY trajectory_id
)
SELECT
    CST_HausdorffDistance(cs.cells, ls.geom, 21)
FROM {trajectory_ls_table} ls
JOIN cs
    ON ls.trajectory_id = cs.trajectory_id
WHERE
    ls.trajectory_id = ?;
"""

SQL = SQL.format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
)

BENCHMARK = ValueBenchmark(
    name="Hausdorff Distance between CellString and LineString",
    sql=SQL,
    with_trajectory_ids=True,
    iterate_trajectory_ids=True,
)
