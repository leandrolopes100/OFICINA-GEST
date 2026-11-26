import io
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core.pdf import desenhar_rodape, texto_seguro
from core.templatetags.oficina_tags import currency
from ordens_servico.models import OrdemServico


def _quantidade(valor):
    return f'{valor.normalize():f}'.replace('.', ',')


def _cabecalho(veiculo, styles):
    logo_path = finders.find('logo_parceiro_claro.png')
    logo = Image(logo_path, width=5.5*cm, height=1.6*cm, kind='proportional', hAlign='LEFT') if logo_path else ''
    titulo = ParagraphStyle('titulo', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=14,
                            fontName='Helvetica-Bold', leading=17)
    subtitulo = ParagraphStyle('subtitulo', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=11)
    tabela = Table(
        [[logo, [Paragraph('HISTÓRICO DO VEÍCULO', titulo),
                 Paragraph(f'<b>Placa {texto_seguro(veiculo.placa)}</b>', subtitulo)]]],
        colWidths=[8.5*cm, 8.5*cm],
    )
    tabela.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _tabela_rotulos(dados, larguras):
    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tabela


def _tabela_itens(ordem, mostrar_valores, celula):
    itens = [('Serviço', item) for item in ordem.itens_servico.all()]
    itens += [('Peça', item) for item in ordem.itens_peca.all()]
    if not itens:
        return None

    if mostrar_valores:
        dados = [['Tipo', 'Descrição', 'Qtd', 'Total']]
        dados += [[tipo, celula(item.descricao), _quantidade(item.quantidade), currency(item.total)]
                  for tipo, item in itens]
        larguras = [2*cm, 10*cm, 2*cm, 3*cm]
    else:
        dados = [['Tipo', 'Descrição', 'Qtd']]
        dados += [[tipo, celula(item.descricao), _quantidade(item.quantidade)] for tipo, item in itens]
        larguras = [2*cm, 13*cm, 2*cm]

    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tabela


def gerar_pdf_historico_veiculo(veiculo):
    historico = OrdemServico.historico_do_veiculo(veiculo)
    ordens = [ordem for ordem in historico.ordens if ordem.status != 'cancelada']
    total_dono_atual = sum(
        (ordem.total for ordem in ordens
         if ordem.status == 'entregue' and ordem.cliente_id == veiculo.cliente_id),
        Decimal('0'),
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm,
                            title=f'Histórico do veículo {veiculo.placa}')
    styles = getSampleStyleSheet()
    pequeno = ParagraphStyle('pequeno', parent=styles['Normal'], fontSize=8.5, leading=11)
    titulo_os = ParagraphStyle('titulo_os', parent=styles['Normal'], fontSize=10.5,
                               fontName='Helvetica-Bold', leading=14, spaceAfter=3)

    def celula(texto):
        return Paragraph(texto_seguro(texto), pequeno)

    story = [
        _cabecalho(veiculo, styles),
        HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1a1a2e'), spaceBefore=6),
        Spacer(1, 0.4*cm),
        _tabela_rotulos([
            ['Veículo:', celula(f'{veiculo.marca} {veiculo.modelo}'), 'Placa:', veiculo.placa],
            ['Ano:', f'{veiculo.ano_fabricacao}/{veiculo.ano_modelo}', 'Cor:', celula(veiculo.cor)],
            ['Proprietário:', celula(veiculo.cliente.nome), 'Emitido em:',
             timezone.localtime().strftime('%d/%m/%Y %H:%M')],
        ], [3*cm, 7*cm, 3*cm, 4*cm]),
        Spacer(1, 0.3*cm),
        _tabela_rotulos([
            ['Visitas:', str(historico.visitas), 'Última visita:',
             timezone.localtime(historico.ultima_visita.data_abertura).strftime('%d/%m/%Y')
             if historico.ultima_visita else '—'],
            ['Total gasto:', currency(total_dono_atual), '', ''],
        ], [3*cm, 7*cm, 3*cm, 4*cm]),
        Paragraph('Total gasto considera apenas as ordens entregues do proprietário atual.', pequeno),
        Spacer(1, 0.5*cm),
    ]

    if not ordens:
        story.append(Paragraph('Nenhuma ordem de serviço registrada para este veículo.', styles['Normal']))

    for ordem in ordens:
        do_dono_atual = ordem.cliente_id == veiculo.cliente_id
        bloco = [
            Paragraph(
                f'OS nº {texto_seguro(ordem.numero)} · '
                f'{timezone.localtime(ordem.data_abertura).strftime("%d/%m/%Y")} · '
                f'{ordem.km_entrada:,} km · {ordem.get_status_display()}'.replace(',', '.'),
                titulo_os,
            ),
            Paragraph(
                f'<b>Cliente:</b> {texto_seguro(ordem.cliente.nome)}' if do_dono_atual
                else '<b>Cliente:</b> proprietário anterior', pequeno,
            ),
            Paragraph(f'<b>Defeito relatado:</b> {texto_seguro(ordem.defeito_relatado)}', pequeno),
            Spacer(1, 0.15*cm),
        ]
        tabela = _tabela_itens(ordem, do_dono_atual, celula)
        if tabela:
            bloco.append(tabela)
        if do_dono_atual:
            bloco.append(Paragraph(f'<b>Total da OS: {currency(ordem.total)}</b>',
                                   ParagraphStyle('total', parent=pequeno, alignment=TA_RIGHT, spaceBefore=3)))
        bloco += [Spacer(1, 0.2*cm), HRFlowable(width='100%', thickness=0.5, color=colors.lightgrey),
                  Spacer(1, 0.3*cm)]
        story.append(KeepTogether(bloco))

    doc.build(story, onFirstPage=desenhar_rodape, onLaterPages=desenhar_rodape)
    return buffer.getvalue()
