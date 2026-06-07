import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

OUTPUT_DIR = Path("benchmarking/graphs/output")
# Optional fixed input report. If None, newest run_*.json is used.
DEFAULT_REPORT_JSON: Optional[str] = None
# Optional fixed thread filter for spatial_range_dual_axis. If None, all threads are shown.
DEFAULT_SPATIAL_THREADS: Optional[List[int]] = None
# Optional fixed thread filter for spatio_temporal_range_facets. If None, all threads are shown.
DEFAULT_SPATIO_TEMPORAL_THREADS: Optional[List[int]] = None

LINESTRING_SERIES = "LineString"
LINESTRING_COLOR = px.colors.qualitative.Safe[0]
FALLBACK_CELLSTRING_SERIES = "CellString"
SERIES_COLOR_SEQUENCE = (
    px.colors.qualitative.Safe[1:]
    + px.colors.qualitative.Set2
    + px.colors.qualitative.Pastel
)
AREA_SIZE_LABELS = {
    1: "S",
    2: "M",
    3: "L",
}
SPATIO_TEMPORAL_NAME_PATTERN = re.compile(
    r"^Spatio-temporal range query - area\s+(?P<region_id>\d+)\s+\((?P<window>[^)]+)\)$",
    re.IGNORECASE,
)
SPATIAL_RANGE_NAME_PATTERN = re.compile(
    r"^Spatial range query - area\s+(?P<region_id>\d+)$",
    re.IGNORECASE,
)
TEMPORAL_RANGE_NAME_PATTERN = re.compile(
    r"^Temporal range query\s*\((?P<window>[^)]+)\)$",
    re.IGNORECASE,
)
PASSAGE_QUERY_NAME_PATTERN = re.compile(
    r"^Passage query\s*-\s*crossings\s+(?P<crossings>.+)$",
    re.IGNORECASE,
)
PASSAGE_LABEL_OVERRIDES = {
    "Skagen,Storebælt Syd,Bornholms Gate": "The Great Belt",
    "Skagen,Sundet Syd,Bornholms Gate": "The Sound",
    "Kiel,Kadetrenden,Bornholms Gate": "The Kieler Canal",
}
SPATIAL_AREA_GROUPS = {
    1: ("Small", "high"),
    2: ("Medium", "high"),
    3: ("Large", "high"),
    7: ("Small", "low"),
    8: ("Medium", "low"),
    9: ("Large", "low"),
}
SPATIAL_AREA_ORDER = ["Small", "Medium", "Large"]
_AREA_NAME_TO_SHORT = {"Small": "S", "Medium": "M", "Large": "L"}
THREAD_PATTERN_SEQUENCE = ["", "/", "x", "-", "+", ".", "\\"]
PATTERN_FG_COLOR = "rgba(0,0,0,1.0)"
PATTERN_FG_OPACITY = 1.0
PATTERN_SIZE = 10
PATTERN_SOLIDITY = 0.15
LINESTRING_COUNT_COLOR = "#1f4fa3"
CELLSTRING_COUNT_COLOR = "#b23a2b"


def _traffic_for_area_id(area_id: int) -> Optional[str]:
    area_info = SPATIAL_AREA_GROUPS.get(area_id)
    if area_info is None:
        return None
    return area_info[1]


def _get_linestring_length_map(meta: Dict[str, Any]) -> Dict[int, float]:
    lengths = meta.get("trajectory_lengths", {})
    return {int(k): float(v) for k, v in lengths.items()}


def _spatio_temporal_area_label(area_id: int) -> str:
    area_info = SPATIAL_AREA_GROUPS.get(area_id)
    if area_info is not None:
        return _AREA_NAME_TO_SHORT.get(area_info[0], f"Area {area_id}")
    return AREA_SIZE_LABELS.get(area_id, f"Area {area_id}")


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


def _parse_thread_filters(selected: Optional[List[str]]) -> Optional[List[int]]:
    if not selected:
        return None

    values: List[int] = []
    for raw in selected:
        token = raw.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError as exc:
            raise ValueError(f"Invalid thread value: {raw}") from exc

    # Keep the order from CLI while removing duplicates.
    deduped: List[int] = list(dict.fromkeys(values))
    return deduped or None


def _parse_traffic_filter(selected: Optional[List[str]]) -> Optional[str]:
    if not selected:
        return None

    chosen: Optional[str] = None
    for raw in selected:
        token = raw.strip().lower()
        if not token:
            continue
        if token not in {"high", "low"}:
            raise ValueError(f"Invalid traffic value: {raw}. Use 'high' or 'low'.")
        # Last value wins to match CLI override behavior.
        chosen = token
    return chosen


def _cellstring_series_name(meta: Dict[str, Any]) -> str:
    # Keep chart naming stable regardless of schema name in the benchmark metadata.
    _ = meta
    return FALLBACK_CELLSTRING_SERIES


def _thread_label(thread_count: int) -> str:
    return (
        f"{thread_count} thread"
        if int(thread_count) == 1
        else f"{thread_count} threads"
    )


def _series_thread_label(series: str, thread_count: int) -> str:
    return f"{series} - {_thread_label(thread_count)}"


def _to_float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_count_pair(result: Dict[str, Any]) -> Dict[str, float]:
    counts = result.get("result_counts") or result.get("match_counts") or {}
    st_count = _to_float_or_none(counts.get(LINESTRING_SERIES))
    cst_count = _to_float_or_none(counts.get(FALLBACK_CELLSTRING_SERIES))
    out: Dict[str, float] = {}
    if st_count is not None:
        out[LINESTRING_SERIES] = st_count
    if cst_count is not None:
        out[FALLBACK_CELLSTRING_SERIES] = cst_count
    return out


def _format_count_text(value: float) -> str:
    base = str(int(value)) if float(value).is_integer() else f"{value:.2f}"
    return f"<b>{base}</b>"


