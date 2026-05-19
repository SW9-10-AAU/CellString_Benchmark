import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import ScalarFormatter, FixedLocator, FixedFormatter

# ── Global font size for all graph text ──────────────────────────────────────
FONT_SIZE = 8

# Vibrant palette colors (Paul Tol)
VIBRANT_COLORS = [
    "#EE7733",
    "#0077BB",
    "#33BBEE",
    "#EE3377",
    "#CC3311",
    "#009988",
    "#BBBBBB",
]

# Try to use scienceplots if available, otherwise fallback to standard styling
try:
    import scienceplots

    plt.style.use(["science", "vibrant"])
    plt.rcParams.update(
        {
            "font.size": FONT_SIZE,
            "axes.labelsize": FONT_SIZE,
            "axes.titlesize": FONT_SIZE,
            "legend.fontsize": FONT_SIZE,
            "xtick.labelsize": FONT_SIZE,
            "ytick.labelsize": FONT_SIZE,
        }
    )
except ImportError:
    # Manual fallback for scientific aesthetics if SciencePlots isn't installed
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [
                "Linux Libertine O",
                "Libertine",
                "Times",
                "Times New Roman",
                "serif",
            ],
            "mathtext.fontset": "custom",
            "mathtext.rm": "Linux Libertine O",
            "mathtext.it": "Linux Libertine O:italic",
            "mathtext.bf": "Linux Libertine O:bold",
            "font.size": FONT_SIZE,
            "axes.labelsize": FONT_SIZE,
            "axes.titlesize": FONT_SIZE,
            "legend.fontsize": FONT_SIZE,
            "xtick.labelsize": FONT_SIZE,
            "ytick.labelsize": FONT_SIZE,
            "axes.linewidth": 0.5,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.5,
            "lines.linewidth": 1.0,
            "lines.markersize": 3,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

