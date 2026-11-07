"""Relatório HTML autônomo e pacote ZIP consolidado."""

import io
import json
import zipfile
from html import escape

import plotly.express as px

from factorlab.research import Study


def interpretation(result):
    alpha = result.coefficients.loc["alpha"]
    if alpha.ci_95_low <= 0 <= alpha.ci_95_high:
        return (
            "O intervalo de confiança do alpha inclui zero; a amostra não fornece "
            "evidência suficiente de alpha diferente de zero."
        )
    return (
        "O intervalo de confiança do alpha não inclui zero nesta amostra. "
        "Isso não prova habilidade, causalidade ou persistência futura."
    )


def html_report(study: Study, metadata: dict, extras=None) -> str:
    sections = []
    for (asset, model), result in study.results.items():
        equation = "R − RF = " + f"{result.coefficients.loc['alpha', 'coefficient']:.6f}"
        for factor, row in result.coefficients.drop(index="alpha").iterrows():
            equation += f" + ({row.coefficient:.4f}) × {factor}"
        sections.append(
            f"<h3>{escape(asset)} · {escape(model)}</h3>"
            f"<p>{interpretation(result)}</p><p>{escape(equation)} + ε</p>"
            + result.coefficients.to_html(escape=True)
            + "<h4>Diagnósticos</h4><pre>"
            + escape(json.dumps(result.diagnostics, indent=2))
            + "</pre>"
        )
    wealth = (1 + study.returns).cumprod()
    chart = px.line(wealth, title="Patrimônio normalizado · base inicial 1").to_html(
        full_html=False, include_plotlyjs=True
    )
    return (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<title>FactorLab — relatório</title><style>body{font:15px Arial;margin:40px}"
        "table{border-collapse:collapse;font-size:12px}td,th{padding:6px;border:1px solid #ccc}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:10px}}</style>"
        "<h1>FactorLab · Relatório de fatores</h1><h2>Resumo executivo</h2>"
        f"<p>{len(study.returns)} meses em amostra comum: "
        f"{study.returns.index.min():%Y-%m} a {study.returns.index.max():%Y-%m}. "
        f"Benchmark: {escape(study.benchmark)}.</p>"
        "<p>Comparação retrospectiva, não recomendação de investimento.</p>"
        + study.summary.to_html(escape=True)
        + chart
        + "".join(sections)
        + "".join(
            f"<h2>{escape(str(name))}</h2>" + frame.to_html(escape=True)
            for name, frame in (extras or {}).items()
        )
        + "<h2>Limitações</h2><p>HAC é assintótico. Múltiplos testes não são corrigidos. "
        "SMB FF3 e FF5 diferem. AIC/BIC são critérios gaussianos convencionais, não robustos "
        "a qualquer dependência dos erros. Custos e impostos não incluídos. "
        "Walk-forward com fatores realizados não é previsão negociável.</p>"
        "<h2>Fontes, parâmetros e rastreabilidade</h2><pre>"
        + escape(json.dumps(metadata, ensure_ascii=False, indent=2))
        + "</pre></html>"
    )


