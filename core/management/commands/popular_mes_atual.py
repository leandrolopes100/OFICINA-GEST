import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from financeiro.models import Lancamento, FormaPagamento
from orcamentos.models import Orcamento, TipoServico, ItemOrcamentoServico
from veiculos.models import Veiculo
from accounts.models import CustomUser

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
    help = (
        'Garante que o mês atual tenha faturamento acima da meta e orçamentos a vencer, '
        'para o dashboard exibir os cartões de alerta com dados reais.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--meta', type=int, default=65000,
            help='Meta de faturamento (receita paga) do mês atual em reais (padrão: 65000)',
        )

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        meta = Decimal(str(options['meta']))

        with transaction.atomic():
            self._completar_faturamento_mes(hoje, meta)
            self._completar_despesas_mes(hoje)
            self._criar_orcamentos_a_vencer(hoje)

        self.stdout.write(self.style.SUCCESS('\nMês atual populado com sucesso.'))

    def _completar_faturamento_mes(self, hoje, meta):
        atual = Lancamento.objects.filter(
            tipo='receita', status='pago',
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        falta = meta - atual
        if falta <= 0:
            self.stdout.write(f'  Faturamento do mês já atinge R$ {atual} (meta R$ {meta}).')
            return

        formas = list(FormaPagamento.objects.filter(ativo=True))
        primeiro_dia = hoje.replace(day=1)
        n_lancamentos = 6
        valores = []
        restante = falta
        for i in range(n_lancamentos - 1):
            parte = (restante / (n_lancamentos - i)).quantize(Decimal('1'))
            valores.append(parte)
            restante -= parte
        valores.append(restante)

        for i, valor in enumerate(valores):
            dia = primeiro_dia + timedelta(days=random.randint(0, (hoje - primeiro_dia).days))
            Lancamento.objects.create(
                tipo='receita',
                categoria=random.choice(CATEGORIAS_RECEITA),
                descricao=random.choice(DESCRICOES_RECEITA),
                valor=valor,
                forma_pagamento=random.choice(formas) if formas else None,
                data_competencia=dia,
                data_pagamento=dia,
                status='pago',
            )
            self.stdout.write(f'  + Receita: R$ {valor} em {dia}')

    def _completar_despesas_mes(self, hoje):
        atual = Lancamento.objects.filter(
            tipo='despesa', status='pago',
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        if atual > 0:
            self.stdout.write(f'  Despesas do mês já possuem R$ {atual} — mantido.')
            return

        primeiro_dia = hoje.replace(day=1)
        for categoria, descricao in DESCRICOES_DESPESA:
            dia = primeiro_dia + timedelta(days=random.randint(0, (hoje - primeiro_dia).days))
            valor = Decimal(random.randint(1800, 8500))
            Lancamento.objects.create(
                tipo='despesa',
                categoria=categoria,
                descricao=descricao,
                valor=valor,
                data_competencia=dia,
                data_pagamento=dia,
                status='pago',
            )
            self.stdout.write(f'  + Despesa: R$ {valor} em {dia} ({descricao})')

    def _criar_orcamentos_a_vencer(self, hoje):
        janela = Orcamento.objects.filter(
            status__in=['rascunho', 'enviado'],
            data_validade__gte=hoje,
            data_validade__lte=hoje + timedelta(days=7),
        ).count()
        alvo = 3
        faltam = max(0, alvo - janela)
        if faltam == 0:
            self.stdout.write('  Já existem orçamentos a vencer nos próximos 7 dias.')
            return

        tipo_servico = TipoServico.objects.filter(ativo=True).first()
        veiculos = list(Veiculo.objects.select_related('cliente').filter(ativo=True))
        criado_por = CustomUser.objects.filter(role='admin').first() or CustomUser.objects.first()
        prazos = [0, 2, 5]  # vence hoje / poucos dias (danger) / alguns dias (warning)

        for i in range(faltam):
            veiculo = random.choice(veiculos)
            validade = hoje + timedelta(days=prazos[i % len(prazos)])
            orc = Orcamento.objects.create(
                cliente=veiculo.cliente,
                veiculo=veiculo,
                criado_por=criado_por,
                status=random.choice(['rascunho', 'enviado']),
                data_validade=validade,
                km_entrada=veiculo.km_atual,
            )
            if tipo_servico:
                ItemOrcamentoServico.objects.create(
                    orcamento=orc,
                    tipo_servico=tipo_servico,
                    descricao=tipo_servico.nome,
                    quantidade=1,
                    preco_unitario=Decimal(random.choice([280, 350, 420, 590])),
                )
                orc.recalcular_totais()
            self.stdout.write(f'  + Orçamento a vencer: ORC-{orc.numero} — válido até {validade} ({veiculo.cliente.nome})')
