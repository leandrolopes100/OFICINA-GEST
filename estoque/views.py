from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, F
from django.shortcuts import render

from .models import Produto, Fornecedor, Categoria, MovimentacaoEstoque
from .forms import ProdutoForm, FornecedorForm, MovimentacaoForm
from core.mixins import RoleRequiredMixin


class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'estoque/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 25

    def get_queryset(self):
        qs = Produto.objects.select_related('categoria', 'fornecedor').filter(ativo=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q))
        cat = self.request.GET.get('categoria')
        if cat:
            qs = qs.filter(categoria_id=cat)
        if self.request.GET.get('alerta'):
            qs = qs.filter(estoque_atual__lte=F('estoque_minimo'))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias'] = Categoria.objects.all()
        ctx['q'] = self.request.GET.get('q', '')
        ctx['alertas'] = Produto.objects.filter(estoque_atual__lte=F('estoque_minimo'), ativo=True).count()
        return ctx


class ProdutoDetailView(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'estoque/produto_detail.html'
    context_object_name = 'produto'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['movimentacoes'] = self.object.movimentacoes.order_by('-data')[:20]
        return ctx


class ProdutoCreateView(LoginRequiredMixin, CreateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'estoque/produto_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Produto cadastrado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('estoque:detail', kwargs={'pk': self.object.pk})


class ProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'estoque/produto_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Produto atualizado!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('estoque:detail', kwargs={'pk': self.object.pk})


class MovimentacaoListView(LoginRequiredMixin, ListView):
    model = MovimentacaoEstoque
    template_name = 'estoque/movimentacao_list.html'
    context_object_name = 'movimentacoes'
    paginate_by = 30

    def get_queryset(self):
        return MovimentacaoEstoque.objects.select_related('produto', 'usuario').order_by('-data')


class MovimentacaoCreateView(LoginRequiredMixin, CreateView):
    model = MovimentacaoEstoque
    form_class = MovimentacaoForm
    template_name = 'estoque/movimentacao_form.html'
    success_url = reverse_lazy('estoque:movimentacao_list')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        messages.success(self.request, 'Movimentação registrada com sucesso!')
        return super().form_valid(form)


class FornecedorListView(LoginRequiredMixin, ListView):
    model = Fornecedor
    template_name = 'estoque/fornecedor_list.html'
    context_object_name = 'fornecedores'
    paginate_by = 20

    def get_queryset(self):
        qs = Fornecedor.objects.filter(ativo=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cnpj__icontains=q))
        return qs


class FornecedorCreateView(LoginRequiredMixin, CreateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = 'estoque/fornecedor_form.html'
    success_url = reverse_lazy('estoque:fornecedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor cadastrado!')
        return super().form_valid(form)


class FornecedorUpdateView(LoginRequiredMixin, UpdateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = 'estoque/fornecedor_form.html'
    success_url = reverse_lazy('estoque:fornecedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor atualizado!')
        return super().form_valid(form)


def estoque_alertas(request):
    produtos = Produto.objects.filter(
        estoque_atual__lte=F('estoque_minimo'), ativo=True
    ).select_related('fornecedor', 'categoria')
    return render(request, 'estoque/alertas.html', {'produtos': produtos})


def produto_search_ajax(request):
    q = request.GET.get('q', '')
    produtos = Produto.objects.filter(
        Q(nome__icontains=q) | Q(codigo__icontains=q), ativo=True
    )[:15]
    data = [{'id': p.id, 'text': str(p), 'preco': float(p.preco_venda)} for p in produtos]
    return JsonResponse({'results': data})
