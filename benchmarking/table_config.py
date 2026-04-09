from __future__ import annotations

import os


LINESTRING_SCHEMA = os.getenv("LINESTRING_SCHEMA", "p10")
CELLSTRING_SCHEMA = os.getenv("CELLSTRING_SCHEMA", "db_design1_v3")


def _ls_table(env_var: str, default_suffix: str) -> str:
    return os.getenv(env_var, f"{LINESTRING_SCHEMA}.{default_suffix}")


def _cs_table(env_var: str, default_suffix: str) -> str:
    return os.getenv(env_var, f"{CELLSTRING_SCHEMA}.{default_suffix}")


TRAJECTORY_LS_TABLE = _ls_table("TRAJECTORY_LS_TABLE", "trajectory_ls")
TRAJECTORY_CS_TABLE = _cs_table("TRAJECTORY_CS_TABLE", "trajectory_cs")

STOP_POLY_TABLE = _ls_table("STOP_POLY_TABLE", "stop_poly")
STOP_CS_TABLE = _cs_table("STOP_CS_TABLE", "stop_cs")

AREA_POLY_TABLE = _ls_table("AREA_POLY_TABLE", "area_poly")
AREA_CS_TABLE = _cs_table("AREA_CS_TABLE", "area_cs")

CROSSING_LS_TABLE = _ls_table("CROSSING_LS_TABLE", "crossing_ls")
CROSSING_CS_TABLE = _cs_table("CROSSING_CS_TABLE", "crossing_cs")

TRAJECTORY_ID_SOURCE_TABLE = os.getenv(
    "TRAJECTORY_ID_SOURCE_TABLE", TRAJECTORY_CS_TABLE
)
STOP_ID_SOURCE_TABLE = os.getenv("STOP_ID_SOURCE_TABLE", STOP_CS_TABLE)
AREA_ID_SOURCE_TABLE = os.getenv("AREA_ID_SOURCE_TABLE", AREA_POLY_TABLE)
