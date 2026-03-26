"""
RLDC Margin Calculator
Estimates Circle's Reserve Less Distribution Costs margin in real-time
using live USDC supply, Treasury yields, and thesis assumptions.

RLDC = Reserve Income - Coinbase Distribution - Other Distribution
RLDC Margin = RLDC / Total Revenue

From Shan's thesis:
- Reserve Income = Avg USDC * Reserve Yield
- CB On-Platform Distribution = CB On-Platform % of USDC * Reserve Income * CB Take (100%)
- CB Off-Platform Distribution = (1 - CB On-Platform %) * Reserve Income * CB Take (50%)
- Other Distribution = 2% of Reserve Income
"""

from config import THESIS


def estimate_rldc(usdc_supply_bn, treasury_yield_pct, coinbase_pct_actual=None):
    """
    Estimate annualized RLDC margin using live data + thesis assumptions.

    Args:
        usdc_supply_bn: Current USDC supply in billions (e.g., 75.3)
        treasury_yield_pct: Current 3-month T-bill rate (e.g., 4.25)
        coinbase_pct_actual: If we have actual Coinbase % from Etherscan, use it.
                            Otherwise falls back to thesis assumption.
    """
    t = THESIS
    yield_decimal = treasury_yield_pct / 100

    # Use actual Coinbase % if available, else thesis assumption
    cb_on_platform_pct = coinbase_pct_actual if coinbase_pct_actual is not None else t["cb_on_platform_pct_of_usdc"]

    # Reserve Income (annualized, $mm)
    reserve_income = usdc_supply_bn * 1000 * yield_decimal  # $mm

    # Other Revenue (transaction + subscription, from thesis)
    other_revenue = t["other_revenue_annual_mm"]
    total_revenue = reserve_income + other_revenue

    # Distribution costs
    cb_on_platform_income = cb_on_platform_pct * reserve_income
    cb_off_platform_income = (1 - cb_on_platform_pct) * reserve_income

    cb_dist_on = cb_on_platform_income * t["cb_takes_on_platform"]
    cb_dist_off = cb_off_platform_income * t["cb_takes_off_platform"]
    other_dist = reserve_income * t["other_distribution_pct"]

    total_distribution = cb_dist_on + cb_dist_off + other_dist

    # RLDC
    rldc = total_revenue - total_distribution
    rldc_margin = rldc / total_revenue if total_revenue > 0 else 0

    # Bonus: estimate EPS
    adj_opex = t["adj_opex_annual_mm"]
    adj_ebitda = rldc - adj_opex
    da = t["da_annual_mm"]
    sbc = t["normalized_sbc_annual_mm"]
    pretax = adj_ebitda - da - sbc
    tax = max(0, pretax * t["tax_rate"])
    net_income = pretax - tax
    gaap_eps = net_income / t["diluted_shares_mm"]

    # Adj EPS (add back SBC after tax)
    adj_net_income = net_income + sbc * (1 - t["tax_rate"])
    adj_eps = adj_net_income / t["diluted_shares_mm"]

    return {
        "usdc_supply_bn": usdc_supply_bn,
        "reserve_yield_pct": treasury_yield_pct,
        "coinbase_pct_used": cb_on_platform_pct,
        "reserve_income_mm": reserve_income,
        "other_revenue_mm": other_revenue,
        "total_revenue_mm": total_revenue,
        "cb_distribution_on_mm": cb_dist_on,
        "cb_distribution_off_mm": cb_dist_off,
        "other_distribution_mm": other_dist,
        "total_distribution_mm": total_distribution,
        "rldc_mm": rldc,
        "rldc_margin": rldc_margin,
        "adj_opex_mm": adj_opex,
        "adj_ebitda_mm": adj_ebitda,
        "gaap_eps": gaap_eps,
        "adj_eps": adj_eps,
    }


