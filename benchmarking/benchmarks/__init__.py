from benchmarking.benchmarks.spatial_range_benchmark import SPATIAL_RANGE_BENCHMARKS
from benchmarking.benchmarks.spatio_temporal_range_benchmark import (
    SPATIO_TEMPORAL_RANGE_BENCHMARKS,
)
from benchmarking.benchmarks.temporal_range_benchmark import TEMPORAL_RANGE_BENCHMARKS
from benchmarking.benchmarks.transit_query_benchmark import TRANSIT_QUERY_BENCHMARKS

RUN_PLAN = [
    *TEMPORAL_RANGE_BENCHMARKS,
    *SPATIAL_RANGE_BENCHMARKS,
    *SPATIO_TEMPORAL_RANGE_BENCHMARKS,
    *TRANSIT_QUERY_BENCHMARKS,
]
