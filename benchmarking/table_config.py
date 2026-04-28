from __future__ import annotations

import os

LINESTRING_SCHEMA = os.getenv("LINESTRING_SCHEMA", "p10_ls")
CELLSTRING_SCHEMA = os.getenv("CELLSTRING_SCHEMA", "p10_cs")


def _ls_table(env_var: str, default_suffix: str) -> str:
    return os.getenv(env_var, f"{LINESTRING_SCHEMA}.{default_suffix}")


def _cs_table(env_var: str, default_suffix: str) -> str:
    return os.getenv(env_var, f"{CELLSTRING_SCHEMA}.{default_suffix}")


TRAJECTORY_LS_TABLE = _ls_table("TRAJECTORY_LS_TABLE", "trajectory_ls")
TRAJECTORY_CS_TABLE = _cs_table("TRAJECTORY_CS_TABLE", "trajectory_cs")

STOP_POLY_TABLE = _ls_table("STOP_POLY_TABLE", "stop_poly")
STOP_CS_TABLE = _cs_table("STOP_CS_TABLE", "stop_cs")

REGION_POLY_TABLE = _ls_table("REGION_POLY_TABLE", "region_poly")
REGION_CS_TABLE = _cs_table("REGION_CS_TABLE", "region_cs")

PASSAGE_LS_TABLE = _ls_table("PASSAGE_LS_TABLE", "passage_ls")
PASSAGE_CS_TABLE = _cs_table("PASSAGE_CS_TABLE", "passage_cs")

TRAJECTORY_ID_SOURCE_TABLE = os.getenv(
    "TRAJECTORY_ID_SOURCE_TABLE", TRAJECTORY_CS_TABLE
)
STOP_ID_SOURCE_TABLE = os.getenv("STOP_ID_SOURCE_TABLE", STOP_CS_TABLE)
REGION_ID_SOURCE_TABLE = os.getenv("REGION_ID_SOURCE_TABLE", REGION_POLY_TABLE)
PASSAGE_ID_SOURCE_TABLE = os.getenv("PASSAGE_ID_SOURCE_TABLE", PASSAGE_LS_TABLE)
