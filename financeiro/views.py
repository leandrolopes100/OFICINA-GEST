from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Q, Sum
from decimal import Decimal

from .models import Lancamento, FormaPagamento
from .forms import LancamentoForm, FormaPagamentoForm
from core.mixins import RoleRequiredMixin


class LancamentoListView(RoleRequiredMixin, ListView):
    model = Lancamento
    template_name = 'financeiro/lancamento_list.html'
    context_object_name = 'lancamentos'
    paginate_by = 25
    allowed_roles = ['admin', 'recepcionista']

    def get_queryset(self):
        qs = Lancamento.objects.select_related('forma_pagamento', 'ordem_servico').order_by('-data_competencia')
        tipo = self.request.GET.get('tipo')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(descricao__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['total_receitas'] = qs.filter(tipo='receita', status='pago').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['total_despesas'] = qs.filter(tipo='despesa', status='pago').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx['saldo'] = ctx['total_receitas'] - ctx['total_despesas']
        return ctx


class LancamentoCreateView(RoleRequiredMixin, CreateView):
    model = Lancamento
    form_class = LancamentoForm
    template_name = 'financeiro/lancamento_form.html'
    success_url = reverse_lazy('financeiro:list')
    allowed_roles = ['admin', 'recepcionista']

    def form_valid(self, form):
        messages.success(self.request, 'Lançamento criado com sucesso!')
        return super().form_valid(form)


class LancamentoUpdateView(RoleRequiredMixin, UpdateView):
    model = Lancamento
    form_class = LancamentoForm
    template_name = 'financeiro/lancamento_form.html'
    success_url = reverse_lazy('financeiro:list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Lançamento atualizado!')
        return super().form_valid(form)


def lancamento_pagar(request, pk):
    lancamento = get_object_or_404(Lancamento, pk=pk)
    lancamento.status = 'pago'
    lancamento.data_pagamento = timezone.now().date()
    lancamento.save()
    messages.success(request, 'Lançamento marcado como pago!')
    return redirect('financeiro:list')


class FluxoCaixaView(RoleRequiredMixin, TemplateView):
    template_name = 'financeiro/fluxo_caixa.html'
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.now().date()
        mes = int(self.request.GET.get('mes', hoje.month))
        ano = int(self.request.GET.get('ano', hoje.year))
        lancamentos = Lancamento.objects.filter(
            data_competencia__month=mes, data_competencia__year=ano
        ).order_by('data_competencia')
        receitas = lancamentos.filter(tipo='receita').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        despesas = lancamentos.filter(tipo='despesa').aggregate(t=Sum('valor'))['t'] or Decimal('0')
        ctx.update({
            'lancamentos': lancamentos,
            'receitas': receitas,
            'despesas': despesas,
            'saldo': receitas - despesas,
            'mes': mes,
            'ano': ano,
        })
        return ctx


class FormaPagamentoListView(RoleRequiredMixin, ListView):
    model = FormaPagamento
    template_name = 'financeiro/forma_pagamento_list.html'
    context_object_name = 'formas'
    allowed_roles = ['admin']


class FormaPagamentoCreateView(RoleRequiredMixin, CreateView):
    model = FormaPagamento
    form_class = FormaPagamentoForm
    template_name = 'financeiro/forma_pagamento_form.html'
    success_url = reverse_lazy('financeiro:formas_list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Forma de pagamento criada!')
        return super().form_valid(form)
