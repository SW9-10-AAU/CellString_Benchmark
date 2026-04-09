from benchmarking.core import TimeBenchmark
from benchmarking.table_config import STOP_CS_TABLE, STOP_POLY_TABLE, TRAJECTORY_CS_TABLE, TRAJECTORY_LS_TABLE

ST_SQL = """
WITH ref AS (
    SELECT mmsi,
           stop_id,
           geom AS ref_geom,
           ts_start AS ref_start,
           ts_end   AS ref_end
    FROM {stop_poly_table}
    WHERE stop_id = ?
)

-- 0. Reference stop (always returned)
SELECT
    'REFERENCE STOP' as type,
    r.mmsi,
    CAST(NULL AS BIGINT) AS trajectory_id,
    r.stop_id,
    CAST(NULL AS DOUBLE) AS overlap_minutes
FROM ref r

UNION

-- 1. Trajectory matches
SELECT DISTINCT
    'INTERSECTING TRAJECTORY' as type,
    t.mmsi,
    t.trajectory_id,
    CAST(NULL AS BIGINT) AS stop_id,
    ROUND(EXTRACT(
        EPOCH FROM (
            LEAST(t.ts_end,   r.ref_end)
          - GREATEST(t.ts_start, r.ref_start)
        )
    ) / 60.0, 2) AS overlap_minutes
FROM ref r
JOIN {trajectory_ls_table} t
  ON t.mmsi <> r.mmsi
 AND ST_Intersects(t.geom, r.ref_geom)
 AND t.ts_end   >= r.ref_start
 AND t.ts_start <= r.ref_end

UNION

-- 2. Stop matches
SELECT DISTINCT
    'INTERSECTING STOP' as type,
    s.mmsi,
    CAST(NULL AS BIGINT) AS trajectory_id,
    s.stop_id,
    ROUND(EXTRACT(
        EPOCH FROM (
            LEAST(s.ts_end,   r.ref_end)
          - GREATEST(s.ts_start, r.ref_start)
        )
    ) / 60.0, 2) AS overlap_minutes
FROM ref r
JOIN {stop_poly_table} s
  ON s.mmsi <> r.mmsi
 AND ST_Intersects(s.geom, r.ref_geom)
 AND s.ts_end   >= r.ref_start
 AND s.ts_start <= r.ref_end;
"""

ST_SQL = ST_SQL.format(
    stop_poly_table=STOP_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
)

CST_SQL = """
WITH ref AS (
    SELECT mmsi,
           stop_id,
           cell_z21 AS ref_cell,
           ts_start AS ref_start,
           ts_end   AS ref_end
    FROM {stop_cs_table}
    WHERE stop_id = ?
)

-- 0. Reference stop (always returned)
SELECT
    'REFERENCE STOP' as type,
    r.mmsi,
    CAST(NULL AS BIGINT) AS trajectory_id,
    r.stop_id,
    CAST(NULL AS DOUBLE) AS overlap_minutes
FROM ref r

UNION

-- 1. Trajectory matches
SELECT DISTINCT
    'INTERSECTING TRAJECTORY' as type,
    t.mmsi,
    t.trajectory_id,
    CAST(NULL AS BIGINT) AS stop_id,
    ROUND(EXTRACT(
        EPOCH FROM (
            LEAST(t.ts_end,   r.ref_end)
          - GREATEST(t.ts_start, r.ref_start)
        )
    ) / 60.0, 2) AS overlap_minutes
FROM ref r
JOIN {trajectory_cs_table} t
  ON t.mmsi <> r.mmsi
 AND t.cell_z21 = r.ref_cell
 AND t.ts_end   >= r.ref_start
 AND t.ts_start <= r.ref_end

UNION

-- 2. Stop matches
SELECT DISTINCT
    'INTERSECTING STOP' as type,
    s.mmsi,
    CAST(NULL AS BIGINT) AS trajectory_id,
    s.stop_id,
    ROUND(EXTRACT(
        EPOCH FROM (
            LEAST(s.ts_end,   r.ref_end)
          - GREATEST(s.ts_start, r.ref_start)
        )
    ) / 60.0, 2) AS overlap_minutes
FROM ref r
JOIN {stop_cs_table} s
  ON s.mmsi <> r.mmsi
 AND s.cell_z21 = r.ref_cell
 AND s.ts_end   >= r.ref_start
 AND s.ts_start <= r.ref_end;
"""

CST_SQL = CST_SQL.format(
    stop_cs_table=STOP_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
)

BENCHMARK = TimeBenchmark(
    name="Find trajectories and stops that intersect a given stop spatially and temporally",
    st_sql=ST_SQL,
    cst_sql=CST_SQL,
    with_stop_ids=True,
)

