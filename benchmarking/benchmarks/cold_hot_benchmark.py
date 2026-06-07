"""Cold/hot benchmark definitions.

Reuses the spatio-temporal range query TimeBenchmark objects to measure
the difference between cold (OS page cache cleared) and hot execution.
"""
from __future__ import annotations

from typing import List

from benchmarking.core import TimeBenchmark
from benchmarking.benchmarks.spatio_temporal_range_benchmark import (
    SPATIO_TEMPORAL_RANGE_BENCHMARKS,
)

# All spatio-temporal benchmarks are included by default.
# The cold/hot runner in cold_hot_main.py supports filtering via
# COLD_HOT_BENCHMARKS in .env if a subset is desired.
COLD_HOT_BENCHMARKS: List[TimeBenchmark] = list(SPATIO_TEMPORAL_RANGE_BENCHMARKS)
