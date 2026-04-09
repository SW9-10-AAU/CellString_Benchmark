from benchmarking.core import TimeBenchmark
from benchmarking.table_config import TRAJECTORY_CS_TABLE, TRAJECTORY_LS_TABLE

ST_SQL = """
SELECT DISTINCT
    trajB.trajectory_id
FROM
    {trajectory_ls_table} AS trajA,
    {trajectory_ls_table} AS trajB
WHERE trajA.trajectory_id <> trajB.trajectory_id
    AND trajA.trajectory_id = ?
    AND ST_Intersects(trajA.geom, trajB.geom);
"""

ST_SQL = ST_SQL.format(trajectory_ls_table=TRAJECTORY_LS_TABLE)

CST_SQL = """
SELECT DISTINCT
    trajB.trajectory_id
FROM
    {trajectory_cs_table} AS trajA
JOIN {trajectory_cs_table} AS trajB
    ON trajA.cell_z21 = trajB.cell_z21
WHERE trajA.trajectory_id <> trajB.trajectory_id
    AND trajA.trajectory_id = ?
;
"""

CST_SQL = CST_SQL.format(trajectory_cs_table=TRAJECTORY_CS_TABLE)

BENCHMARK = TimeBenchmark(
    name="Find trajectories that intersects another trajectory",
    st_sql=ST_SQL,
    cst_sql=CST_SQL,
    with_trajectory_ids=True,
)