def pdf_report(study: Study, metadata: dict, extras=None) -> bytes:
    """PDF nativo sem navegador ou serviço externo."""
    from reportlab.graphics.shapes import Drawing, PolyLine, String
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("FactorLab - Relatório de fatores", styles["Title"]),
        Paragraph(
            f"Amostra comum: {study.returns.index.min():%Y-%m} a "
            f"{study.returns.index.max():%Y-%m}; {len(study.returns)} meses. "
            f"Benchmark: {escape(study.benchmark)}.",
            styles["Normal"],
        ),
    ]
    drawing = Drawing(480, 180)
    wealth = (1 + study.returns).cumprod()
    low, high = float(wealth.min().min()), float(wealth.max().max())
    palette = [colors.blue, colors.red, colors.green, colors.orange, colors.purple]
    for i, asset in enumerate(wealth):
        values = wealth[asset].to_numpy()
        points = [
            (20 + j * 440 / max(1, len(values) - 1), 30 + (v - low) * 120 / max(high - low, 1e-12))
            for j, v in enumerate(values)
        ]
        drawing.add(PolyLine(points, strokeColor=palette[i % len(palette)], strokeWidth=1))
        drawing.add(
            String(
                20 + (i % 4) * 115,
                10 + (i // 4) * 12,
                str(asset)[:18],
                fontSize=8,
                fillColor=palette[i % len(palette)],
            )
        )
    story.extend(
        [
            Spacer(1, 0.4 * cm),
            Paragraph("Patrimônio normalizado (base 1)", styles["Heading2"]),
            drawing,
        ]
    )
    for (asset, model), result in study.results.items():
        story.extend(
            [
                Paragraph(f"{escape(asset)} / {escape(model)}", styles["Heading2"]),
                Paragraph(interpretation(result), styles["Normal"]),
                Paragraph(
                    escape(
                        "R - RF = alpha + "
                        + " + ".join(
                            f"beta({f}) * {f}" for f in result.coefficients.index if f != "alpha"
                        )
                        + " + erro"
                    ),
                    styles["Normal"],
                ),
            ]
        )
        rows = [["Fator", "Coeficiente", "IC 95% inf.", "IC 95% sup."]]
        rows += [
            [f, f"{r.coefficient:.6f}", f"{r.ci_95_low:.6f}", f"{r.ci_95_high:.6f}"]
            for f, r in result.coefficients.iterrows()
        ]
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            )
        )
        story.extend(
            [
                table,
                Paragraph(escape(json.dumps(result.metrics)), styles["Normal"]),
                Paragraph(
                    "Diagnósticos: " + escape(json.dumps(result.diagnostics)), styles["Normal"]
                ),
            ]
        )
    story.extend(
        [
            Paragraph("Limitações e rastreabilidade", styles["Heading2"]),
            Paragraph(
                "Sem recomendação de investimento. HAC é assintótico; SMB FF3/FF5 diferem. "
                "Avaliação explicativa com fatores realizados não é previsão. Previsão defasada "
                "não garante rentabilidade nem disponibilidade point-in-time. Sem custos ou impostos.",
                styles["Normal"],
            ),
            Paragraph(escape(json.dumps(metadata, ensure_ascii=False)), styles["Normal"]),
        ]
    )
    for name, frame in (extras or {}).items():
        story.append(Paragraph(escape(str(name)), styles["Heading2"]))
        # Transpõe em registros para manter tabelas largas legíveis; limita tamanho explícito.
        for index, row in frame.head(60).iterrows():
            text = str(index) + ": " + "; ".join(f"{col}={value}" for col, value in row.items())
            story.append(Paragraph(escape(text), styles["Normal"]))
        if len(frame) > 60:
            story.append(
                Paragraph("Prévia de 60 linhas; dados completos no CSV do ZIP.", styles["Normal"])
            )
    SimpleDocTemplate(buffer, rightMargin=1.5 * cm, leftMargin=1.5 * cm).build(story)
    return buffer.getvalue()


def export_bundle(study: Study, metadata: dict, extras=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.csv", study.summary.to_csv())
        archive.writestr("returns.csv", study.returns.to_csv())
        archive.writestr("manifest.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        archive.writestr("report.html", html_report(study, metadata, extras))
        archive.writestr("report.pdf", pdf_report(study, metadata, extras))
        # Identificadores numéricos evitam caminhos fornecidos pelo usuário dentro do ZIP.
        for i, ((asset, model), result) in enumerate(study.results.items()):
            prefix = f"analyses/{i:03d}"
            archive.writestr(
                f"{prefix}/identity.json", json.dumps({"asset": asset, "model": model})
            )
            archive.writestr(f"{prefix}/coefficients.csv", result.coefficients.to_csv())
            archive.writestr(f"{prefix}/rolling.csv", result.rolling.to_csv())
            archive.writestr(
                f"{prefix}/observations.csv",
                result.data.join(result.fitted).join(result.residuals).to_csv(),
            )
        for i, (name, frame) in enumerate((extras or {}).items()):
            archive.writestr(f"extras/{i:03d}.csv", frame.to_csv())
            archive.writestr(f"extras/{i:03d}.json", json.dumps({"name": name}))
    return buffer.getvalue()
