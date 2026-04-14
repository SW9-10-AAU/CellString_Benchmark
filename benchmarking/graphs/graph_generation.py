import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px

OUTPUT_DIR = Path("benchmarking/graphs/output")
# Optional fixed input report. If None, newest run_*.json is used.
DEFAULT_REPORT_JSON: Optional[str] = None

LINESTRING_SERIES = "LineString"
LINESTRING_COLOR = px.colors.qualitative.Safe[0]
FALLBACK_CELLSTRING_SERIES = "CellString"
SERIES_COLOR_SEQUENCE = (
    px.colors.qualitative.Safe[1:]
    + px.colors.qualitative.Set2
    + px.colors.qualitative.Pastel
)
AREA_SIZE_LABELS = {
    1: "Small",
    2: "Medium",
    3: "Large",
}
SPATIO_TEMPORAL_NAME_PATTERN = re.compile(
    r"^Spatio-temporal range query - area\s+(?P<area_id>\d+)\s+\((?P<window>[^)]+)\)$",
    re.IGNORECASE,
)


def _next_output_path(base_name: str, extension: str = ".pdf") -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counter_file = OUTPUT_DIR / f".{base_name}_counter"
    last_index = 0
    if counter_file.exists():
        try:
            last_index = int(counter_file.read_text().strip())
        except ValueError:
            last_index = 0
    next_index = last_index + 1
    counter_file.write_text(str(next_index))
    return OUTPUT_DIR / f"{base_name}_{next_index}{extension}"


def _ensure_report_path(path_arg: Optional[str]) -> Path:
    if path_arg:
        candidate = Path(path_arg).expanduser()
        if not candidate.exists():
            raise FileNotFoundError(f"No report found at {candidate}")
        return candidate

    if DEFAULT_REPORT_JSON:
        candidate = Path(DEFAULT_REPORT_JSON).expanduser()
        if not candidate.exists():
            raise FileNotFoundError(f"No report found at {candidate}")
        return candidate

    report_dir = Path("benchmarking/benchmark_results")
    if not report_dir.exists():
        raise FileNotFoundError(f"No report found at {report_dir}")
    reports = sorted(report_dir.glob("run_*.json"))
    if not reports:
        raise FileNotFoundError(f"No JSON reports inside {report_dir}")
    return reports[-1]


def _load_report(report_path: Path) -> Dict[str, Any]:
    print(f"Loading benchmarking report from {report_path}")
    return json.loads(report_path.read_text())


def _filter_benchmarks(
    benchmarks: List[Dict[str, Any]], selected: Optional[List[str]]
) -> List[Dict[str, Any]]:
    if not selected:
        return benchmarks
    wanted = set(selected)
    return [bench for bench in benchmarks if bench["name"] in wanted]


def _parse_plot_filters(selected: Optional[List[str]]) -> Optional[set[str]]:
    if not selected:
        return None
    return {entry.lower() for entry in selected}


def _cellstring_series_name(meta: Dict[str, Any]) -> str:
    configured = str(meta.get("cellstring_schema") or "").strip()
    return configured or FALLBACK_CELLSTRING_SERIES


def _series_color_map(series_names: List[str]) -> Dict[str, str]:
    color_map: Dict[str, str] = {LINESTRING_SERIES: LINESTRING_COLOR}
    others = [name for name in sorted(set(series_names)) if name != LINESTRING_SERIES]
    for idx, name in enumerate(others):
        color_map[name] = SERIES_COLOR_SEQUENCE[idx % len(SERIES_COLOR_SEQUENCE)]
    return color_map


def _apply_transparent_theme(
    fig,
    legend_horizontal: Optional[bool] = None,
    left_legend: Optional[bool] = None,
    with_bar_text: bool = False,
    show_grid: bool = False,
    top_margin: int = 25,
    bottom_margin: int = 0,
) -> None:
    xaxis_layout = {
        "showgrid": show_grid,
        "showline": True,
        "linewidth": 2,
        "linecolor": "black",
        "ticks": "inside",
        "mirror": True,
        "minorloglabels": "complete",
        "tickfont_size": 25,
    }
    yaxis_layout = {
        "showgrid": show_grid,
        "showline": True,
        "linewidth": 2,
        "linecolor": "black",
        "ticks": "inside",
        "mirror": True,
        "minorloglabels": "complete",
        "tickfont_size": 25,
        "automargin": "left",
    }
    if show_grid:
        xaxis_layout["gridcolor"] = "rgba(0,0,0,0.10)"
        xaxis_layout["gridwidth"] = 1
        yaxis_layout["gridcolor"] = "rgba(0,0,0,0.10)"
        yaxis_layout["gridwidth"] = 1

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=15, t=top_margin, b=bottom_margin),
        legend_title=dict(text=""),
        font_size=22,
        font_weight=500,
        legend_font_size=22,
        legend_font_weight=500,
        legend_itemsizing="constant",
    )
    if with_bar_text:
        fig.update_traces(
            marker=dict(line_color="grey", pattern_fillmode="replace"),
            textfont_size=20,
            textangle=0,
            textposition="outside",
            cliponaxis=False,
        )

    fig.update_xaxes(**xaxis_layout)
    fig.update_yaxes(**yaxis_layout)

    if legend_horizontal is None and left_legend is None:
        fig.update_layout(
            legend=dict(
                yanchor="top",
                y=0.98,
                xanchor="right",
                x=0.98,
            )
        )
    elif legend_horizontal is None and left_legend:
        fig.update_layout(
            legend=dict(
                yanchor="top",
                y=0.98,
                xanchor="left",
                x=0.02,
            ),
        )
    else:
        fig.update_layout(
            legend=dict(
                orientation="h",
                entrywidth=120,
                yanchor="top",
                y=0.98,
                xanchor="left",
                x=0.02,
            ),
        )


