"""Identidade compartilhada do workspace financeiro, sem feed fictício."""

from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from factorlab.security import require_login


def setup_terminal(section: str):
    st.markdown(
        Path(__file__).with_name("terminal.css").read_text(encoding="utf-8"), unsafe_allow_html=True
    )
    require_login()
    pio.templates["factorlab"] = go.layout.Template(
        layout=dict(
            paper_bgcolor="#111318",
            plot_bgcolor="#111318",
            font=dict(family="Consolas, monospace", color="#c0c4cc", size=11),
            colorway=["#ffab40", "#7bb8ff", "#69e0aa", "#f07178", "#c9a7ff", "#e8edf5"],
            xaxis=dict(gridcolor="#282b32", zerolinecolor="#41444c"),
            yaxis=dict(gridcolor="#282b32", zerolinecolor="#41444c"),
            margin=dict(l=35, r=25, t=60, b=35),
            legend=dict(orientation="h", y=-0.2),
            hoverlabel=dict(bgcolor="#17191e", font_color="#f0f5fc"),
        )
    )
    pio.templates.default = "plotly_dark+factorlab"
    st.markdown(
        '<div class="terminal-top"><div class="terminal-brand">FACTOR<span>LAB</span> ▥</div>'
        '<div class="terminal-context">QUANTITATIVE RESEARCH / '
        + escape(section.upper())
        + '</div><div class="terminal-status">● ANALYTICS WORKSPACE</div></div>'
        '<div class="terminal-eyebrow">01 RESEARCH &nbsp; / &nbsp; 02 DATA QUALITY &nbsp; / &nbsp; 03 PORTFOLIO &nbsp; / &nbsp; 04 RISK</div>',
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
            "Mercado, tamanho, valor, rentabilidade, investimento e momentum.",
        ),
        (
            "02 / INFERENCE",
            "Investigue o alpha",
            "Inferência HAC, influência e qualidade dos dados antes da decisão.",
        ),
        (
            "03 / ALLOCATION",
            "Compare e documente",
            "Risco, estresse, alocação com custos e relatórios executivos integrados.",
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