def estimate_rldc_3bucket(usdc_supply_bn, treasury_yield_pct,
                          circle_direct_bn=0, coinbase_on_platform_pct=None):
    """
    Three-bucket RLDC estimation incorporating Circle-direct USDC.

    Bucket 1: On-platform (CB keeps 100%) — thesis assumption
    Bucket 2: Off-platform CB-distributed (CB gets 50%) — residual
    Bucket 3: Circle-direct (CB gets 0%) — observable from chain data

    Args:
        usdc_supply_bn: Total USDC supply in billions
        treasury_yield_pct: Current 3-month T-bill rate
        circle_direct_bn: USDC minted directly through Circle (bypasses CB)
        coinbase_on_platform_pct: CB on-platform % (None = thesis default)
    """
    t = THESIS
    yield_decimal = treasury_yield_pct / 100

    cb_on_pct = coinbase_on_platform_pct if coinbase_on_platform_pct is not None else t["cb_on_platform_pct_of_usdc"]
    circle_direct_pct = circle_direct_bn / usdc_supply_bn if usdc_supply_bn > 0 else 0
    cb_distributed_pct = max(0, 1 - circle_direct_pct - cb_on_pct)

    # Reserve Income
    reserve_income = usdc_supply_bn * 1000 * yield_decimal
    other_revenue = t["other_revenue_annual_mm"]
    total_revenue = reserve_income + other_revenue

    # Distribution by bucket
    bucket1_dist = cb_on_pct * reserve_income * t["cb_takes_on_platform"]       # CB keeps 100%
    bucket2_dist = cb_distributed_pct * reserve_income * t["cb_takes_off_platform"]  # CB gets 50%
    bucket3_dist = 0  # Circle-direct: CB gets nothing
    other_dist = reserve_income * t["other_distribution_pct"]

    total_distribution = bucket1_dist + bucket2_dist + bucket3_dist + other_dist

    # What CB *would* have gotten on Circle-direct USDC under 2-bucket model
    cb_savings_mm = circle_direct_pct * reserve_income * t["cb_takes_off_platform"]

    # RLDC
    rldc = total_revenue - total_distribution
    rldc_margin = rldc / total_revenue if total_revenue > 0 else 0

    # Also compute 2-bucket for comparison
    old = estimate_rldc(usdc_supply_bn, treasury_yield_pct, cb_on_pct)
    margin_uplift = rldc_margin - old["rldc_margin"]

    # EPS
    adj_opex = t["adj_opex_annual_mm"]
    adj_ebitda = rldc - adj_opex
    da = t["da_annual_mm"]
    sbc = t["normalized_sbc_annual_mm"]
    pretax = adj_ebitda - da - sbc
    tax = max(0, pretax * t["tax_rate"])
    net_income = pretax - tax
    gaap_eps = net_income / t["diluted_shares_mm"]
    adj_net_income = net_income + sbc * (1 - t["tax_rate"])
    adj_eps = adj_net_income / t["diluted_shares_mm"]

    return {
        "usdc_supply_bn": usdc_supply_bn,
        "reserve_yield_pct": treasury_yield_pct,
        # Bucket breakdown
        "cb_on_platform_pct": cb_on_pct,
        "cb_distributed_pct": cb_distributed_pct,
        "circle_direct_pct": circle_direct_pct,
        "circle_direct_bn": circle_direct_bn,
        # Distribution
        "bucket1_dist_mm": bucket1_dist,
        "bucket2_dist_mm": bucket2_dist,
        "bucket3_dist_mm": bucket3_dist,
        "other_distribution_mm": other_dist,
        "total_distribution_mm": total_distribution,
        # Revenue
        "reserve_income_mm": reserve_income,
        "other_revenue_mm": other_revenue,
        "total_revenue_mm": total_revenue,
        # RLDC
        "rldc_mm": rldc,
        "rldc_margin": rldc_margin,
        "rldc_margin_2bucket": old["rldc_margin"],
        "margin_uplift": margin_uplift,
        "cb_savings_mm": cb_savings_mm,
        # Earnings
        "adj_opex_mm": adj_opex,
        "adj_ebitda_mm": adj_ebitda,
        "gaap_eps": gaap_eps,
        "adj_eps": adj_eps,
    }


def sensitivity_table(usdc_supply_bn, yield_range, cb_pct_range):
    """
    Generate RLDC margin sensitivity across yield and Coinbase % scenarios.
    Useful for stress testing the thesis.
    """
    rows = []
    for y in yield_range:
        row = {"yield_pct": y}
        for cb in cb_pct_range:
            result = estimate_rldc(usdc_supply_bn, y, cb)
            row[f"cb_{cb:.0%}"] = result["rldc_margin"]
        rows.append(row)
    return rows


if __name__ == "__main__":
    # Example with thesis assumptions
    result = estimate_rldc(usdc_supply_bn=90.4, treasury_yield_pct=3.7)

    print(f"\n{'='*55}")
    print(f"RLDC MARGIN ESTIMATE (Annualized)")
    print(f"{'='*55}")
    print(f"USDC Supply:        ${result['usdc_supply_bn']:.1f}B")
    print(f"Reserve Yield:      {result['reserve_yield_pct']:.2f}%")
    print(f"CB % (on-platform): {result['coinbase_pct_used']:.1%}")
    print(f"{'─'*55}")
    print(f"Reserve Income:     ${result['reserve_income_mm']:,.0f}mm")
    print(f"Other Revenue:      ${result['other_revenue_mm']:,.0f}mm")
    print(f"Total Revenue:      ${result['total_revenue_mm']:,.0f}mm")
    print(f"{'─'*55}")
    print(f"CB Dist (on-plat):  ${result['cb_distribution_on_mm']:,.0f}mm")
    print(f"CB Dist (off-plat): ${result['cb_distribution_off_mm']:,.0f}mm")
    print(f"Other Dist:         ${result['other_distribution_mm']:,.0f}mm")
    print(f"Total Distribution: ${result['total_distribution_mm']:,.0f}mm")
    print(f"{'─'*55}")
    print(f"RLDC:               ${result['rldc_mm']:,.0f}mm")
    print(f"RLDC Margin:        {result['rldc_margin']:.1%}")
    print(f"{'─'*55}")
    print(f"Adj EBITDA:         ${result['adj_ebitda_mm']:,.0f}mm")
    print(f"GAAP EPS:           ${result['gaap_eps']:.2f}")
    print(f"Adj EPS:            ${result['adj_eps']:.2f}")