# PGF output settings for native Overleaf compilation
plt.rcParams.update(
    {
        "pgf.texsystem": "lualatex",
        "pgf.rcfonts": False,
        "text.usetex": False,
    }
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


# Target JSON
TARGET_JSON = "benchmarking/benchmark_results/run_20260429_094356.json"
OUTPUT_DIR = Path("benchmarking/graphs/output")

# Constants
LINESTRING_SERIES = "LineString"
CELLSTRING_SERIES = "CellString"
TEMPORAL_RANGE_NAME_PATTERN = re.compile(
    r"^Temporal range query\s*\((?P<window>[^)]+)\)$",
    re.IGNORECASE,
)

SPATIAL_AREA_GROUPS = {
    1: (1, "high"),
    2: (24, "high"),
    3: (435, "high"),
    4: (1, "low"),
    5: (24, "low"),
    6: (435, "low"),
}
SPATIAL_AREA_ORDER = [1, 24, 435]
SPATIAL_RANGE_NAME_PATTERN = re.compile(
    r"^Spatial range query\s*-\s*(?:area|region)\s*(?P<region_id>\d+)$", re.IGNORECASE
)
SPATIAL_RANGE_NO_RTREE_NAME_PATTERN = re.compile(
    r"^Spatial range query\s*\(no rtree\)\s*-\s*(?:area|region)\s*(?P<region_id>\d+)$",
    re.IGNORECASE,
)
SPATIO_TEMPORAL_RANGE_NAME_PATTERN = re.compile(
    r"^Spatio-temporal range query - (?:area|region)\s*(?P<region_id>\d+)\s*\((?P<window>[^)]+)\)$",
    re.IGNORECASE,
)
PASSAGE_QUERY_NAME_PATTERN = re.compile(
    r"^Passage query - crossings\s*(?P<crossings>.+)$",
    re.IGNORECASE,
)
PASSAGE_NAME_MAP = {
    "Skagen,Storebælt Syd,Bornholms Gate": "The Great Belt",
    "Skagen,Sundet Syd,Bornholms Gate": "The Sound",
    "Kiel,Kadetrenden,Bornholms Gate": "The Kieler Kanal",
}
PASSAGE_ORDER = ["The Great Belt", "The Sound", "The Kieler Kanal"]
COVERAGE_MMSI_NAME_PATTERN = re.compile(
    r"^CoverageByMMSI - region (?P<region_id>\d+)\s*\(zoom (?P<zoom>\d+)\)$",
    re.IGNORECASE,
)


def _load_report(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Report not found at {file_path}")
    print(f"Loading report from {file_path}")
    return json.loads(file_path.read_text())


def plot_temporal_range(
    data: Dict[str, Any], thread_filter: List[int] = None, plot_type: str = "bar"
) -> None:
    benchmarks = data.get("benchmarks", [])
    rows = []

    window_order = [1, 7, 30, 180]

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = TEMPORAL_RANGE_NAME_PATTERN.match(name)
        if not match:
            continue

        window_raw = match.group("window").strip()
        try:
            window_value = int(window_raw)
        except ValueError:
            continue
        if window_value not in window_order:
            continue

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")

        if st_exec is not None:
            rows.append(
                {
                    "window": window_value,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "window": window_value,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print("No temporal range benchmark data found.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("window")

    # Half-column width = 3.33 inches
    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    if plot_type == "line":
        sns.lineplot(
            data=df,
            x="window",
            y="exec_ms",
            hue="series",
            style="series",
            ax=ax,
            markers=True,
            dashes=False,
            markersize=6,
            linewidth=1.5,
        )
    else:
        sns.barplot(
            data=df,
            x="window",
            y="exec_ms",
            hue="series",
            ax=ax,
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_ylabel("Execution time (ms)")
    ax.set_xlabel("Time window (day)")
    ax.set_xscale("log")
    ax.set_xlim(min(window_order) / 1.2, max(window_order) * 1.2)
    ax.xaxis.set_major_locator(FixedLocator(window_order))
    ax.xaxis.set_major_formatter(FixedFormatter([str(value) for value in window_order]))

    ax.set_yscale("log")

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)

    # Hide the minor ticks on both axes
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_locator(plt.NullLocator())

    # Minimalist grid
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    # Remove inline legend; we'll draw a floating one after layout
    if ax.get_legend():
        ax.get_legend().remove()

    y_data = df["exec_ms"]
    base_ticks = [1, 2.5, 5, 7.5]
    ticks = np.array([b * (10**p) for p in range(0, 6) for b in base_ticks])
    y_min, y_max = np.min(y_data), np.max(y_data)
    # Use one tick BELOW the lowest and one ABOVE the highest for buffer
    below_ticks = ticks[ticks <= y_min]
    above_ticks = ticks[ticks >= y_max]
    bottom_tick = (
        below_ticks[-1]
        if len(below_ticks) >= 1
        else (below_ticks[-1] if len(below_ticks) > 0 else y_min * 0.9)
    )
    top_tick = (
        above_ticks[0]
        if len(above_ticks) >= 1
        else (above_ticks[0] if len(above_ticks) > 0 else y_max * 1.1)
    )
    visible_ticks = ticks[(ticks >= bottom_tick) & (ticks <= top_tick)]

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)

    # Floating legend above the plot, centered on the axes
    box = ax.get_position()
    center_x = (box.x0 + box.x1) / 2
    handles, labels = ax.get_legend_handles_labels()
    legend_y = box.y1 + 0.02
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, legend_y),
        ncol=2,
        frameon=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pgf_path = _next_output_path("temporal_range_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(
            f"Notice: Could not save PGF file (LaTeX might not be installed natively): {e}"
        )


def plot_spatial_range(
    data: Dict[str, Any],
    thread_filter: List[int] = None,
    plot_type: str = "bar",
    include_no_rtree: bool = False,
) -> None:
    benchmarks = data.get("benchmarks", [])
    rows = []

    traffic_labels = {"high": "HT", "low": "LT"}

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = SPATIAL_RANGE_NAME_PATTERN.match(name)
        match_no_rtree = SPATIAL_RANGE_NO_RTREE_NAME_PATTERN.match(name)
        if not match and not match_no_rtree:
            continue
        if match_no_rtree and not include_no_rtree:
            continue

        match = match or match_no_rtree
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

        traffic_suffix = traffic_labels[traffic_class]

        if st_exec is not None:
            if match_no_rtree:
                rows.append(
                    {
                        "area": area_label,
                        "series": f"{LINESTRING_SERIES} (No R-tree, {traffic_suffix})",
                        "exec_ms": float(st_exec),
                    }
                )
            else:
                rows.append(
                    {
                        "area": area_label,
                        "series": f"{LINESTRING_SERIES} ({traffic_suffix})",
                        "exec_ms": float(st_exec),
                    }
                )

        if cst_exec is not None and not match_no_rtree:
            rows.append(
                {
                    "area": area_label,
                    "series": f"{CELLSTRING_SERIES} ({traffic_suffix})",
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print("No spatial range benchmark data found.")
        return

    df = pd.DataFrame(rows)
    df["area"] = pd.Categorical(df["area"], categories=SPATIAL_AREA_ORDER, ordered=True)

    series_order = [
        f"{LINESTRING_SERIES} (LT)",
        f"{LINESTRING_SERIES} (HT)",
    ]
    if include_no_rtree:
        series_order.extend(
            [
                f"{LINESTRING_SERIES} (No R-tree, LT)",
                f"{LINESTRING_SERIES} (No R-tree, HT)",
            ]
        )
    series_order.extend(
        [
            f"{CELLSTRING_SERIES} (LT)",
            f"{CELLSTRING_SERIES} (HT)",
        ]
    )

    df["series"] = pd.Categorical(df["series"], categories=series_order, ordered=True)
    df = df.sort_values(["series", "area"])

    palette = {
        f"{LINESTRING_SERIES} (LT)": VIBRANT_COLORS[3],
        f"{LINESTRING_SERIES} (HT)": VIBRANT_COLORS[0],
        f"{CELLSTRING_SERIES} (LT)": VIBRANT_COLORS[2],
        f"{CELLSTRING_SERIES} (HT)": VIBRANT_COLORS[1],
    }
    if include_no_rtree:
        palette.update(
            {
                f"{LINESTRING_SERIES} (No R-tree, LT)": VIBRANT_COLORS[5],
                f"{LINESTRING_SERIES} (No R-tree, HT)": VIBRANT_COLORS[4],
            }
        )

    # Explicit marker assignment per series
    marker_map = {
        f"{LINESTRING_SERIES} (LT)": "s",
        f"{LINESTRING_SERIES} (HT)": "o",
        f"{CELLSTRING_SERIES} (LT)": "P",
        f"{CELLSTRING_SERIES} (HT)": "X",
    }
    if include_no_rtree:
        marker_map.update(
            {
                f"{LINESTRING_SERIES} (No R-tree, LT)": "^",
                f"{LINESTRING_SERIES} (No R-tree, HT)": "v",
            }
        )

    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    if plot_type == "line":
        sns.lineplot(
            data=df,
            x="area",
            y="exec_ms",
            hue="series",
            style="series",
            hue_order=series_order,
            style_order=series_order,
            palette=palette,
            markers=marker_map,
            ax=ax,
            dashes=False,
            estimator=None,
            units="series",
            sort=False,
            markersize=6,
            linewidth=1.5,
        )
    else:
        sns.barplot(
            data=df,
            x="area",
            y="exec_ms",
            hue="series",
            hue_order=series_order,
            palette=palette,
            ax=ax,
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_ylabel("Execution time (ms)")
    ax.set_xlabel(r"Area ($\mathrm{km}^2$)")
    ax.set_xscale("log")
    ax.set_xlim(min(SPATIAL_AREA_ORDER) / 1.2, max(SPATIAL_AREA_ORDER) * 1.2)
    ax.xaxis.set_major_locator(FixedLocator(SPATIAL_AREA_ORDER))
    ax.xaxis.set_major_formatter(
        FixedFormatter([str(value) for value in SPATIAL_AREA_ORDER])
    )

    ax.set_yscale("log")

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_locator(plt.NullLocator())

    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    # Remove inline legend; we'll draw a floating one after layout
    if ax.get_legend():
        ax.get_legend().remove()

    y_data = df["exec_ms"]
    base_ticks = [1, 2.5, 5, 7.5]
    ticks = np.array([b * (10**p) for p in range(0, 6) for b in base_ticks])
    y_min, y_max = np.min(y_data), np.max(y_data)
    # Use one tick BELOW the lowest and one ABOVE the highest for buffer
    below_ticks = ticks[ticks <= y_min]
    above_ticks = ticks[ticks >= y_max]
    bottom_tick = (
        below_ticks[-1]
        if len(below_ticks) >= 1
        else (below_ticks[-1] if len(below_ticks) > 0 else y_min * 0.9)
    )
    top_tick = (
        above_ticks[0]
        if len(above_ticks) >= 1
        else (above_ticks[0] if len(above_ticks) > 0 else y_max * 1.1)
    )
    visible_ticks = ticks[(ticks >= bottom_tick) & (ticks <= top_tick)]

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)

    # Floating legend above the plot, centered on the axes
    box = ax.get_position()
    center_x = (box.x0 + box.x1) / 2
    handles, labels = ax.get_legend_handles_labels()
    legend_y = box.y1 + 0.02
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, legend_y),
        ncol=2,
        frameon=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pgf_path = _next_output_path("spatial_range_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(f"Notice: Could not save PGF file: {e}")


def plot_spatio_temporal_range(
    data: Dict[str, Any],
    traffic: str = "high",
    thread_filter: List[int] = None,
    plot_type: str = "bar",
) -> None:
    benchmarks = data.get("benchmarks", [])
    rows = []

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = SPATIO_TEMPORAL_RANGE_NAME_PATTERN.match(name)
        if not match:
            continue

        area_id = int(match.group("region_id"))
        window = match.group("window")

        area_info = SPATIAL_AREA_GROUPS.get(area_id)
        if area_info is None:
            continue

        area_label, traffic_class = area_info
        if traffic_class != traffic:
            continue

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        # Use area label directly
        area_short = area_label

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")

        if st_exec is not None:
            rows.append(
                {
                    "window": window,
                    "area_short": area_short,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "window": window,
                    "area_short": area_short,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print(f"No spatio-temporal range benchmark data found for {traffic} traffic.")
        return

    df = pd.DataFrame(rows)
    window_order = ["1", "7", "30", "180"]
    area_order_short = SPATIAL_AREA_ORDER

    df["window"] = pd.Categorical(df["window"], categories=window_order, ordered=True)
    df["area_short"] = pd.Categorical(
        df["area_short"], categories=area_order_short, ordered=True
    )

    fig, axes = plt.subplots(1, len(window_order), figsize=(3.33, 2.2), sharey=True)

    for i, window in enumerate(window_order):
        ax = axes[i]
        subset = df[df["window"] == window]

        if not subset.empty:
            if plot_type == "line":
                sns.lineplot(
                    data=subset,
                    x="area_short",
                    y="exec_ms",
                    hue="series",
                    style="series",
                    ax=ax,
                    markers=True,
                    dashes=False,
                    markersize=6,
                    linewidth=1.5,
                )
            else:
                sns.barplot(
                    data=subset,
                    x="area_short",
                    y="exec_ms",
                    hue="series",
                    ax=ax,
                    edgecolor="black",
                    linewidth=0.5,
                )

        ax.set_title(window, fontsize=FONT_SIZE)
        ax.set_xlabel("")
        plt.setp(ax.get_xticklabels(), rotation=0, ha="center", fontsize=FONT_SIZE)
        ax.set_xlim(-0.3, len(area_order_short) - 1 + 0.3)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        ax.set_yscale("log")
        formatter = ScalarFormatter()
        formatter.set_scientific(False)
        ax.yaxis.set_major_formatter(formatter)
        ax.yaxis.set_minor_locator(plt.NullLocator())
        ax.xaxis.set_minor_locator(plt.NullLocator())

        if ax.get_legend():
            ax.get_legend().remove()

    axes[0].set_ylabel("Execution time (ms)")

    # We wait to draw the legend until after tight_layout so it doesn't squish the subplots

    y_data = df["exec_ms"]
    base_ticks = [1, 2.5, 5, 7.5]
    ticks = np.array([b * (10**p) for p in range(0, 6) for b in base_ticks])
    y_min, y_max = np.min(y_data), np.max(y_data)
    bottom_tick = (
        ticks[ticks <= y_min][-1] if len(ticks[ticks <= y_min]) > 0 else y_min * 0.9
    )
    top_tick = (
        ticks[ticks >= y_max][0] if len(ticks[ticks >= y_max]) > 0 else y_max * 1.1
    )
    visible_ticks = ticks[(ticks >= bottom_tick) & (ticks <= top_tick)]

    axes[0].set_ylim(bottom=bottom_tick, top=top_tick)
    axes[0].set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)
    fig.subplots_adjust(wspace=0, bottom=0.16)

    # Calculate the exact visual center of the subplots AFTER tight_layout and adjustments
    box0 = axes[0].get_position()
    box2 = axes[-1].get_position()
    center_x = (box0.x0 + box2.x1) / 2

    # Draw centered X-axis label beneath the subplots
    fig.text(
        center_x,
        0.05,
        r"Area ($\mathrm{km}^2$)",
        ha="center",
        va="center",
        fontsize=FONT_SIZE,
    )

    # Draw centered top X-axis label above the subplots (dynamically spaced above the axes)
    days_y = box0.y1 + 0.08
    fig.text(
        center_x,
        days_y,
        "Time window (day)",
        ha="center",
        va="bottom",
        fontsize=FONT_SIZE,
    )

    # Draw a global figure legend exactly over that center
    handles, labels = axes[0].get_legend_handles_labels()
    legend_y = box0.y1 + 0.10
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, legend_y),
        ncol=2,
        frameon=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pgf_path = _next_output_path(f"spatio_temporal_range_{traffic}_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(f"Notice: Could not save PGF file: {e}")


def plot_thread_scalability(
    data: Dict[str, Any],
    benchmark_kind: str = "spatial",
    region_id: int | None = 6,
    window: str | None = None,
    passage: str | None = None,
) -> None:
    """Plot thread scalability for a specific benchmark slice."""
    benchmarks = data.get("benchmarks", [])
    rows = []

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")

        if benchmark_kind == "spatial":
            match = SPATIAL_RANGE_NAME_PATTERN.match(name)
            if not match:
                continue
            area_id = int(match.group("region_id"))
            if region_id is not None and area_id != region_id:
                continue
        elif benchmark_kind == "temporal":
            match = TEMPORAL_RANGE_NAME_PATTERN.match(name)
            if not match:
                continue
            window_key = match.group("window").strip().lower()
            if window is not None and window_key != str(window).strip().lower():
                continue
        elif benchmark_kind == "spatio-temporal":
            match = SPATIO_TEMPORAL_RANGE_NAME_PATTERN.match(name)
            if not match:
                continue
            area_id = int(match.group("region_id"))
            window_key = match.group("window").strip().lower()
            if region_id is not None and area_id != region_id:
                continue
            if window is not None and window_key != str(window).strip().lower():
                continue
        elif benchmark_kind == "passage":
            match = PASSAGE_QUERY_NAME_PATTERN.match(name)
            if not match:
                continue
            crossings = _normalize_passage_key(match.group("crossings"))
            passage_label = PASSAGE_NAME_MAP.get(crossings, crossings)
            if passage is not None:
                passage_key = passage.strip()
                if passage_key not in {passage_label, crossings}:
                    continue
        else:
            raise ValueError(f"Unsupported benchmark kind: {benchmark_kind}")

        thread_count = int(bench.get("thread_count") or 1)

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")

        if st_exec is not None:
            rows.append(
                {
                    "threads": thread_count,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "threads": thread_count,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print("No thread scalability data found for the selected filters.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("threads")

    thread_order = [str(t) for t in sorted(df["threads"].unique())]
    df["threads"] = df["threads"].astype(str)
    df["threads"] = pd.Categorical(df["threads"], categories=thread_order, ordered=True)

    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    sns.lineplot(
        data=df,
        x="threads",
        y="exec_ms",
        hue="series",
        style="series",
        ax=ax,
        markers=True,
        dashes=False,
        markersize=6,
        linewidth=1.5,
    )

    ax.set_ylabel("Execution time (ms)")
    ax.set_xlabel("Threads")

    ax.set_yscale("log")

    ax.xaxis.set_minor_locator(plt.NullLocator())

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.yaxis.set_minor_locator(plt.NullLocator())

    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    # Remove inline legend
    if ax.get_legend():
        ax.get_legend().remove()

    y_data = df["exec_ms"]
    base_ticks = [1, 2.5, 5, 7.5]
    ticks = np.array([b * (10**p) for p in range(0, 7) for b in base_ticks])
    y_min, y_max = np.min(y_data), np.max(y_data)
    # Use one tick BELOW the lowest and one ABOVE the highest for buffer
    below_ticks = ticks[ticks <= y_min]
    above_ticks = ticks[ticks >= y_max]
    bottom_tick = (
        below_ticks[-2]
        if len(below_ticks) >= 2
        else (below_ticks[-1] if len(below_ticks) > 0 else y_min * 0.9)
    )
    top_tick = (
        above_ticks[1]
        if len(above_ticks) >= 2
        else (above_ticks[0] if len(above_ticks) > 0 else y_max * 1.1)
    )
    visible_ticks = ticks[(ticks >= bottom_tick) & (ticks <= top_tick)]

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)

    # Floating legend above the plot, centered on the axes
    box = ax.get_position()
    center_x = (box.x0 + box.x1) / 2
    handles, labels = ax.get_legend_handles_labels()
    legend_y = box.y1 + 0.02
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, legend_y),
        ncol=2,
        frameon=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pgf_path = _next_output_path(f"thread_scalability_{benchmark_kind}_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(f"Notice: Could not save PGF file: {e}")


def _normalize_passage_key(crossings: str) -> str:
    parts = [part.strip() for part in crossings.split(",") if part.strip()]
    return ",".join(parts)


def plot_passage_query(
    data: Dict[str, Any],
    thread_filter: List[int] = None,
    plot_type: str = "line",
) -> None:
    benchmarks = data.get("benchmarks", [])
    rows = []

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = PASSAGE_QUERY_NAME_PATTERN.match(name)
        if not match:
            continue

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        crossings = _normalize_passage_key(match.group("crossings"))
        passage_label = PASSAGE_NAME_MAP.get(crossings, crossings)

        result = bench.get("result", {})
        st_exec = result.get("st", {}).get("exec_ms_med")
        cst_exec = result.get("cst", {}).get("exec_ms_med")

        if st_exec is not None:
            rows.append(
                {
                    "passage": passage_label,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "passage": passage_label,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print("No passage query benchmark data found.")
        return

    df = pd.DataFrame(rows)
    df["passage"] = pd.Categorical(
        df["passage"], categories=PASSAGE_ORDER, ordered=True
    )

    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    if plot_type == "bar":
        sns.barplot(
            data=df,
            x="passage",
            y="exec_ms",
            hue="series",
            ax=ax,
            edgecolor="black",
            linewidth=0.5,
        )
    else:
        sns.lineplot(
            data=df,
            x="passage",
            y="exec_ms",
            hue="series",
            style="series",
            ax=ax,
            markers=True,
            dashes=False,
            markersize=6,
            linewidth=1.5,
        )

    ax.set_ylabel("Execution time (ms)")
    ax.set_xlabel("Passage")

    ax.set_yscale("log")

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_locator(plt.NullLocator())

    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    if ax.get_legend():
        ax.get_legend().remove()

    y_data = df["exec_ms"]
    base_ticks = [1, 2.5, 5, 7.5]
    ticks = np.array([b * (10**p) for p in range(0, 6) for b in base_ticks])
    y_min, y_max = np.min(y_data), np.max(y_data)
    below_ticks = ticks[ticks <= y_min]
    above_ticks = ticks[ticks >= y_max]
    bottom_tick = (
        below_ticks[-2]
        if len(below_ticks) >= 2
        else (below_ticks[-1] if len(below_ticks) > 0 else y_min * 0.9)
    )
    top_tick = (
        above_ticks[1]
        if len(above_ticks) >= 2
        else (above_ticks[0] if len(above_ticks) > 0 else y_max * 1.1)
    )
    visible_ticks = ticks[(ticks >= bottom_tick) & (ticks <= top_tick)]

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)

    box = ax.get_position()
    center_x = (box.x0 + box.x1) / 2
    handles, labels = ax.get_legend_handles_labels()
    legend_y = box.y1 + 0.02
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, legend_y),
        ncol=2,
        frameon=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pgf_path = _next_output_path("passage_query_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(f"Notice: Could not save PGF file: {e}")


def plot_coverage_mmsi(
    data: Dict[str, Any],
    thread_filter: List[int] = None,
    plot_type: str = "line",
) -> None:
    benchmarks = data.get("benchmarks", [])
    rows = []

    for bench in benchmarks:
        if bench.get("benchmark_type") != "time":
            continue

        name = str(bench.get("name") or "")
        match = COVERAGE_MMSI_NAME_PATTERN.match(name)
        if not match:
            continue

        thread_count = int(bench.get("thread_count") or 1)
        if thread_filter and thread_count not in thread_filter:
            continue

        zoom = int(match.group("zoom"))

        result = bench.get("result", {})
        cst_exec = result.get("cst", {}).get("exec_ms_med")
        if cst_exec is None:
            continue

        rows.append(
            {"zoom": zoom, "exec_ms": float(cst_exec), "series": CELLSTRING_SERIES}
        )

    if not rows:
        print("No CoverageByMMSI benchmark data found.")
        return

    df = pd.DataFrame(rows)
    df = df.groupby(["zoom", "series"], as_index=False)["exec_ms"].median()
    df = df.sort_values("zoom")

    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    palette = {CELLSTRING_SERIES: VIBRANT_COLORS[1]}
    marker_map = {CELLSTRING_SERIES: "X"}

    if plot_type == "bar":
        sns.barplot(
            data=df,
            x="zoom",
            y="exec_ms",
            hue="series",
            palette=palette,
            ax=ax,
            edgecolor="black",
            linewidth=0.5,
        )
    else:
        sns.lineplot(
            data=df,
            x="zoom",
            y="exec_ms",
            hue="series",
            style="series",
            palette=palette,
            markers=marker_map,
            ax=ax,
            dashes=False,
            markersize=6,
            linewidth=1.5,
        )

    ax.set_ylabel("Execution time (ms)")
    ax.set_xlabel("Zoom level")

    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_locator(plt.NullLocator())

    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    if ax.get_legend():
        ax.get_legend().remove()

    plt.tight_layout(pad=0.1)

    box = ax.get_position()
    center_x = (box.x0 + box.x1) / 2
    handles, labels = ax.get_legend_handles_labels()
    if handles and labels:
        legend_y = box.y1 + 0.02
        fig.legend(
            handles,
            labels,
            loc="lower center",
            bbox_to_anchor=(center_x, legend_y),
            ncol=1,
            frameon=False,
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pgf_path = _next_output_path("coverage_mmsi_paper", ".pgf")

    try:
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(f"Notice: Could not save PGF file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate ACM Sigconf compliant graphs."
    )
    parser.add_argument(
        "--json", type=str, default=TARGET_JSON, help="Path to the benchmark JSON file."
    )
    parser.add_argument(
        "--threads",
        type=int,
        nargs="+",
        help="Filter results to only include these thread counts (e.g. --threads 64 120)",
    )
    parser.add_argument(
        "--plot",
        type=str,
        choices=[
            "temporal",
            "spatial",
            "spatio-temporal",
            "thread-scalability",
            "passage",
            "coverage-mmsi",
        ],
        required=True,
        help="Which type of plot to generate.",
    )
    parser.add_argument(
        "--traffic",
        type=str,
        choices=["high", "low"],
        default="high",
        help="Traffic level to plot (only applies to spatial and spatio-temporal range).",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["bar", "line"],
        default="bar",
        help="Type of chart to generate (bar or line).",
    )
    parser.add_argument(
        "--spatial-include-no-rtree",
        action="store_true",
        help="Include the LineString no-R-tree results in spatial range plots.",
    )
    parser.add_argument(
        "--thread-benchmark",
        type=str,
        choices=["temporal", "spatial", "spatio-temporal", "passage"],
        default="spatial",
        help="Benchmark kind to use for thread scalability plots.",
    )
    parser.add_argument(
        "--region",
        type=int,
        default=6,
        help="Region id filter for spatial/spatio-temporal thread scalability plots.",
    )
    parser.add_argument(
        "--window",
        type=str,
        help="Time window filter for temporal/spatio-temporal thread scalability plots.",
    )
    parser.add_argument(
        "--passage",
        type=str,
        help="Passage name or crossings string filter for passage thread scalability plots.",
    )
    args = parser.parse_args()

    data = _load_report(args.json)

    if args.plot == "temporal":
        plot_temporal_range(data, thread_filter=args.threads, plot_type=args.type)
    elif args.plot == "spatial":
        plot_spatial_range(
            data,
            thread_filter=args.threads,
            plot_type=args.type,
            include_no_rtree=args.spatial_include_no_rtree,
        )
    elif args.plot == "spatio-temporal":
        plot_spatio_temporal_range(
            data, traffic=args.traffic, thread_filter=args.threads, plot_type=args.type
        )
    elif args.plot == "thread-scalability":
        plot_thread_scalability(
            data,
            benchmark_kind=args.thread_benchmark,
            region_id=args.region,
            window=args.window,
            passage=args.passage,
        )
    elif args.plot == "passage":
        plot_passage_query(data, thread_filter=args.threads, plot_type=args.type)
    elif args.plot == "coverage-mmsi":
        plot_coverage_mmsi(data, thread_filter=args.threads, plot_type=args.type)


if __name__ == "__main__":
    main()
