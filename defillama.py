"""
DefiLlama client — USDC total supply and per-chain breakdown.
No API key required. 500 req/min rate limit.
"""

import requests

DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoin/2"  # USDC = ID 2 on DefiLlama

def get_usdc_data():
    """Fetch USDC supply data from DefiLlama stablecoins API."""
    resp = requests.get(DEFILLAMA_STABLECOIN_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Total circulating supply
    total_supply = 0
    chain_breakdown = {}

    chain_circs = data.get("currentChainBalances", {})
    for chain, info in chain_circs.items():
        current = info.get("peggedUSD", 0)
        if current > 0:
            chain_breakdown[chain] = current
            total_supply += current

    # Sort chains by supply descending
    chain_breakdown = dict(sorted(chain_breakdown.items(), key=lambda x: x[1], reverse=True))

    return {
        "name": data.get("name", "USD Coin"),
        "symbol": data.get("symbol", "USDC"),
        "total_supply_usd": total_supply,
        "chain_breakdown": chain_breakdown,
        "price": data.get("price", 1.0),
    }


def fmt_supply(val):
    """Format large dollar amounts."""
    if val >= 1e9:
        return f"${val / 1e9:.2f}B"
    elif val >= 1e6:
        return f"${val / 1e6:.1f}M"
    return f"${val:,.0f}"


if __name__ == "__main__":
    data = get_usdc_data()
    print(f"\n{'='*50}")
    print(f"USDC Total Supply: {fmt_supply(data['total_supply_usd'])}")
    print(f"Price: ${data['price']:.4f}")
    print(f"\nTop chains:")
    for chain, supply in list(data["chain_breakdown"].items())[:10]:
        pct = supply / data["total_supply_usd"] * 100
        print(f"  {chain:20s} {fmt_supply(supply):>12s}  ({pct:.1f}%)")