def plot_exec_time_bars(benchmarks: List[Dict[str, Any]], meta: Dict[str, Any]) -> None:
    rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        if st_exec is not None:
            rows.append(
                {
                    "benchmark": bench["name"],
                    "series": LINESTRING_SERIES,
                    "exec_ms": st_exec,
                }
            )
        if cst_exec is not None:
            rows.append(
                {"benchmark": bench["name"], "series": cst_series, "exec_ms": cst_exec}
            )

    if not rows:
        print("No time benchmark data found; skipping execution bars.")
        return

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="benchmark",
        y="exec_ms",
        color="series",
        barmode="group",
        color_discrete_map=_series_color_map(df["series"].tolist()),
        labels={"benchmark": "", "exec_ms": "Execution median (ms)", "series": ""},
        log_y=True,
        text_auto=".2f",
    )
    fig.update_layout(width=1100, height=650)
    _apply_transparent_theme(fig, legend_horizontal=True, with_bar_text=True)
    output_path = _next_output_path("exec_time_bars")
    fig.write_image(output_path)
    print(f"Wrote execution bars to {output_path}")


def plot_spatio_temporal_range_facets(
    benchmarks: List[Dict[str, Any]], meta: Dict[str, Any]
) -> None:
    rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    window_order = ["1 day", "1 week", "1 month"]
    area_order = [AREA_SIZE_LABELS[1], AREA_SIZE_LABELS[2], AREA_SIZE_LABELS[3]]

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        name = str(bench.get("name") or "")
        match = SPATIO_TEMPORAL_NAME_PATTERN.match(name)
        if not match:
            continue

        area_id = int(match.group("area_id"))
        window = match.group("window").strip().lower()
        if window not in window_order:
            continue

        area_label = AREA_SIZE_LABELS.get(area_id, f"Area {area_id}")
        thread_count = int(bench.get("thread_count") or 1)
        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")

        if st_exec is not None:
            rows.append(
                {
                    "window": window,
                    "area": area_label,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                    "thread_count": thread_count,
                }
            )
        if cst_exec is not None:
            rows.append(
                {
                    "window": window,
                    "area": area_label,
                    "series": cst_series,
                    "exec_ms": float(cst_exec),
                    "thread_count": thread_count,
                }
            )

    if not rows:
        print(
            "No spatio-temporal range benchmark data found; skipping facet line chart."
        )
        return

    df = pd.DataFrame(rows)
    df["window"] = pd.Categorical(df["window"], categories=window_order, ordered=True)
    df["area"] = pd.Categorical(df["area"], categories=area_order, ordered=True)
    df["thread_label"] = df["thread_count"].map(
        lambda n: f"{int(n)} thread" if int(n) == 1 else f"{int(n)} threads"
    )
    thread_count_unique = sorted(
        int(n) for n in df["thread_count"].dropna().unique().tolist()
    )
    has_thread_scaling = len(thread_count_unique) > 1

    fig_kwargs: Dict[str, Any] = {
        "data_frame": df,
        "x": "area",
        "y": "exec_ms",
        "log_y": True,
        "color": "series",
        "facet_col": "window",
        "markers": True,
        "category_orders": {
            "window": window_order,
            "area": area_order,
        },
        "color_discrete_map": _series_color_map(df["series"].tolist()),
        "labels": {
            "area": "",
            "exec_ms": "Execution median (ms)",
            "series": "",
            "window": "",
        },
    }
    if has_thread_scaling:
        fig_kwargs["line_dash"] = "thread_label"
        fig_kwargs["category_orders"]["thread_label"] = [
            f"{int(n)} thread" if int(n) == 1 else f"{int(n)} threads"
            for n in thread_count_unique
        ]

    fig = px.line(**fig_kwargs)
    fig.update_layout(width=1350, height=750)

    # Clean facet labels from "window=..." to simple "1 day", "1 week", "1 month".
    fig.for_each_annotation(
        lambda ann: (
            ann.update(text=ann.text.split("=", 1)[-1].strip())
            if isinstance(ann.text, str) and "=" in ann.text
            else None
        )
    )

    _apply_transparent_theme(fig, show_grid=True, left_legend=True)
    output_path = _next_output_path("spatio_temporal_range_facets")
    fig.write_image(output_path)
    print(f"Wrote spatio-temporal facet chart to {output_path}")


