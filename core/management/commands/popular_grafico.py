import calendar
import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from financeiro.models import Lancamento

# valores plausíveis por mês, do mais antigo (5 meses atrás) para o mês atual
RECEITAS_PADRAO = [Decimal('47500'), Decimal('53200'), Decimal('84164.25'), Decimal('36012'), Decimal('49800'), Decimal('56000')]
DESPESAS_PADRAO = [Decimal('19800'), Decimal('22100'), Decimal('24600'), Decimal('6099'), Decimal('20300'), Decimal('21500')]

DESCRICOES_RECEITA = ['Recebimento de serviços', 'Venda de peças no balcão', 'Recebimento OS encerradas']
CATEGORIAS_RECEITA = ['servico', 'venda_peca']
DESCRICOES_DESPESA = [
    ('salario', 'Folha de pagamento'),
    ('aluguel', 'Aluguel do galpão'),
    ('utilidades', 'Água / Luz / Internet'),
    ('fornecedor', 'Compra de peças — fornecedor'),
    ('manutencao', 'Manutenção de equipamentos'),
]


class Command(BaseCommand):
    help = 'Preenche receitas/despesas pagas dos últimos 6 meses para popular o gráfico do dashboard'

    def handle(self, *args, **options):
        hoje = timezone.now().date()

        meses = []
        for i in range(5, -1, -1):
            m = hoje.month - i
            if m <= 0:
                meses.append((hoje.year - 1, m + 12))
            else:
                meses.append((hoje.year, m))

        with transaction.atomic():
            for idx, (ano, mes) in enumerate(meses):
                self._preencher_mes(ano, mes, 'receita', RECEITAS_PADRAO[idx])
                self._preencher_mes(ano, mes, 'despesa', DESPESAS_PADRAO[idx])

        self.stdout.write(self.style.SUCCESS('\nGráfico do dashboard populado com sucesso.'))

    def _preencher_mes(self, ano, mes, tipo, valor_alvo):
        existe = Lancamento.objects.filter(
            tipo=tipo, status='pago',
            data_pagamento__year=ano, data_pagamento__month=mes,
        ).aggregate(t=Sum('valor'))['t']

        if existe:
            self.stdout.write(f'  {tipo} {mes:02d}/{ano}: já possui R$ {existe} — mantido.')
            return

        ultimo_dia = calendar.monthrange(ano, mes)[1]
        dia = random.randint(1, ultimo_dia)
        dia_pagamento = date(ano, mes, dia)

        if tipo == 'receita':
            categoria = random.choice(CATEGORIAS_RECEITA)
            descricao = random.choice(DESCRICOES_RECEITA)
        else:
            categoria, descricao = random.choice(DESCRICOES_DESPESA)

        Lancamento.objects.create(
            tipo=tipo,
            categoria=categoria,
            descricao=descricao,
            valor=valor_alvo,
            data_competencia=dia_pagamento,
            data_pagamento=dia_pagamento,
            status='pago',
        )
        self.stdout.write(f'  + {tipo} {mes:02d}/{ano}: R$ {valor_alvo}')
