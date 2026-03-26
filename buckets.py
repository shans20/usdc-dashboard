"""
Circle-Direct Classification Engine (Third Bucket)

Classifies USDC chain supply into three distribution buckets:
  Bucket 1: On-platform (Coinbase) — CB keeps 100% of reserve income
  Bucket 2: Off-platform Coinbase-distributed — CB gets 50%
  Bucket 3: Circle-direct — CB gets 0%

Source: Circle CFO meeting (Mar 4, 2026)
"""

from config import CIRCLE_DIRECT_CHAINS, THESIS


def classify_chains(chain_breakdown, total_usdc_bn=None):
    """
    Classify chain-level USDC supply into three buckets.

    Args:
        chain_breakdown: dict of {chain_name: supply} where supply is in $B or raw USD
        total_usdc_bn: total USDC supply in billions (if None, summed from chain_breakdown)

    Returns dict with bucket breakdown.
    """
    # Detect if values are in billions or raw USD
    sample_val = next(iter(chain_breakdown.values()), 0) if chain_breakdown else 0
    is_billions = sample_val < 1000  # if < 1000, assume billions; else raw USD

    circle_direct_chains = {}
    coinbase_distributed_chains = {}

    for chain, supply in chain_breakdown.items():
        supply_bn = supply if is_billions else supply / 1e9
        if chain in CIRCLE_DIRECT_CHAINS:
            circle_direct_chains[chain] = supply_bn
        else:
            coinbase_distributed_chains[chain] = supply_bn

    circle_direct_bn = sum(circle_direct_chains.values())
    coinbase_distributed_bn = sum(coinbase_distributed_chains.values())

    if total_usdc_bn is None:
        total_usdc_bn = circle_direct_bn + coinbase_distributed_bn

    circle_direct_pct = circle_direct_bn / total_usdc_bn if total_usdc_bn > 0 else 0
    cb_on_platform_pct = THESIS["cb_on_platform_pct_of_usdc"]

    # Bucket 2 = everything that's not Circle-direct and not on-platform
    cb_distributed_pct = max(0, 1 - circle_direct_pct - cb_on_platform_pct)

    return {
        "circle_direct_bn": round(circle_direct_bn, 2),
        "circle_direct_pct": circle_direct_pct,
        "circle_direct_chains": circle_direct_chains,
        "cb_on_platform_pct": cb_on_platform_pct,
        "cb_distributed_pct": cb_distributed_pct,
        "coinbase_distributed_bn": round(coinbase_distributed_bn, 2),
        "total_usdc_bn": round(total_usdc_bn, 2),
    }


if __name__ == "__main__":
    # Quick test with current approximate data
    test_chains = {
        "Ethereum": 52.14, "Solana": 8.14, "Hyperliquid L1": 4.82,
        "Base": 4.35, "Arbitrum": 2.16, "Polygon": 1.85, "BSC": 1.28,
        "Sui": 0.40, "Avalanche": 0.56,
    }
    result = classify_chains(test_chains)
    print(f"\nThree-Bucket Classification:")
    print(f"  Bucket 1 (On-platform, CB 100%):  {result['cb_on_platform_pct']:.1%}")
    print(f"  Bucket 2 (Off-platform, CB 50%):  {result['cb_distributed_pct']:.1%}")
    print(f"  Bucket 3 (Circle-direct, CB 0%):  {result['circle_direct_pct']:.1%}")
    print(f"\n  Circle-direct chains:")
    for chain, bn in result["circle_direct_chains"].items():
        print(f"    {chain:20s} ${bn:.2f}B")
    print(f"  Total Circle-direct: ${result['circle_direct_bn']:.2f}B")
