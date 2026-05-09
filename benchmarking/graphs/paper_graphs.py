import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import ScalarFormatter

# Try to use scienceplots if available, otherwise fallback to standard styling
try:
    import scienceplots

    plt.style.use(["science", "vibrant"])
    # Override standard IEEE 8pt to ACM 9pt
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
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
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.linewidth": 0.5,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.5,
            "lines.linewidth": 1.0,
            "lines.markersize": 3,
            "pdf.fonttype": 42,  # Embed fonts in PDF
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
    1: ("Small", "high"),
    2: ("Medium", "high"),
    3: ("Large", "high"),
    7: ("Small", "low"),
    8: ("Medium", "low"),
    9: ("Large", "low"),
}
SPATIAL_AREA_ORDER = ["Small", "Medium", "Large"]
SPATIAL_RANGE_NAME_PATTERN = re.compile(
    r"^Spatial range query\s*-\s*area\s*(?P<region_id>\d+)$", re.IGNORECASE
)
SPATIO_TEMPORAL_RANGE_NAME_PATTERN = re.compile(
    r"^Spatio-temporal range query - area\s*(?P<region_id>\d+)\s*\((?P<window>[^)]+)\)$",
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

    window_order = ["1 day", "1 week", "1 month"]

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

        if st_exec is not None:
            rows.append(
                {
                    "window": window,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "window": window,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print("No temporal range benchmark data found.")
        return

    df = pd.DataFrame(rows)
    df["window"] = pd.Categorical(df["window"], categories=window_order, ordered=True)

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

    ax.set_ylabel("Execution median (ms)")
    ax.set_xlabel("")

    ax.set_yscale("log")

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)

    # Hide the minor ticks since we specified detailed major ticks
    ax.yaxis.set_minor_locator(plt.NullLocator())

    # Minimalist grid
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="", loc="best", frameon=False)

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

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pgf_path = _next_output_path("temporal_range_paper", ".pgf")

    try:
        # Saving as PGF requires LaTeX
        fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
        print(f"Successfully saved to {pgf_path}")
    except Exception as e:
        print(
            f"Notice: Could not save PGF file (LaTeX might not be installed natively): {e}"
        )


def plot_spatial_range(
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
        match = SPATIAL_RANGE_NAME_PATTERN.match(name)
        if not match:
            continue

        area_id = int(match.group("region_id"))
        area_info = SPATIAL_AREA_GROUPS.get(area_id)
        if area_info is None:
            continue

        area_label, traffic_class = area_info
        if traffic_class != traffic:
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
                    "area": area_label,
                    "series": LINESTRING_SERIES,
                    "exec_ms": float(st_exec),
                }
            )

        if cst_exec is not None:
            rows.append(
                {
                    "area": area_label,
                    "series": CELLSTRING_SERIES,
                    "exec_ms": float(cst_exec),
                }
            )

    if not rows:
        print(f"No spatial range benchmark data found for {traffic} traffic.")
        return

    df = pd.DataFrame(rows)
    df["area"] = pd.Categorical(df["area"], categories=SPATIAL_AREA_ORDER, ordered=True)

    fig, ax = plt.subplots(figsize=(3.33, 2.2))

    if plot_type == "line":
        sns.lineplot(
            data=df,
            x="area",
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
            x="area",
            y="exec_ms",
            hue="series",
            ax=ax,
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_ylabel("Execution median (ms)")
    ax.set_xlabel("")

    ax.set_yscale("log")

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.yaxis.set_minor_locator(plt.NullLocator())

    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="", loc="best", frameon=False)

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

    ax.set_ylim(bottom=bottom_tick, top=top_tick)
    ax.set_yticks(visible_ticks)

    plt.tight_layout(pad=0.1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pgf_path = _next_output_path(f"spatial_range_{traffic}_paper", ".pgf")

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

        # Abbreviate area to fit in narrow subplots
        area_short = {"Small": "S", "Medium": "M", "Large": "L"}.get(
            area_label, area_label
        )

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
    window_order = ["1 day", "1 week", "1 month"]
    area_order_short = ["S", "M", "L"]

    df["window"] = pd.Categorical(df["window"], categories=window_order, ordered=True)
    df["area_short"] = pd.Categorical(
        df["area_short"], categories=area_order_short, ordered=True
    )

    fig, axes = plt.subplots(1, 3, figsize=(3.33, 2.2), sharey=True)

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

        ax.set_title(window, fontsize=9)
        ax.set_xlabel("")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        ax.set_yscale("log")
        formatter = ScalarFormatter()
        formatter.set_scientific(False)
        ax.yaxis.set_major_formatter(formatter)
        ax.yaxis.set_minor_locator(plt.NullLocator())

        if ax.get_legend():
            ax.get_legend().remove()

    axes[0].set_ylabel("Execution median (ms)")

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

    # Calculate the exact visual center of the subplots AFTER tight_layout
    box0 = axes[0].get_position()
    box2 = axes[-1].get_position()
    center_x = (box0.x0 + box2.x1) / 2

    # Draw a global figure legend exactly over that center
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(center_x, 1.0),
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
        choices=["temporal", "spatial", "spatio-temporal"],
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
    args = parser.parse_args()

    data = _load_report(args.json)

    if args.plot == "temporal":
        plot_temporal_range(data, thread_filter=args.threads, plot_type=args.type)
    elif args.plot == "spatial":
        plot_spatial_range(
            data, traffic=args.traffic, thread_filter=args.threads, plot_type=args.type
        )
    elif args.plot == "spatio-temporal":
        plot_spatio_temporal_range(
            data, traffic=args.traffic, thread_filter=args.threads, plot_type=args.type
        )


if __name__ == "__main__":
    main()
