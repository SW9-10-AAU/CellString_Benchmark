from __future__ import annotations

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)

ST_SQL = """
WITH query_traj AS (
    SELECT mmsi, geom, ts_start, ts_end
    FROM {trajectory_ls_table}
    WHERE trajectory_id = ?
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} t
JOIN query_traj q ON ST_Intersects(t.geom, q.geom)
WHERE t.mmsi <> q.mmsi
  AND t.ts_start <= q.ts_end
  AND t.ts_end >= q.ts_start

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} s
JOIN query_traj q ON ST_Intersects(s.geom, q.geom)
WHERE s.mmsi <> q.mmsi
  AND s.ts_start <= q.ts_end
  AND s.ts_end >= q.ts_start;
""".format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SQL = """
WITH query_traj AS (
    SELECT mmsi, trajectory_id, ts, delta_sec, cell_z21
    FROM {trajectory_cs_table}
    WHERE trajectory_id = ?
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_cs_table} t
JOIN query_traj q ON t.cell_z21 = q.cell_z21
WHERE t.mmsi <> q.mmsi
  AND t.ts <= q.ts + (INTERVAL (q.delta_sec) SECOND)
  AND t.ts + (INTERVAL (t.delta_sec) SECOND) >= q.ts

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_cs_table} AS s
JOIN query_traj q ON s.cell_z21 = q.cell_z21
WHERE s.mmsi <> q.mmsi
  AND s.ts_start <= q.ts + (INTERVAL (q.delta_sec) SECOND)
  AND s.ts_end >= q.ts;
""".format(
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)

def build_spatio_temporal_join_benchmark() -> TimeBenchmark:
    return TimeBenchmark(
        name="Spatio-temporal join (ID temporal)",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        with_trajectory_ids=True,
    )

SPATIO_TEMPORAL_JOIN_BENCHMARKS = [
    build_spatio_temporal_join_benchmark()
]
