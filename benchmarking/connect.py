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

    try:
        conn.execute("LOAD spatial")
    except Exception:
        # Spatial extension is optional in case it is not installed on the server image.
        pass

    return conn
