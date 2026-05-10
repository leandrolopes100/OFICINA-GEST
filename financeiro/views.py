from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.db.models import Q, Sum
from decimal import Decimal
import json

from .models import Lancamento, FormaPagamento
from .forms import LancamentoForm, FormaPagamentoForm
from core.mixins import RoleRequiredMixin
from core.utils import parse_mes_ano, calcular_taxa


class LancamentoListView(RoleRequiredMixin, ListView):
    model = Lancamento
    template_name = 'financeiro/lancamento_list.html'
    context_object_name = 'lancamentos'
    paginate_by = 25
    allowed_roles = ['admin', 'recepcionista']

    def get_queryset(self):
        qs = Lancamento.objects.select_related('forma_pagamento', 'ordem_servico').order_by('-data_competencia')
        tipo   = self.request.GET.get('tipo')
        status = self.request.GET.get('status')
        q      = self.request.GET.get('q')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(descricao__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Usa object_list (já paginado pelo Django) como base para os totais,
        # evitando chamar get_queryset() uma segunda vez.
        qs = self.object_list
        ctx['total_receitas'] = qs.filter(tipo='receita', status='pago').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['total_despesas'] = qs.filter(tipo='despesa', status='pago').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['saldo'] = ctx['total_receitas'] - ctx['total_despesas']
        return ctx


def _formas_data_json():
    """Retorna JSON com taxa e prazo de todas as formas ativas."""
    return json.dumps({
        str(fp.id): {'taxa': float(fp.taxa), 'prazo_dias': fp.prazo_dias}
        for fp in FormaPagamento.objects.filter(ativo=True).only('id', 'taxa', 'prazo_dias')
    })


class LancamentoCreateView(RoleRequiredMixin, CreateView):
    model = Lancamento
    form_class = LancamentoForm
    template_name = 'financeiro/lancamento_form.html'
    success_url = reverse_lazy('financeiro:list')
    allowed_roles = ['admin', 'recepcionista']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['formas_data'] = _formas_data_json()
        return ctx

    def form_valid(self, form):
        lancamento = form.save(commit=False)
        lancamento.valor_taxa = calcular_taxa(lancamento.valor, lancamento.forma_pagamento)
        self.object = lancamento
        lancamento.save()
        messages.success(self.request, 'Lançamento criado com sucesso!')
        return redirect(self.get_success_url())


class LancamentoUpdateView(RoleRequiredMixin, UpdateView):
    model = Lancamento
    form_class = LancamentoForm
    template_name = 'financeiro/lancamento_form.html'
    success_url = reverse_lazy('financeiro:list')
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['formas_data'] = _formas_data_json()
        return ctx

    def form_valid(self, form):
        lancamento = form.save(commit=False)
        lancamento.valor_taxa = calcular_taxa(lancamento.valor, lancamento.forma_pagamento)
        self.object = lancamento
        lancamento.save()
        messages.success(self.request, 'Lançamento atualizado!')
        return redirect(self.get_success_url())


class LancamentoPagarView(RoleRequiredMixin, View):
    allowed_roles = ['admin', 'recepcionista']

    def post(self, request, pk):
        lancamento = get_object_or_404(Lancamento, pk=pk)

        # Bloqueia marcação como pago para lançamentos em estado terminal
        if lancamento.status == 'cancelado':
            messages.error(request, 'Não é possível marcar como pago um lançamento cancelado.')
            return redirect(reverse('financeiro:list'))

        if lancamento.status == 'pago':
            messages.info(request, 'Este lançamento já está marcado como pago.')
            return redirect(reverse('financeiro:list'))

        lancamento.status         = 'pago'
        lancamento.data_pagamento = timezone.now().date()
        lancamento.save()
        messages.success(request, 'Lançamento marcado como pago!')
        return redirect(reverse('financeiro:list'))


class LancamentoDeleteView(RoleRequiredMixin, View):
    allowed_roles = ['admin']

    def get(self, request, pk):
        lancamento = get_object_or_404(Lancamento, pk=pk)
        return render(request, 'financeiro/lancamento_confirm_delete.html', {
            'lancamento': lancamento,
        })

    def post(self, request, pk):
        lancamento = get_object_or_404(Lancamento, pk=pk)
        descricao  = lancamento.descricao
        lancamento.delete()
        messages.success(request, f'Lançamento "{descricao}" excluído com sucesso.')
        return redirect(reverse('financeiro:list'))


class FluxoCaixaView(RoleRequiredMixin, TemplateView):
    template_name = 'financeiro/fluxo_caixa.html'
    allowed_roles = ['admin', 'recepcionista']

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        # [C-01] Validação de parâmetros GET — evita ValueError e erro 500
        mes, ano = parse_mes_ano(self.request, hoje)

        lancamentos = Lancamento.objects.filter(
            data_competencia__month=mes, data_competencia__year=ano
        ).order_by('data_competencia')

        # [C-02] Exclui lançamentos cancelados do cálculo do saldo
        status_validos = ['pendente', 'pago', 'vencido']
        receitas = lancamentos.filter(tipo='receita', status__in=status_validos).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        despesas = lancamentos.filter(tipo='despesa', status__in=status_validos).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        ctx.update({
            'lancamentos': lancamentos,
            'receitas':    receitas,
            'despesas':    despesas,
            'saldo':       receitas - despesas,
            'mes':         mes,
            'ano':         ano,
        })
        return ctx


class FormaPagamentoListView(RoleRequiredMixin, ListView):
    model = FormaPagamento
    template_name = 'financeiro/forma_pagamento_list.html'
    context_object_name = 'formas'
    allowed_roles = ['admin']
    paginate_by = 20


class FormaPagamentoCreateView(RoleRequiredMixin, CreateView):
    model = FormaPagamento
    form_class = FormaPagamentoForm
    template_name = 'financeiro/forma_pagamento_form.html'
    success_url = reverse_lazy('financeiro:formas_list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Forma de pagamento criada!')
        return super().form_valid(form)


class FormaPagamentoUpdateView(RoleRequiredMixin, UpdateView):
    model = FormaPagamento
    form_class = FormaPagamentoForm
    template_name = 'financeiro/forma_pagamento_form.html'
    success_url = reverse_lazy('financeiro:formas_list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Forma de pagamento atualizada com sucesso!')
        return super().form_valid(form)


class FormaPagamentoDeleteView(RoleRequiredMixin, View):
    allowed_roles = ['admin']

    def _contadores(self, forma):
        """Retorna (n_ativos, n_pagos, n_cancelados) para a forma dada."""
        qs = Lancamento.objects.filter(forma_pagamento=forma)
        return (
            qs.filter(status__in=['pendente', 'vencido']).count(),
            qs.filter(status='pago').count(),
            qs.filter(status='cancelado').count(),
        )

    def get(self, request, pk):
        forma = get_object_or_404(FormaPagamento, pk=pk)
        n_ativos, n_pagos, n_cancelados = self._contadores(forma)
        return render(request, 'financeiro/forma_pagamento_confirm_delete.html', {
            'forma':        forma,
            'n_ativos':     n_ativos,
            'n_pagos':      n_pagos,
            'n_cancelados': n_cancelados,
            'n_total':      n_ativos + n_pagos + n_cancelados,
        })

    def post(self, request, pk):
        forma = get_object_or_404(FormaPagamento, pk=pk)
        acao  = request.POST.get('acao', '')

        if acao == 'inativar':
            if forma.ativo:
                forma.ativo = False
                forma.save(update_fields=['ativo'])
                messages.success(
                    request,
                    f'Forma de pagamento "{forma.nome}" inativada. '
                    'Ela não aparecerá em novos lançamentos.'
                )
            else:
                messages.info(request, f'"{forma.nome}" já estava inativa.')
            return redirect(reverse('financeiro:formas_list'))

        if acao == 'excluir':
            n_ativos, n_pagos, n_cancelados = self._contadores(forma)

            # Bloqueia no servidor independente do que o template mostrou
            if n_ativos:
                messages.error(
                    request,
                    f'Não é possível excluir "{forma.nome}": '
                    f'há {n_ativos} lançamento(s) pendente(s) ou vencido(s). '
                    f'Quite ou cancele-os antes de excluir.'
                )
                return redirect(
                    reverse('financeiro:formas_delete', kwargs={'pk': pk})
                )

            nome = forma.nome
            forma.delete()
            messages.success(
                request, f'Forma de pagamento "{nome}" excluída permanentemente.'
            )
            return redirect(reverse('financeiro:formas_list'))

        messages.error(request, 'Ação inválida.')
        return redirect(reverse('financeiro:formas_list'))
