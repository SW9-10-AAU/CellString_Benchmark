from __future__ import annotations

from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    REGION_CS_TABLE,
    STOP_CS_TABLE,
    TRAJECTORY_CS_TABLE,
)

ST_SQL = """
SELECT NULL WHERE FALSE;
"""

CST_SETUP_SQL = """
SET VARIABLE coverage_region_id = ?;
SET VARIABLE zoom = ?;
"""

CST_SQL = """
WITH query_region AS (
    SELECT DISTINCT CS_GetParentCell(cell_z21, 21, getvariable('zoom')) AS cell_z21
    FROM {region_cs_table}
    WHERE region_id = getvariable('coverage_region_id')
),
cs_vessel_footprint AS (
    SELECT DISTINCT mmsi, CS_GetParentCell(cell_z21, 21, getvariable('zoom')) AS cell_z21
    FROM {trajectory_cs_table}

    UNION ALL

    SELECT DISTINCT mmsi, CS_GetParentCell(cell_z21, 21, getvariable('zoom')) AS cell_z21
    FROM {stop_cs_table}
)
SELECT * FROM CS_CoverageByMMSI(query_region, cs_vessel_footprint);
""".format(
    region_cs_table=REGION_CS_TABLE,
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    stop_cs_table=STOP_CS_TABLE,
)


def build_coverage_mmsi_benchmark(region_id: int, zoom: int) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"CoverageByMMSI - region {region_id} (zoom {zoom})",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        cst_setup_params=(region_id, zoom),
        params=tuple(),
        repeats=5,
    )


COVERAGE_MMSI_ZOOMS: List[int] = [13, 14, 15, 16, 17, 18, 19]
COVERAGE_MMSI_REGION_ID = 7

COVERAGE_MMSI_BENCHMARKS: List[TimeBenchmark] = [
    build_coverage_mmsi_benchmark(COVERAGE_MMSI_REGION_ID, zoom)
    for zoom in COVERAGE_MMSI_ZOOMS
]
