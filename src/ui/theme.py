"""Tokens, CSS e template Plotly únicos. Não modifica dados ou cálculos."""

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TOKENS = {
    "base": "#0A0E14",
    "panel": "#0F151D",
    "raised": "#151C26",
    "hover": "#1B2633",
    "border": "#293544",
    "accent": "#8CAED0",
    "primary": "#EBF0F6",
    "secondary": "#BAC6D4",
    "muted": "#93A3B7",
    "positive": "#80B69B",
    "negative": "#D89B9B",
}
CATEGORY = ["#8CAED0", "#80B69B", "#C4B58B", "#B0A0C4", "#90BAC0", "#D89B9B", "#AFB7C4", "#C3A68F"]
DIVERGING = ["#B67676", "#202C3A", "#9BB9D8"]


def apply_theme():
    variables = ":root{" + "".join(f"--{key}:{value};" for key, value in TOKENS.items()) + "}"
    css = Path(__file__).with_name("theme.css").read_text(encoding="utf-8")
    st.markdown("<style>" + variables + css + "</style>", unsafe_allow_html=True)
    pio.templates["institutional"] = go.layout.Template(
        layout=dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(
                family="IBM Plex Sans, Arial, sans-serif", color=TOKENS["secondary"], size=12
            ),
            colorway=CATEGORY,
            hovermode="x unified",
            separators=",.",
            xaxis=dict(gridcolor="#202B38", zeroline=False, showline=False, tickfont=dict(size=11)),
            yaxis=dict(gridcolor="#202B38", zeroline=False, showline=False, tickfont=dict(size=11)),
            legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11), title_text=""),
            margin=dict(l=40, r=20, t=55, b=35),
            hoverlabel=dict(
                bgcolor=TOKENS["raised"], font_color=TOKENS["primary"], bordercolor=TOKENS["border"]
            ),
            colorscale=dict(diverging=DIVERGING, sequential=["#182638", "#9BB9D8"]),
            modebar=dict(bgcolor="rgba(0,0,0,0)", color=TOKENS["muted"]),
        )
    )
    pio.templates.default = "institutional"
