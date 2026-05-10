from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q, Count
from .models import Cliente
from .forms import ClienteForm
from core.utils import rate_limit_ajax


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        inativos = self.request.GET.get('inativos') == '1'
        qs = Cliente.objects.filter(ativo=not inativos).annotate(num_veiculos=Count('veiculos')).order_by('nome')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q) | Q(telefone__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['inativos'] = self.request.GET.get('inativos') == '1'
        # 2 counts → 1 query agregada
        totais = Cliente.objects.aggregate(
            ativos=Count('id', filter=Q(ativo=True)),
            inativos=Count('id', filter=Q(ativo=False)),
        )
        ctx['total'] = totais['ativos']
        ctx['total_inativos'] = totais['inativos']
        return ctx


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detail.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['veiculos'] = self.object.veiculos.filter(ativo=True)
        ctx['orcamentos'] = self.object.orcamentos.select_related('veiculo').order_by('-data_criacao')[:5]
        ctx['ordens'] = self.object.ordens_servico.select_related('veiculo', 'mecanico').order_by('-data_abertura')[:5]
        return ctx


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente cadastrado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('clientes:detail', kwargs={'pk': self.object.pk})


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('clientes:detail', kwargs={'pk': self.object.pk})


@login_required
def cliente_toggle_ativo(request, pk):
    if request.method != 'POST':
        return redirect(reverse('clientes:list'))

    cliente = get_object_or_404(Cliente, pk=pk)

    raw_next = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()}):
        next_url = raw_next
    else:
        next_url = reverse('clientes:list')

    if cliente.ativo:
        os_abertas = cliente.ordens_servico.filter(
            status__in=['aberta', 'em_andamento', 'aguardando']
        ).count()
        if os_abertas:
            messages.error(
                request,
                f'Não é possível desativar "{cliente.nome}": '
                f'há {os_abertas} ordem(ns) de serviço em aberto. '
                f'Finalize ou cancele-as primeiro.'
            )
            return redirect(next_url)
        cliente.ativo = False
        cliente.save()
        messages.warning(request, f'Cliente "{cliente.nome}" desativado com sucesso.')
    else:
        cliente.ativo = True
        cliente.save()
        messages.success(request, f'Cliente "{cliente.nome}" reativado com sucesso!')

    return redirect(next_url)


@login_required
@rate_limit_ajax(max_calls=60, window=60)
def cliente_search_ajax(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.filter(
        Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q), ativo=True
    )[:10]
    data = [{'id': c.id, 'text': f'{c.nome} — {c.cpf_cnpj}'} for c in clientes]
    return JsonResponse({'results': data})
