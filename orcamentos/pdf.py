import io
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def gerar_pdf_orcamento(orcamento):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16)
    normal = styles['Normal']
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8)

    # Header
    story.append(Paragraph('ORÇAMENTO DE SERVIÇOS - OFICINA RUBI', title_style))
    story.append(Paragraph(f'<b>Nº {orcamento.numero}</b>', ParagraphStyle('num', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12)))
    story.append(Spacer(1, 0.5*cm))

    # Cliente/Veículo info
    info_data = [
        ['Cliente:', orcamento.cliente.nome, 'Telefone:', orcamento.cliente.telefone],
        ['Veículo:', str(orcamento.veiculo.modelo), 'Placa:', orcamento.veiculo.placa],
        ['Data:', orcamento.data_criacao.strftime('%d/%m/%Y'), 'Validade:', orcamento.data_validade.strftime('%d/%m/%Y')],
        ['KM:', str(orcamento.km_entrada), 'Status:', orcamento.get_status_display()],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 7*cm, 3*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Serviços
    story.append(Paragraph('<b>SERVIÇOS</b>', styles['Heading3']))
    svc_data = [['Descrição', 'Qtd', 'Valor Unit.', 'Total']]
    for item in orcamento.itens_servico.all():
        svc_data.append([
            item.descricao,
            str(item.quantidade),
            f'R$ {item.preco_unitario:,.2f}',
            f'R$ {item.total:,.2f}',
        ])
    if len(svc_data) > 1:
        t = Table(svc_data, colWidths=[10*cm, 2*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightyellow]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ]))
        story.append(t)
    story.append(Spacer(1, 0.3*cm))

    # Peças
    story.append(Paragraph('<b>PEÇAS / MATERIAIS</b>', styles['Heading3']))
    peca_data = [['Descrição', 'Qtd', 'Valor Unit.', 'Total']]
    for item in orcamento.itens_peca.all():
        peca_data.append([
            item.descricao,
            str(item.quantidade),
            f'R$ {item.preco_unitario:,.2f}',
            f'R$ {item.total:,.2f}',
        ])
    if len(peca_data) > 1:
        t = Table(peca_data, colWidths=[10*cm, 2*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgreen]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ]))
        story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Totais
    totais_data = [
        ['Subtotal Serviços:', f'R$ {orcamento.subtotal_servicos:,.2f}'],
        ['Subtotal Peças:', f'R$ {orcamento.subtotal_pecas:,.2f}'],
    ]
    if orcamento.desconto_valor:
        totais_data.append(['Desconto:', f'- R$ {orcamento.desconto_valor:,.2f}'])
    if orcamento.taxa_valor:
        totais_data.append(['Taxa/Acréscimo:', f'R$ {orcamento.taxa_valor:,.2f}'])
    totais_data.append(['TOTAL:', f'R$ {orcamento.total:,.2f}'])

    t = Table(totais_data, colWidths=[13*cm, 4*cm])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(t)

    if orcamento.observacoes:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f'<b>Observações:</b> {orcamento.observacoes}', small))
    if orcamento.condicoes:
        story.append(Paragraph(f'<b>Condições:</b> {orcamento.condicoes}', small))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width='100%'))
    story.append(Paragraph('Assinatura do Cliente: _______________________________   Data: ___/___/______', small))

    doc.build(story)
    return buffer.getvalue()
