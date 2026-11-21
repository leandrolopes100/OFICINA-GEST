from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.templatetags.oficina_tags import currency

FORMATO_REAIS = '"R$" #,##0.00;[Red]-"R$" #,##0.00'
FORMATO_PERCENTUAL = '0.0%'
FORMATO_DATA = 'DD/MM/YYYY'

COR_ESCURA = '1A1A2E'
COR_DESTAQUE = 'E5252A'
COR_CINZA = 'F8F9FA'
COR_VERDE = '146C43'
COR_VERMELHA = 'B02A37'

FONTE_TITULO = Font(bold=True, size=14, color=COR_ESCURA)
FONTE_SUBTITULO = Font(size=10, color='6C757D')
FONTE_CABECALHO = Font(bold=True, color='FFFFFF')
FONTE_SECAO = Font(bold=True, size=11, color=COR_ESCURA)
FONTE_NEGRITO = Font(bold=True)
PREENCHIMENTO_CABECALHO = PatternFill('solid', fgColor=COR_ESCURA)
PREENCHIMENTO_SUBTOTAL = PatternFill('solid', fgColor=COR_CINZA)
PREENCHIMENTO_LUCRO = PatternFill('solid', fgColor='E8F3EE')
PREENCHIMENTO_PREJUIZO = PatternFill('solid', fgColor='F8E7E9')
BORDA_SUPERIOR = Border(top=Side(style='thin', color='DEE2E6'))


def _percentual(valor):
    return None if valor is None else float(valor) / 100


def _cabecalho_do_relatorio(aba, titulo, contexto):
    aba['A1'] = 'OFICINA GEST'
    aba['A1'].font = Font(bold=True, size=10, color=COR_DESTAQUE)
    aba['A2'] = f'{titulo} — {contexto["nome_mes"]}/{contexto["ano"]}'
    aba['A2'].font = FONTE_TITULO
    aba['A3'] = (
        f'Emitido em {contexto["emitido_em"]:%d/%m/%Y às %H:%M} por {contexto["emitido_por"]} · '
        'considera os lançamentos pagos/recebidos no mês'
    )
    aba['A3'].font = FONTE_SUBTITULO


def _linha_de_cabecalho(aba, linha, titulos):
    for coluna, titulo in enumerate(titulos, start=1):
        celula = aba.cell(row=linha, column=coluna, value=titulo)
        celula.font = FONTE_CABECALHO
        celula.fill = PREENCHIMENTO_CABECALHO
        celula.alignment = Alignment(horizontal='left' if coluna == 1 else 'right', vertical='center')
    aba.row_dimensions[linha].height = 20


def _escrever(aba, linha, rotulo, valor, formato=FORMATO_REAIS, fonte=None, preenchimento=None, recuo=0):
    celula_rotulo = aba.cell(row=linha, column=1, value=rotulo)
    celula_rotulo.alignment = Alignment(indent=recuo)
    celula_valor = aba.cell(row=linha, column=2, value=valor)
    celula_valor.number_format = formato
    for celula in (celula_rotulo, celula_valor):
        if fonte:
            celula.font = fonte
        if preenchimento:
            celula.fill = preenchimento


def _aba_resumo(livro, lucro, contexto):
    aba = livro.active
    aba.title = 'Resumo'
    _cabecalho_do_relatorio(aba, 'Relatório de Lucratividade', contexto)

    linha = 5
    _linha_de_cabecalho(aba, linha, ['Resultado do mês', 'Valor', 'Margem'])
    linhas = [
        ('Receitas de OS', lucro.receita_os, None, {}),
        ('Receitas sem OS', lucro.receita_sem_os, None, {}),
        ('Faturamento', lucro.faturamento, None, {'fonte': FONTE_NEGRITO, 'preenchimento': PREENCHIMENTO_SUBTOTAL}),
        ('(−) Custo das peças', -lucro.custo_pecas, None, {}),
        ('(−) Taxas de cartão', -lucro.taxas, None, {}),
        ('Lucro bruto', lucro.lucro_bruto, lucro.margem_bruta,
         {'fonte': FONTE_NEGRITO, 'preenchimento': PREENCHIMENTO_SUBTOTAL}),
        ('(−) Despesas da oficina', -lucro.despesas, None, {}),
    ]
    linhas += [
        (despesa['categoria'], -despesa['total'], None, {'recuo': 2})
        for despesa in lucro.despesas_por_categoria
    ]
    linhas.append((
        'Lucro líquido', lucro.lucro_liquido, lucro.margem_liquida,
        {
            'fonte': Font(bold=True, size=12, color=COR_VERMELHA if lucro.prejuizo else COR_VERDE),
            'preenchimento': PREENCHIMENTO_PREJUIZO if lucro.prejuizo else PREENCHIMENTO_LUCRO,
        },
    ))
    for rotulo, valor, margem, estilo in linhas:
        linha += 1
        _escrever(aba, linha, rotulo, float(valor), **estilo)
        celula_margem = aba.cell(row=linha, column=3, value=_percentual(margem))
        celula_margem.number_format = FORMATO_PERCENTUAL
        if estilo.get('preenchimento'):
            celula_margem.fill = estilo['preenchimento']
        if estilo.get('fonte'):
            celula_margem.font = estilo['fonte']

    linha += 2
    _linha_de_cabecalho(aba, linha, ['Para onde foi o faturamento', 'Valor', '% do total'])
    for parte in contexto['composicao']:
        linha += 1
        _escrever(aba, linha, parte['nome'], float(parte['valor']))
        celula = aba.cell(row=linha, column=3, value=_percentual(parte['percentual']))
        celula.number_format = FORMATO_PERCENTUAL
    if lucro.prejuizo:
        linha += 1
        aviso = aba.cell(row=linha, column=1, value=(
            f'Mês no prejuízo: os custos passaram o faturamento em {currency(lucro.valor_prejuizo)}. '
            'Os percentuais são sobre o total de custos.'
        ))
        aviso.font = Font(italic=True, color=COR_VERMELHA)

    linha += 2
    _linha_de_cabecalho(aba, linha, ['Fora do lucro do mês', 'Valor', ''])
    linha += 1
    _escrever(aba, linha, 'Investido em estoque (compras de peças pagas no mês)', float(lucro.compras_de_pecas))
    linha += 1
    _escrever(
        aba, linha,
        f'A receber hoje ({lucro.qtd_a_receber} OS concluídas/entregues sem pagamento)',
        float(lucro.valor_a_receber),
    )

    aba.column_dimensions['A'].width = 58
    aba.column_dimensions['B'].width = 18
    aba.column_dimensions['C'].width = 12
    aba.sheet_view.showGridLines = False


