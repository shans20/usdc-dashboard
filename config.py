"""
USDC Scraper Configuration
Thesis assumptions from Shan's CRCL thesis (Feb 2026)
Calibrated against Circle 10-K + Coinbase 10-K (FY2025 actuals)
"""

# --- API Keys (Streamlit secrets > env vars > hardcoded fallback) ---
import os

def _get_secret(key, fallback=""):
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, fallback))
    except Exception:
        return os.getenv(key, fallback)

ETHERSCAN_API_KEY = _get_secret("ETHERSCAN_API_KEY", "EYUAQAHVWKWGNIEQFEW9J7UI9MM1SAM5W5")
FRED_API_KEY = _get_secret("FRED_API_KEY", "fc6e4ed5c7de32699ea8a742a5a8b05b")

# --- Known Coinbase Ethereum Wallets ---
# These are publicly labeled Coinbase hot/cold wallets on Ethereum
COINBASE_ETH_WALLETS = [
    "0x503828976D22510aad0201ac7EC88293211D23Da",  # Coinbase 2
    "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740",  # Coinbase 3
    "0x3cD751E6b0078Be393132286c442345e68FF0aaa",  # Coinbase 4
    "0xA090e606E30bD747d4E6245a1517EbE430F0057e",  # Coinbase Commerce
    "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",  # Coinbase 1
    "0x02466E547BFDAb679fC49e96bBfc62B9747D997C",  # Coinbase 8
    "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",  # Coinbase 10
    "0x77134cbC06cB00b66F4c7e623D5fdBF6777635EC",  # Coinbase 11
]

# USDC contract on Ethereum
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# --- Thesis Assumptions (from Shan's CRCL model) ---
# These are used to estimate RLDC margin in real-time
THESIS = {
    # Coinbase distribution assumptions
    # NOTE: This is an EFFECTIVE model parameter, not the literal USDC on Coinbase.
    # Coinbase 10-K: actual USDC AOP = $9.26B (12.3% of total) at Dec 2025.
    # the actual 63.1% distribution/reserve-income ratio from Circle's 10-K.
    # Coinbase FY25 stablecoin rev: $1,349mm. USDC rewards paid: $441mm (S&M expense).
    "cb_on_platform_pct_of_usdc": 0.21,   # Effective parameter (back-solved from 10-K distribution ratio)
    "cb_takes_on_platform": 1.00,          # 100% of on-platform reserve income
    "cb_takes_off_platform": 0.50,         # 50% of off-platform remainder (confirmed both 10-Ks)
    "other_distribution_pct": 0.025,       # 2.5% of reserve income (Binance $152mm + other partners $60mm in FY25)
    # OpEx
    "adj_opex_annual_mm": 549,             # FY26E adj opex $549mm (FY25A normalized: $537mm)
    "normalized_sbc_annual_mm": 230,       # FY26E normalized SBC (FY25A: $142mm ex-IPO vesting; ramps w/ post-IPO grants)
    "da_annual_mm": 85,                    # FY26E D&A (FY25A: $77mm)
    # Other
    "other_revenue_annual_mm": 176,        # FY26E other revenue (FY25A: $110mm — sub $85mm + txn $24mm + other $1mm)
    "tax_rate": 0.21,                      # Statutory rate (FY25A effective 32.4% distorted by IPO SBC)
    "diluted_shares_mm": 270,              # FY26E diluted shares (FY25 year-end: 242mm + 32mm dilutive = 274mm)
# Chains where USDC is minted directly through Circle Mint, bypassing Coinbase economics.
}

# --- Circle-Direct Chain Classification (Third Bucket) ---
# Source: Circle CFO meeting (Mar 4, 2026) — "We have partnerships with lots of different
# exchanges and there's ways we can structure things so Coinbase don't get any backend economics."
CIRCLE_DIRECT_CHAINS = [
    "Hyperliquid L1",  # CFO confirmed: mints directly through Circle Mint (~$4.8B)
    "Sui",             # Direct Circle partnership for native USDC
]

# Forward projections for Circle-direct % of total USDC (for scenario analysis)
# 10-K reveals "USDC on platform" (Circle Mint + Circle wallets) = 16.6% at Dec 2025 year-end
# This is MUCH larger than chain-data observable (Hyperliquid+Sui ~6.9%) because it includes
# institutional Circle Mint accounts and managed wallets not visible on-chain.
# Chain-level tracking underestimates the true Circle-direct bucket.
CIRCLE_DIRECT_GROWTH = {
    2026: 0.18,   # 10-K: 16.6% EOY 2025, growing — Circle Mint + managed wallets + chain-direct
    2027: 0.25,   # CPN + more exchange direct deals + institutional adoption
    2028: 0.32,   # EM neobanks, Arc participants
    2029: 0.38,   # Broad institutional adoption
    2030: 0.45,   # Mature Circle-direct ecosystem (pre-CB renegotiation benefit)
}

# --- FRED Series ---
# Using 3-month T-bill as proxy for reserve yield (Circle holds short-duration)
FRED_SERIES_ID = "DTB3"  # 3-Month Treasury Bill: Secondary Market Rate
