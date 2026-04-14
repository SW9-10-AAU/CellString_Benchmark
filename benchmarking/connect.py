import os
from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class DuckDBConfig:
    db_path: str
    threads: int = 1


def connect_to_db(config: DuckDBConfig | None = None) -> duckdb.DuckDBPyConnection:
    db_path = os.getenv("DUCKDB_PATH", "cellstring.duckdb")
    threads = int(os.getenv("DUCKDB_THREADS", "1"))
    resolved = config or DuckDBConfig(db_path=db_path, threads=threads)

    conn = duckdb.connect(resolved.db_path)
    conn.execute(f"PRAGMA threads={max(1, resolved.threads)}")
    conn.execute("PRAGMA enable_progress_bar=false")

    spatial_error: Exception | None = None
    try:
        conn.execute("INSTALL spatial")
    except Exception:
        # INSTALL can fail on offline servers if extension is already present locally.
        pass

    try:
        conn.execute("LOAD spatial")
        conn.execute("SELECT ST_Intersects(ST_Point(0, 0), ST_Point(0, 0))")
    except Exception as exc:
        spatial_error = exc

    if spatial_error is not None:
        raise RuntimeError(
            "DuckDB spatial extension is required but could not be loaded. "
            "Run these once in DuckDB: INSTALL spatial; LOAD spatial; "
            "then rerun benchmarks."
        ) from spatial_error

    return conn
