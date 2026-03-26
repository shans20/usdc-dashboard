#!/usr/bin/env python3
"""
USDC Dashboard — Real-time CRCL thesis tracker
Pulls USDC supply, Coinbase concentration, Treasury yields,
and estimates RLDC margin using Shan's thesis assumptions.

Usage:
    python3 dashboard.py              # Full dashboard
    python3 dashboard.py --quick      # Skip Etherscan (faster, no API key needed)
    python3 dashboard.py --sensitivity # Include RLDC sensitivity table
"""

import sys
import json
from datetime import datetime

from defillama import get_usdc_data, fmt_supply
from etherscan import get_coinbase_usdc_holdings
from fred import get_treasury_yield
from rldc import estimate_rldc, estimate_rldc_3bucket, sensitivity_table
from buckets import classify_chains
from config import ETHERSCAN_API_KEY, FRED_API_KEY, THESIS


def print_header():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*62}")
    print(f"  CRCL THESIS TRACKER — USDC Dashboard")
    print(f"  {now}")
    print(f"{'='*62}")


def print_usdc_supply(usdc_data):
    print(f"\n📊 USDC SUPPLY")
    print(f"{'─'*62}")
    print(f"  Total Circulating:  {fmt_supply(usdc_data['total_supply_usd'])}")
    print(f"  Peg Price:          ${usdc_data['price']:.4f}")
    print(f"\n  Top Chains:")
    for chain, supply in list(usdc_data["chain_breakdown"].items())[:8]:
        pct = supply / usdc_data["total_supply_usd"] * 100
        bar = "█" * int(pct / 2) + "░" * (25 - int(pct / 2))
        print(f"    {chain:16s} {fmt_supply(supply):>10s}  {bar} {pct:5.1f}%")


def print_coinbase(coinbase_data, usdc_total):
    print(f"\n🏦 COINBASE USDC CONCENTRATION (Ethereum only)")
    print(f"{'─'*62}")
    cb_total = coinbase_data["total_usdc_on_coinbase_eth"]
    cb_pct = cb_total / usdc_total * 100 if usdc_total > 0 else 0
    print(f"  USDC on Coinbase (ETH): {fmt_supply(cb_total)}")
    print(f"  % of Total USDC:        {cb_pct:.1f}%")
    print(f"  Thesis assumption:      {THESIS['cb_on_platform_pct_of_usdc']:.0%}")
    delta = cb_pct / 100 - THESIS["cb_on_platform_pct_of_usdc"]
    direction = "ABOVE" if delta > 0 else "BELOW"
    print(f"  vs Thesis:              {abs(delta):.1%} {direction}")
    print(f"\n  ⚠️  {coinbase_data['note']}")
    return cb_pct / 100


def print_yield(yield_data):
    print(f"\n📈 TREASURY YIELD (Reserve Income Proxy)")
    print(f"{'─'*62}")
    if yield_data.get("yield_pct") is not None:
        print(f"  {yield_data['description']}: {yield_data['yield_pct']:.2f}%")
        print(f"  As of: {yield_data['date']}")
        thesis_yield = THESIS.get("_last_yield")  # not in config, just for display
        print(f"  Thesis FY26E yield:     3.70%")
    else:
        print(f"  ⚠️  {yield_data.get('error')}")