def _count_line_color_map(cst_series: str) -> Dict[str, str]:
    return {
        LINESTRING_SERIES: LINESTRING_COUNT_COLOR,
        cst_series: CELLSTRING_COUNT_COLOR,
    }


def _is_primary_series_thread(
    series: str, thread_count: int, primary_thread_count: Optional[int]
) -> bool:
    if series != LINESTRING_SERIES:
        return True
    if primary_thread_count is None:
        return True
    return int(thread_count) == int(primary_thread_count)


def _series_color_map(series_names: List[str]) -> Dict[str, str]:
    color_map: Dict[str, str] = {LINESTRING_SERIES: LINESTRING_COLOR}
    others = [name for name in sorted(set(series_names)) if name != LINESTRING_SERIES]
    for idx, name in enumerate(others):
        color_map[name] = SERIES_COLOR_SEQUENCE[idx % len(SERIES_COLOR_SEQUENCE)]
    return color_map


def _lighten_hex(color: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))

    # Plotly qualitative palettes often use rgb(r, g, b) strings.
    if color.startswith("rgb(") and color.endswith(")"):
        raw = color[4:-1]
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) == 3:
            try:
                r = int(parts[0])
                g = int(parts[1])
                b = int(parts[2])
            except ValueError:
                return color
        else:
            return color
    elif color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    else:
        return color

    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"rgb({r}, {g}, {b})"


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


