from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    REGION_CS_TABLE,
    REGION_POLY_TABLE,
    STOP_CS_TABLE,
    STOP_POLY_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)


def _parse_start() -> datetime:
    raw = os.getenv("TEMPORAL_RANGE_START", "2026-02-01 00:00:00")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _window(start: datetime, days: int) -> tuple[str, str]:
    end = start + timedelta(days=days)
    return (start.isoformat(sep=" "), end.isoformat(sep=" "))


ST_SETUP_SQL = """
SET VARIABLE ts_period_start = CAST(? AS TIMESTAMP);
SET VARIABLE ts_period_end = CAST(? AS TIMESTAMP);
SET VARIABLE region_id = ?;
SET VARIABLE query_region = (
    SELECT geom
    FROM {region_poly_table}
    WHERE region_id = getvariable('region_id')
);
"""

ST_SETUP_SQL = ST_SETUP_SQL.format(region_poly_table=REGION_POLY_TABLE)

ST_SQL = """
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, 'trajectory' AS source
FROM {trajectory_ls_table} AS t
WHERE ST_Intersects(t.geom, getvariable('query_region'))
AND t.ts_start <= getvariable('ts_period_end') AND t.ts_end >= getvariable('ts_period_start')

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, 'stop' AS source
FROM {stop_poly_table} AS s
WHERE ST_Intersects(s.geom, getvariable('query_region'))
AND s.ts_start <= getvariable('ts_period_end') AND s.ts_end >= getvariable('ts_period_start');
"""

ST_SQL = ST_SQL.format(
    region_poly_table=REGION_POLY_TABLE,
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    stop_poly_table=STOP_POLY_TABLE,
)

CST_SETUP_SQL = """
SET VARIABLE ts_period_start = CAST(? AS TIMESTAMP);
SET VARIABLE ts_period_end = CAST(? AS TIMESTAMP);
SET VARIABLE region_id = ?;
"""

CST_SQL = """
WITH query_region AS (
    SELECT region_id, cell_z21
    FROM {region_cs_table}
    WHERE region_id = getvariable('region_id')
)
SELECT DISTINCT t.mmsi, t.trajectory_id, NULL::INTEGER AS stop_id, r.region_id, 'trajectory' AS source
FROM {trajectory_cs_table} AS t
JOIN query_region AS r ON t.cell_z21 = r.cell_z21
WHERE t.ts <= getvariable('ts_period_end')
  AND t.ts + (INTERVAL (t.delta_sec) SECOND) >= getvariable('ts_period_start')

UNION ALL

SELECT DISTINCT s.mmsi, NULL::INTEGER AS trajectory_id, s.stop_id, r.region_id, 'stop' AS source
FROM {stop_cs_table} AS s
JOIN query_region AS r ON s.cell_z21 = r.cell_z21
WHERE s.ts_start <= getvariable('ts_period_end')
  AND s.ts_end >= getvariable('ts_period_start');
"""

CST_SQL = CST_SQL.format(
    region_cs_table=REGION_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_spatio_temporal_range_benchmark(
    label: str, days: int, region_id: int
) -> TimeBenchmark:
    start = _parse_start()
    t_start, t_end = _window(start, days)
    return TimeBenchmark(
        name=f"Spatio-temporal range query - region {region_id} ({label})",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        st_setup_sql=ST_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(t_start, t_end, region_id),
        cst_setup_params=(t_start, t_end, region_id),
        params=tuple(),
        repeats=5,
    )


SPATIO_TEMPORAL_RANGE_BENCHMARKS: List[TimeBenchmark] = (
    [
        build_spatio_temporal_range_benchmark("1 day", 1, region_id)
        for region_id in (1, 2, 3, 4, 5, 6)
    ]
    + [
        build_spatio_temporal_range_benchmark("1 week", 7, region_id)
        for region_id in (1, 2, 3, 4, 5, 6)
    ]
    + [
        build_spatio_temporal_range_benchmark("1 month", 30, region_id)
        for region_id in (1, 2, 3, 4, 5, 6)
    ]
)
