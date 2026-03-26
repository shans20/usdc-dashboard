"""
Etherscan client — track USDC held in known Coinbase wallets.
Requires free Etherscan API key for reliable rate limits.
"""

import requests
import time
from config import ETHERSCAN_API_KEY, COINBASE_ETH_WALLETS, USDC_CONTRACT

ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
USDC_DECIMALS = 6


def get_usdc_balance(wallet_address):
    """Get USDC balance for a single Ethereum address."""
    params = {
        "chainid": 1,
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": USDC_CONTRACT,
        "address": wallet_address,
        "tag": "latest",
    }
    if ETHERSCAN_API_KEY:
        params["apikey"] = ETHERSCAN_API_KEY

    resp = requests.get(ETHERSCAN_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") == "1":
        raw_balance = int(data["result"])
        return raw_balance / (10 ** USDC_DECIMALS)
    return 0.0


def get_coinbase_usdc_holdings():
    """
    Sum USDC across all known Coinbase Ethereum wallets.
    Note: This is Ethereum-only. Coinbase also holds USDC on Base, Solana, etc.
    Ethereum typically represents the majority of exchange holdings.
    """
    holdings = {}
    total = 0.0

    for wallet in COINBASE_ETH_WALLETS:
        balance = get_usdc_balance(wallet)
        if balance > 0:
            holdings[wallet] = balance
            total += balance
        # Rate limit: 5 calls/sec with key, 1 call/5sec without
        if ETHERSCAN_API_KEY:
            time.sleep(0.25)
        else:
            time.sleep(5.5)

    return {
        "total_usdc_on_coinbase_eth": total,
        "wallet_balances": holdings,
        "note": "Ethereum mainnet only — does not include Base, Solana, or other chains",
    }


if __name__ == "__main__":
    if not ETHERSCAN_API_KEY:
        print("WARNING: No ETHERSCAN_API_KEY set. Rate limited to 1 req/5sec.")
        print("Get a free key at https://etherscan.io/apis\n")

    print("Fetching Coinbase USDC holdings (Ethereum)...")
    data = get_coinbase_usdc_holdings()
    print(f"\nTotal USDC on Coinbase (ETH): ${data['total_usdc_on_coinbase_eth']:,.0f}")
    print(f"\nBreakdown:")
    for wallet, bal in sorted(data["wallet_balances"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {wallet[:10]}...{wallet[-6:]}  ${bal:>15,.0f}")
    print(f"\n{data['note']}")
