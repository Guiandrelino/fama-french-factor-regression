"""Identidade visual compartilhada: terminal financeiro, sem dependências externas."""

from html import escape

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CSS = """
<style>
:root { --green:#20e3a2; --navy:#101d30; --muted:#8193ac; --border:#203149; }
.stApp { background: #070c14; color:#f0f5fc; }
[data-testid="stHeader"] { background:rgba(7,12,20,.94); border-bottom:1px solid #17263b; }
[data-testid="stSidebar"] { background:#0b1422; border-right:1px solid var(--border); }
[data-testid="stSidebar"] > div:first-child { padding-top:2rem; }
.block-container { max-width:1600px; padding-top:4.5rem; padding-bottom:3rem; }
h1,h2,h3 { font-family: 'Segoe UI',sans-serif !important; letter-spacing:-.035em; }
h1 { font-size:2.4rem !important; font-weight:700 !important; }
h2 { font-size:1.5rem !important; }
h3 { font-size:1.05rem !important; }
p, label, [data-testid="stCaptionContainer"] { line-height:1.65; }
[data-testid="stCaptionContainer"] { color:#8da0ba; }
[data-testid="stMetric"] { background:linear-gradient(135deg,#101d30,#0b1422);
 border:1px solid #203149; border-top:2px solid #20e3a2; border-radius:6px;
 padding:20px 22px; min-height:126px; }
[data-testid="stMetricLabel"] { color:#8da0ba; font-size:.75rem; text-transform:uppercase; letter-spacing:.07em; }
[data-testid="stMetricValue"] { color:#f0f5fc; font-family:Consolas,monospace; font-size:1.85rem; }
[data-testid="stBaseButton-primary"] { background:#20e3a2; border:1px solid #20e3a2;
 color:#04140e; font-weight:700; border-radius:4px; }
[data-testid="stBaseButton-primary"]:hover { background:#54edba; border-color:#54edba; color:#04140e; }
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
 border:1px solid #2c405c; background:#101d30; border-radius:4px; }
button { transition:background .15s ease,border-color .15s ease; }
button:focus-visible,a:focus-visible { outline:2px solid #20e3a2 !important; outline-offset:3px; }
[data-baseweb="tab-list"] { border-bottom:1px solid #203149; gap:22px; }
[data-baseweb="tab"] { color:#8da0ba; font-size:.78rem; letter-spacing:.02em; padding:12px 0; }
[data-baseweb="tab"][aria-selected="true"] { color:#20e3a2; }
[data-baseweb="tab-highlight"] { background:#20e3a2; }
[data-testid="stDataFrame"], [data-testid="stPlotlyChart"] { border:1px solid #203149; border-radius:6px; }
[data-testid="stExpander"] { border-color:#203149; background:#0b1422; }
[data-testid="stAlert"] { border-radius:4px; }
[data-testid="stFileUploader"] { border:1px dashed #2c405c; border-radius:6px; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color:#a8b8cd; font-size:.76rem; }
.terminal-top { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
 gap:12px; border-bottom:1px solid #203149; padding:0 0 18px; margin-bottom:28px; }
.terminal-brand { color:white; font:bold 17px Consolas,monospace; letter-spacing:.12em; }
.terminal-brand span { color:#20e3a2; }
.terminal-context { color:#8193ac; font:11px Consolas,monospace; letter-spacing:.08em; }
.terminal-status { color:#20e3a2; background:#0c241e; border:1px solid #164b39;
 border-radius:3px; padding:6px 10px; font:10px Consolas,monospace; letter-spacing:.07em; }
.terminal-eyebrow { color:#20e3a2; font:11px Consolas,monospace; letter-spacing:.16em; margin:10px 0 8px; }
.terminal-strip { display:grid; grid-template-columns:repeat(4,1fr); border:1px solid #203149;
 background:#0b1422; border-radius:5px; margin:18px 0 26px; }
.terminal-strip > div { padding:14px 18px; border-right:1px solid #203149; }
.terminal-strip > div:last-child { border:0; }
.terminal-strip small { display:block; color:#8193ac; font:10px Consolas,monospace; letter-spacing:.09em; }
.terminal-strip strong { display:block; color:#e7effa; font:12px Consolas,monospace; margin-top:7px; }
.terminal-cards { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:20px 0; }
.terminal-card { background:#0b1422; border:1px solid #203149; padding:24px; border-radius:5px; }
.terminal-card small { color:#20e3a2; font:11px Consolas,monospace; }
.terminal-card h3 { color:#eef5ff; margin:12px 0; }
.terminal-card p { color:#8da0ba; font:12px/1.8 Consolas,monospace; margin:0; }
.terminal-footer { border-top:1px solid #203149; margin-top:24px; padding:14px 0;
 color:#8193ac; font:10px/1.8 Consolas,monospace; letter-spacing:.04em; }
@media(max-width:760px) {
 .terminal-strip { grid-template-columns:repeat(2,1fr); }
 .terminal-strip > div { border-bottom:1px solid #203149; }
 .terminal-cards { grid-template-columns:1fr; }
 .terminal-context { display:none; }
 h1 { font-size:1.8rem !important; }
}
</style>
"""


def setup_terminal(section: str):
    pio.templates["factorlab"] = go.layout.Template(
        layout=dict(
            paper_bgcolor="#0b1422",
            plot_bgcolor="#0b1422",
            font=dict(family="Consolas, monospace", color="#b9c8dd", size=11),
            colorway=["#20e3a2", "#5b9dff", "#e8edf5", "#a58cff", "#e5ba68", "#47cfda"],
            xaxis=dict(gridcolor="#1b2c42", zerolinecolor="#2c405c"),
            yaxis=dict(gridcolor="#1b2c42", zerolinecolor="#2c405c"),
            margin=dict(l=35, r=25, t=60, b=35),
            legend=dict(orientation="h", y=-0.2),
            hoverlabel=dict(bgcolor="#101d30", font_color="#f0f5fc"),
        )
    )
    pio.templates.default = "plotly_dark+factorlab"
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="terminal-top"><div class="terminal-brand">FACTOR<span>LAB</span>'
        ' <span>▥</span></div><div class="terminal-context">QUANTITATIVE RESEARCH / '
        + escape(section.upper())
        + '</div><div class="terminal-status">● ANALYTICS TERMINAL</div></div>'
        '<div class="terminal-eyebrow">FACTOR INTELLIGENCE / RESEARCH DESK</div>',
        unsafe_allow_html=True,
    )


def context_strip(items):
    st.markdown(
        '<div class="terminal-strip">'
        + "".join(
            f"<div><small>{escape(str(label))}</small><strong>{escape(str(value))}</strong></div>"
            for label, value in items
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def welcome_cards():
    cards = [
        (
            "01 / EXPOSURE",
            "Mapeie as exposições",
            "Isole mercado, tamanho, valor, rentabilidade, investimento e momentum.",
        ),
        (
            "02 / INFERENCE",
            "Investigue o alpha",
            "Coeficientes, intervalos de confiança HAC e diagnósticos em uma mesma estação.",
        ),
        (
            "03 / RESEARCH",
            "Compare e documente",
            "Ativos, carteiras e modelos com amostra comum e relatórios rastreáveis.",
        ),
    ]
    st.markdown(
        '<div class="terminal-cards">'
        + "".join(
            f'<div class="terminal-card"><small>{n}</small><h3>{title}</h3><p>{text}</p></div>'
            for n, title, text in cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )
