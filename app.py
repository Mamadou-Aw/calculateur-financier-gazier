"""
Calculateur Financier — Projet Gazier
Lancer :  streamlit run app.py
Prérequis : pip install streamlit plotly pandas
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------
st.set_page_config(page_title="Calculateur Financier Gazier", page_icon="⛽", layout="wide")

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

st.title("⛽ Calculateur Financier — Projet Gazier")
st.caption("VAN · TRI · Payback · Cash-flow actualisé")

# -----------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Hypothèses financières")

    capex = st.number_input("CAPEX initial (MM USD)", value=9.0, step=0.5, min_value=0.0)
    opex_base = st.number_input("OPEX année 1 (MM USD/an)", value=2.0, step=0.1, min_value=0.0)
    taux_impot = st.slider("Taux d'impôt — Tax Rate (%)", 0.0, 60.0, 35.0, 1.0) / 100
    taux_actualisation = st.slider("Taux d'actualisation — Discount Rate (%)", 0.0, 30.0, 10.0, 0.5) / 100
    taux_inflation = st.slider("Inflation annuelle sur OPEX (%)", 0.0, 20.0, 8.0, 0.5) / 100
    avec_inflation = st.checkbox("Appliquer l'inflation sur l'OPEX", value=False)
    inclure_ethane = st.checkbox("Inclure le revenu Éthane", value=True)

    st.divider()
    st.subheader("📅 Durée du projet")
    duree = st.slider("Nombre d'années", 5, 50, 20, 1)
    st.caption("💡 Mets > 20 pour simuler au-delà de l'amortissement standard.")

    st.divider()
    st.subheader("🛢️ Production & Prix")
    col1, col2 = st.columns(2)
    with col1:
        debit_gaz = st.number_input("Débit gaz (std m³/h)", value=3752.0, step=10.0)
        prod_propane = st.number_input("Propane (t/h)", value=0.200, step=0.01, format="%.3f")
        prod_butane = st.number_input("Butane (t/h)", value=0.111, step=0.01, format="%.3f")
        prod_ethane = st.number_input("Éthane (t/h)", value=0.124, step=0.01, format="%.3f")
    with col2:
        prix_gaz = st.number_input("Prix gaz (USD/m³)", value=0.15, step=0.01, format="%.2f")
        prix_propane = st.number_input("Prix propane ($/t)", value=300.0, step=10.0)
        prix_butane = st.number_input("Prix butane ($/t)", value=500.0, step=10.0)
        prix_ethane = st.number_input("Prix éthane ($/t)", value=200.0, step=10.0)
    jours = st.number_input("Jours de production / an", value=344, step=1, min_value=1, max_value=365)


# -----------------------------------------------------------------------
# CALCULS
# -----------------------------------------------------------------------
rev_gaz     = debit_gaz   * prix_gaz     * 24 * jours / 1_000_000
rev_propane = prod_propane * prix_propane * 24 * jours / 1_000_000
rev_butane  = prod_butane  * prix_butane  * 24 * jours / 1_000_000
rev_ethane  = prod_ethane  * prix_ethane  * 24 * jours / 1_000_000 if inclure_ethane else 0.0
rev_total   = rev_gaz + rev_propane + rev_butane + rev_ethane

rows = []
for annee in range(0, duree + 1):
    if annee == 0:
        c, o = -capex, 0.0
        rg = rp = rb = re = 0.0
        total_rev = 0.0
        ncf_after_tax = -capex
    else:
        c = 0.0
        o = opex_base * (1 + taux_inflation) ** (annee - 1) if avec_inflation else opex_base
        rg, rp, rb, re = rev_gaz, rev_propane, rev_butane, rev_ethane
        total_rev = rev_total
        ncf_after_tax = (total_rev - o) * (1 - taux_impot)

    rows.append({
        "Année": annee,
        "CAPEX (MM$)": c,
        "OPEX (MM$)": -o,
        "Rev. Gaz (MM$)": rg,
        "Rev. Éthane (MM$)": re,
        "Rev. Propane (MM$)": rp,
        "Rev. Butane (MM$)": rb,
        "Revenus Total (MM$)": total_rev,
        "CF Net après Impôt (MM$)": ncf_after_tax,
    })

df = pd.DataFrame(rows)
df["Cumul (MM$)"] = df["CF Net après Impôt (MM$)"].cumsum()

cf_list = df["CF Net après Impôt (MM$)"].tolist()
cumul_list = df["Cumul (MM$)"].tolist()

# VAN (NPV)
van = sum(cf / (1 + taux_actualisation) ** (i + 1) for i, cf in enumerate(cf_list))

# TRI (IRR)
def calcul_tri(cfs, precision=1e-8, max_iter=500):
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

tri = calcul_tri(cf_list)

# Payback
def calcul_payback(cumul):
    for i in range(1, len(cumul)):
        if cumul[i] >= 0 and cumul[i - 1] < 0:
            frac = -cumul[i - 1] / (cumul[i] - cumul[i - 1])
            total_mois = ((i - 1) + frac) * 12
            return int(total_mois // 12), int(round(total_mois % 12))
    return None, None

payback_ans, payback_mois = calcul_payback(cumul_list)


# -----------------------------------------------------------------------
# INDICATEURS
# -----------------------------------------------------------------------
st.subheader(f"📊 Indicateurs économiques — {duree} ans")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("VAN (MM$)", f"{van:.3f}")
c2.metric("TRI", f"{tri*100:.2f} %" if tri else "N/A")
if payback_ans is not None:
    c3.metric("Payback", f"{payback_ans} ans et {payback_mois} mois")
else:
    c3.metric("Payback", "Non atteint")
c4.metric("Cumul final (MM$)", f"{cumul_list[-1]:.3f}")
c5.metric("Revenu annuel (MM$)", f"{rev_total:.3f}")

st.divider()

# -----------------------------------------------------------------------
# GRAPHIQUES
# -----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Cash-flow cumulé",
    "💰 CF Net après Impôt",
    "🔄 Impact de l'inflation",
    "📋 Tableau détaillé"
])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["Cumul (MM$)"],
        mode="lines+markers", name="Cumul CF après impôt",
        line=dict(color="#22d3ee", width=3), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(34,211,238,0.06)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    if payback_ans is not None:
        pb_exact = payback_ans + payback_mois / 12
        fig.add_vline(x=pb_exact, line_dash="dot", line_color="#34d399",
                      annotation_text=f"Payback ≈ {payback_ans}a {payback_mois}m",
                      annotation_position="top")
    fig.update_layout(
        template="plotly_dark", height=450,
        title="Cash-flow cumulé net après impôt",
        xaxis_title="Année", yaxis_title="MM USD",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    colors = ["#ef4444" if v < 0 else "#22d3ee" for v in df["CF Net après Impôt (MM$)"]]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["Année"], y=df["CF Net après Impôt (MM$)"],
        marker_color=colors, name="CF Net après Impôt",
    ))
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    fig2.update_layout(
        template="plotly_dark", height=450,
        title="Cash-flow net après impôt — année par année",
        xaxis_title="Année", yaxis_title="MM USD",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    cumul_compare = []
    total_cf = 0
    for annee in range(0, duree + 1):
        if annee == 0:
            ncf = -capex
        else:
            if not avec_inflation:
                o_c = opex_base * (1 + taux_inflation) ** (annee - 1)
            else:
                o_c = opex_base
            ncf = (rev_total - o_c) * (1 - taux_impot)
        total_cf += ncf
        cumul_compare.append(total_cf)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=list(range(duree + 1)), y=cumul_list,
        mode="lines+markers", name="Scénario actuel",
        line=dict(color="#22d3ee", width=3),
    ))
    fig3.add_trace(go.Scatter(
        x=list(range(duree + 1)), y=cumul_compare,
        mode="lines+markers",
        name="Avec inflation" if not avec_inflation else "Sans inflation",
        line=dict(color="#f97316", width=3, dash="dash"),
    ))
    fig3.add_hline(y=0, line_dash="dash", line_color="gray")
    fig3.update_layout(
        template="plotly_dark", height=450,
        title="Comparaison : impact de l'inflation sur le cumul",
        xaxis_title="Année", yaxis_title="Cumul CF (MM USD)",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    df_display = df.copy()
    for col in df_display.columns:
        if col != "Année":
            df_display[col] = df_display[col].round(3)
    st.dataframe(df_display, use_container_width=True, height=500)

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Télécharger en CSV", csv, "cashflow_projet.csv", "text/csv")


# -----------------------------------------------------------------------
# DÉTAIL DES REVENUS
# -----------------------------------------------------------------------
with st.expander("🔍 Détail du calcul des revenus annuels"):
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Gaz", f"{rev_gaz:.3f} MM$/an")
    r2.metric("Propane", f"{rev_propane:.3f} MM$/an")
    r3.metric("Butane", f"{rev_butane:.3f} MM$/an")
    r4.metric("Éthane", f"{rev_ethane:.3f} MM$/an")
    st.caption("Formule : production × prix × 24h × jours ÷ 1 000 000")

st.divider()
st.caption("Calculateur basé sur les formules NCF, DCF, VAN, TRI et Payback "
           "du projet d'étude technico-économique.")
