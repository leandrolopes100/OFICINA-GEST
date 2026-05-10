import calendar
from datetime import date, timedelta

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
import json

from core.mixins import RoleRequiredMixin
from core.utils import parse_mes_ano


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/dashboard.html'

    def get_context_data(self, **kwargs):
        from ordens_servico.models import OrdemServico
        from orcamentos.models import Orcamento
        from clientes.models import Cliente
        from estoque.models import Produto
        from financeiro.models import Lancamento
        from django.db.models import F

        ctx = super().get_context_data(**kwargs)
        hoje       = timezone.now().date()
        mes_atual  = hoje.month
        ano_atual  = hoje.year

        ctx['hoje'] = hoje

        ctx['total_clientes'] = Cliente.objects.filter(ativo=True).count()
        ctx['os_abertas'] = OrdemServico.objects.filter(
            status__in=['aberta', 'em_andamento', 'aguardando']
        ).count()
        ctx['orcamentos_pendentes'] = Orcamento.objects.filter(
            status__in=['rascunho', 'enviado']
        ).count()
        ctx['alertas_estoque'] = Produto.objects.filter(
            estoque_atual__lte=F('estoque_minimo'), ativo=True
        ).count()
        # Usa data_pagamento (regime de caixa) — mesmo critério do Relatório de Faturamento
        ctx['faturamento_mes'] = Lancamento.objects.filter(
            tipo='receita', status='pago',
            data_pagamento__month=mes_atual,
            data_pagamento__year=ano_atual,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        ctx['ordens_recentes'] = OrdemServico.objects.select_related(
            'cliente', 'veiculo'
        ).order_by('-data_abertura')[:8]
        ctx['orcamentos_recentes'] = Orcamento.objects.select_related(
            'cliente'
        ).order_by('-data_criacao')[:5]

        prazo_alerta = hoje + timedelta(days=7)
        orcamentos_expirando_qs = Orcamento.objects.filter(
            status__in=['rascunho', 'enviado'],
            data_validade__gte=hoje,
            data_validade__lte=prazo_alerta,
        ).select_related('cliente', 'veiculo').order_by('data_validade')

        ctx['orcamentos_expirando'] = [
            {
                'orc': orc,
                'dias_restantes': (orc.data_validade - hoje).days,
            }
            for orc in orcamentos_expirando_qs
        ]

        return ctx


# [S-01] Endpoint de API financeira protegido por autenticação
@login_required
def dashboard_data_api(request):
    """Retorna dados do gráfico de 6 meses. 12 queries → 1 query."""
    from financeiro.models import Lancamento

    hoje = timezone.now().date()

    meses = []
    for i in range(5, -1, -1):
        m = hoje.month - i
        if m <= 0:
            meses.append((hoje.year - 1, m + 12))
        else:
            meses.append((hoje.year, m))

    inicio    = date(meses[0][0], meses[0][1], 1)
    ultimo_dia = calendar.monthrange(meses[-1][0], meses[-1][1])[1]
    fim       = date(meses[-1][0], meses[-1][1], ultimo_dia)

    rows = (
        Lancamento.objects
        .filter(status='pago', data_pagamento__gte=inicio, data_pagamento__lte=fim)
        .values('data_pagamento__year', 'data_pagamento__month', 'tipo')
        .annotate(t=Sum('valor'))
    )
    lookup = {
        (r['data_pagamento__year'], r['data_pagamento__month'], r['tipo']): float(r['t'])
        for r in rows
    }

    labels, receitas, despesas = [], [], []
    for ano_i, mes_i in meses:
        labels.append(f'{mes_i:02d}/{ano_i}')
        receitas.append(lookup.get((ano_i, mes_i, 'receita'), 0))
        despesas.append(lookup.get((ano_i, mes_i, 'despesa'), 0))

    return JsonResponse({'labels': labels, 'receitas': receitas, 'despesas': despesas})


# [S-02] Relatórios financeiros restritos a admin e recepcionista
class RelatorioFaturamentoView(RoleRequiredMixin, TemplateView):
    template_name = 'relatorios/faturamento.html'
    allowed_roles = ['admin', 'recepcionista']

    def get_context_data(self, **kwargs):
        from financeiro.models import Lancamento
        ctx  = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        # [C-01] Validação de parâmetros GET
        mes, ano = parse_mes_ano(self.request, hoje)

        tipo_filtro   = self.request.GET.get('tipo',   '')
        status_filtro = self.request.GET.get('status', '')

        # [C-04] KPIs de valores pagos/recebidos usam data_pagamento (regime de caixa)
        # — mesmo critério do Dashboard, evitando divergência entre as duas telas.
        base_caixa = Lancamento.objects.filter(
            data_pagamento__month=mes, data_pagamento__year=ano, status='pago'
        )
        rec_pagas  = base_caixa.filter(tipo='receita').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        desp_pagas = base_caixa.filter(tipo='despesa').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        saldo_realizado = rec_pagas - desp_pagas

        # Pendentes e vencidos usam data_competencia (regime de competência)
        base_comp      = Lancamento.objects.filter(
            data_competencia__month=mes, data_competencia__year=ano
        )
        rec_pendentes  = base_comp.filter(tipo='receita', status__in=['pendente', 'vencido']).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        desp_pendentes = base_comp.filter(tipo='despesa', status__in=['pendente', 'vencido']).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        # Custo de taxas sobre receitas pagas
        taxas_por_forma = list(
            base_caixa
            .filter(tipo='receita', valor_taxa__gt=0)
            .values('forma_pagamento__nome')
            .annotate(total=Sum('valor_taxa'))
            .order_by('-total')
        )
        total_taxas  = base_caixa.filter(tipo='receita').aggregate(t=Sum('valor_taxa'))['t'] or Decimal('0')
        saldo_liquido = saldo_realizado - total_taxas

        # Tabela: aplica filtros opcionais sobre base de competência
        qs = base_comp.select_related('forma_pagamento', 'ordem_servico')
        if tipo_filtro:
            qs = qs.filter(tipo=tipo_filtro)
        if status_filtro:
            qs = qs.filter(status=status_filtro)
        lancamentos = qs.order_by('-data_competencia', '-id')

        # Gráfico diário — usa data_pagamento (mesmo critério dos KPIs)
        dias_no_mes = calendar.monthrange(ano, mes)[1]
        rec_dia     = {i: 0.0 for i in range(1, dias_no_mes + 1)}
        desp_dia    = {i: 0.0 for i in range(1, dias_no_mes + 1)}
        for row in base_caixa.values('data_pagamento', 'tipo').annotate(t=Sum('valor')):
            dia = row['data_pagamento'].day
            if row['tipo'] == 'receita':
                rec_dia[dia]  += float(row['t'])
            else:
                desp_dia[dia] += float(row['t'])

        # Navegação prev/next
        prev_mes = mes - 1 if mes > 1  else 12
        prev_ano = ano     if mes > 1  else ano - 1
        next_mes = mes + 1 if mes < 12 else 1
        next_ano = ano     if mes < 12 else ano + 1

        nomes_mes = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                     'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

        ctx.update({
            'lancamentos':       lancamentos,
            'rec_pagas':         rec_pagas,
            'rec_pendentes':     rec_pendentes,
            'desp_pagas':        desp_pagas,
            'desp_pendentes':    desp_pendentes,
            'saldo_realizado':   saldo_realizado,
            'total_taxas':       total_taxas,
            'saldo_liquido':     saldo_liquido,
            'taxas_por_forma':   taxas_por_forma,
            'total_receitas':    rec_pagas + rec_pendentes,
            'total_despesas':    desp_pagas + desp_pendentes,
            'saldo':             (rec_pagas + rec_pendentes) - (desp_pagas + desp_pendentes),
            'count_lancamentos': lancamentos.count(),
            'chart_labels':      json.dumps([str(d) for d in range(1, dias_no_mes + 1)]),
            'chart_receitas':    json.dumps([rec_dia[d]  for d in range(1, dias_no_mes + 1)]),
            'chart_despesas':    json.dumps([desp_dia[d] for d in range(1, dias_no_mes + 1)]),
            'mes':               mes,
            'ano':               ano,
            'nome_mes':          nomes_mes[mes],
            'tipo_filtro':       tipo_filtro,
            'status_filtro':     status_filtro,
            'prev_mes': prev_mes, 'prev_ano': prev_ano,
            'next_mes': next_mes, 'next_ano': next_ano,
        })
        return ctx


class RelatorioOrcamentosView(RoleRequiredMixin, TemplateView):
    template_name = 'relatorios/orcamentos.html'
    allowed_roles = ['admin', 'recepcionista']

    def get_context_data(self, **kwargs):
        from orcamentos.models import Orcamento
        ctx  = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        # [C-01] Validação de parâmetros GET
        mes, ano = parse_mes_ano(self.request, hoje)

        orcamentos = Orcamento.objects.filter(
            data_criacao__month=mes, data_criacao__year=ano
        )
        totais = orcamentos.aggregate(
            total=Count('id'),
            aprovados=Count('id', filter=Q(status='aprovado')),
            reprovados=Count('id', filter=Q(status='reprovado')),
            pendentes=Count('id', filter=Q(status__in=['rascunho', 'enviado'])),
        )
        ctx['total']      = totais['total']
        ctx['aprovados']  = totais['aprovados']
        ctx['reprovados'] = totais['reprovados']
        ctx['pendentes']  = totais['pendentes']
        ctx['orcamentos'] = orcamentos.select_related('cliente').order_by('-data_criacao')
        ctx['mes'] = mes
        ctx['ano'] = ano
        return ctx


class RelatorioServicosView(RoleRequiredMixin, TemplateView):
    template_name = 'relatorios/servicos.html'
    allowed_roles = ['admin', 'recepcionista']

    def get_context_data(self, **kwargs):
        from ordens_servico.models import ItemOSServico
        from clientes.models import Cliente
        from django.db.models import Q

        ctx  = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        # periodo: 'mes' (padrão) | 'ano' | 'todo'
        periodo = self.request.GET.get('periodo', 'mes')
        mes, ano = parse_mes_ano(self.request, hoje)

        if periodo == 'todo':
            filtro_item = Q()
            filtro_os   = Q()
        elif periodo == 'ano':
            filtro_item = Q(ordem_servico__data_abertura__year=ano)
            # Count('ordens_servico') parte do model Cliente — precisa do prefixo do relacionamento
            filtro_os   = Q(ordens_servico__data_abertura__year=ano)
        else:  # 'mes' — padrão
            filtro_item = Q(
                ordem_servico__data_abertura__year=ano,
                ordem_servico__data_abertura__month=mes,
            )
            filtro_os = Q(
                ordens_servico__data_abertura__year=ano,
                ordens_servico__data_abertura__month=mes,
            )

        ctx['servicos_mais_realizados'] = (
            ItemOSServico.objects
            .filter(filtro_item)
            .values('tipo_servico__nome')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        ctx['clientes_frequentes'] = (
            Cliente.objects.filter(ativo=True)
            .annotate(total_os=Count('ordens_servico', filter=filtro_os))
            .filter(total_os__gt=0)
            .order_by('-total_os')[:10]
        )

        prev_mes = mes - 1 if mes > 1 else 12
        prev_ano = ano     if mes > 1 else ano - 1
        next_mes = mes + 1 if mes < 12 else 1
        next_ano = ano     if mes < 12 else ano + 1

        nomes_mes = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                     'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

        ctx.update({
            'periodo':  periodo,
            'mes':      mes,
            'ano':      ano,
            'nome_mes': nomes_mes[mes],
            'prev_mes': prev_mes, 'prev_ano': prev_ano,
            'next_mes': next_mes, 'next_ano': next_ano,
        })
        return ctx