def print_rldc(rldc_result, actual_cb_pct=None):
    r = rldc_result
    print(f"\n💰 RLDC MARGIN ESTIMATE (Annualized)")
    print(f"{'─'*62}")
    if actual_cb_pct is not None:
        print(f"  Using LIVE Coinbase %:  {r['coinbase_pct_used']:.1%}")
    else:
        print(f"  Using THESIS CB %:      {r['coinbase_pct_used']:.1%}")
    print(f"  USDC Supply:            ${r['usdc_supply_bn']:.1f}B")
    print(f"  Reserve Yield:          {r['reserve_yield_pct']:.2f}%")
    print(f"")
    print(f"  Revenue")
    print(f"    Reserve Income:       ${r['reserve_income_mm']:>8,.0f}mm")
    print(f"    Other Revenue:        ${r['other_revenue_mm']:>8,.0f}mm")
    print(f"    Total Revenue:        ${r['total_revenue_mm']:>8,.0f}mm")
    print(f"")
    print(f"  Distribution")
    print(f"    CB On-Platform:       ${r['cb_distribution_on_mm']:>8,.0f}mm")
    print(f"    CB Off-Platform:      ${r['cb_distribution_off_mm']:>8,.0f}mm")
    print(f"    Other:                ${r['other_distribution_mm']:>8,.0f}mm")
    print(f"    Total Distribution:   ${r['total_distribution_mm']:>8,.0f}mm")
    print(f"")
    print(f"  ┌─────────────────────────────────────┐")
    print(f"  │  RLDC:          ${r['rldc_mm']:>8,.0f}mm          │")
    print(f"  │  RLDC Margin:   {r['rldc_margin']:>7.1%}             │")
    print(f"  │  Adj EBITDA:    ${r['adj_ebitda_mm']:>8,.0f}mm          │")
    print(f"  │  GAAP EPS:      ${r['gaap_eps']:>7.2f}              │")
    print(f"  │  Adj EPS:       ${r['adj_eps']:>7.2f}              │")
    print(f"  └─────────────────────────────────────┘")


def print_sensitivity(usdc_supply_bn):
    print(f"\n📐 RLDC MARGIN SENSITIVITY")
    print(f"{'─'*62}")
    yields = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    cb_pcts = [0.15, 0.18, 0.21, 0.25, 0.30]

    # Header
    header = f"  {'Yield':>6s}"
    for cb in cb_pcts:
        header += f"  CB={cb:.0%}"
    print(header)
    print(f"  {'─'*50}")

    for y in yields:
        row = f"  {y:5.1f}%"
        for cb in cb_pcts:
            result = estimate_rldc(usdc_supply_bn, y, cb)
            row += f"  {result['rldc_margin']:>6.1%}"
        print(row)

    print(f"\n  (USDC supply held constant at ${usdc_supply_bn:.1f}B)")