def plot_false_match_counts(benchmarks: List[Dict[str, Any]]) -> None:
    rows: List[Dict[str, Any]] = []
    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        result = bench.get("result", {})
        counts = result.get("result_counts") or result.get("match_counts") or {}
        baseline = counts.get("LineString")
        if baseline is None:
            continue
        if not isinstance(baseline, (int, float, str)):
            continue
        try:
            baseline_value = float(baseline)
        except (TypeError, ValueError):
            continue
        if baseline_value <= 0:
            continue
        fp = result.get("false_positives")
        fn = result.get("false_negatives")
        if fp is not None:
            rows.append(
                {
                    "benchmark": bench["name"],
                    "metric": "FP",
                    "pct": (float(fp) / baseline_value) * 100.0,
                }
            )
        if fn is not None:
            rows.append(
                {
                    "benchmark": bench["name"],
                    "metric": "FN",
                    "pct": (float(fn) / baseline_value) * 100.0,
                }
            )

    if not rows:
        print("No false match data found; skipping false-match plot.")
        return

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="benchmark",
        y="pct",
        color="metric",
        barmode="group",
        labels={"benchmark": "", "pct": "% of LineString matches", "metric": ""},
        text_auto=".1f",
    )
    fig.update_traces(texttemplate="%{y:.1f}%")
    fig.update_layout(width=1100, height=650)
    fig.update_yaxes(ticksuffix="%")
    _apply_transparent_theme(fig, legend_horizontal=True, with_bar_text=True)
    output_path = _next_output_path("false_match_counts")
    fig.write_image(output_path)
    print(f"Wrote false-match plot to {output_path}")


def plot_cell_length_exec_time(
    benchmarks: List[Dict[str, Any]], meta: Dict[str, Any]
) -> None:
    cardinalities_raw = meta.get("trajectory_cardinalities") or {}
    if not isinstance(cardinalities_raw, dict) or not cardinalities_raw:
        print(
            "No trajectory cardinality metadata found; skipping cell-count scatter plot."
        )
        return

    cardinalities: Dict[int, int] = {}
    for trajectory_id, count in cardinalities_raw.items():
        try:
            cardinalities[int(trajectory_id)] = int(count)
        except (TypeError, ValueError):
            continue

    rows: List[Dict[str, Any]] = []
    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        result = bench.get("result", {})
        for sample in result.get("cst", {}).get("samples", []):
            trajectory_id = sample.get("trajectory_id")
            exec_ms = sample.get("exec_ms")
            if trajectory_id is None or exec_ms is None:
                continue
            cardinality = cardinalities.get(int(trajectory_id))
            if cardinality is None or cardinality <= 0:
                continue
            rows.append(
                {
                    "benchmark": bench["name"],
                    "trajectory_id": trajectory_id,
                    "cell_count": cardinality,
                    "exec_ms": exec_ms,
                }
            )

    if not rows:
        print(
            "No sampled CellString execution data found; skipping cell-count scatter plot."
        )
        return

    df = pd.DataFrame(rows)
    fig = px.scatter(
        df,
        x="cell_count",
        y="exec_ms",
        color="benchmark",
        labels={
            "cell_count": "Cell count",
            "exec_ms": "Execution time (ms)",
            "benchmark": "Benchmark",
        },
        log_x=True,
        log_y=True,
        trendline="lowess",
        trendline_options=dict(frac=0.2),
    )
    fig.update_layout(width=1100, height=650)
    _apply_transparent_theme(fig)
    output_path = _next_output_path("cell_count_exec_time")
    fig.write_image(output_path)
    print(f"Wrote cell-count scatter plot to {output_path}")


def plot_linestring_containment_pct(benchmarks: List[Dict[str, Any]]) -> None:
    rows: List[Dict[str, Any]] = []
    for bench in benchmarks:
        if bench.get("benchmark_type") != "value":
            continue
        if "LineString containment vs CellString" not in bench.get("name", ""):
            continue
        values = bench.get("result", {}).get("median_values", {})
        pct = values.get("not_contained_pct")
        if pct is None:
            continue
        rows.append({"benchmark": bench["name"], "percentage": float(pct)})

    if not rows:
        print("No containment data found; skipping containment plot.")
        return

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="benchmark",
        y="percentage",
        labels={"benchmark": "", "percentage": "% of trajectories not contained"},
        text_auto=".1f",
    )
    fig.update_traces(texttemplate="%{y:.1f}%")
    fig.update_layout(width=900, height=600)
    fig.update_yaxes(ticksuffix="%")
    _apply_transparent_theme(fig, with_bar_text=True)
    output_path = _next_output_path("linestring_containment_pct")
    fig.write_image(output_path)
    print(f"Wrote containment plot to {output_path}")


