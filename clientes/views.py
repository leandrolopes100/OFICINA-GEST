from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Cliente
from .forms import ClienteForm


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Cliente.objects.filter(ativo=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q) | Q(telefone__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['total'] = Cliente.objects.filter(ativo=True).count()
        return ctx


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detail.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['veiculos'] = self.object.veiculos.filter(ativo=True)
        ctx['orcamentos'] = self.object.orcamentos.order_by('-data_criacao')[:5]
        ctx['ordens'] = self.object.ordens_servico.order_by('-data_abertura')[:5]
        return ctx


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:list')

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


class ClienteDeleteView(LoginRequiredMixin, UpdateView):
    model = Cliente
    fields = []
    template_name = 'clientes/cliente_confirm_delete.html'
    success_url = reverse_lazy('clientes:list')

    def form_valid(self, form):
        self.object.ativo = False
        self.object.save()
        messages.success(self.request, 'Cliente desativado com sucesso!')
        return super(UpdateView, self).form_valid(form)


def cliente_search_ajax(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.filter(
        Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q), ativo=True
    )[:10]
    data = [{'id': c.id, 'text': f'{c.nome} — {c.cpf_cnpj}'} for c in clientes]
    return JsonResponse({'results': data})
