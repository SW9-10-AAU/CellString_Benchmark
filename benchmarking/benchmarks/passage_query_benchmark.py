from __future__ import annotations

from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.table_config import (
    CROSSING_CS_TABLE,
    CROSSING_LS_TABLE,
    TRAJECTORY_CS_TABLE,
    TRAJECTORY_LS_TABLE,
)

ST_SETUP_SQL = """
SET VARIABLE crossing_id_a = ?;
SET VARIABLE crossing_id_b = ?;
SET VARIABLE crossing_id_c = ?;
"""

ST_SQL = """
SELECT
    traj.trajectory_id,
    traj.mmsi
FROM {trajectory_ls_table} AS traj,
     {crossing_ls_table} AS crossingA,
     {crossing_ls_table} AS crossingB,
     {crossing_ls_table} AS crossingC
WHERE crossingA.crossing_id = getvariable('crossing_id_a')
  AND crossingB.crossing_id = getvariable('crossing_id_b')
  AND crossingC.crossing_id = getvariable('crossing_id_c')
  AND ST_Intersects(traj.geom, crossingA.geom)
  AND ST_Intersects(traj.geom, crossingB.geom)
  AND ST_Intersects(traj.geom, crossingC.geom);
""".format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    crossing_ls_table=CROSSING_LS_TABLE,
)

CST_SETUP_SQL = """
SET VARIABLE crossing_id_a = ?;
SET VARIABLE crossing_id_b = ?;
SET VARIABLE crossing_id_c = ?;
"""

CST_SQL = """
SELECT
    t.trajectory_id,
    t.mmsi
FROM {trajectory_cs_table} t
JOIN {crossing_cs_table} c ON t.cell_z21 = c.cell_z21
WHERE c.crossing_id IN (
    getvariable('crossing_id_a'),
    getvariable('crossing_id_b'),
    getvariable('crossing_id_c')
)
GROUP BY t.trajectory_id, t.mmsi
HAVING COUNT(DISTINCT c.crossing_id) = 3;
""".format(
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    crossing_cs_table=CROSSING_CS_TABLE,
)


def build_passage_query_benchmark(
    crossing_id_a: int,
    crossing_id_b: int,
    crossing_id_c: int,
) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"Passage query - crossings {crossing_id_a},{crossing_id_b},{crossing_id_c}",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        st_setup_sql=ST_SETUP_SQL,
        cst_setup_sql=CST_SETUP_SQL,
        st_setup_params=(crossing_id_a, crossing_id_b, crossing_id_c),
        cst_setup_params=(crossing_id_a, crossing_id_b, crossing_id_c),
        params=tuple(),
        repeats=5,
    )


PASSAGE_QUERY_BENCHMARKS: List[TimeBenchmark] = [
    build_passage_query_benchmark(7, 11, 14),
]