def plot_area_mmsi_coverage(benchmarks: List[Dict[str, Any]], top_k: int = 3) -> None:
    area_to_rows: Dict[str, List[Dict[str, Any]]] = {}

    for bench in benchmarks:
        if bench.get("benchmark_type") != "value":
            continue
        if "MMSI Coverage" not in bench.get("name", ""):
            continue
        for row in bench.get("result", {}).get("rows", []):
            area_id = row.get("area_id")
            mmsi = row.get("mmsi")
            coverage = row.get("coverage_percent")
            if area_id is None or mmsi is None or coverage is None:
                continue
            area_to_rows.setdefault(str(area_id), []).append(
                {
                    "area_id": str(area_id),
                    "mmsi": str(mmsi),
                    "coverage_percent": float(coverage),
                }
            )

    if not area_to_rows:
        print("No MMSI coverage rows found; skipping coverage plot.")
        return

    for area_id, rows in area_to_rows.items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        ranked = (
            df.groupby("mmsi", as_index=False)["coverage_percent"]
            .max()
            .sort_values("coverage_percent", ascending=False)
            .head(top_k)
        )
        keep = set(ranked["mmsi"].tolist())
        filtered = df[df["mmsi"].isin(keep)]
        fig = px.bar(
            filtered,
            x="mmsi",
            y="coverage_percent",
            labels={"mmsi": "MMSI", "coverage_percent": "Coverage (%)"},
            text_auto=".1f",
        )
        fig.update_traces(texttemplate="%{y:.1f}%")
        fig.update_layout(width=900, height=600)
        fig.update_yaxes(ticksuffix="%")
        _apply_transparent_theme(fig, with_bar_text=True)
        output_path = _next_output_path(f"area_mmsi_coverage_area{area_id}")
        fig.write_image(output_path)
        print(f"Wrote MMSI coverage plot for area {area_id} to {output_path}")


def run_all_graphs(
    report_path: Path,
    selected_benchmarks: Optional[List[str]] = None,
    selected_plots: Optional[List[str]] = None,
) -> None:
    data = _load_report(report_path)
    benchmarks = _filter_benchmarks(data["benchmarks"], selected_benchmarks)
    if not benchmarks:
        print("No benchmarks matched the requested filters; nothing to plot.")
        return

    plot_filters = _parse_plot_filters(selected_plots)

    def wants(name: str) -> bool:
        return plot_filters is None or name.lower() in plot_filters

    if wants("exec_time_bars"):
        plot_exec_time_bars(benchmarks, data.get("meta", {}))

    if wants("false_match_counts"):
        plot_false_match_counts(benchmarks)

    if wants("cell_count_exec_time"):
        plot_cell_length_exec_time(benchmarks, data.get("meta", {}))

    if wants("linestring_containment_pct"):
        plot_linestring_containment_pct(benchmarks)

    if wants("area_mmsi_coverage"):
        plot_area_mmsi_coverage(benchmarks)

    if wants("spatio_temporal_range_facets"):
        plot_spatio_temporal_range_facets(benchmarks, data.get("meta", {}))


def main(
    path_arg: Optional[str] = None,
    benchmarks: Optional[List[str]] = None,
    plots: Optional[List[str]] = None,
) -> None:
    report_path = _ensure_report_path(path_arg)
    run_all_graphs(report_path, benchmarks, plots)


if __name__ == "__main__":
    args = sys.argv[1:]
    report_arg: Optional[str] = None
    benchmark_filters: List[str] = []
    plot_filters: List[str] = []

    for arg in args:
        if arg.startswith("--benchmark="):
            benchmark_filters.append(arg.split("=", 1)[1])
        elif arg.startswith("--benchmarks="):
            benchmark_filters.extend(
                filter(None, (name.strip() for name in arg.split("=", 1)[1].split(",")))
            )
        elif arg.startswith("--plot="):
            plot_filters.append(arg.split("=", 1)[1])
        elif arg.startswith("--plots="):
            plot_filters.extend(
                filter(None, (name.strip() for name in arg.split("=", 1)[1].split(",")))
            )
        elif report_arg is None:
            report_arg = arg
        else:
            benchmark_filters.append(arg)

    main(report_arg, benchmark_filters or None, plot_filters or None)
