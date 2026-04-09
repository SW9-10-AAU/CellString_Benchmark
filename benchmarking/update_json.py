import json
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from benchmarking.connect import connect_to_db
from benchmarking.table_config import TRAJECTORY_CS_TABLE

JSON_PATH = Path("benchmarking/benchmark_results/run_20251209_095304.json")
TABLE = TRAJECTORY_CS_TABLE


def _collect_samples(node: Dict) -> List[int]:
    samples = []
    if not isinstance(node, dict):
        return samples
    for sample in node.get("samples", []):
        traj_id = sample.get("trajectory_id")
        if traj_id is None:
            continue
        try:
            samples.append(int(traj_id))
        except (TypeError, ValueError):
            continue
    return samples


def load_ids() -> Tuple[Dict, List[int]]:
    data = json.loads(JSON_PATH.read_text())
    ids = set()
    for bench in data.get("benchmarks", []):
        result = bench.get("result", {})
        ids.update(_collect_samples(result.get("st")))
        ids.update(_collect_samples(result.get("cst")))
        for area_runs in result.get("per_area_results", {}).values():
            if not isinstance(area_runs, dict):
                continue
            for run in area_runs.values():
                ids.update(_collect_samples(run))
    for traj_id in data.get("meta", {}).get("trajectory_ids", []):
        try:
            ids.add(int(traj_id))
        except (TypeError, ValueError):
            continue
    return data, sorted(ids)


def fetch_trajectory_cardinality(conn, ids: List[int]) -> Dict[int, int]:
    if not ids:
        return {}
    placeholders = ", ".join(["?"] * len(ids))
    rows = conn.execute(
        f"""
        SELECT trajectory_id, COUNT(*)
        FROM {TABLE}
        WHERE trajectory_id IN ({placeholders})
        GROUP BY trajectory_id
        """,
        ids,
    ).fetchall()
    return {int(traj_id): int(count) for traj_id, count in rows if count is not None}


def embed(data: Dict, cardinalities: Dict[int, int]) -> None:
    meta = data.setdefault("meta", {})
    meta["trajectory_cardinalities"] = {
        str(traj_id): count for traj_id, count in sorted(cardinalities.items())
    }


if __name__ == "__main__":
    load_dotenv()
    data, ids = load_ids()
    if not ids:
        raise SystemExit("No trajectory IDs found in the report.")
    conn = connect_to_db()
    try:
        cardinalities = fetch_trajectory_cardinality(conn, ids)
    finally:
        conn.close()
    embed(data, cardinalities)
    JSON_PATH.write_text(json.dumps(data, indent=2))
    print(f"Updated {JSON_PATH} with trajectory cardinalities for {len(ids)} trajectories.")