def save_snapshot(data):
    """Save a JSON snapshot for historical tracking."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"snapshots/snapshot_{timestamp}.json"
    import os
    os.makedirs("snapshots", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  💾 Snapshot saved: {filename}")


def main():
    quick_mode = "--quick" in sys.argv
    show_sensitivity = "--sensitivity" in sys.argv

    print_header()

    # 1. USDC Supply from DefiLlama
    print("\n  Fetching USDC supply from DefiLlama...")
    usdc_data = get_usdc_data()
    usdc_supply_bn = usdc_data["total_supply_usd"] / 1e9
    print_usdc_supply(usdc_data)

    # 2. Coinbase concentration from Etherscan
    actual_cb_pct = None
    coinbase_data = None
    if not quick_mode:
        if not ETHERSCAN_API_KEY:
            print(f"\n  ⚠️  No ETHERSCAN_API_KEY — skipping Coinbase tracking.")
            print(f"     Set env var or edit config.py. Free key: https://etherscan.io/apis")
        else:
            print("\n  Fetching Coinbase wallets from Etherscan...")
            coinbase_data = get_coinbase_usdc_holdings()
            cb_pct = print_coinbase(coinbase_data, usdc_data["total_supply_usd"])
            # Only use live CB% if it's meaningful (wallets may be outdated)
            if cb_pct > 0.01:
                actual_cb_pct = cb_pct
            else:
                print(f"\n  ⚠️  Coinbase wallets returned ~0 — likely outdated addresses.")
                print(f"     Falling back to thesis assumption ({THESIS['cb_on_platform_pct_of_usdc']:.0%}).")
                print(f"     Update COINBASE_ETH_WALLETS in config.py with current addresses.")

    # 3. Treasury yield from FRED
    yield_data = get_treasury_yield()
    print_yield(yield_data)

    # Use live yield if available, else thesis assumption
    reserve_yield = yield_data.get("yield_pct") or 3.7

    # 4. RLDC Margin estimate (2-bucket legacy)
    rldc_result = estimate_rldc(usdc_supply_bn, reserve_yield, actual_cb_pct)
    print_rldc(rldc_result, actual_cb_pct)

    # 5. Circle-Direct Analysis (Third Bucket)
    chain_breakdown_bn = {k: v / 1e9 for k, v in usdc_data["chain_breakdown"].items()}
    buckets = classify_chains(chain_breakdown_bn, usdc_supply_bn)
    r3 = estimate_rldc_3bucket(usdc_supply_bn, reserve_yield,
                                circle_direct_bn=buckets["circle_direct_bn"])

    print(f"\n🔵 CIRCLE-DIRECT ANALYSIS (Third Bucket)")
    print(f"{'─'*62}")
    print(f"  Circle-Direct chains (CB gets $0):")
    for chain, bn in sorted(buckets["circle_direct_chains"].items(), key=lambda x: x[1], reverse=True):
        pct = bn / usdc_supply_bn * 100
        print(f"    {chain:20s} ${bn:.2f}B  ({pct:.1f}%)")
    print(f"  Total Circle-Direct:    ${buckets['circle_direct_bn']:.2f}B  ({buckets['circle_direct_pct']:.1%})")
    print(f"")
    print(f"  Three-Bucket Distribution:")
    print(f"    Bucket 1 (On-plat, CB 100%):  {r3['cb_on_platform_pct']:.1%}  → ${r3['bucket1_dist_mm']:>7,.0f}mm")
    print(f"    Bucket 2 (Off-plat, CB 50%):  {r3['cb_distributed_pct']:.1%}  → ${r3['bucket2_dist_mm']:>7,.0f}mm")
    print(f"    Bucket 3 (Circle-direct, 0%): {r3['circle_direct_pct']:.1%}   → $       0mm")
    print(f"")
    print(f"  ┌─────────────────────────────────────────────┐")
    print(f"  │  3-Bucket RLDC Margin:  {r3['rldc_margin']:.1%}                │")
    print(f"  │  vs 2-Bucket:           {rldc_result['rldc_margin']:.1%}  (+{r3['margin_uplift']:.1%})   │")
    print(f"  │  CB Savings:            ${r3['cb_savings_mm']:>6,.0f}mm/yr         │")
    print(f"  │  3-Bucket Adj EPS:      ${r3['adj_eps']:>6.2f}              │")
    print(f"  └─────────────────────────────────────────────┘")

    # 6. Sensitivity table
    if show_sensitivity:
        print_sensitivity(usdc_supply_bn)

    # 7. vs Thesis check
    print(f"\n📋 THESIS CHECK")
    print(f"{'─'*62}")
    thesis_usdc_fy26 = 105.4
    pct_to_target = usdc_supply_bn / thesis_usdc_fy26 * 100
    print(f"  USDC now:          ${usdc_supply_bn:.1f}B")
    print(f"  FY26E target:      ${thesis_usdc_fy26:.1f}B  (40% CAGR)")
    print(f"  Progress:          {pct_to_target:.0f}%")
    print(f"  RLDC Margin now:   {rldc_result['rldc_margin']:.1%}")
    print(f"  FY26E target:      40.6%")

    # Save snapshot
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "usdc_supply_bn": usdc_supply_bn,
        "reserve_yield_pct": reserve_yield,
        "coinbase_pct": actual_cb_pct,
        "rldc_margin": rldc_result["rldc_margin"],
        "rldc_mm": rldc_result["rldc_mm"],
        "adj_eps": rldc_result["adj_eps"],
        "total_revenue_mm": rldc_result["total_revenue_mm"],
        "adj_ebitda_mm": rldc_result["adj_ebitda_mm"],
        "chain_breakdown": {k: round(v / 1e9, 2) for k, v in list(usdc_data["chain_breakdown"].items())[:15]},
        # 3-bucket fields
        "circle_direct_bn": buckets["circle_direct_bn"],
        "circle_direct_pct": buckets["circle_direct_pct"],
        "circle_direct_chains": buckets["circle_direct_chains"],
        "rldc_margin_3bucket": r3["rldc_margin"],
        "cb_savings_mm": r3["cb_savings_mm"],
        "margin_uplift": r3["margin_uplift"],
    }
    save_snapshot(snapshot)

    print(f"\n{'='*62}\n")


if __name__ == "__main__":
    main()
