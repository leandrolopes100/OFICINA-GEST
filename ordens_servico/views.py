from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone

from .models import OrdemServico, ItemOSServico, ItemOSPeca
from .forms import OrdemServicoForm, ItemOSServicoFormSet, ItemOSPecaFormSet
from core.mixins import RoleRequiredMixin


class OSListView(LoginRequiredMixin, ListView):
    model = OrdemServico
    template_name = 'ordens_servico/os_list.html'
    context_object_name = 'ordens'
    paginate_by = 20

    def get_queryset(self):
        qs = OrdemServico.objects.select_related('cliente', 'veiculo', 'mecanico').order_by('-data_abertura')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(cliente__nome__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = OrdemServico.STATUS_CHOICES
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class OSDetailView(LoginRequiredMixin, DetailView):
    model = OrdemServico
    template_name = 'ordens_servico/os_detail.html'
    context_object_name = 'os'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['itens_servico'] = self.object.itens_servico.select_related('tipo_servico')
        ctx['itens_peca'] = self.object.itens_peca.select_related('produto')
        return ctx


class OSCreateView(LoginRequiredMixin, CreateView):
    model = OrdemServico
    form_class = OrdemServicoForm
    template_name = 'ordens_servico/os_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset_servico'] = ItemOSServicoFormSet(self.request.POST, prefix='servico')
            ctx['formset_peca'] = ItemOSPecaFormSet(self.request.POST, prefix='peca')
        else:
            ctx['formset_servico'] = ItemOSServicoFormSet(prefix='servico')
            ctx['formset_peca'] = ItemOSPecaFormSet(prefix='peca')
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
            messages.success(self.request, f'Ordem de Serviço {self.object} criada!')
            return redirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('ordens_servico:detail', kwargs={'pk': self.object.pk})


class OSUpdateView(LoginRequiredMixin, UpdateView):
    model = OrdemServico
    form_class = OrdemServicoForm
    template_name = 'ordens_servico/os_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset_servico'] = ItemOSServicoFormSet(self.request.POST, instance=self.object, prefix='servico')
            ctx['formset_peca'] = ItemOSPecaFormSet(self.request.POST, instance=self.object, prefix='peca')
        else:
            ctx['formset_servico'] = ItemOSServicoFormSet(instance=self.object, prefix='servico')
            ctx['formset_peca'] = ItemOSPecaFormSet(instance=self.object, prefix='peca')
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
            messages.success(self.request, 'Ordem de Serviço atualizada!')
            return redirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('ordens_servico:detail', kwargs={'pk': self.object.pk})


def os_atualizar_status(request, pk, novo_status):
    os_obj = get_object_or_404(OrdemServico, pk=pk)
    os_obj.status = novo_status
    if novo_status == 'concluida':
        os_obj.data_conclusao = timezone.now()
    elif novo_status == 'entregue':
        os_obj.data_entrega = timezone.now()
        km_saida = request.POST.get('km_saida')
        if km_saida:
            os_obj.km_saida = km_saida
        # Atualiza KM do veículo
        if os_obj.km_saida:
            veiculo = os_obj.veiculo
            veiculo.km_atual = os_obj.km_saida
            veiculo.save(update_fields=['km_atual'])
        # Gerar lançamento financeiro
        from financeiro.models import Lancamento
        if not os_obj.lancamentos.filter(tipo='receita').exists():
            Lancamento.objects.create(
                tipo='receita',
                categoria='servico',
                ordem_servico=os_obj,
                descricao=f'Serviço OS-{os_obj.numero} — {os_obj.cliente}',
                valor=os_obj.total,
                data_competencia=timezone.now().date(),
                data_vencimento=timezone.now().date(),
                status='pendente',
            )
    os_obj.save()
    status_labels = {
        'em_andamento': 'Em andamento',
        'aguardando': 'Aguardando',
        'concluida': 'Concluída',
        'entregue': 'Entregue',
        'cancelada': 'Cancelada',
    }
    messages.success(request, f'OS atualizada para: {status_labels.get(novo_status, novo_status)}')
    return redirect('ordens_servico:detail', pk=pk)


def os_concluir(request, pk):
    return os_atualizar_status(request, pk, 'concluida')

def os_entregar(request, pk):
    return os_atualizar_status(request, pk, 'entregue')

def os_cancelar(request, pk):
    return os_atualizar_status(request, pk, 'cancelada')

def os_em_andamento(request, pk):
    return os_atualizar_status(request, pk, 'em_andamento')


def os_pdf(request, pk):
    from .pdf import gerar_pdf_os
    os_obj = get_object_or_404(OrdemServico, pk=pk)
    pdf_bytes = gerar_pdf_os(os_obj)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="os-{os_obj.numero}.pdf"'
    return response
