from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    REGION_CS_TABLE,
    REGION_POLY_TABLE,
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)

ST_SETUP_SQL = """
SET VARIABLE region_id = ?;
SET VARIABLE query_region = (
    SELECT geom
    FROM {region_poly_table}
    WHERE region_id = getvariable('region_id'));
"""

ST_SETUP_SQL = ST_SETUP_SQL.format(region_poly_table=REGION_POLY_TABLE)

ST_SQL = """
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
WHERE ST_Intersects(t.geom, getvariable('query_region'))

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} AS s
WHERE ST_Intersects(s.geom, getvariable('query_region'));
""".format(
    region_poly_table=REGION_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

ST_NO_RTREE_SETUP_SQL = """
SET VARIABLE region_id = ?;
"""

ST_NO_RTREE_SQL = """
WITH query_region AS (
    SELECT region_id, geom
    FROM {region_poly_table}
    WHERE region_id = getvariable('region_id')
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
JOIN query_region AS q ON ST_Intersects(t.geom, q.geom)

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} AS s
JOIN query_region AS q ON ST_Intersects(s.geom, q.geom);
""".format(
    region_poly_table=REGION_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SETUP_SQL = """
SET VARIABLE region_id = ?;
"""

CST_SQL = """
WITH query_region AS (
    SELECT region_id, cell_z21
    FROM {region_cs_table}
    WHERE region_id = getvariable('region_id')
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
JOIN query_region AS r ON t.cell_z21 = r.cell_z21

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_cs_table} AS s
JOIN query_region AS r ON s.cell_z21 = r.cell_z21;
""".format(
    region_cs_table=REGION_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_spatial_range_benchmark(region_id: int) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"Spatial range query - region {region_id}",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        st_setup_sql=ST_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(region_id,),
        cst_setup_params=(region_id,),
        params=tuple(),
        repeats=5,
    )


def build_spatial_range_no_rtree_benchmark(region_id: int) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"Spatial range query (no rtree) - region {region_id}",
        st_sql=ST_NO_RTREE_SQL,
        cst_sql=CST_SQL,
        st_setup_sql=ST_NO_RTREE_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(region_id,),
        cst_setup_params=(region_id,),
        params=tuple(),
        repeats=5,
    )


SPATIAL_RANGE_BENCHMARKS = [
    build_spatial_range_benchmark(region_id) for region_id in (1, 2, 3, 4, 5, 6)
]

SPATIAL_RANGE_NO_RTREE_BENCHMARKS = [
    build_spatial_range_no_rtree_benchmark(region_id) for region_id in (1, 2, 3, 4, 5, 6)
]

