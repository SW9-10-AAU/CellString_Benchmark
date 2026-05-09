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
    raw = os.getenv("TEMPORAL_RANGE_START", "2025-10-01 00:00:00")
    # Accept both 'YYYY-MM-DD HH:MM:SS' and full ISO-8601 values.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _window(start: datetime, days: int) -> tuple[str, str]:
    end = start + timedelta(days=days)
    return (start.isoformat(sep=" "), end.isoformat(sep=" "))


ST_SETUP_SQL = """
SET VARIABLE ts_period_start = CAST(? AS TIMESTAMP);
SET VARIABLE ts_period_end = CAST(? AS TIMESTAMP);
"""

ST_SQL = """
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
WHERE t.ts_start <= getvariable('ts_period_end')
  AND t.ts_end >= getvariable('ts_period_start')
    
UNION ALL
    
SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} AS s
WHERE s.ts_start <= getvariable('ts_period_end')
  AND s.ts_end >= getvariable('ts_period_start');
"""

ST_SQL = ST_SQL.format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)


CST_SETUP_SQL = """
SET VARIABLE ts_period_start = CAST(? AS TIMESTAMP);
SET VARIABLE ts_period_end = CAST(? AS TIMESTAMP);
"""

CST_SQL = """
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
WHERE t.ts_entry <= getvariable('ts_period_end')
  AND t.ts_exit >= getvariable('ts_period_start')

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_cs_table} AS s
WHERE s.ts_start <= getvariable('ts_period_end')
  AND s.ts_end >= getvariable('ts_period_start');
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
        st_setup_sql=ST_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(t_start, t_end),
        cst_setup_params=(t_start, t_end),
        params=tuple(),
        repeats=5,
    )


TEMPORAL_RANGE_BENCHMARKS: List[TimeBenchmark] = [
    build_temporal_range_benchmark("1", 1),
    build_temporal_range_benchmark("7", 7),
    build_temporal_range_benchmark("30", 30),
    build_temporal_range_benchmark("180", 180),
]
