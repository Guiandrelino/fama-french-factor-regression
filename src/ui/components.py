"""Componentes de apresentação; valores originais permanecem inalterados."""

import importlib.metadata
from contextlib import contextmanager
from datetime import UTC, datetime
from html import escape

import pandas as pd
import streamlit as st

from ui.theme import TOKENS


def br_number(value, decimals=2):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def percent(value, decimals=2):
    return br_number(value * 100, decimals) + "%"


def sidebar_header(title, subtitle):
    st.markdown(
        f'<div class="sidebar-identity"><span class="sidebar-monogram">F</span><div><b>FactorLab</b><small>Plataforma de pesquisa</small></div></div><div class="sidebar-context"><strong>{escape(title)}</strong><span>{escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def sidebar_section(number, title):
    st.markdown(
        f'<div class="sidebar-section"><span>{escape(number)}</span>{escape(title)}</div>',
        unsafe_allow_html=True,
    )


def top_bar(context):
    now = datetime.now(UTC).strftime("%d/%m/%Y · %H:%M UTC")
    st.markdown(
        '<header class="institutional-bar"><div class="brand">FactorLab <span>/ Research</span></div>'
        f'<div class="bar-context">{escape(context)}</div><div class="bar-status">{now}<br>Dados históricos · sem feed em tempo real</div></header>',
        unsafe_allow_html=True,
    )


def section_header(title, subtitle=""):
    st.markdown(
        f'<div class="section-line"><strong>{escape(title)}</strong><span>{escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def note(text):
    st.markdown(f'<div class="editorial-note">{escape(text)}</div>', unsafe_allow_html=True)


@contextmanager
def panel(title, subtitle=""):
    section_header(title, subtitle)
    with st.container(border=True):
        yield


def context_strip(items):
    st.markdown(
        '<div class="context-grid">'
        + "".join(
            f"<div><small>{escape(str(label))}</small><b>{escape(str(value))}</b></div>"
            for label, value in items
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def kpi_card(label, value, delta=None, help=None):
    # Mantém st.metric para acessibilidade e compatibilidade de testes.
    st.metric(label, value, delta=delta, help=help)


def styled_table(frame, **kwargs):
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    if not isinstance(frame, pd.DataFrame):
        return st.dataframe(frame, **kwargs)
    numeric = frame.select_dtypes(include="number").columns
    percent_columns = {
        "asset_return",
        "excess_return",
        "fitted_excess",
        "residual",
        "alpha",
        "alpha_monthly",
        "alpha_annual_arithmetic",
        "residual_vol_annual",
        "residual_rmse",
        "tracking_error_annual",
        "active_return_annual_arithmetic",
        "cumulative_return",
        "annualized_return",
        "vol_annual",
        "max_drawdown",
        "impact",
        "factor_return",
        "weight",
        "gross",
        "net",
        "cost",
        "turnover",
        "actual_return",
        "predicted_return",
        "actual_excess",
        "explained_excess",
        "error",
        "baseline_error",
        "historical_mean_forecast",
    }
    formatters = {}
    for column in numeric:
        if str(column) in percent_columns:
            formatters[column] = percent
        elif pd.api.types.is_integer_dtype(frame[column]):
            formatters[column] = lambda v: br_number(v, 0)
        else:
            formatters[column] = lambda v: br_number(v, 5)
    style = frame.style.format(formatters, na_rep="—")
    if frame.index.is_unique and frame.columns.is_unique:
        style = style.apply(
            lambda row: (
                [
                    f"background-color: {TOKENS['raised']}"
                    if frame.index.get_loc(row.name) % 2
                    else f"background-color: {TOKENS['panel']}"
                ]
                * len(row)
            ),
            axis=1,
        )
    # Sinal explícito na cor condicional: a leitura não depende da cor.
    semantic = [c for c in numeric if str(c) in percent_columns]
    if semantic:
        style = style.map(
            lambda v: (
                f"color: {TOKENS['negative']}"
                if pd.notna(v) and v < 0
                else f"color: {TOKENS['primary']}"
            ),
            subset=semantic,
        )
    # Numéricos à direita; texto à esquerda. Nunca modifica o DataFrame.
    style = style.set_properties(
        subset=list(numeric), **{"text-align": "right", "font-family": "IBM Plex Mono, monospace"}
    )
    kwargs.setdefault("width", "stretch")
    return st.dataframe(style, **kwargs)


def format_chart(fig, unit=None):
    fig.update_layout(template="institutional")
    if unit == "percent":
        fig.update_yaxes(tickformat=".1%")
        fig.update_traces(hovertemplate="%{y:.2%}<extra>%{fullData.name}</extra>")
    elif unit == "wealth":
        fig.update_yaxes(title_text="Patrimônio · base 1", tickformat=",.2f")
    elif unit == "distribution":
        fig.update_xaxes(title_text="Retorno residual mensal", tickformat=".1%")
        fig.update_yaxes(title_text="Observações")
    return fig


def footer():
    version = importlib.metadata.version("factorlab")
    timestamp = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    st.markdown(
        f'<footer class="platform-footer"><span>Pesquisa quantitativa · não constitui recomendação de investimento.</span><span>FactorLab {escape(version)} · {timestamp}</span></footer>',
        unsafe_allow_html=True,
    )


def welcome_cards():
    cards = [
        (
            "01 / EXPOSIÇÕES",
            "Pesquisa de fatores",
            "Compare modelos e exposições com amostra mensal comum e fontes identificadas.",
        ),
        (
            "02 / INFERÊNCIA",
            "Evidência, não promessa",
            "Interprete alpha, intervalos HAC, influência e estabilidade dos coeficientes.",
        ),
        (
            "03 / ALOCAÇÃO",
            "Risco e implementação",
            "Avalie cenários, custos, restrições e resultados fora da amostra.",
        ),
    ]
    st.markdown(
        '<div class="feature-grid">'
        + "".join(
            f"<article><small>{a}</small><h3>{b}</h3><p>{c}</p></article>" for a, b, c in cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )
