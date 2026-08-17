"""Geração de relatório PDF consolidado com ReportLab."""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

_COR_PRETO = colors.HexColor("#1A1A1A")
_COR_CLARO = colors.HexColor("#F5F5F5")
_COR_VERDE = colors.HexColor("#C8E6C9")
_COR_VERMELHO = colors.HexColor("#FFCDD2")
_COR_LINHA = colors.HexColor("#D0D0D0")

def _estilos() -> dict:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("Titulo", parent=base["Title"], fontSize=18, textColor=_COR_PRETO, spaceAfter=4),
        "sub": ParagraphStyle("Sub", parent=base["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=16),
        "secao": ParagraphStyle("Secao", parent=base["Heading2"], fontSize=13, textColor=_COR_PRETO, spaceBefore=12, spaceAfter=6),
        "corpo": ParagraphStyle("Corpo", parent=base["Normal"], fontSize=9, leading=12, spaceAfter=4),
        "celula": ParagraphStyle("Cel", parent=base["Normal"], fontSize=8, leading=10),
        "celula_b": ParagraphStyle("CelB", parent=base["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold"),
        "parecer": ParagraphStyle("Parecer", parent=base["Normal"], fontSize=9, leading=13, spaceAfter=6),
    }

def _tabela_produto(produto: dict, estilos: dict, indice: int) -> Table:
    """Tabela de um produto com checklist."""
    conforme = produto.get("conforme", False)
    pct = produto.get("conformidade_percentual", 0)
    status = "✅ CONFORME" if conforme else "❌ NÃO CONFORME"

    preco = produto.get("preco", "N/D")
    cb = produto.get("custo_beneficio", 0)

    # Checklist
    checklist = produto.get("checklist", [])
    checklist_txt = ""
    if checklist:
        for c in checklist:
            icon = "✅" if c.get("atendido") else "❌"
            checklist_txt += f"{icon} {c.get('requisito', '')}: {c.get('observacao', '')}<br/>"
    else:
        checklist_txt = "N/D"

    dados = [
        [Paragraph(f"<b>Produto {indice}</b>", estilos["celula_b"]), Paragraph(status, estilos["celula_b"])],
        [Paragraph("Marca", estilos["celula"]), Paragraph(str(produto.get("marca", "N/D")), estilos["celula"])],
        [Paragraph("Modelo", estilos["celula"]), Paragraph(str(produto.get("modelo", "N/D")), estilos["celula"])],
        [Paragraph("Preço", estilos["celula"]), Paragraph(str(preco), estilos["celula"])],
        [Paragraph("Custo-Benefício", estilos["celula"]), Paragraph(f"{cb}/10", estilos["celula"])],
        [Paragraph("Link do Catálogo", estilos["celula"]), Paragraph(str(produto.get("link_catalogo", "N/D")), estilos["celula"])],
        [Paragraph("Contato do Fabricante", estilos["celula"]), Paragraph(str(produto.get("contato_fabricante", "N/D")), estilos["celula"])],
        [Paragraph("Checklist de Conferência", estilos["celula"]), Paragraph(checklist_txt, estilos["celula"])],
    ]

    tabela = Table(dados, colWidths=[45*mm, 215*mm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COR_VERDE if conforme else _COR_VERMELHO),
        ("GRID", (0, 0), (-1, -1), 0.5, _COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabela

def _tabela_historico(historico: list[dict], estilos: dict) -> Table:
    """Tabela com histórico de licitações."""
    if not historico:
        return Paragraph("Sem histórico de licitações disponível.", estilos["corpo"])

    dados = [[
        Paragraph("<b>Processo</b>", estilos["celula_b"]),
        Paragraph("<b>Órgão</b>", estilos["celula_b"]),
        Paragraph("<b>Marca</b>", estilos["celula_b"]),
        Paragraph("<b>Valor</b>", estilos["celula_b"]),
        Paragraph("<b>Link</b>", estilos["celula_b"]),
    ]]

    for h in historico:
        dados.append([
            Paragraph(str(h.get("processo", "N/D")), estilos["celula"]),
            Paragraph(str(h.get("orgao", "N/D")), estilos["celula"]),
            Paragraph(str(h.get("marca", "N/D")), estilos["celula"]),
            Paragraph(str(h.get("valor_unitario", "N/D")), estilos["celula"]),
            Paragraph(str(h.get("link_processo", "N/D")), estilos["celula"]),
        ])

    tabela = Table(dados, colWidths=[45*mm, 55*mm, 40*mm, 30*mm, 90*mm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COR_PRETO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, _COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COR_CLARO]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela

def _secao_item(item: dict, estilos: dict) -> list:
    """Gera todos os elementos de um item no PDF."""
    elementos = []
    codigo = item.get("codigo_siad", "N/A")
    espec = item.get("especificacao", "N/D")

    elementos.append(Paragraph(f"Código SIAD: {codigo}", estilos["secao"]))
    elementos.append(Paragraph(f"<b>Especificação:</b> {espec}", estilos["corpo"]))
    elementos.append(Spacer(1, 6))

    # Produtos
    produtos = item.get("produtos", [])
    if produtos:
        for i, prod in enumerate(produtos, 1):
            elementos.append(_tabela_produto(prod, estilos, i))
            elementos.append(Spacer(1, 6))
    else:
        elementos.append(Paragraph("Nenhum produto encontrado.", estilos["corpo"]))

    # Histórico
    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph("Histórico de Licitações (ComprasMG / PNCP)", estilos["secao"]))
    elementos.append(_tabela_historico(item.get("historico", []), estilos))
    elementos.append(Spacer(1, 8))

    # Parecer
    parecer = item.get("parecer", {})
    conclusao = parecer.get("parecer", "N/D")
    cor = _COR_VERDE if "FAVOR" in conclusao.upper() else _COR_VERMELHO

    dados_parecer = [
        [Paragraph("<b>PARECER TÉCNICO</b>", estilos["celula_b"]),
         Paragraph(f"<b>{conclusao}</b>", estilos["celula_b"])],
        [Paragraph("Justificativa", estilos["celula"]),
         Paragraph(str(parecer.get("justificativa", "N/D")), estilos["parecer"])],
        [Paragraph("Modelo Recomendado", estilos["celula"]),
         Paragraph(f"{parecer.get('marca_recomendada', '')} — {parecer.get('modelo_recomendado', '')} — {parecer.get('preco_recomendado', '')}", estilos["celula"])],
    ]

    tabela = Table(dados_parecer, colWidths=[45*mm, 215*mm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cor),
        ("BACKGROUND", (0, 1), (-1, -1), _COR_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.5, _COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela)
    elementos.append(Spacer(1, 16))

    return elementos

def gerar_pdf(resultados: list[dict]) -> bytes:
    """Gera relatório PDF completo."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    estilos = _estilos()
    elementos = []

    # Cabeçalho
    elementos.append(Paragraph("Sistema de Inteligência de Licitações", estilos["titulo"]))
    elementos.append(Paragraph(
        f"Lobo Soluções em Licitações — {datetime.now().strftime('%d/%m/%Y')}",
        estilos["sub"],
    ))

    for idx, item in enumerate(resultados):
        elementos.extend(_secao_item(item, estilos))
        if idx < len(resultados) - 1:
            elementos.append(PageBreak())

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()