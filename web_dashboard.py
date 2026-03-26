#!/usr/bin/env python3
"""
CRCL Thesis Tracker — Streamlit Web Dashboard
Launch: streamlit run web_dashboard.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from defillama import get_usdc_data, fmt_supply
from fred import get_treasury_yield
from rldc import estimate_rldc, estimate_rldc_3bucket
from buckets import classify_chains
from config import THESIS

st.set_page_config(page_title="CRCL Thesis Tracker", page_icon="🔵", layout="wide")

# --- Dark theme styling ---
st.markdown("""
<style>
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: bold; color: #58a6ff; }
    .metric-label { font-size: 13px; color: #8b949e; margin-top: 4px; }
    .metric-delta-up { color: #3fb950; font-size: 13px; }
    .metric-delta-down { color: #f85149; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

st.title("CRCL Thesis Tracker")
st.caption(f"Live USDC data  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")


@st.cache_data(ttl=300)
def fetch_data():
    usdc_data = get_usdc_data()
    yield_data = get_treasury_yield()
    return usdc_data, yield_data


with st.spinner("Fetching live data from DefiLlama & FRED..."):
    usdc_data, yield_data = fetch_data()

usdc_supply_bn = usdc_data["total_supply_usd"] / 1e9
reserve_yield = yield_data.get("yield_pct") or 3.7

# Chain buckets
chain_breakdown_bn = {k: v / 1e9 for k, v in usdc_data["chain_breakdown"].items()}
buckets = classify_chains(chain_breakdown_bn, usdc_supply_bn)

# RLDC calculations
rldc_2b = estimate_rldc(usdc_supply_bn, reserve_yield)
rldc_3b = estimate_rldc_3bucket(usdc_supply_bn, reserve_yield,
                                 circle_direct_bn=buckets["circle_direct_bn"])

# ============================================================
# TOP METRICS
# ============================================================
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)

thesis_usdc_fy26 = 105.4
progress = usdc_supply_bn / thesis_usdc_fy26 * 100

c1.metric("USDC Supply", f"${usdc_supply_bn:.1f}B", f"{progress:.0f}% of FY26E target")
c2.metric("Reserve Yield", f"{reserve_yield:.2f}%", f"Thesis: 3.70%")
c3.metric("RLDC Margin (2-Bucket)", f"{rldc_2b['rldc_margin']:.1%}", f"Target: 40.6%")
c4.metric("RLDC Margin (3-Bucket)", f"{rldc_3b['rldc_margin']:.1%}", f"+{rldc_3b['margin_uplift']:.1%} uplift")
c5.metric("Adj EPS (3-Bucket)", f"${rldc_3b['adj_eps']:.2f}", f"GAAP: ${rldc_3b['gaap_eps']:.2f}")

# ============================================================
# ROW 1: Chain Breakdown + Revenue Waterfall
# ============================================================
st.markdown("---")
col_left, col_right = st.columns(2)

# --- Chain Breakdown Donut ---
with col_left:
    st.subheader("USDC Distribution by Chain")
    chains = list(usdc_data["chain_breakdown"].items())[:10]
    labels = [c[0] for c in chains]
    values = [c[1] / 1e9 for c in chains]
    other = usdc_supply_bn - sum(values)
    if other > 0.01:
        labels.append("Other")
        values.append(other)

    fig_donut = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5, textinfo="label+percent",
        textposition="outside",
        marker=dict(colors=px.colors.qualitative.Set2),
    ))
    fig_donut.update_layout(
        height=420, margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        showlegend=False,
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# --- Revenue Waterfall ---
with col_right:
    st.subheader("Revenue Waterfall (Run-Rate)")
    r = rldc_2b
    wf_labels = ["Reserve Income", "Other Revenue", "CB On-Plat", "CB Off-Plat", "Other Dist", "RLDC", "Adj OpEx", "Adj EBITDA"]
    wf_measures = ["relative", "relative", "relative", "relative", "relative", "total", "relative", "total"]
    wf_values = [
        r["reserve_income_mm"], r["other_revenue_mm"],
        -r["cb_distribution_on_mm"], -r["cb_distribution_off_mm"],
        -r["other_distribution_mm"], 0,
        -r["adj_opex_mm"], 0,
    ]
    wf_text = [f"${abs(v):,.0f}mm" for v in wf_values]
    wf_text[5] = f"${r['rldc_mm']:,.0f}mm"
    wf_text[7] = f"${r['adj_ebitda_mm']:,.0f}mm"

    fig_wf = go.Figure(go.Waterfall(
        x=wf_labels, y=wf_values, measure=wf_measures,
        text=wf_text, textposition="outside",
        connector=dict(line=dict(color="#30363d")),
        increasing=dict(marker_color="#3fb950"),
        decreasing=dict(marker_color="#f85149"),
        totals=dict(marker_color="#58a6ff"),
    ))
    fig_wf.update_layout(
        height=420, margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        yaxis=dict(gridcolor="#21262d", title="$ Millions"),
        xaxis=dict(gridcolor="#21262d"),
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ============================================================
# ROW 2: Three-Bucket Analysis + Sensitivity Heatmap
# ============================================================
st.markdown("---")
col_3b, col_sens = st.columns(2)

# --- Three-Bucket Breakdown ---
with col_3b:
    st.subheader("Three-Bucket Distribution")
    bucket_labels = ["Bucket 1: On-Platform\n(CB 100%)", "Bucket 2: Off-Platform\n(CB 50%)", "Bucket 3: Circle-Direct\n(CB 0%)"]
    bucket_pcts = [rldc_3b["cb_on_platform_pct"], rldc_3b["cb_distributed_pct"], rldc_3b["circle_direct_pct"]]
    bucket_dists = [rldc_3b["bucket1_dist_mm"], rldc_3b["bucket2_dist_mm"], 0]

    fig_3b = go.Figure()
    fig_3b.add_trace(go.Bar(
        x=bucket_labels, y=[p * 100 for p in bucket_pcts],
        text=[f"{p:.1%}" for p in bucket_pcts],
        textposition="outside",
        marker_color=["#f85149", "#d29922", "#3fb950"],
        name="% of USDC",
    ))
    fig_3b.update_layout(
        height=400, margin=dict(t=30, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        yaxis=dict(title="% of USDC", gridcolor="#21262d"),
        xaxis=dict(gridcolor="#21262d"),
    )

    # Annotate distribution costs
    for i, d in enumerate(bucket_dists):
        fig_3b.add_annotation(x=bucket_labels[i], y=bucket_pcts[i] * 100 * 0.5,
                              text=f"Dist: ${d:,.0f}mm", showarrow=False,
                              font=dict(color="white", size=11))

    st.plotly_chart(fig_3b, use_container_width=True)

    st.info(f"CB Savings from Circle-Direct: **${rldc_3b['cb_savings_mm']:,.0f}mm/yr**  |  3-Bucket Adj EPS: **${rldc_3b['adj_eps']:.2f}**")

# --- Sensitivity Heatmap ---
with col_sens:
    st.subheader("RLDC Margin Sensitivity")
    yields = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    cb_pcts = [0.10, 0.15, 0.18, 0.21, 0.25, 0.30]

    z = []
    for y in yields:
        row = []
        for cb in cb_pcts:
            result = estimate_rldc(usdc_supply_bn, y, cb)
            row.append(round(result["rldc_margin"] * 100, 1))
        z.append(row)

    fig_heat = go.Figure(go.Heatmap(
        z=z,
        x=[f"CB={cb:.0%}" for cb in cb_pcts],
        y=[f"{y:.1f}%" for y in yields],
        text=[[f"{v:.1f}%" for v in row] for row in z],
        texttemplate="%{text}",
        colorscale="RdYlGn",
        zmin=30, zmax=55,
    ))
    fig_heat.update_layout(
        height=400, margin=dict(t=30, b=20, l=20, r=60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        xaxis=dict(title="Coinbase On-Platform %"),
        yaxis=dict(title="Reserve Yield"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# ============================================================
# ROW 3: Thesis Trajectory
# ============================================================
st.markdown("---")
st.subheader("Thesis Trajectory: Now vs FY26E-FY30E")

col_usdc_proj, col_eps_proj = st.columns(2)

years = ["Now (run-rate)", "FY26E", "FY27E", "FY28E", "FY29E", "FY30E"]
thesis_usdc = [usdc_supply_bn, 105.4, 147.6, 206.6, 289.3, 405.0]
thesis_eps = [rldc_2b["adj_eps"], 2.32, 3.48, 5.13, 10.47, 14.30]

with col_usdc_proj:
    fig_usdc = go.Figure(go.Bar(
        x=years, y=thesis_usdc,
        text=[f"${v:.0f}B" for v in thesis_usdc],
        textposition="outside",
        marker_color=["#58a6ff"] + ["#3fb950"] * 5,
    ))
    fig_usdc.update_layout(
        title="USDC Supply ($B) — 40% CAGR Target",
        height=380, margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        yaxis=dict(gridcolor="#21262d"),
    )
    st.plotly_chart(fig_usdc, use_container_width=True)

with col_eps_proj:
    fig_eps = go.Figure(go.Bar(
        x=years, y=thesis_eps,
        text=[f"${v:.2f}" for v in thesis_eps],
        textposition="outside",
        marker_color=["#d29922"] + ["#bc8cff"] * 5,
    ))
    fig_eps.update_layout(
        title="Adj EPS ($)",
        height=380, margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        yaxis=dict(gridcolor="#21262d"),
    )
    st.plotly_chart(fig_eps, use_container_width=True)

# ============================================================
# SIDEBAR: Interactive Scenario Builder
# ============================================================
st.sidebar.header("Scenario Builder")
st.sidebar.caption("Override thesis assumptions to model scenarios")

custom_supply = st.sidebar.slider("USDC Supply ($B)", 40.0, 200.0, usdc_supply_bn, 1.0)
custom_yield = st.sidebar.slider("Reserve Yield (%)", 1.0, 6.0, reserve_yield, 0.1)
custom_cb_pct = st.sidebar.slider("CB On-Platform %", 0.05, 0.40, THESIS["cb_on_platform_pct_of_usdc"], 0.01)
custom_cd_pct = st.sidebar.slider("Circle-Direct %", 0.0, 0.50, buckets["circle_direct_pct"], 0.01)

custom_2b = estimate_rldc(custom_supply, custom_yield, custom_cb_pct)
custom_3b = estimate_rldc_3bucket(custom_supply, custom_yield,
                                   circle_direct_bn=custom_supply * custom_cd_pct,
                                   coinbase_on_platform_pct=custom_cb_pct)

st.sidebar.markdown("---")
st.sidebar.markdown("### Scenario Results")
st.sidebar.metric("Revenue", f"${custom_2b['total_revenue_mm']:,.0f}mm")
st.sidebar.metric("RLDC Margin (2B)", f"{custom_2b['rldc_margin']:.1%}")
st.sidebar.metric("RLDC Margin (3B)", f"{custom_3b['rldc_margin']:.1%}")
st.sidebar.metric("Adj EPS (3B)", f"${custom_3b['adj_eps']:.2f}")
st.sidebar.metric("CB Savings", f"${custom_3b['cb_savings_mm']:,.0f}mm/yr")

# ============================================================
# FOOTER: Detailed P&L
# ============================================================
st.markdown("---")
with st.expander("Detailed P&L (Run-Rate, Annualized)"):
    pl1, pl2 = st.columns(2)
    with pl1:
        st.markdown("**Revenue**")
        st.text(f"  Reserve Income:      ${rldc_2b['reserve_income_mm']:>8,.0f}mm")
        st.text(f"  Other Revenue:       ${rldc_2b['other_revenue_mm']:>8,.0f}mm")
        st.text(f"  Total Revenue:       ${rldc_2b['total_revenue_mm']:>8,.0f}mm")
    with pl2:
        st.markdown("**Distribution & Earnings**")
        st.text(f"  CB On-Platform:      ${rldc_2b['cb_distribution_on_mm']:>8,.0f}mm")
        st.text(f"  CB Off-Platform:     ${rldc_2b['cb_distribution_off_mm']:>8,.0f}mm")
        st.text(f"  Other Dist:          ${rldc_2b['other_distribution_mm']:>8,.0f}mm")
        st.text(f"  RLDC:                ${rldc_2b['rldc_mm']:>8,.0f}mm")
        st.text(f"  Adj EBITDA:          ${rldc_2b['adj_ebitda_mm']:>8,.0f}mm")
        st.text(f"  GAAP EPS:            ${rldc_2b['gaap_eps']:>8.2f}")
        st.text(f"  Adj EPS:             ${rldc_2b['adj_eps']:>8.2f}")

st.caption("Data: DefiLlama (USDC supply) | FRED (Treasury yield) | Thesis assumptions from Shan's CRCL model")