def _aba_lucro_por_os(livro, lucro, contexto):
    aba = livro.create_sheet('Lucro por OS')
    _cabecalho_do_relatorio(aba, 'Lucro por OS', contexto)
    titulos = ['OS', 'Cliente', 'Pago em', 'Recebido', 'Peças', 'Taxa', 'Lucro', 'Margem', 'Observação']
    linha_cabecalho = 5
    _linha_de_cabecalho(aba, linha_cabecalho, titulos)
    aba.cell(row=linha_cabecalho, column=2).alignment = Alignment(horizontal='left', vertical='center')
    aba.cell(row=linha_cabecalho, column=9).alignment = Alignment(horizontal='left', vertical='center', indent=1)

    linha = linha_cabecalho
    for item in lucro.linhas:
        linha += 1
        observacoes = []
        if item.abaixo_do_custo:
            observacoes.append('peça abaixo do custo')
        if item.custo_estimado:
            observacoes.append('custo estimado')
        valores = [
            f'OS-{item.ordem.numero}', item.ordem.cliente.nome, item.data_pagamento,
            float(item.recebido), float(item.custo_pecas), float(item.taxa), float(item.lucro),
            _percentual(item.margem), ', '.join(observacoes),
        ]
        for coluna, valor in enumerate(valores, start=1):
            aba.cell(row=linha, column=coluna, value=valor)
        aba.cell(row=linha, column=3).number_format = FORMATO_DATA
        for coluna in (4, 5, 6, 7):
            aba.cell(row=linha, column=coluna).number_format = FORMATO_REAIS
        aba.cell(row=linha, column=8).number_format = FORMATO_PERCENTUAL
        aba.cell(row=linha, column=9).alignment = Alignment(indent=1)
        aba.cell(row=linha, column=7).font = Font(bold=True, color=COR_VERMELHA if item.lucro < 0 else COR_VERDE)

    if lucro.linhas:
        primeira, ultima = linha_cabecalho + 1, linha
        linha += 1
        aba.cell(row=linha, column=1, value='Total das OS')
        for coluna in (4, 5, 6, 7):
            letra = get_column_letter(coluna)
            celula = aba.cell(row=linha, column=coluna, value=f'=SUM({letra}{primeira}:{letra}{ultima})')
            celula.number_format = FORMATO_REAIS
        margem = aba.cell(row=linha, column=8, value=f'=IF(D{linha}=0,"",G{linha}/D{linha})')
        margem.number_format = FORMATO_PERCENTUAL
        for coluna in range(1, len(titulos) + 1):
            celula = aba.cell(row=linha, column=coluna)
            celula.font = FONTE_NEGRITO
            celula.fill = PREENCHIMENTO_SUBTOTAL
            celula.border = BORDA_SUPERIOR
        aba.auto_filter.ref = f'A{linha_cabecalho}:{get_column_letter(len(titulos))}{ultima}'
    else:
        aba.cell(row=linha + 1, column=1, value=f'Nenhuma OS recebida em {contexto["nome_mes"]}/{contexto["ano"]}.')

    aba.freeze_panes = f'A{linha_cabecalho + 1}'
    for coluna, largura in zip('ABCDEFGHI', (13, 34, 12, 15, 15, 12, 15, 11, 30)):
        aba.column_dimensions[coluna].width = largura


def _aba_avisos(livro, lucro, contexto):
    avisos = []
    if lucro.qtd_receitas_sem_os:
        avisos.append(
            f'{lucro.qtd_receitas_sem_os} receita(s) sem OS não têm custo de peça vinculado: '
            'o lucro dessas vendas aparece maior do que é.'
        )
    if lucro.qtd_custo_estimado:
        avisos.append(f'{lucro.qtd_custo_estimado} OS com custo estimado (sem baixa de estoque registrada na época).')
    if lucro.qtd_abaixo_do_custo:
        avisos.append(f'{lucro.qtd_abaixo_do_custo} OS com peça vendida abaixo do custo.')
    if not avisos:
        return
    aba = livro.create_sheet('Avisos')
    _cabecalho_do_relatorio(aba, 'Atenção ao ler os números', contexto)
    for indice, aviso in enumerate(avisos, start=5):
        aba.cell(row=indice, column=1, value=f'• {aviso}')
    aba.column_dimensions['A'].width = 110
    aba.sheet_view.showGridLines = False


def gerar_planilha_lucro(lucro, contexto):
    livro = Workbook()
    _aba_resumo(livro, lucro, contexto)
    _aba_lucro_por_os(livro, lucro, contexto)
    _aba_avisos(livro, lucro, contexto)
    livro.properties.title = f'Lucratividade {contexto["nome_mes"]}/{contexto["ano"]}'
    livro.properties.creator = 'Oficina Gest'
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()
