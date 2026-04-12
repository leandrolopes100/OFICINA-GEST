from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
import json


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
        hoje = timezone.now().date()
        mes_atual = hoje.month
        ano_atual = hoje.year

        ctx['total_clientes'] = Cliente.objects.filter(ativo=True).count()
        ctx['os_abertas'] = OrdemServico.objects.filter(status__in=['aberta', 'em_andamento', 'aguardando']).count()
        ctx['orcamentos_pendentes'] = Orcamento.objects.filter(status__in=['rascunho', 'enviado']).count()
        ctx['alertas_estoque'] = Produto.objects.filter(estoque_atual__lte=F('estoque_minimo'), ativo=True).count()

        # Faturamento do mês
        faturamento_mes = Lancamento.objects.filter(
            tipo='receita', status='pago',
            data_pagamento__month=mes_atual,
            data_pagamento__year=ano_atual
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['faturamento_mes'] = faturamento_mes

        # Ordens recentes
        ctx['ordens_recentes'] = OrdemServico.objects.select_related('cliente', 'veiculo').order_by('-data_abertura')[:8]
        ctx['orcamentos_recentes'] = Orcamento.objects.select_related('cliente').order_by('-data_criacao')[:5]

        return ctx


def dashboard_data_api(request):
    from financeiro.models import Lancamento
    hoje = timezone.now().date()
    labels = []
    receitas = []
    despesas = []

    for i in range(5, -1, -1):
        mes = (hoje.month - i - 1) % 12 + 1
        ano = hoje.year if hoje.month - i > 0 else hoje.year - 1
        labels.append(f'{mes:02d}/{ano}')
        r = Lancamento.objects.filter(
            tipo='receita', status='pago',
            data_pagamento__month=mes, data_pagamento__year=ano
        ).aggregate(t=Sum('valor'))['t'] or 0
        d = Lancamento.objects.filter(
            tipo='despesa', status='pago',
            data_pagamento__month=mes, data_pagamento__year=ano
        ).aggregate(t=Sum('valor'))['t'] or 0
        receitas.append(float(r))
        despesas.append(float(d))

    return JsonResponse({'labels': labels, 'receitas': receitas, 'despesas': despesas})


class RelatorioFaturamentoView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/faturamento.html'

    def get_context_data(self, **kwargs):
        from financeiro.models import Lancamento
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.now().date()
        mes = int(self.request.GET.get('mes', hoje.month))
        ano = int(self.request.GET.get('ano', hoje.year))
        lancamentos = Lancamento.objects.filter(
            data_competencia__month=mes, data_competencia__year=ano
        ).order_by('-data_competencia')
        ctx['lancamentos'] = lancamentos
        ctx['total_receitas'] = lancamentos.filter(tipo='receita').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['total_despesas'] = lancamentos.filter(tipo='despesa').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['saldo'] = ctx['total_receitas'] - ctx['total_despesas']
        ctx['mes'] = mes
        ctx['ano'] = ano
        return ctx


class RelatorioOrcamentosView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/orcamentos.html'

    def get_context_data(self, **kwargs):
        from orcamentos.models import Orcamento
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.now().date()
        mes = int(self.request.GET.get('mes', hoje.month))
        ano = int(self.request.GET.get('ano', hoje.year))
        orcamentos = Orcamento.objects.filter(
            data_criacao__month=mes, data_criacao__year=ano
        )
        ctx['total'] = orcamentos.count()
        ctx['aprovados'] = orcamentos.filter(status='aprovado').count()
        ctx['reprovados'] = orcamentos.filter(status='reprovado').count()
        ctx['pendentes'] = orcamentos.filter(status__in=['rascunho', 'enviado']).count()
        ctx['orcamentos'] = orcamentos.select_related('cliente').order_by('-data_criacao')
        ctx['mes'] = mes
        ctx['ano'] = ano
        return ctx


class RelatorioServicosView(LoginRequiredMixin, TemplateView):
    template_name = 'relatorios/servicos.html'

    def get_context_data(self, **kwargs):
        from ordens_servico.models import OrdemServico, ItemOSServico
        from clientes.models import Cliente
        ctx = super().get_context_data(**kwargs)
        ctx['servicos_mais_realizados'] = ItemOSServico.objects.values(
            'tipo_servico__nome'
        ).annotate(total=Count('id')).order_by('-total')[:10]
        ctx['clientes_frequentes'] = Cliente.objects.annotate(
            total_os=Count('ordens_servico')
        ).filter(total_os__gt=0).order_by('-total_os')[:10]
        return ctx
