from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)


def _parse_start() -> datetime:
    raw = os.getenv("TEMPORAL_RANGE_START", "2025-12-01 00:00:00")
    # Accept both 'YYYY-MM-DD HH:MM:SS' and full ISO-8601 values.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _window(start: datetime, days: int) -> tuple[str, str]:
    end = start + timedelta(days=days)
    return (start.isoformat(sep=" "), end.isoformat(sep=" "))


ST_SQL = """
WITH bounds AS (
    SELECT CAST(? AS TIMESTAMP) AS t_start, CAST(? AS TIMESTAMP) AS t_end
)
SELECT DISTINCT t.mmsi, t.trajectory_id, CAST(NULL AS INTEGER) AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
CROSS JOIN bounds AS b
WHERE t.ts_start <= b.t_end
  AND t.ts_end >= b.t_start
UNION ALL
SELECT DISTINCT s.mmsi, CAST(NULL AS INTEGER) AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} AS s
CROSS JOIN bounds AS b
WHERE s.ts_start <= b.t_end
  AND s.ts_end >= b.t_start;
"""

ST_SQL = ST_SQL.format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SQL = """
WITH bounds AS (
    SELECT CAST(? AS TIMESTAMP) AS t_start, CAST(? AS TIMESTAMP) AS t_end
)
SELECT DISTINCT t.mmsi, t.trajectory_id, CAST(NULL AS INTEGER) AS stop_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
CROSS JOIN bounds AS b
WHERE t.ts BETWEEN b.t_start AND b.t_end
UNION ALL
SELECT DISTINCT s.mmsi, CAST(NULL AS INTEGER) AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_cs_table} AS s
CROSS JOIN bounds AS b
WHERE s.ts_start <= b.t_end
  AND s.ts_end >= b.t_start;
"""

CST_SQL = CST_SQL.format(
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_temporal_range_benchmark(label: str, days: int) -> TimeBenchmark:
    start = _parse_start()
    t_start, t_end = _window(start, days)
    return TimeBenchmark(
        name=f"Temporal range query ({label})",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        params=(t_start, t_end),
        repeats=5,
    )


TEMPORAL_RANGE_BENCHMARKS: List[TimeBenchmark] = [
    build_temporal_range_benchmark("1 day", 1),
    build_temporal_range_benchmark("1 week", 7),
    build_temporal_range_benchmark("1 month", 30),
]
