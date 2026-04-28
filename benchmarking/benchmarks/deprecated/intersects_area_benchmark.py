from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    AREA_CS_TABLE,
    REGION_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)

ST_SQL = """
SELECT
    traj.trajectory_id
FROM
    {trajectory_ls_table} AS traj,
    {area_poly_table} AS area
WHERE area.region_id = ?
    AND ST_Intersects(traj.geom, area.geom);
"""

ST_SQL = ST_SQL.format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    region_poly_table=REGION_POLY_TABLE,
)

CST_SQL = """
SELECT
    traj.trajectory_id
FROM
    {trajectory_cs_table} AS traj
JOIN {area_cs_table} AS area
    ON traj.cell_z21 = area.cell_z21
WHERE area.region_id = ?
;
"""

CST_SQL = CST_SQL.format(
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    area_cs_table=AREA_CS_TABLE,
)


BENCHMARK = TimeBenchmark(
    name="Find trajectories that intersects an area",
    st_sql=ST_SQL,
    cst_sql=CST_SQL,
    repeats=2,
    use_region_ids=True,
)