def _enhance_bar_pattern_visibility(fig) -> None:
    # Stronger pattern foreground improves readability in legend swatches.
    fig.update_traces(
        marker_pattern_fgcolor=PATTERN_FG_COLOR,
        marker_pattern_fgopacity=PATTERN_FG_OPACITY,
        marker_pattern_size=PATTERN_SIZE,
        marker_pattern_solidity=PATTERN_SOLIDITY,
        selector=dict(type="bar"),
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
    benchmarks: List[Dict[str, Any]],
    meta: Dict[str, Any],
    selected_threads: Optional[List[int]] = None,
    selected_traffic: Optional[str] = None,
) -> None:
    rows: List[Dict[str, Any]] = []
    count_rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    window_order = ["1 day", "1 week", "1 month"]
    area_order = [AREA_SIZE_LABELS[1], AREA_SIZE_LABELS[2], AREA_SIZE_LABELS[3]]
    effective_threads = (
        selected_threads
        if selected_threads is not None
        else DEFAULT_SPATIO_TEMPORAL_THREADS
    )
    thread_filter = set(effective_threads or [])

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        name = str(bench.get("name") or "")
        match = SPATIO_TEMPORAL_NAME_PATTERN.match(name)
        if not match:
            continue

        area_id = int(match.group("region_id"))
        area_traffic = _traffic_for_area_id(area_id)
        if selected_traffic in {"low", "high"} and area_traffic != selected_traffic:
            continue

        window = match.group("window").strip().lower()
        if window not in window_order:
            continue

        area_label = _spatio_temporal_area_label(area_id)
        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        count_pair = _extract_count_pair(result)

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
        for series_name, count_value in count_pair.items():
            normalized_series = (
                cst_series if series_name == FALLBACK_CELLSTRING_SERIES else series_name
            )
            count_rows.append(
                {
                    "window": window,
                    "area": area_label,
                    "series": normalized_series,
                    "thread_count": thread_count,
                    "count": float(count_value),
                }
            )

    if not rows:
        if selected_traffic in {"low", "high"}:
            print(
                f"No spatio-temporal range benchmark data found for {selected_traffic} traffic; skipping facet bar chart."
            )
            return
        if thread_filter:
            print(
                "Requested thread filters were not found in spatio-temporal data; skipping facet bar chart."
            )
        else:
            print(
                "No spatio-temporal range benchmark data found; skipping facet bar chart."
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
    if effective_threads:
        preferred_order = [
            int(n) for n in effective_threads if int(n) in set(thread_count_unique)
        ]
        remaining = [n for n in thread_count_unique if n not in set(preferred_order)]
        thread_count_order = preferred_order + remaining
    else:
        thread_count_order = thread_count_unique

    primary_thread_count = thread_count_order[0] if thread_count_order else None
    if primary_thread_count is not None:
        df = df[
            (df["series"] != LINESTRING_SERIES)
            | (df["thread_count"].astype(int) == int(primary_thread_count))
        ].copy()

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
        "barmode": "group",
        "facet_col": "window",
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
        fig_kwargs["pattern_shape"] = "thread_label"
        # First thread is solid; subsequent threads get different textures.
        fig_kwargs["pattern_shape_sequence"] = THREAD_PATTERN_SEQUENCE
        fig_kwargs["category_orders"]["thread_label"] = [
            f"{int(n)} thread" if int(n) == 1 else f"{int(n)} threads"
            for n in thread_count_order
        ]

    fig = px.bar(**fig_kwargs)
    fig.update_layout(width=1350, height=750)

    # Normalize PX legend labels to: "Series - x thread(s)".
    for trace in fig.data:
        if not isinstance(trace.name, str):
            continue
        if "," in trace.name:
            parts = [part.strip() for part in trace.name.split(",", 1)]
            if len(parts) == 2:
                trace.name = f"{parts[0]} - {parts[1]}"

    # Clean facet labels from "window=..." to simple "1 day", "1 week", "1 month".
    fig.for_each_annotation(
        lambda ann: (
            ann.update(text=ann.text.split("=", 1)[-1].strip())
            if isinstance(ann.text, str) and "=" in ann.text
            else None
        )
    )

    _apply_transparent_theme(fig, show_grid=True, left_legend=True)
    _enhance_bar_pattern_visibility(fig)

    # Add right-side count lines (one pair per facet) using the primary thread only.
    if count_rows and thread_count_order:
        count_color_map = _count_line_color_map(cst_series)
        primary_thread = int(thread_count_order[0])
        counts_df = pd.DataFrame(count_rows)
        counts_df = counts_df[
            counts_df["thread_count"].astype(int) == primary_thread
        ].copy()
        counts_df = counts_df.sort_values(["window", "area", "series"]).drop_duplicates(
            subset=["window", "area", "series"], keep="first"
        )
        canonical_count_axis = f"y{len(window_order) + len(window_order)}"

        for facet_idx, window in enumerate(window_order, start=1):
            facet_counts = counts_df[counts_df["window"] == window].copy()
            if facet_counts.empty:
                continue

            xaxis_ref = "x" if facet_idx == 1 else f"x{facet_idx}"
            yaxis_ref = f"y{len(window_order) + facet_idx}"
            overlay_axis = "y" if facet_idx == 1 else f"y{facet_idx}"
            layout_yaxis_key = f"yaxis{len(window_order) + facet_idx}"
            anchor_x = "x" if facet_idx == 1 else f"x{facet_idx}"

            fig.update_layout(
                {
                    layout_yaxis_key: dict(
                        anchor=anchor_x,
                        overlaying=overlay_axis,
                        matches=canonical_count_axis,
                        side="right",
                        type="log",
                        exponentformat="none",
                        minorloglabels="complete",
                        showgrid=False,
                        title="Result count" if facet_idx == len(window_order) else "",
                        showticklabels=facet_idx == len(window_order),
                        ticks="inside",
                        ticklabelstandoff=8,
                        showline=facet_idx == len(window_order),
                    )
                }
            )

            for series_name in [LINESTRING_SERIES, cst_series]:
                series_counts = facet_counts[
                    facet_counts["series"] == series_name
                ].copy()
                if series_counts.empty:
                    continue
                series_counts = series_counts[series_counts["count"] > 0].copy()
                if series_counts.empty:
                    continue
                series_counts["area"] = pd.Categorical(
                    series_counts["area"], categories=area_order, ordered=True
                )
                series_counts = series_counts.sort_values("area")
                fig.add_trace(
                    go.Scatter(
                        x=series_counts["area"].astype(str).tolist(),
                        y=series_counts["count"].astype(float).tolist(),
                        mode="lines+markers+text",
                        name=f"{series_name} count",
                        legendgroup=f"{series_name}_count",
                        showlegend=facet_idx == 1,
                        text=[
                            _format_count_text(v)
                            for v in series_counts["count"].tolist()
                        ],
                        textposition="top center",
                        xaxis=xaxis_ref,
                        yaxis=yaxis_ref,
                        line=dict(dash="dot", color=count_color_map[series_name]),
                        marker=dict(color=count_color_map[series_name]),
                    )
                )

    output_path = _next_output_path("spatio_temporal_range_facets")
    fig.write_image(output_path)
    print(f"Wrote spatio-temporal facet bar chart to {output_path}")


def plot_spatial_range_dual_axis(
    benchmarks: List[Dict[str, Any]],
    meta: Dict[str, Any],
    selected_threads: Optional[List[int]] = None,
    selected_traffic: Optional[str] = None,
) -> None:
    rows: List[Dict[str, Any]] = []
    count_rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    area_order = SPATIAL_AREA_ORDER
    effective_threads = (
        selected_threads if selected_threads is not None else DEFAULT_SPATIAL_THREADS
    )
    thread_filter = set(effective_threads or [])

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        name = str(bench.get("name") or "")
        match = SPATIAL_RANGE_NAME_PATTERN.match(name)
        if not match:
            continue

        area_id = int(match.group("region_id"))
        area_info = SPATIAL_AREA_GROUPS.get(area_id)
        if area_info is None:
            continue
        area_label, traffic_class = area_info

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        count_pair = _extract_count_pair(result)

        if st_exec is not None:
            rows.append(
                {
                    "area": area_label,
                    "traffic": traffic_class,
                    "series": LINESTRING_SERIES,
                    "thread_count": thread_count,
                    "exec_ms": float(st_exec),
                }
            )
        if cst_exec is not None:
            rows.append(
                {
                    "area": area_label,
                    "traffic": traffic_class,
                    "series": cst_series,
                    "thread_count": thread_count,
                    "exec_ms": float(cst_exec),
                }
            )
        for series_name, count_value in count_pair.items():
            normalized_series = (
                cst_series if series_name == FALLBACK_CELLSTRING_SERIES else series_name
            )
            count_rows.append(
                {
                    "area": area_label,
                    "traffic": traffic_class,
                    "series": normalized_series,
                    "thread_count": thread_count,
                    "count": float(count_value),
                }
            )

    if not rows:
        print("No spatial range benchmark data found; skipping dual-axis bar chart.")
        return

    df = pd.DataFrame(rows)
    if selected_traffic in {"low", "high"}:
        df = df[df["traffic"] == selected_traffic].copy()
        if df.empty:
            print(
                f"No spatial range benchmark data found for {selected_traffic} traffic; skipping chart."
            )
            return

    df = (
        df.groupby(["area", "traffic", "series", "thread_count"], as_index=False)[
            "exec_ms"
        ]
        .median()
        .sort_values(["area", "series", "thread_count", "traffic"])
    )

    if selected_traffic in {"low", "high"}:
        thread_order = (
            effective_threads
            if effective_threads
            else sorted(int(n) for n in df["thread_count"].unique().tolist())
        )
        thread_order = [
            t for t in thread_order if t in set(df["thread_count"].tolist())
        ]
        if not thread_order:
            print("Requested thread filters were not found in report; skipping chart.")
            return

        positive_vals = [float(v) for v in df["exec_ms"].tolist() if float(v) > 0.0]
        if not positive_vals:
            print(
                "Spatial range values are non-positive; cannot render log y-axis chart."
            )
            return

        base_colors = {
            LINESTRING_SERIES: LINESTRING_COLOR,
            cst_series: px.colors.qualitative.Safe[1],
        }
        series_order = [LINESTRING_SERIES, cst_series]

        primary_thread_count = thread_order[0] if thread_order else None
        fig = go.Figure()
        for idx, thread_count in enumerate(thread_order):
            for series_idx, series in enumerate(series_order):
                if not _is_primary_series_thread(
                    series, thread_count, primary_thread_count
                ):
                    continue
                subset = df[
                    (df["series"] == series) & (df["thread_count"] == thread_count)
                ].copy()
                if subset.empty:
                    continue

                subset["area"] = pd.Categorical(
                    subset["area"], categories=area_order, ordered=True
                )
                subset = subset.sort_values("area")

                color = base_colors[series]
                legend_name = _series_thread_label(series, thread_count)
                pattern_shape = THREAD_PATTERN_SEQUENCE[
                    idx % len(THREAD_PATTERN_SEQUENCE)
                ]
                marker: Dict[str, Any] = {"color": color}
                if pattern_shape:
                    marker["pattern"] = {"shape": pattern_shape}

                fig.add_trace(
                    go.Bar(
                        x=subset["area"].tolist(),
                        y=subset["exec_ms"].astype(float).tolist(),
                        name=legend_name,
                        legendgroup=f"{series}_{thread_count}",
                        offsetgroup=f"{series}_{thread_count}",
                        legendrank=10 + (idx * len(series_order)) + series_idx,
                        marker=marker,
                        hovertemplate="<b>%{x}</b><br>Execution median: %{y:.2f} ms<extra></extra>",
                    )
                )

        fig.update_layout(
            barmode="group",
            width=1450,
            height=760,
            xaxis=dict(
                categoryorder="array",
                categoryarray=area_order,
            ),
            yaxis=dict(
                title="Execution median (ms)",
                type="log",
            ),
        )

        _apply_transparent_theme(fig, show_grid=True, left_legend=True)
        _enhance_bar_pattern_visibility(fig)
        fig.update_layout(margin=dict(l=80, r=120, t=25, b=10))
        fig.update_yaxes(type="log")
        fig.update_layout(legend_tracegroupgap=0)

        if count_rows:
            count_color_map = _count_line_color_map(cst_series)
            primary_thread = int(thread_order[0]) if thread_order else None
            counts_df = pd.DataFrame(count_rows)
            counts_df = counts_df[counts_df["traffic"] == selected_traffic].copy()
            if primary_thread is not None:
                counts_df = counts_df[
                    counts_df["thread_count"].astype(int) == int(primary_thread)
                ].copy()
            counts_df = counts_df.sort_values(["area", "series"]).drop_duplicates(
                subset=["area", "series"], keep="first"
            )
            if not counts_df.empty:
                fig.update_layout(
                    yaxis2=dict(
                        title="Result count",
                        overlaying="y",
                        side="right",
                        type="log",
                        exponentformat="none",
                        minorloglabels="complete",
                        ticks="inside",
                        ticklabelstandoff=8,
                        showgrid=False,
                    )
                )
                for series_name in [LINESTRING_SERIES, cst_series]:
                    series_counts = counts_df[counts_df["series"] == series_name].copy()
                    if series_counts.empty:
                        continue
                    series_counts = series_counts[series_counts["count"] > 0].copy()
                    if series_counts.empty:
                        continue
                    series_counts["area"] = pd.Categorical(
                        series_counts["area"], categories=area_order, ordered=True
                    )
                    series_counts = series_counts.sort_values("area")
                    fig.add_trace(
                        go.Scatter(
                            x=series_counts["area"].astype(str).tolist(),
                            y=series_counts["count"].astype(float).tolist(),
                            mode="lines+markers+text",
                            name=f"{series_name} count",
                            legendgroup=f"{series_name}_count",
                            text=[
                                _format_count_text(v)
                                for v in series_counts["count"].tolist()
                            ],
                            textposition="top center",
                            yaxis="y2",
                            line=dict(dash="dot", color=count_color_map[series_name]),
                            marker=dict(color=count_color_map[series_name]),
                        )
                    )

        output_path = _next_output_path(f"spatial_range_dual_axis_{selected_traffic}")
        fig.write_image(output_path)
        print(
            f"Wrote spatial-range chart ({selected_traffic} traffic) to {output_path}"
        )
        return

    pivot = (
        df.pivot_table(
            index=["area", "series", "thread_count"],
            columns="traffic",
            values="exec_ms",
            aggfunc="median",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    if "low" not in pivot.columns or "high" not in pivot.columns:
        print("Spatial range data is missing low/high traffic pairs; skipping chart.")
        return

    pivot = pivot.dropna(subset=["low", "high"])
    if pivot.empty:
        print("Spatial range data has no complete low/high pairs; skipping chart.")
        return

    thread_order = (
        effective_threads
        if effective_threads
        else sorted(int(n) for n in pivot["thread_count"].unique().tolist())
    )
    thread_order = [t for t in thread_order if t in set(pivot["thread_count"].tolist())]
    if not thread_order:
        print("Requested thread filters were not found in report; skipping chart.")
        return

    positive_vals = [
        float(v)
        for v in pd.concat([pivot["low"], pivot["high"]]).tolist()
        if float(v) > 0.0
    ]
    if not positive_vals:
        print("Spatial range values are non-positive; cannot render log y-axis chart.")
        return

    y_min = min(positive_vals)

    base_colors = {
        LINESTRING_SERIES: LINESTRING_COLOR,
        cst_series: px.colors.qualitative.Safe[1],
    }
    series_order = [LINESTRING_SERIES, cst_series]

    fig = go.Figure()

    # Style-only traffic keys.
    fig.add_trace(
        go.Bar(
            x=[area_order[0]],
            y=[y_min],
            name="Low traffic",
            legendgroup="traffic_style_low",
            visible="legendonly",
            marker=dict(
                color="rgba(120,120,120,0.45)",
                pattern=dict(shape="/", fgopacity=0.55),
                line=dict(color="rgba(90,90,90,0.45)", width=0.6),
            ),
            hoverinfo="skip",
            legendrank=1,
        )
    )
    fig.add_trace(
        go.Bar(
            x=[area_order[0]],
            y=[y_min],
            name="High traffic",
            legendgroup="traffic_style_high",
            visible="legendonly",
            marker=dict(color="rgba(120,120,120,0.90)"),
            hoverinfo="skip",
            legendrank=2,
        )
    )

    primary_thread_count = thread_order[0] if thread_order else None
    for idx, thread_count in enumerate(thread_order):
        for series_idx, series in enumerate(series_order):
            if not _is_primary_series_thread(
                series, thread_count, primary_thread_count
            ):
                continue
            subset = pivot[
                (pivot["series"] == series) & (pivot["thread_count"] == thread_count)
            ].copy()
            if subset.empty:
                continue

            subset["area"] = pd.Categorical(
                subset["area"], categories=area_order, ordered=True
            )
            subset = subset.sort_values("area")

            color = base_colors[series]
            legend_name = _series_thread_label(series, thread_count)
            offset_group_low = f"{series}_{thread_count}_low"
            offset_group_high = f"{series}_{thread_count}_high"
            pattern_shape = THREAD_PATTERN_SEQUENCE[idx % len(THREAD_PATTERN_SEQUENCE)]
            high_marker: Dict[str, Any] = {"color": color}
            low_marker: Dict[str, Any] = {
                "color": color,
                "opacity": 0.45,
                "line": {"color": color, "width": 2},
            }
            if pattern_shape:
                high_marker["pattern"] = {"shape": pattern_shape}
                low_marker["pattern"] = {"shape": pattern_shape, "fgopacity": 0.55}

            low_vals = subset["low"].astype(float).tolist()
            high_vals = subset["high"].astype(float).tolist()

            fig.add_trace(
                go.Bar(
                    x=subset["area"].tolist(),
                    y=low_vals,
                    name=legend_name,
                    legendgroup=f"{series}_{thread_count}",
                    offsetgroup=offset_group_low,
                    showlegend=False,
                    marker=low_marker,
                    hovertemplate="<b>%{x}</b><br>Low traffic median: %{y:.2f} ms<extra></extra>",
                )
            )
            fig.add_trace(
                go.Bar(
                    x=subset["area"].tolist(),
                    y=high_vals,
                    name=legend_name,
                    legendgroup=f"{series}_{thread_count}",
                    offsetgroup=offset_group_high,
                    marker=high_marker,
                    legendrank=10 + (idx * len(series_order)) + series_idx,
                    hovertemplate="<b>%{x}</b><br>High traffic median: %{y:.2f} ms<extra></extra>",
                )
            )

    fig.update_layout(
        barmode="group",
        width=1450,
        height=760,
        xaxis=dict(
            categoryorder="array",
            categoryarray=area_order,
        ),
        yaxis=dict(
            title="Execution median (ms)",
            type="log",
        ),
    )

    _apply_transparent_theme(fig, show_grid=True, left_legend=True)
    _enhance_bar_pattern_visibility(fig)
    fig.update_layout(margin=dict(l=80, r=120, t=25, b=10))
    fig.update_yaxes(type="log")
    fig.update_layout(legend_tracegroupgap=0)

    if count_rows:
        count_color_map = _count_line_color_map(cst_series)
        primary_thread = int(thread_order[0]) if thread_order else None
        counts_df = pd.DataFrame(count_rows)
        if primary_thread is not None:
            counts_df = counts_df[
                counts_df["thread_count"].astype(int) == int(primary_thread)
            ].copy()
        counts_df = counts_df.sort_values(["area", "series"]).drop_duplicates(
            subset=["area", "series"], keep="first"
        )
        if not counts_df.empty:
            fig.update_layout(
                yaxis2=dict(
                    title="Result count",
                    overlaying="y",
                    side="right",
                    type="log",
                    exponentformat="none",
                    minorloglabels="complete",
                    ticks="inside",
                    ticklabelstandoff=8,
                    showgrid=False,
                )
            )
            for series_name in [LINESTRING_SERIES, cst_series]:
                series_counts = counts_df[counts_df["series"] == series_name].copy()
                if series_counts.empty:
                    continue
                series_counts = series_counts[series_counts["count"] > 0].copy()
                if series_counts.empty:
                    continue
                series_counts["area"] = pd.Categorical(
                    series_counts["area"], categories=area_order, ordered=True
                )
                series_counts = series_counts.sort_values("area")
                fig.add_trace(
                    go.Scatter(
                        x=series_counts["area"].astype(str).tolist(),
                        y=series_counts["count"].astype(float).tolist(),
                        mode="lines+markers+text",
                        name=f"{series_name} count",
                        legendgroup=f"{series_name}_count",
                        text=[
                            _format_count_text(v)
                            for v in series_counts["count"].tolist()
                        ],
                        textposition="top center",
                        yaxis="y2",
                        line=dict(dash="dot", color=count_color_map[series_name]),
                        marker=dict(color=count_color_map[series_name]),
                    )
                )

    output_path = _next_output_path("spatial_range_dual_axis")
    fig.write_image(output_path)
    print(f"Wrote spatial-range dual-axis chart to {output_path}")


def plot_temporal_range_grouped(
    benchmarks: List[Dict[str, Any]],
    meta: Dict[str, Any],
    selected_threads: Optional[List[int]] = None,
) -> None:
    rows: List[Dict[str, Any]] = []
    count_rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    window_order = ["1 day", "1 week", "1 month"]
    effective_threads = (
        selected_threads
        if selected_threads is not None
        else DEFAULT_SPATIO_TEMPORAL_THREADS
    )
    thread_filter = set(effective_threads or [])

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = TEMPORAL_RANGE_NAME_PATTERN.match(name)
        if not match:
            continue

        window = match.group("window").strip().lower()
        if window not in window_order:
            continue

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        count_pair = _extract_count_pair(result)

        if st_exec is not None:
            rows.append(
                {
                    "window": window,
                    "series": LINESTRING_SERIES,
                    "thread_count": thread_count,
                    "exec_ms": float(st_exec),
                }
            )
        if cst_exec is not None:
            rows.append(
                {
                    "window": window,
                    "series": cst_series,
                    "thread_count": thread_count,
                    "exec_ms": float(cst_exec),
                }
            )
        for series_name, count_value in count_pair.items():
            normalized_series = (
                cst_series if series_name == FALLBACK_CELLSTRING_SERIES else series_name
            )
            count_rows.append(
                {
                    "window": window,
                    "series": normalized_series,
                    "thread_count": thread_count,
                    "count": float(count_value),
                }
            )

    if not rows:
        if thread_filter:
            print(
                "Requested thread filters were not found in temporal range data; skipping grouped chart."
            )
        else:
            print("No temporal range benchmark data found; skipping grouped chart.")
        return

    df = pd.DataFrame(rows)
    thread_order = (
        effective_threads
        if effective_threads
        else sorted(int(n) for n in df["thread_count"].dropna().unique().tolist())
    )
    thread_order = [t for t in thread_order if t in set(df["thread_count"].tolist())]
    if not thread_order:
        print("Requested thread filters were not found in report; skipping chart.")
        return

    positive_vals = [float(v) for v in df["exec_ms"].tolist() if float(v) > 0.0]
    if not positive_vals:
        print("Temporal range values are non-positive; cannot render log y-axis chart.")
        return

    df["window"] = pd.Categorical(df["window"], categories=window_order, ordered=True)
    base_colors = {
        LINESTRING_SERIES: LINESTRING_COLOR,
        cst_series: px.colors.qualitative.Safe[1],
    }
    series_order = [LINESTRING_SERIES, cst_series]

    primary_thread_count = thread_order[0] if thread_order else None
    fig = go.Figure()
    for idx, thread_count in enumerate(thread_order):
        for series_idx, series in enumerate(series_order):
            if not _is_primary_series_thread(
                series, thread_count, primary_thread_count
            ):
                continue
            subset = df[
                (df["series"] == series) & (df["thread_count"] == thread_count)
            ].copy()
            if subset.empty:
                continue

            subset = subset.sort_values("window")
            color = base_colors[series]
            pattern_shape = THREAD_PATTERN_SEQUENCE[idx % len(THREAD_PATTERN_SEQUENCE)]
            marker: Dict[str, Any] = {"color": color}
            if pattern_shape:
                marker["pattern"] = {"shape": pattern_shape}

            fig.add_trace(
                go.Bar(
                    x=subset["window"].astype(str).tolist(),
                    y=subset["exec_ms"].astype(float).tolist(),
                    name=_series_thread_label(series, thread_count),
                    legendgroup=f"{series}_{thread_count}",
                    offsetgroup=f"{series}_{thread_count}",
                    legendrank=10 + (idx * len(series_order)) + series_idx,
                    marker=marker,
                    hovertemplate="<b>%{x}</b><br>Execution median: %{y:.2f} ms<extra></extra>",
                )
            )

    fig.update_layout(
        barmode="group",
        width=1350,
        height=750,
        xaxis=dict(
            categoryorder="array",
            categoryarray=window_order,
        ),
        yaxis=dict(title="Execution median (ms)", type="log"),
    )
    _apply_transparent_theme(fig, show_grid=True, left_legend=True)
    _enhance_bar_pattern_visibility(fig)
    fig.update_layout(margin=dict(l=80, r=120, t=25, b=10), legend_tracegroupgap=0)
    fig.update_yaxes(type="log")

    if count_rows:
        count_color_map = _count_line_color_map(cst_series)
        primary_thread = int(thread_order[0]) if thread_order else None
        counts_df = pd.DataFrame(count_rows)
        if primary_thread is not None:
            counts_df = counts_df[
                counts_df["thread_count"].astype(int) == int(primary_thread)
            ].copy()
        counts_df = counts_df.sort_values(["window", "series"]).drop_duplicates(
            subset=["window", "series"], keep="first"
        )
        if not counts_df.empty:
            fig.update_layout(
                yaxis2=dict(
                    title="Result count",
                    overlaying="y",
                    side="right",
                    type="log",
                    exponentformat="none",
                    minorloglabels="complete",
                    ticks="inside",
                    ticklabelstandoff=8,
                    showgrid=False,
                )
            )
            for series_name in [LINESTRING_SERIES, cst_series]:
                series_counts = counts_df[counts_df["series"] == series_name].copy()
                if series_counts.empty:
                    continue
                series_counts = series_counts[series_counts["count"] > 0].copy()
                if series_counts.empty:
                    continue
                series_counts["window"] = pd.Categorical(
                    series_counts["window"], categories=window_order, ordered=True
                )
                series_counts = series_counts.sort_values("window")
                fig.add_trace(
                    go.Scatter(
                        x=series_counts["window"].astype(str).tolist(),
                        y=series_counts["count"].astype(float).tolist(),
                        mode="lines+markers+text",
                        name=f"{series_name} count",
                        legendgroup=f"{series_name}_count",
                        text=[
                            _format_count_text(v)
                            for v in series_counts["count"].tolist()
                        ],
                        textposition="top center",
                        yaxis="y2",
                        line=dict(dash="dot", color=count_color_map[series_name]),
                        marker=dict(color=count_color_map[series_name]),
                    )
                )

    output_path = _next_output_path("temporal_range_grouped")
    fig.write_image(output_path)
    print(f"Wrote temporal-range grouped chart to {output_path}")


def plot_passage_query_grouped(
    benchmarks: List[Dict[str, Any]],
    meta: Dict[str, Any],
    selected_threads: Optional[List[int]] = None,
) -> None:
    rows: List[Dict[str, Any]] = []
    count_rows: List[Dict[str, Any]] = []
    cst_series = _cellstring_series_name(meta)
    effective_threads = (
        selected_threads
        if selected_threads is not None
        else DEFAULT_SPATIO_TEMPORAL_THREADS
    )
    thread_filter = set(effective_threads or [])

    passage_labels_seen: List[str] = []
    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = PASSAGE_QUERY_NAME_PATTERN.match(name)
        if not match:
            continue

        crossings_raw = match.group("crossings").strip()
        passage_label = PASSAGE_LABEL_OVERRIDES.get(crossings_raw, crossings_raw)
        if passage_label not in passage_labels_seen:
            passage_labels_seen.append(passage_label)

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        count_pair = _extract_count_pair(result)

        if st_exec is not None:
            rows.append(
                {
                    "passage": passage_label,
                    "series": LINESTRING_SERIES,
                    "thread_count": thread_count,
                    "exec_ms": float(st_exec),
                }
            )
        if cst_exec is not None:
            rows.append(
                {
                    "passage": passage_label,
                    "series": cst_series,
                    "thread_count": thread_count,
                    "exec_ms": float(cst_exec),
                }
            )
        for series_name, count_value in count_pair.items():
            normalized_series = (
                cst_series if series_name == FALLBACK_CELLSTRING_SERIES else series_name
            )
            count_rows.append(
                {
                    "passage": passage_label,
                    "series": normalized_series,
                    "thread_count": thread_count,
                    "count": float(count_value),
                }
            )

    if not rows:
        if not passage_labels_seen:
            print("No passage query benchmark data found; skipping grouped chart.")
        elif thread_filter:
            print(
                "Requested thread filters were not found in passage query data; skipping grouped chart."
            )
        else:
            print("No passage query benchmark data found; skipping grouped chart.")
        return

    passage_order = passage_labels_seen

    df = pd.DataFrame(rows)
    thread_order = (
        effective_threads
        if effective_threads
        else sorted(int(n) for n in df["thread_count"].dropna().unique().tolist())
    )
    thread_order = [t for t in thread_order if t in set(df["thread_count"].tolist())]
    if not thread_order:
        print("Requested thread filters were not found in report; skipping chart.")
        return

    positive_vals = [float(v) for v in df["exec_ms"].tolist() if float(v) > 0.0]
    if not positive_vals:
        print("Passage query values are non-positive; cannot render log y-axis chart.")
        return

    df["passage"] = pd.Categorical(
        df["passage"], categories=passage_order, ordered=True
    )
    base_colors = {
        LINESTRING_SERIES: LINESTRING_COLOR,
        cst_series: px.colors.qualitative.Safe[1],
    }
    series_order = [LINESTRING_SERIES, cst_series]

    primary_thread_count = thread_order[0] if thread_order else None
    fig = go.Figure()
    for idx, thread_count in enumerate(thread_order):
        for series_idx, series in enumerate(series_order):
            if not _is_primary_series_thread(
                series, thread_count, primary_thread_count
            ):
                continue
            subset = df[
                (df["series"] == series) & (df["thread_count"] == thread_count)
            ].copy()
            if subset.empty:
                continue

            subset = subset.sort_values("passage")
            color = base_colors[series]
            pattern_shape = THREAD_PATTERN_SEQUENCE[idx % len(THREAD_PATTERN_SEQUENCE)]
            marker: Dict[str, Any] = {"color": color}
            if pattern_shape:
                marker["pattern"] = {"shape": pattern_shape}

            fig.add_trace(
                go.Bar(
                    x=subset["passage"].astype(str).tolist(),
                    y=subset["exec_ms"].astype(float).tolist(),
                    name=_series_thread_label(series, thread_count),
                    legendgroup=f"{series}_{thread_count}",
                    offsetgroup=f"{series}_{thread_count}",
                    legendrank=10 + (idx * len(series_order)) + series_idx,
                    marker=marker,
                    hovertemplate="<b>%{x}</b><br>Execution median: %{y:.2f} ms<extra></extra>",
                )
            )

    fig.update_layout(
        barmode="group",
        width=1350,
        height=750,
        xaxis=dict(
            categoryorder="array",
            categoryarray=passage_order,
            title="",
        ),
        yaxis=dict(title="Execution median (ms)", type="log"),
    )
    _apply_transparent_theme(fig, show_grid=True, left_legend=True)
    _enhance_bar_pattern_visibility(fig)
    fig.update_layout(margin=dict(l=80, r=120, t=25, b=10), legend_tracegroupgap=0)
    fig.update_yaxes(type="log")

    if count_rows:
        count_color_map = _count_line_color_map(cst_series)
        primary_thread = int(thread_order[0]) if thread_order else None
        counts_df = pd.DataFrame(count_rows)
        if primary_thread is not None:
            counts_df = counts_df[
                counts_df["thread_count"].astype(int) == int(primary_thread)
            ].copy()
        counts_df = counts_df.sort_values(["passage", "series"]).drop_duplicates(
            subset=["passage", "series"], keep="first"
        )
        if not counts_df.empty:
            fig.update_layout(
                yaxis2=dict(
                    title="Result count",
                    overlaying="y",
                    side="right",
                    type="log",
                    exponentformat="none",
                    minorloglabels="complete",
                    ticks="inside",
                    ticklabelstandoff=8,
                    showgrid=False,
                )
            )
            for series_name in [LINESTRING_SERIES, cst_series]:
                series_counts = counts_df[counts_df["series"] == series_name].copy()
                if series_counts.empty:
                    continue
                series_counts = series_counts[series_counts["count"] > 0].copy()
                if series_counts.empty:
                    continue
                series_counts["passage"] = pd.Categorical(
                    series_counts["passage"], categories=passage_order, ordered=True
                )
                series_counts = series_counts.sort_values("passage")
                fig.add_trace(
                    go.Scatter(
                        x=series_counts["passage"].astype(str).tolist(),
                        y=series_counts["count"].astype(float).tolist(),
                        mode="lines+markers+text",
                        name=f"{series_name} count",
                        legendgroup=f"{series_name}_count",
                        text=[
                            _format_count_text(v)
                            for v in series_counts["count"].tolist()
                        ],
                        textposition="top center",
                        yaxis="y2",
                        line=dict(dash="dot", color=count_color_map[series_name]),
                        marker=dict(color=count_color_map[series_name]),
                    )
                )

    output_path = _next_output_path("passage_query_grouped")
    fig.write_image(output_path)
    print(f"Wrote passage-query grouped chart to {output_path}")


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
            area_id = row.get("region_id")
            mmsi = row.get("mmsi")
            coverage = row.get("coverage_percent")
            if area_id is None or mmsi is None or coverage is None:
                continue
            area_to_rows.setdefault(str(area_id), []).append(
                {
                    "region_id": str(area_id),
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


def plot_cellstring_delta(
    benchmarks: List[Dict[str, Any]], meta: Dict[str, Any]
) -> None:
    length_map = _get_linestring_length_map(meta)
    if not length_map:
        print(
            "No LineString length data found in the report; skipping Execution time vs. LineString length plot."
        )
        return

    rows: List[Dict[str, Any]] = []

    def _collect_samples(
        samples: List[Dict[str, Any]], series: str, bench_name: str
    ) -> None:
        for sample in samples or []:
            traj_id = sample.get("trajectory_id")
            exec_ms = sample.get("exec_ms")
            if traj_id is None or exec_ms is None:
                continue
            length_km = length_map.get(int(traj_id))
            if length_km is None:
                continue
            rows.append(
                {
                    "benchmark": bench_name,
                    "series": series,
                    "trajectory_id": traj_id,
                    "length_km": length_km,
                    "exec_ms": exec_ms,
                }
            )

    cst_series_name = _cellstring_series_name(meta)
    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue
        # Only apply to spatio-temporal join queries (ID Temporal)
        if "Spatio-temporal join" not in bench["name"]:
            continue
        result = bench.get("result", {})
        _collect_samples(
            result.get("st", {}).get("samples", []), LINESTRING_SERIES, bench["name"]
        )
        _collect_samples(
            result.get("cst", {}).get("samples", []), cst_series_name, bench["name"]
        )

    if not rows:
        print(
            "No benchmark samples with LineString lengths for Spatio-temporal join; skipping Execution time vs. LineString length plot."
        )
        return

    df = pd.DataFrame(rows).sort_values(["benchmark", "series", "length_km"])
    fig = px.scatter(
        df,
        x="length_km",
        y="exec_ms",
        color="series",
        color_discrete_map=_series_color_map(df["series"].tolist()),
        category_orders={"series": [LINESTRING_SERIES, cst_series_name]},
        labels={
            "length_km": "LineString length (km)",
            "exec_ms": "Execution time (ms)",
            "series": "Data",
        },
        log_y=True,
        log_x=True,
        trendline="lowess",
        trendline_options=dict(frac=0.2),
    )
    fig.update_layout(
        width=1000,
        height=650,
    )
    _apply_transparent_theme(fig, legend_horizontal=True)
    output_path = _next_output_path("cellstring_delta")
    fig.write_image(output_path)
    print(f"Wrote Execution time vs. LineString length plot to {output_path}")


def run_all_graphs(
    report_path: Path,
    selected_benchmarks: Optional[List[str]] = None,
    selected_plots: Optional[List[str]] = None,
    selected_threads: Optional[List[int]] = None,
    selected_traffic: Optional[str] = None,
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
        plot_spatio_temporal_range_facets(
            benchmarks,
            data.get("meta", {}),
            selected_threads=selected_threads,
            selected_traffic=selected_traffic,
        )

    if wants("spatial_range_dual_axis"):
        plot_spatial_range_dual_axis(
            benchmarks,
            data.get("meta", {}),
            selected_threads=selected_threads,
            selected_traffic=selected_traffic,
        )

    if wants("temporal_range_grouped"):
        plot_temporal_range_grouped(
            benchmarks,
            data.get("meta", {}),
            selected_threads=selected_threads,
        )

    if wants("passage_query_grouped"):
        plot_passage_query_grouped(
            benchmarks,
            data.get("meta", {}),
            selected_threads=selected_threads,
        )

    if wants("cellstring_delta"):
        plot_cellstring_delta(benchmarks, data.get("meta", {}))


def main(
    path_arg: Optional[str] = None,
    benchmarks: Optional[List[str]] = None,
    plots: Optional[List[str]] = None,
    threads: Optional[List[int]] = None,
    traffic: Optional[str] = None,
) -> None:
    report_path = _ensure_report_path(path_arg)
    run_all_graphs(
        report_path,
        benchmarks,
        plots,
        selected_threads=threads,
        selected_traffic=traffic,
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    report_arg: Optional[str] = None
    benchmark_filters: List[str] = []
    plot_filters: List[str] = []
    thread_filters: List[str] = []
    traffic_filters: List[str] = []

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
        elif arg.startswith("--thread="):
            thread_filters.append(arg.split("=", 1)[1])
        elif arg.startswith("--threads="):
            thread_filters.extend(
                filter(None, (name.strip() for name in arg.split("=", 1)[1].split(",")))
            )
        elif arg.startswith("--traffic="):
            traffic_filters.append(arg.split("=", 1)[1])
        elif arg in {
            "--high-traffic",
            "--low-traffic",
            "-high-traffic",
            "-low-traffic",
        }:
            raise ValueError("Use --traffic=high or --traffic=low.")
        elif report_arg is None:
            report_arg = arg
        else:
            benchmark_filters.append(arg)

    parsed_threads = _parse_thread_filters(thread_filters)
    parsed_traffic = _parse_traffic_filter(traffic_filters)
    main(
        report_arg,
        benchmark_filters or None,
        plot_filters or None,
        parsed_threads,
        traffic=parsed_traffic,
    )
