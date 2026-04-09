from benchmarking.core import TimeBenchmark
from benchmarking.table_config import CROSSING_CS_TABLE, CROSSING_LS_TABLE, TRAJECTORY_CS_TABLE, TRAJECTORY_LS_TABLE

ST_SQL = """
SELECT
    traj.trajectory_id,
    traj.mmsi
FROM {trajectory_ls_table} AS traj,
     {crossing_ls_table} AS crossingA,
     {crossing_ls_table} AS crossingB,
     {crossing_ls_table} AS crossingC
WHERE crossingA.crossing_id = ?
  AND crossingB.crossing_id = ?
  AND crossingC.crossing_id = ?
  AND ST_Intersects(traj.geom, crossingA.geom)
  AND ST_Intersects(traj.geom, crossingB.geom)
  AND ST_Intersects(traj.geom, crossingC.geom);
"""

ST_SQL = ST_SQL.format(
    trajectory_ls_table=TRAJECTORY_LS_TABLE,
    crossing_ls_table=CROSSING_LS_TABLE,
)

CST_SQL = """
SELECT
    traj.trajectory_id,
    traj.mmsi
FROM {trajectory_cs_table} AS traj
WHERE EXISTS (
        SELECT 1
        FROM {crossing_cs_table} AS crossingA
        WHERE crossingA.crossing_id = ?
          AND crossingA.cell_z21 = traj.cell_z21
    )
  AND EXISTS (
        SELECT 1
        FROM {crossing_cs_table} AS crossingB
        WHERE crossingB.crossing_id = ?
          AND crossingB.cell_z21 = traj.cell_z21
    )
  AND EXISTS (
        SELECT 1
        FROM {crossing_cs_table} AS crossingC
        WHERE crossingC.crossing_id = ?
          AND crossingC.cell_z21 = traj.cell_z21
    );
"""

CST_SQL = CST_SQL.format(
    trajectory_cs_table=TRAJECTORY_CS_TABLE,
    crossing_cs_table=CROSSING_CS_TABLE,
)


def build_via_benchmark(label: str, crossings: tuple[int, int, int]) -> TimeBenchmark:
    return TimeBenchmark(
        name=f"{label}",
        st_sql=ST_SQL,
        cst_sql=CST_SQL,
        params=crossings,
        repeats=5,
    )


CROSSING_VIA_BENCHMARKS = [
    build_via_benchmark("Skagen-Storebælt-Bornholm", (1, 2, 4)),
    build_via_benchmark("Skagen-Kattegat-Storebælt", (1, 6, 2))
]