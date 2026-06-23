"""
Calculateur Financier — Projet Gazier (type Sabria)
=====================================================
Interface Streamlit interactive : VAN, TRI, Payback, Cash-flow cumulé,
avec ou sans inflation, sur une durée modulable (avant/après 20 ans).

Lancer avec :  streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# -----------------------------------------------------------------------
# CONFIG PAGE
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Calculateur Financier Gazier",
    page_icon="⛽",
    layout="wide",
)

# -----------------------------------------------------------------------
# STYLE CSS PERSONNALISÉ
# -----------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stMetric {
        background: linear-gradient(135deg, #1a2332 0%, #0e1117 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
    }
    h1, h2, h3 { color: #e2e8f0; }
    .block-container { padding-top: 2rem; }
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #2d3748;
    }
</style>
""", unsafe_allow_html=True)

st.title("⛽ Calculateur Financier — Projet Gazier")
st.caption("Inspiré du projet Sabria · VAN · TRI · Payback · Cash-flow actualisé")

# -----------------------------------------------------------------------
# SIDEBAR : HYPOTHÈSES
# -----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Hypothèses")

    st.subheader("Investissement & Finance")
    capex = st.number_input("CAPEX initial (MM USD)", value=9.0, step=0.5, min_value=0.0)
    opex_an1 = st.number_input("OPEX année 1 (MM USD/an)", value=2.0, step=0.1, min_value=0.0)
    taux_actualisation = st.slider("Taux d'actualisation (%)", 0.0, 30.0, 10.0, 0.5) / 100
    taux_inflation = st.slider("Inflation OPEX (%)", 0.0, 20.0, 8.0, 0.5) / 100
    avec_inflation = st.checkbox("Appliquer l'inflation sur l'OPEX", value=True)

    st.subheader("Durée du projet")
    duree_annees = st.slider("Durée d'analyse (années)", 5, 50, 20, 1)
    st.caption("💡 Mets > 20 pour voir ce qui se passe **après** l'amortissement standard.")

    st.subheader("Production & Prix")
    col1, col2 = st.columns(2)
    with col1:
        debit_gaz = st.number_input("Débit gaz (std m³/h)", value=3752.0, step=10.0)
        prod_propane = st.number_input("Propane (t/h)", value=0.200, step=0.01, format="%.3f")
        prod_butane = st.number_input("Butane (t/h)", value=0.111, step=0.01, format="%.3f")
        prod_ethane = st.number_input("Éthane (t/h)", value=0.124, step=0.01, format="%.3f")
    with col2:
        prix_gaz = st.number_input("Prix gaz (USD/m³)", value=0.15, step=0.01, format="%.2f")
        prix_propane = st.number_input("Prix propane (USD/t)", value=300.0, step=10.0)
        prix_butane = st.number_input("Prix butane (USD/t)", value=500.0, step=10.0)
        prix_ethane = st.number_input("Prix éthane (USD/t)", value=200.0, step=10.0)

    jours_prod = st.number_input("Jours de production / an", value=344, step=1, min_value=1, max_value=365)

# -----------------------------------------------------------------------
# CALCULS
# -----------------------------------------------------------------------
def calculer_revenu_annuel():
    rev_gaz = debit_gaz * prix_gaz * 24 * jours_prod / 1_000_000
    rev_propane = prod_propane * prix_propane * 24 * jours_prod / 1_000_000
    rev_butane = prod_butane * prix_butane * 24 * jours_prod / 1_000_000
    rev_ethane = prod_ethane * prix_ethane * 24 * jours_prod / 1_000_000
    return rev_gaz, rev_propane, rev_butane, rev_ethane


def generer_cashflow(n):
    rev_gaz, rev_propane, rev_butane, rev_ethane = calculer_revenu_annuel()
    revenu_total = rev_gaz + rev_propane + rev_butane + rev_ethane

    lignes = []
    for annee in range(0, n + 1):
        if annee == 0:
            opex = 0.0
            revenu = 0.0
            ncf = -capex
        else:
            opex = opex_an1 * ((1 + taux_inflation) ** (annee - 1)) if avec_inflation else opex_an1
            revenu = revenu_total
            ncf = revenu - opex
        lignes.append({"Année": annee, "OPEX": -opex if annee > 0 else -capex if annee == 0 else 0,
                        "Revenu": revenu, "CashFlowNet": ncf})

    df = pd.DataFrame(lignes)
    df.loc[0, "CashFlowNet"] = -capex
    df["CumulNonActualise"] = df["CashFlowNet"].cumsum()
    df["FacteurActualisation"] = 1 / (1 + taux_actualisation) ** df["Année"]
    df["CashFlowActualise"] = df["CashFlowNet"] * df["FacteurActualisation"]
    df["VANCumulee"] = df["CashFlowActualise"].cumsum()
    return df, revenu_total


