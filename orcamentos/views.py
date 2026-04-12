from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.utils import timezone

from .models import Orcamento, TipoServico
from .forms import OrcamentoForm, ItemServicoFormSet, ItemPecaFormSet, TipoServicoForm
from core.mixins import RoleRequiredMixin


class OrcamentoListView(LoginRequiredMixin, ListView):
    model = Orcamento
    template_name = 'orcamentos/orcamento_list.html'
    context_object_name = 'orcamentos'
    paginate_by = 20

    def get_queryset(self):
        qs = Orcamento.objects.select_related('cliente', 'veiculo').order_by('-data_criacao')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(cliente__nome__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Orcamento.STATUS_CHOICES
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class OrcamentoDetailView(LoginRequiredMixin, DetailView):
    model = Orcamento
    template_name = 'orcamentos/orcamento_detail.html'
    context_object_name = 'orcamento'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['itens_servico'] = self.object.itens_servico.select_related('tipo_servico')
        ctx['itens_peca'] = self.object.itens_peca.select_related('produto')
        return ctx


class OrcamentoCreateView(LoginRequiredMixin, CreateView):
    model = Orcamento
    form_class = OrcamentoForm
    template_name = 'orcamentos/orcamento_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset_servico'] = ItemServicoFormSet(self.request.POST, prefix='servico')
            ctx['formset_peca'] = ItemPecaFormSet(self.request.POST, prefix='peca')
        else:
            ctx['formset_servico'] = ItemServicoFormSet(prefix='servico')
            ctx['formset_peca'] = ItemPecaFormSet(prefix='peca')
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        fs_servico = ctx['formset_servico']
        fs_peca = ctx['formset_peca']
        if fs_servico.is_valid() and fs_peca.is_valid():
            form.instance.criado_por = self.request.user
            self.object = form.save()
            fs_servico.instance = self.object
            fs_servico.save()
            fs_peca.instance = self.object
            fs_peca.save()
            self.object.recalcular_totais()
            messages.success(self.request, f'Orçamento {self.object} criado com sucesso!')
            return redirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('orcamentos:detail', kwargs={'pk': self.object.pk})


class OrcamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = Orcamento
    form_class = OrcamentoForm
    template_name = 'orcamentos/orcamento_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset_servico'] = ItemServicoFormSet(self.request.POST, instance=self.object, prefix='servico')
            ctx['formset_peca'] = ItemPecaFormSet(self.request.POST, instance=self.object, prefix='peca')
        else:
            ctx['formset_servico'] = ItemServicoFormSet(instance=self.object, prefix='servico')
            ctx['formset_peca'] = ItemPecaFormSet(instance=self.object, prefix='peca')
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        fs_servico = ctx['formset_servico']
        fs_peca = ctx['formset_peca']
        if fs_servico.is_valid() and fs_peca.is_valid():
            self.object = form.save()
            fs_servico.save()
            fs_peca.save()
            self.object.recalcular_totais()
            messages.success(self.request, 'Orçamento atualizado com sucesso!')
            return redirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('orcamentos:detail', kwargs={'pk': self.object.pk})


def orcamento_aprovar(request, pk):
    orc = get_object_or_404(Orcamento, pk=pk)
    orc.status = 'aprovado'
    orc.data_aprovacao = timezone.now()
    orc.save()
    messages.success(request, f'Orçamento {orc} aprovado!')
    return redirect('orcamentos:detail', pk=pk)


def orcamento_reprovar(request, pk):
    orc = get_object_or_404(Orcamento, pk=pk)
    orc.status = 'reprovado'
    orc.save()
    messages.warning(request, f'Orçamento {orc} reprovado.')
    return redirect('orcamentos:detail', pk=pk)


def orcamento_enviar(request, pk):
    orc = get_object_or_404(Orcamento, pk=pk)
    orc.status = 'enviado'
    orc.save()
    messages.info(request, f'Orçamento {orc} marcado como enviado ao cliente.')
    return redirect('orcamentos:detail', pk=pk)


def orcamento_gerar_os(request, pk):
    from ordens_servico.models import OrdemServico, ItemOSServico, ItemOSPeca
    orc = get_object_or_404(Orcamento, pk=pk, status='aprovado')
    if hasattr(orc, 'ordem_servico'):
        messages.warning(request, 'Já existe uma OS para este orçamento.')
        return redirect('ordens_servico:detail', pk=orc.ordem_servico.pk)
    os_obj = OrdemServico.objects.create(
        orcamento=orc,
        cliente=orc.cliente,
        veiculo=orc.veiculo,
        criado_por=request.user,
        km_entrada=orc.km_entrada,
        defeito_relatado='Gerado a partir do orçamento ' + str(orc),
        desconto_valor=orc.desconto_valor,
    )
    for item in orc.itens_servico.all():
        ItemOSServico.objects.create(
            ordem_servico=os_obj,
            tipo_servico=item.tipo_servico,
            descricao=item.descricao,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
        )
    for item in orc.itens_peca.all():
        ItemOSPeca.objects.create(
            ordem_servico=os_obj,
            produto=item.produto,
            descricao=item.descricao,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
        )
    os_obj.recalcular_totais()
    messages.success(request, f'Ordem de Serviço {os_obj} criada com sucesso!')
    return redirect('ordens_servico:detail', pk=os_obj.pk)


def orcamento_pdf(request, pk):
    from .pdf import gerar_pdf_orcamento
    orc = get_object_or_404(Orcamento, pk=pk)
    pdf_bytes = gerar_pdf_orcamento(orc)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="orcamento-{orc.numero}.pdf"'
    return response


class TipoServicoListView(LoginRequiredMixin, ListView):
    model = TipoServico
    template_name = 'orcamentos/tipo_servico_list.html'
    context_object_name = 'tipos'


class TipoServicoCreateView(LoginRequiredMixin, CreateView):
    model = TipoServico
    form_class = TipoServicoForm
    template_name = 'orcamentos/tipo_servico_form.html'
    success_url = reverse_lazy('orcamentos:tipo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de serviço cadastrado!')
        return super().form_valid(form)


class TipoServicoUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoServico
    form_class = TipoServicoForm
    template_name = 'orcamentos/tipo_servico_form.html'
    success_url = reverse_lazy('orcamentos:tipo_list')
