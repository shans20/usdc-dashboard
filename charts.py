#!/usr/bin/env python3
"""
CRCL Thesis Charts — Visual dashboard for USDC tracking.

Usage:
    python3 charts.py           # Generate all charts
    python3 charts.py --show    # Generate and open
"""

import sys
import os
import json
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime

from defillama import get_usdc_data, fmt_supply
from fred import get_treasury_yield
from rldc import estimate_rldc
from config import THESIS

# Style
plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#c9d1d9",
    "text.color": "#c9d1d9",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "grid.color": "#21262d",
    "font.size": 11,
    "font.family": "monospace",
})

ACCENT = "#58a6ff"
GREEN = "#3fb950"
ORANGE = "#d29922"
RED = "#f85149"
PURPLE = "#bc8cff"

OUTPUT_DIR = "charts"


def load_snapshots():
    """Load all historical snapshots for time series."""
    snapshots = []
    snap_dir = "snapshots"
    if not os.path.exists(snap_dir):
        return snapshots
    for fname in sorted(os.listdir(snap_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(snap_dir, fname)) as f:
                snapshots.append(json.load(f))
    return snapshots


def chart_chain_breakdown(usdc_data):
    """Pie + bar chart of USDC distribution across chains."""
    chains = list(usdc_data["chain_breakdown"].items())[:10]
    labels = [c[0] for c in chains]
    values = [c[1] / 1e9 for c in chains]
    other = (usdc_data["total_supply_usd"] - sum(c[1] for c in chains)) / 1e9
    if other > 0:
        labels.append("Other")
        values.append(other)

    colors = [ACCENT, GREEN, ORANGE, PURPLE, RED, "#8b949e", "#f0883e", "#a371f7", "#79c0ff", "#56d364", "#484f58"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Pie chart
    wedges, texts, autotexts = ax1.pie(
        values, labels=None, autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
        colors=colors[:len(values)], pctdistance=0.8,
        wedgeprops=dict(width=0.5, edgecolor="#0d1117", linewidth=1.5),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(9)
    ax1.set_title(f"USDC Distribution by Chain\nTotal: {fmt_supply(usdc_data['total_supply_usd'])}", fontsize=13, fontweight="bold")
    ax1.legend(labels, loc="center left", bbox_to_anchor=(-0.15, 0.5), fontsize=9, frameon=False)

    # Horizontal bar
    ax2.barh(labels[::-1], values[::-1], color=colors[:len(values)][::-1], height=0.6)
    ax2.set_xlabel("USDC (Billions $)")
    ax2.set_title("USDC by Chain ($B)", fontsize=13, fontweight="bold")
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))
    for i, v in enumerate(values[::-1]):
        ax2.text(v + 0.3, i, f"${v:.1f}B", va="center", fontsize=9, color="#c9d1d9")
    ax2.grid(axis="x", alpha=0.3)

    fig.suptitle(f"CRCL Thesis Tracker — {datetime.now().strftime('%Y-%m-%d')}", fontsize=9, color="#8b949e", y=0.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "chain_breakdown.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def chart_rldc_sensitivity(usdc_supply_bn):
    """Heatmap of RLDC margin across yield and Coinbase % scenarios."""
    yields = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    cb_pcts = [0.10, 0.15, 0.18, 0.21, 0.25, 0.30, 0.35]

    margins = []
    for y in yields:
        row = []
        for cb in cb_pcts:
            r = estimate_rldc(usdc_supply_bn, y, cb)
            row.append(r["rldc_margin"] * 100)
        margins.append(row)

    fig, ax = plt.subplots(figsize=(10, 7))
    im = ax.imshow(margins, cmap="RdYlGn", aspect="auto", vmin=30, vmax=55)

    ax.set_xticks(range(len(cb_pcts)))
    ax.set_xticklabels([f"{cb:.0%}" for cb in cb_pcts])
    ax.set_yticks(range(len(yields)))
    ax.set_yticklabels([f"{y:.1f}%" for y in yields])
    ax.set_xlabel("Coinbase On-Platform % of USDC", fontsize=12)
    ax.set_ylabel("Reserve Yield (3mo T-Bill)", fontsize=12)

    # Annotate cells
    for i, y in enumerate(yields):
        for j, cb in enumerate(cb_pcts):
            color = "white" if margins[i][j] < 38 or margins[i][j] > 48 else "black"
            ax.text(j, i, f"{margins[i][j]:.1f}%", ha="center", va="center", fontsize=10, color=color, fontweight="bold")

    # Mark current position
    current_yield = 3.63
    current_cb = THESIS["cb_on_platform_pct_of_usdc"]
    yi = min(range(len(yields)), key=lambda i: abs(yields[i] - current_yield))
    ci = min(range(len(cb_pcts)), key=lambda j: abs(cb_pcts[j] - current_cb))
    ax.add_patch(plt.Rectangle((ci - 0.5, yi - 0.5), 1, 1, fill=False, edgecolor="white", linewidth=3))
    ax.text(ci, yi - 0.35, "NOW", ha="center", va="top", fontsize=7, color="white", fontweight="bold")

    plt.colorbar(im, ax=ax, label="RLDC Margin %", shrink=0.8)
    ax.set_title(f"RLDC Margin Sensitivity (USDC = ${usdc_supply_bn:.1f}B)\nWhite box = current position", fontsize=13, fontweight="bold")

    fig.suptitle(f"CRCL Thesis Tracker — {datetime.now().strftime('%Y-%m-%d')}", fontsize=9, color="#8b949e", y=0.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rldc_sensitivity.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def chart_thesis_trajectory(usdc_supply_bn, current_yield):
    """Bar chart comparing current run-rate vs thesis FY26-FY30 projections."""
    # Thesis projections from the model
    years = ["Now\n(run-rate)", "FY26E", "FY27E", "FY28E", "FY29E", "FY30E"]
    thesis_usdc = [usdc_supply_bn, 105.4, 147.6, 206.6, 289.3, 405.0]
    thesis_eps = [None, 2.32, 3.48, 5.13, 10.47, 14.30]  # Adj EPS from thesis

    # Current run-rate
    current = estimate_rldc(usdc_supply_bn, current_yield)
    thesis_eps[0] = current["adj_eps"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # USDC supply trajectory
    bar_colors = [ACCENT] + [GREEN] * 5
    bars = ax1.bar(years, thesis_usdc, color=bar_colors, width=0.6, edgecolor="#30363d")
    ax1.set_ylabel("USDC Supply ($B)")
    ax1.set_title("USDC Supply: Now vs Thesis\n(40% CAGR target)", fontsize=13, fontweight="bold")
    for bar, val in zip(bars, thesis_usdc):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                 f"${val:.0f}B", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax1.set_ylim(0, max(thesis_usdc) * 1.15)
    ax1.grid(axis="y", alpha=0.3)

    # Adj EPS trajectory
    bar_colors2 = [ORANGE] + [PURPLE] * 5
    bars2 = ax2.bar(years, thesis_eps, color=bar_colors2, width=0.6, edgecolor="#30363d")
    ax2.set_ylabel("Adj EPS ($)")
    ax2.set_title("Adj EPS: Now vs Thesis\n(60% other revenue CAGR)", fontsize=13, fontweight="bold")
    for bar, val in zip(bars2, thesis_eps):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"${val:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax2.set_ylim(0, max(thesis_eps) * 1.15)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(f"CRCL Thesis Tracker — {datetime.now().strftime('%Y-%m-%d')}", fontsize=9, color="#8b949e", y=0.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "thesis_trajectory.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def chart_revenue_waterfall(usdc_supply_bn, current_yield):
    """Waterfall chart showing revenue -> distribution -> RLDC -> EBITDA."""
    r = estimate_rldc(usdc_supply_bn, current_yield)

    labels = [
        "Reserve\nIncome",
        "Other\nRevenue",
        "Total\nRevenue",
        "CB On-Plat\nDist",
        "CB Off-Plat\nDist",
        "Other\nDist",
        "RLDC",
        "Adj OpEx",
        "Adj\nEBITDA",
    ]
    values = [
        r["reserve_income_mm"],
        r["other_revenue_mm"],
        r["total_revenue_mm"],
        -r["cb_distribution_on_mm"],
        -r["cb_distribution_off_mm"],
        -r["other_distribution_mm"],
        r["rldc_mm"],
        -r["adj_opex_mm"],
        r["adj_ebitda_mm"],
    ]
    # Which bars are totals (start from 0)
    is_total = [False, False, True, False, False, False, True, False, True]

    fig, ax = plt.subplots(figsize=(14, 7))

    running = 0
    bottoms = []
    for i, (v, total) in enumerate(zip(values, is_total)):
        if total:
            bottoms.append(0)
            running = v
        else:
            if v >= 0:
                bottoms.append(running)
                running += v
            else:
                running += v
                bottoms.append(running)

    colors = []
    for i, (v, total) in enumerate(zip(values, is_total)):
        if total:
            colors.append(ACCENT)
        elif v >= 0:
            colors.append(GREEN)
        else:
            colors.append(RED)

    bars = ax.bar(labels, [abs(v) for v in values], bottom=bottoms, color=colors, width=0.6, edgecolor="#30363d")

    for bar, v in zip(bars, values):
        y = bar.get_y() + bar.get_height() / 2
        ax.text(bar.get_x() + bar.get_width() / 2, y,
                f"${abs(v):,.0f}mm", ha="center", va="center", fontsize=9, fontweight="bold", color="white")

    ax.set_ylabel("$ Millions (Annualized)")
    ax.set_title(f"CRCL Revenue Waterfall (Run-Rate)\nRLDC Margin: {r['rldc_margin']:.1%}  |  Adj EPS: ${r['adj_eps']:.2f}",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(y=0, color="#30363d", linewidth=0.8)

    fig.suptitle(f"CRCL Thesis Tracker — {datetime.now().strftime('%Y-%m-%d')}", fontsize=9, color="#8b949e", y=0.02)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "revenue_waterfall.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching live data...")
    usdc_data = get_usdc_data()
    usdc_supply_bn = usdc_data["total_supply_usd"] / 1e9
    yield_data = get_treasury_yield()
    current_yield = yield_data.get("yield_pct") or 3.7

    print(f"  USDC: ${usdc_supply_bn:.1f}B  |  Yield: {current_yield:.2f}%\n")

    print("Generating charts...")
    p1 = chart_chain_breakdown(usdc_data)
    print(f"  [1/4] {p1}")

    p2 = chart_rldc_sensitivity(usdc_supply_bn)
    print(f"  [2/4] {p2}")

    p3 = chart_thesis_trajectory(usdc_supply_bn, current_yield)
    print(f"  [3/4] {p3}")

    p4 = chart_revenue_waterfall(usdc_supply_bn, current_yield)
    print(f"  [4/4] {p4}")

    print(f"\nAll charts saved to {OUTPUT_DIR}/")

    if "--show" in sys.argv:
        import subprocess
        for p in [p1, p2, p3, p4]:
            subprocess.Popen(["open", p])


if __name__ == "__main__":
    main()
