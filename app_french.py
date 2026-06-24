"""
Financial Calculator — Gas Project
Run:  streamlit run app.py
Requirements: pip install streamlit plotly pandas
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# -----------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------
st.set_page_config(page_title="Petroleum Economics Simulator", page_icon="⛽", layout="wide")

st.markdown("""
<style>
    .stMetric {
        background: linear-gradient(135deg, #1a2332 0%, #0e1117 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; }
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #2d3748;
    }
</style>
""", unsafe_allow_html=True)

st.title("⛽ Petroleum Economics Simulator")
st.caption("NPV · IRR · Payback · Discounted Cash Flow")

# -----------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Financial Assumptions")

    capex = st.number_input("Initial CAPEX (MM USD)", value=9.0, step=0.5, min_value=0.0)
    opex_base = st.number_input("Year 1 OPEX (MM USD/year)", value=2.0, step=0.1, min_value=0.0)
    tax_rate = st.slider("Tax Rate (%)", 0.0, 60.0, 35.0, 1.0) / 100
    discount_rate = st.slider("Discount Rate (%)", 0.0, 30.0, 10.0, 0.5) / 100
    inflation_rate = st.slider("Annual OPEX Inflation (%)", 0.0, 20.0, 8.0, 0.5) / 100
    apply_inflation = st.checkbox("Apply OPEX inflation", value=False)
    include_ethane = st.checkbox("Include ethane revenue", value=True)

    st.divider()
    st.subheader("📅 Project Duration")
    project_life = st.slider("Number of years", 5, 50, 20, 1)
    st.caption("💡 Set the duration above 20 years to simulate beyond the standard depreciation period.")

    st.divider()
    st.subheader("🛢️ Production & Prices")
    col1, col2 = st.columns(2)
    with col1:
        gas_flow_rate = st.number_input("Gas flow rate (std m³/h)", value=3752.0, step=10.0)
        propane_prod = st.number_input("Propane production (t/h)", value=0.200, step=0.01, format="%.3f")
        butane_prod = st.number_input("Butane production (t/h)", value=0.111, step=0.01, format="%.3f")
        ethane_prod = st.number_input("Ethane production (t/h)", value=0.124, step=0.01, format="%.3f")
    with col2:
        gas_price = st.number_input("Gas price (USD/m³)", value=0.15, step=0.01, format="%.2f")
        propane_price = st.number_input("Propane price (USD/t)", value=300.0, step=10.0)
        butane_price = st.number_input("Butane price (USD/t)", value=500.0, step=10.0)
        ethane_price = st.number_input("Ethane price (USD/t)", value=200.0, step=10.0)
    production_days = st.number_input("Production days per year", value=344, step=1, min_value=1, max_value=365)


# -----------------------------------------------------------------------
# CALCULATIONS
# -----------------------------------------------------------------------
gas_revenue = gas_flow_rate * gas_price * 24 * production_days / 1_000_000
propane_revenue = propane_prod * propane_price * 24 * production_days / 1_000_000
butane_revenue = butane_prod * butane_price * 24 * production_days / 1_000_000
ethane_revenue = ethane_prod * ethane_price * 24 * production_days / 1_000_000 if include_ethane else 0.0
total_revenue = gas_revenue + propane_revenue + butane_revenue + ethane_revenue

rows = []
for year in range(0, project_life + 1):
    if year == 0:
        c, o = -capex, 0.0
        rg = rp = rb = re = 0.0
        total_rev = 0.0
        ncf_after_tax = -capex
    else:
        c = 0.0
        o = opex_base * (1 + inflation_rate) ** (year - 1) if apply_inflation else opex_base
        rg, rp, rb, re = gas_revenue, propane_revenue, butane_revenue, ethane_revenue
        total_rev = total_revenue
        ncf_after_tax = (total_rev - o) * (1 - tax_rate)

    rows.append({
        "Year": year,
        "CAPEX (MM$)": c,
        "OPEX (MM$)": -o,
        "Gas Revenue (MM$)": rg,
        "Ethane Revenue (MM$)": re,
        "Propane Revenue (MM$)": rp,
        "Butane Revenue (MM$)": rb,
        "Total Revenue (MM$)": total_rev,
        "Net CF after Tax (MM$)": ncf_after_tax,
    })

df = pd.DataFrame(rows)
df["Cumulative CF (MM$)"] = df["Net CF after Tax (MM$)"].cumsum()

cf_list = df["Net CF after Tax (MM$)"].tolist()
cumulative_list = df["Cumulative CF (MM$)"].tolist()

# NPV
npv = sum(cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(cf_list))

# IRR
def calculate_irr(cfs, precision=1e-8, max_iter=500):
    def npv_std(t):
        return sum(cf / (1 + t) ** i for i, cf in enumerate(cfs))

    lo = -0.50
    if npv_std(lo) < 0:
        return None

    hi = None
    for pct in range(int(lo * 100) + 1, 1001):
        t = pct / 100
        if npv_std(t) < 0:
            hi = t
            lo = (pct - 1) / 100
            break

    if hi is None:
        return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        v = npv_std(mid)
        if abs(v) < precision:
            return mid
        if v > 0:
            lo = mid
        else:
            hi = mid

    return mid

irr = calculate_irr(cf_list)

# Payback Period
def calculate_payback(cumulative):
    for i in range(1, len(cumulative)):
        if cumulative[i] >= 0 and cumulative[i - 1] < 0:
            frac = -cumulative[i - 1] / (cumulative[i] - cumulative[i - 1])
            total_months = ((i - 1) + frac) * 12
            return int(total_months // 12), int(round(total_months % 12))
    return None, None

payback_years, payback_months = calculate_payback(cumulative_list)


# -----------------------------------------------------------------------
# ECONOMIC INDICATORS
# -----------------------------------------------------------------------
st.subheader(f"📊 Economic Indicators — {project_life} years")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("NPV (MM$)", f"{npv:.3f}")
c2.metric("IRR", f"{irr*100:.2f} %" if irr else "N/A")

if payback_years is not None:
    c3.metric("Payback", f"{payback_years} years and {payback_months} months")
else:
    c3.metric("Payback", "Not reached")

c4.metric("Final Cumulative CF (MM$)", f"{cumulative_list[-1]:.3f}")
c5.metric("Annual Revenue (MM$)", f"{total_revenue:.3f}")

st.divider()

# -----------------------------------------------------------------------
# CHARTS
# -----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Cumulative Cash Flow",
    "💰 Net CF after Tax",
    "🔄 Inflation Impact",
    "📋 Detailed Table"
])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"],
        y=df["Cumulative CF (MM$)"],
        mode="lines+markers",
        name="Cumulative CF after tax",
        line=dict(color="#22d3ee", width=3),
        marker=dict(size=5),
        fill="tozeroy",
        fillcolor="rgba(34,211,238,0.06)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    if payback_years is not None:
        pb_exact = payback_years + payback_months / 12
        fig.add_vline(
            x=pb_exact,
            line_dash="dot",
            line_color="#34d399",
            annotation_text=f"Payback ≈ {payback_years}y {payback_months}m",
            annotation_position="top",
        )

    fig.update_layout(
        template="plotly_dark",
        height=450,
        title="Cumulative net cash flow after tax",
        xaxis_title="Year",
        yaxis_title="MM USD",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    colors = ["#ef4444" if v < 0 else "#22d3ee" for v in df["Net CF after Tax (MM$)"]]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["Year"],
        y=df["Net CF after Tax (MM$)"],
        marker_color=colors,
        name="Net CF after Tax",
    ))
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    fig2.update_layout(
        template="plotly_dark",
        height=450,
        title="Net cash flow after tax — year by year",
        xaxis_title="Year",
        yaxis_title="MM USD",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    cumulative_compare = []
    total_cf = 0

    for year in range(0, project_life + 1):
        if year == 0:
            ncf = -capex
        else:
            if not apply_inflation:
                o_c = opex_base * (1 + inflation_rate) ** (year - 1)
            else:
                o_c = opex_base
            ncf = (total_revenue - o_c) * (1 - tax_rate)

        total_cf += ncf
        cumulative_compare.append(total_cf)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=list(range(project_life + 1)),
        y=cumulative_list,
        mode="lines+markers",
        name="Current scenario",
        line=dict(color="#22d3ee", width=3),
    ))
    fig3.add_trace(go.Scatter(
        x=list(range(project_life + 1)),
        y=cumulative_compare,
        mode="lines+markers",
        name="With inflation" if not apply_inflation else "Without inflation",
        line=dict(color="#f97316", width=3, dash="dash"),
    ))
    fig3.add_hline(y=0, line_dash="dash", line_color="gray")
    fig3.update_layout(
        template="plotly_dark",
        height=450,
        title="Comparison: impact of inflation on cumulative cash flow",
        xaxis_title="Year",
        yaxis_title="Cumulative CF (MM USD)",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    df_display = df.copy()
    for col in df_display.columns:
        if col != "Year":
            df_display[col] = df_display[col].round(3)

    st.dataframe(df_display, use_container_width=True, height=500)

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "project_cashflow.csv", "text/csv")


# -----------------------------------------------------------------------
# REVENUE DETAILS
# -----------------------------------------------------------------------
with st.expander("🔍 Annual revenue calculation details"):
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Gas", f"{gas_revenue:.3f} MM$/year")
    r2.metric("Propane", f"{propane_revenue:.3f} MM$/year")
    r3.metric("Butane", f"{butane_revenue:.3f} MM$/year")
    r4.metric("Ethane", f"{ethane_revenue:.3f} MM$/year")
    st.caption("Formula: production × price × 24h × days ÷ 1,000,000")

st.divider()
st.caption(
    "Calculator based on the NCF, DCF, NPV, IRR, and Payback formulas "
    "used in the technical-economic study."
)
