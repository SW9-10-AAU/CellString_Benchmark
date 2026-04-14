from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    AREA_CS_TABLE,
    AREA_POLY_TABLE,
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)


def _parse_start() -> datetime:
    raw = os.getenv("TEMPORAL_RANGE_START", "2025-12-01 00:00:00")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _window(start: datetime, days: int) -> tuple[str, str]:
    end = start + timedelta(days=days)
    return (start.isoformat(sep=" "), end.isoformat(sep=" "))


ST_SQL = """
WITH bounds AS (
    SELECT CAST(? AS TIMESTAMP) AS t_start, CAST(? AS TIMESTAMP) AS t_end
),
selected_areas AS (
    SELECT area_id, geom
    FROM {area_poly_table}
    WHERE area_id = ?
)
SELECT DISTINCT t.mmsi, t.trajectory_id, CAST(NULL AS INTEGER) AS stop_id, a.area_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
JOIN selected_areas AS a ON ST_Intersects(t.geom, a.geom)
CROSS JOIN bounds AS b
WHERE t.ts_start <= b.t_end
  AND t.ts_end >= b.t_start
UNION ALL
SELECT DISTINCT s.mmsi, CAST(NULL AS INTEGER) AS trajectory_id, s.stop_id, a.area_id, 'stop' AS source
FROM {stop_poly_table} AS s
JOIN selected_areas AS a ON ST_Intersects(s.geom, a.geom)
CROSS JOIN bounds AS b
WHERE s.ts_start <= b.t_end
  AND s.ts_end >= b.t_start;
"""

ST_SQL = ST_SQL.format(
    area_poly_table=AREA_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SQL = """
WITH bounds AS (
    SELECT CAST(? AS TIMESTAMP) AS t_start, CAST(? AS TIMESTAMP) AS t_end
),
selected_area AS (
    SELECT area_id, cell_z21
    FROM {area_cs_table}
    WHERE area_id = ?
)
SELECT DISTINCT t.mmsi, t.trajectory_id, CAST(NULL AS INTEGER) AS stop_id, a.area_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
JOIN selected_area AS a ON t.cell_z21 = a.cell_z21
CROSS JOIN bounds AS b
WHERE t.ts BETWEEN b.t_start AND b.t_end
UNION ALL
SELECT DISTINCT s.mmsi, CAST(NULL AS INTEGER) AS trajectory_id, s.stop_id, a.area_id, 'stop' AS source
FROM {stop_cs_table} AS s
JOIN selected_area AS a ON s.cell_z21 = a.cell_z21
CROSS JOIN bounds AS b
WHERE s.ts_start <= b.t_end
  AND s.ts_end >= b.t_start;
"""

CST_SQL = CST_SQL.format(
    area_cs_table=AREA_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_spatio_temporal_range_benchmark(label: str, days: int, area_id: int) -> TimeBenchmark:
    start = _parse_start()
    t_start, t_end = _window(start, days)
    return TimeBenchmark(
        name=f"Spatio-temporal range query - area {area_id} ({label})",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        params=(t_start, t_end, area_id),
        repeats=5,
    )


SPATIO_TEMPORAL_RANGE_BENCHMARKS: List[TimeBenchmark] = [
    build_spatio_temporal_range_benchmark("1 day", 1, area_id)
    for area_id in (1, 2, 3)
] + [
    build_spatio_temporal_range_benchmark("1 week", 7, area_id)
    for area_id in (1, 2, 3)
] + [
    build_spatio_temporal_range_benchmark("1 month", 30, area_id)
    for area_id in (1, 2, 3)
]

