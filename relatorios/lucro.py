from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Exists, OuterRef, Sum

CATEGORIA_COMPRA_DE_PECAS = 'fornecedor'
STATUS_OS_A_RECEBER = ('concluida', 'entregue')
ZERO = Decimal('0')


def _margem(lucro, receita):
    if not receita:
        return None
    return (lucro / receita * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


@dataclass
class LinhaOS:
    ordem: object
    data_pagamento: object
    recebido: Decimal
    custo_pecas: Decimal
    taxa: Decimal
    custo_estimado: bool
    abaixo_do_custo: bool

    @property
    def lucro(self):
        return self.recebido - self.custo_pecas - self.taxa

    @property
    def margem(self):
        return _margem(self.lucro, self.recebido)


@dataclass
class LucroDoMes:
    receita_os: Decimal = ZERO
    receita_sem_os: Decimal = ZERO
    qtd_receitas_sem_os: int = 0
    custo_pecas: Decimal = ZERO
    taxas: Decimal = ZERO
    despesas_por_categoria: list = field(default_factory=list)
    compras_de_pecas: Decimal = ZERO
    linhas: list = field(default_factory=list)
    qtd_a_receber: int = 0
    valor_a_receber: Decimal = ZERO

    @property
    def faturamento(self):
        return self.receita_os + self.receita_sem_os

    @property
    def lucro_bruto(self):
        return self.faturamento - self.custo_pecas - self.taxas

    @property
    def despesas(self):
        return sum((linha['total'] for linha in self.despesas_por_categoria), ZERO)

    @property
    def lucro_liquido(self):
        return self.lucro_bruto - self.despesas

    @property
    def margem_bruta(self):
        return _margem(self.lucro_bruto, self.faturamento)

    @property
    def margem_liquida(self):
        return _margem(self.lucro_liquido, self.faturamento)

    @property
    def taxas_os(self):
        return sum((linha.taxa for linha in self.linhas), ZERO)

    @property
    def lucro_os(self):
        return sum((linha.lucro for linha in self.linhas), ZERO)

    @property
    def margem_os(self):
        return _margem(self.lucro_os, self.receita_os)

    @property
    def prejuizo(self):
        return self.lucro_liquido < 0

    @property
    def valor_prejuizo(self):
        return -self.lucro_liquido if self.prejuizo else ZERO

    def composicao(self):
        partes = [
            ('Peças', self.custo_pecas, '#dc3545', False),
            ('Taxas de cartão', self.taxas, '#fd7e14', True),
            ('Despesas da oficina', self.despesas, '#6f42c1', False),
            ('Lucro líquido', max(self.lucro_liquido, ZERO), '#198754', False),
        ]
        base = max(self.faturamento, self.custo_pecas + self.taxas + self.despesas)
        if base <= 0:
            return []
        return [
            {
                'nome': nome,
                'valor': valor,
                'percentual': (valor / base * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
                'cor': cor,
                'texto_escuro': texto_escuro,
            }
            for nome, valor, cor, texto_escuro in partes
            if valor > 0
        ]

    @property
    def qtd_custo_estimado(self):
        return sum(1 for linha in self.linhas if linha.custo_estimado)

    @property
    def qtd_abaixo_do_custo(self):
        return sum(1 for linha in self.linhas if linha.abaixo_do_custo)


def calcular_lucro_do_mes(mes, ano):
    from financeiro.models import Lancamento
    from ordens_servico.models import ItemOSPeca, OrdemServico

    resultado = LucroDoMes()
    pagos_no_mes = Lancamento.objects.filter(
        status='pago', data_pagamento__month=mes, data_pagamento__year=ano,
    )

    receitas_os = list(
        pagos_no_mes.filter(tipo='receita', ordem_servico__isnull=False)
        .select_related('ordem_servico__cliente')
        .order_by('data_pagamento', 'id')
    )
    ids_os = {receita.ordem_servico_id for receita in receitas_os}
    itens_por_os = defaultdict(list)
    for item in ItemOSPeca.objects.filter(ordem_servico_id__in=ids_os).select_related('produto'):
        itens_por_os[item.ordem_servico_id].append(item)

    for receita in receitas_os:
        cancelada = receita.ordem_servico.status == 'cancelada'
        itens = [] if cancelada else itens_por_os[receita.ordem_servico_id]
        linha = LinhaOS(
            ordem=receita.ordem_servico,
            data_pagamento=receita.data_pagamento,
            recebido=receita.valor,
            custo_pecas=sum((item.custo_total for item in itens), ZERO),
            taxa=receita.valor_taxa,
            custo_estimado=any(item.custo_estimado or item.custo_unitario is None for item in itens),
            abaixo_do_custo=any(item.abaixo_do_custo for item in itens),
        )
        resultado.linhas.append(linha)
        resultado.receita_os += linha.recebido
        resultado.custo_pecas += linha.custo_pecas
        resultado.taxas += linha.taxa

    sem_os = pagos_no_mes.filter(tipo='receita', ordem_servico__isnull=True)
    totais_sem_os = sem_os.aggregate(valor=Sum('valor'), taxa=Sum('valor_taxa'))
    resultado.receita_sem_os = totais_sem_os['valor'] or ZERO
    resultado.taxas += totais_sem_os['taxa'] or ZERO
    resultado.qtd_receitas_sem_os = sem_os.count()

    despesas = pagos_no_mes.filter(tipo='despesa')
    resultado.compras_de_pecas = (
        despesas.filter(categoria=CATEGORIA_COMPRA_DE_PECAS).aggregate(t=Sum('valor'))['t'] or ZERO
    )
    nomes = dict(Lancamento.CATEGORIA_CHOICES)
    resultado.despesas_por_categoria = [
        {'categoria': nomes.get(linha['categoria'], linha['categoria']), 'total': linha['total']}
        for linha in despesas.exclude(categoria=CATEGORIA_COMPRA_DE_PECAS)
        .values('categoria').annotate(total=Sum('valor')).order_by('-total')
    ]

    receita_paga = Lancamento.objects.filter(ordem_servico_id=OuterRef('pk'), tipo='receita', status='pago')
    a_receber = OrdemServico.objects.filter(status__in=STATUS_OS_A_RECEBER).exclude(Exists(receita_paga))
    totais_a_receber = a_receber.aggregate(total=Sum('total'))
    resultado.qtd_a_receber = a_receber.count()
    resultado.valor_a_receber = totais_a_receber['total'] or ZERO
    return resultado
