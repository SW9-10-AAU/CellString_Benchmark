import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import ScalarFormatter

# Try to use scienceplots if available, otherwise fallback to standard styling
try:
    import scienceplots

    plt.style.use(["science", "bright"])
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


def _load_report(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Report not found at {file_path}")
    print(f"Loading report from {file_path}")
    return json.loads(file_path.read_text())


def plot_temporal_range(data: Dict[str, Any], thread_filter: List[int] = None) -> None:
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

    # Specify the exact ticks we want to see text for, making it more detailed than just 10, 100
    # but not so cluttered that the text overlaps.
    ax.set_yticks([10, 25, 50, 100, 250, 500, 1000])

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)

    # Hide the minor ticks since we specified detailed major ticks
    ax.yaxis.set_minor_locator(plt.NullLocator())

    # Minimalist grid
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)

    # Refine legend
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="", loc="upper left", frameon=False)

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
    args = parser.parse_args()

    data = _load_report(args.json)
    plot_temporal_range(data, thread_filter=args.threads)


if __name__ == "__main__":
    main()