def calcul_tri(cashflows, precision=1e-6, max_iter=200):
    def van_pour_taux(taux):
        return sum(cf / (1 + taux) ** i for i, cf in enumerate(cashflows))

    taux_bas = taux_haut = None
    precedent = van_pour_taux(-0.50)
    taux_precedent = -0.50
    for pct in range(-49, 1000):
        t = pct / 100
        v = van_pour_taux(t)
        if precedent * v < 0:
            taux_bas, taux_haut = taux_precedent, t
            break
        precedent, taux_precedent = v, t

    if taux_bas is None:
        return None

    for _ in range(max_iter):
        taux_mid = (taux_bas + taux_haut) / 2
        van_mid = van_pour_taux(taux_mid)
        if abs(van_mid) < precision:
            return taux_mid
        if van_pour_taux(taux_bas) * van_mid < 0:
            taux_haut = taux_mid
        else:
            taux_bas = taux_mid
    return taux_mid


def calcul_payback(cumul):
    for i in range(1, len(cumul)):
        if cumul[i] >= 0 and cumul[i - 1] < 0:
            fraction = -cumul[i - 1] / (cumul[i] - cumul[i - 1])
            return (i - 1) + fraction
    return None


df, revenu_total = generer_cashflow(duree_annees)
van = df["CashFlowActualise"].sum()
tri = calcul_tri(df["CashFlowNet"].tolist())
payback = calcul_payback(df["CumulNonActualise"].tolist())
cumul_final = df["CumulNonActualise"].iloc[-1]

# -----------------------------------------------------------------------
# INDICATEURS — METRICS EN HAUT
# -----------------------------------------------------------------------
st.subheader(f"📊 Indicateurs économiques — sur {duree_annees} ans")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("VAN", f"{van:.2f} MM$", delta=f"@ {taux_actualisation*100:.0f}%")
c2.metric("TRI", f"{tri*100:.1f} %" if tri is not None else "N/A")
c3.metric("Payback", f"{payback:.2f} ans" if payback is not None else "Non atteint")
c4.metric("Cash cumulé final", f"{cumul_final:.2f} MM$")
c5.metric("Revenu annuel", f"{revenu_total:.2f} MM$/an")

st.divider()

# -----------------------------------------------------------------------
# GRAPHIQUES
# -----------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📈 Cash-flow cumulé", "💰 VAN cumulée", "📋 Tableau détaillé"])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Année"], y=df["CumulNonActualise"],
        mode="lines+markers", name="Cumul non actualisé",
        line=dict(color="#22d3ee", width=3),
        marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(34,211,238,0.08)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    if duree_annees > 20:
        fig.add_vline(x=20, line_dash="dot", line_color="#f87171",
                       annotation_text="Fin année 20", annotation_position="top")
    fig.update_layout(
        template="plotly_dark",
        title="Évolution du cash-flow cumulé (non actualisé)",
        xaxis_title="Année", yaxis_title="MM USD",
        height=450, margin=dict(t=60, b=40),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["Année"], y=df["VANCumulee"],
        mode="lines+markers", name="VAN cumulée",
        line=dict(color="#a78bfa", width=3),
        marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
    ))
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    if duree_annees > 20:
        fig2.add_vline(x=20, line_dash="dot", line_color="#f87171",
                        annotation_text="Fin année 20", annotation_position="top")
    fig2.update_layout(
        template="plotly_dark",
        title=f"VAN cumulée actualisée @ {taux_actualisation*100:.0f}%",
        xaxis_title="Année", yaxis_title="MM USD",
        height=450, margin=dict(t=60, b=40),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    df_affiche = df.copy()
    for col in ["OPEX", "Revenu", "CashFlowNet", "CumulNonActualise",
                "CashFlowActualise", "VANCumulee"]:
        df_affiche[col] = df_affiche[col].round(3)
    df_affiche = df_affiche.drop(columns=["FacteurActualisation"])
    st.dataframe(df_affiche, use_container_width=True, height=500)

    csv = df_affiche.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Télécharger en CSV", csv, "cashflow_projet.csv", "text/csv")

# -----------------------------------------------------------------------
# DÉTAIL DES REVENUS
# -----------------------------------------------------------------------
with st.expander("🔍 Détail du calcul des revenus annuels"):
    rev_gaz, rev_propane, rev_butane, rev_ethane = calculer_revenu_annuel()
    rd1, rd2, rd3, rd4 = st.columns(4)
    rd1.metric("Revenu Gaz", f"{rev_gaz:.3f} MM$/an")
    rd2.metric("Revenu Propane", f"{rev_propane:.3f} MM$/an")
    rd3.metric("Revenu Butane", f"{rev_butane:.3f} MM$/an")
    rd4.metric("Revenu Éthane", f"{rev_ethane:.3f} MM$/an")
    st.caption(
        "Formule : débit/production × prix × 24h × jours de production ÷ 1 000 000"
    )

st.divider()
st.caption("Calculateur basé sur les formules NCF, DCF, VAN, TRI et Payback "
           "du projet d'étude technico-économique (type Sabria).")
