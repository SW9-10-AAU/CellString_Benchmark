from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    AREA_CS_TABLE,
    AREA_POLY_TABLE,
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)

ST_SETUP_SQL = """
SET VARIABLE area_id = ?;
"""

ST_SQL = """
WITH selected_area AS (
    SELECT area_id, geom
    FROM {area_poly_table}
    WHERE area_id = getvariable('area_id')
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, a.area_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
JOIN selected_area AS a ON ST_Intersects(t.geom, a.geom)
UNION ALL
SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, a.area_id, 'stop' AS source
FROM {stop_poly_table} AS s
JOIN selected_area AS a ON ST_Intersects(s.geom, a.geom);
""".format(
    area_poly_table=AREA_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SETUP_SQL = """
SET VARIABLE area_id = ?;
"""

CST_SQL = """
WITH selected_area AS (
    SELECT area_id, cell_z21
    FROM {area_cs_table}
    WHERE area_id = getvariable('area_id')
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, a.area_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
JOIN selected_area AS a ON t.cell_z21 = a.cell_z21

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, a.area_id, 'stop' AS source
FROM {stop_cs_table} AS s
JOIN selected_area AS a ON s.cell_z21 = a.cell_z21;
""".format(
    area_cs_table=AREA_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_spatial_range_benchmark(area_id: int) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"Spatial range query - area {area_id}",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        st_setup_sql=ST_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(area_id,),
        cst_setup_params=(area_id,),
        params=tuple(),
        repeats=5,
    )


SPATIAL_RANGE_BENCHMARKS = [
    build_spatial_range_benchmark(area_id) for area_id in (1, 2, 3, 7, 8, 9)
]
