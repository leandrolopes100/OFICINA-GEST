from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Veiculo, Marca, Modelo
from .forms import VeiculoForm, MarcaForm, ModeloForm


class VeiculoListView(LoginRequiredMixin, ListView):
    model = Veiculo
    template_name = 'veiculos/veiculo_list.html'
    context_object_name = 'veiculos'
    paginate_by = 20

    def get_queryset(self):
        qs = Veiculo.objects.select_related('cliente', 'marca', 'modelo').filter(ativo=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(placa__icontains=q) | Q(cliente__nome__icontains=q) |
                Q(marca__nome__icontains=q) | Q(modelo__nome__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class VeiculoDetailView(LoginRequiredMixin, DetailView):
    model = Veiculo
    template_name = 'veiculos/veiculo_detail.html'
    context_object_name = 'veiculo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['orcamentos'] = self.object.orcamentos.order_by('-data_criacao')[:5]
        ctx['ordens'] = self.object.ordens_servico.order_by('-data_abertura')[:10]
        return ctx


class VeiculoCreateView(LoginRequiredMixin, CreateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/veiculo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente_id'] = self.request.GET.get('cliente')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Veículo cadastrado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('veiculos:detail', kwargs={'pk': self.object.pk})


class VeiculoUpdateView(LoginRequiredMixin, UpdateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/veiculo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente_id'] = None
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Veículo atualizado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('veiculos:detail', kwargs={'pk': self.object.pk})


class VeiculoDeleteView(LoginRequiredMixin, UpdateView):
    model = Veiculo
    fields = []
    template_name = 'veiculos/veiculo_confirm_delete.html'
    success_url = reverse_lazy('veiculos:list')

    def form_valid(self, form):
        self.object.ativo = False
        self.object.save()
        messages.success(self.request, 'Veículo desativado!')
        return super(UpdateView, self).form_valid(form)


class MarcaListView(LoginRequiredMixin, ListView):
    model = Marca
    template_name = 'veiculos/marca_list.html'
    context_object_name = 'marcas'


class MarcaCreateView(LoginRequiredMixin, CreateView):
    model = Marca
    form_class = MarcaForm
    template_name = 'veiculos/marca_form.html'
    success_url = reverse_lazy('veiculos:marca_list')

    def form_valid(self, form):
        messages.success(self.request, 'Marca cadastrada!')
        return super().form_valid(form)


def veiculos_por_cliente_ajax(request, cliente_pk):
    veiculos = Veiculo.objects.filter(cliente_id=cliente_pk, ativo=True)
    data = [{'id': v.id, 'text': str(v)} for v in veiculos]
    return JsonResponse({'results': data})


def modelos_por_marca_ajax(request, marca_pk):
    modelos = Modelo.objects.filter(marca_id=marca_pk).order_by('nome')
    data = [{'id': m.id, 'text': m.nome} for m in modelos]
    return JsonResponse({'results': data})
