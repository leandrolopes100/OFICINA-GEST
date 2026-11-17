from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models.deletion import ProtectedError
from django.db.models import Q, Sum, F
from django.shortcuts import get_object_or_404, render, redirect

from .models import Produto, Fornecedor, Categoria, MovimentacaoEstoque
from .forms import ProdutoForm, FornecedorForm, MovimentacaoForm
from core.mixins import RoleRequiredMixin
from core.utils import rate_limit_ajax


class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'estoque/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 25

    def get_queryset(self):
        status = self.request.GET.get('status', 'ativos')
        base   = Produto.objects.select_related('categoria', 'fornecedor')

        if status == 'inativos':
            qs = base.filter(ativo=False)
        else:
            qs = base.filter(ativo=True)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q))

        cat = self.request.GET.get('categoria')
        if cat:
            qs = qs.filter(categoria_id=cat)

        # Filtro de alerta só faz sentido para produtos ativos
        if self.request.GET.get('alerta') and status != 'inativos':
            qs = qs.filter(estoque_atual__lte=F('estoque_minimo'))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias']       = Categoria.objects.all()
        ctx['q']                = self.request.GET.get('q', '')
        ctx['status_filtro']    = self.request.GET.get('status', 'ativos')
        ctx['categoria_filtro'] = self.request.GET.get('categoria', '')
        ctx['alerta_filtro']    = self.request.GET.get('alerta', '')
        ctx['total_inativos']   = Produto.objects.filter(ativo=False).count()
        ctx['alertas']          = Produto.objects.filter(
            estoque_atual__lte=F('estoque_minimo'), ativo=True
        ).count()
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
        self.object = form.save()
        qtd = form.cleaned_data.get('quantidade_inicial')
        if qtd and qtd > 0:
            MovimentacaoEstoque.objects.create(
                produto=self.object,
                tipo='entrada',
                quantidade=qtd,
                custo_unitario=self.object.preco_custo,
                observacao='Estoque inicial',
                usuario=self.request.user,
            )
            messages.success(
                self.request,
                f'Produto cadastrado! Estoque inicial de {qtd:g} unidade(s) registrado.'
            )
        else:
            messages.success(self.request, 'Produto cadastrado com sucesso!')
        return HttpResponseRedirect(self.get_success_url())

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


def _produto_tem_historico(produto):
    """Retorna True se o produto tem registros vinculados que impedem exclusão."""
    return (
        produto.movimentacoes.exists() or
        produto.itemospeca_set.exists() or
        produto.itemorcamentopeca_set.exists()
    )


class ProdutoDeleteView(LoginRequiredMixin, View):
    """
    GET  → exibe confirmação adequada (excluir ou inativar).
    POST → executa a ação escolhida ('excluir' ou 'inativar').
    """

    def _get_produto(self, pk):
        return get_object_or_404(Produto, pk=pk)

    def get(self, request, pk):
        produto      = self._get_produto(pk)
        tem_historico = _produto_tem_historico(produto)
        return render(request, 'estoque/produto_confirm_delete.html', {
            'produto':         produto,
            'tem_historico':   tem_historico,
            'n_movimentacoes': produto.movimentacoes.count(),
            'n_os':            produto.itemospeca_set.count(),
            'n_orcamentos':    produto.itemorcamentopeca_set.count(),
        })

    def post(self, request, pk):
        produto = self._get_produto(pk)
        acao    = request.POST.get('acao')

        # Re-verifica no servidor — nunca confia apenas no front-end
        tem_historico = _produto_tem_historico(produto)

        if acao == 'excluir':
            if tem_historico:
                messages.error(
                    request,
                    'Exclusão bloqueada: o produto possui registros vinculados. '
                    'Use a opção Inativar.'
                )
                return redirect('estoque:delete', pk=pk)
            try:
                nome = produto.nome
                produto.delete()
                messages.success(request, f'Produto "{nome}" excluído permanentemente.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não foi possível excluir: existem registros vinculados a este produto.'
                )
            return redirect('estoque:list')

        elif acao == 'inativar':
            produto.ativo = False
            produto.save(update_fields=['ativo'])
            messages.success(
                request,
                f'Produto "{produto.nome}" inativado. '
                'Ele não aparecerá em novas OS ou orçamentos.'
            )
            return redirect('estoque:list')

        messages.error(request, 'Ação inválida.')
        return redirect('estoque:list')


class ProdutoReativarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        produto = get_object_or_404(Produto, pk=pk, ativo=False)
        produto.ativo = True
        produto.save(update_fields=['ativo'])
        messages.success(request, f'Produto "{produto.nome}" reativado com sucesso!')
        return redirect(f"{reverse_lazy('estoque:list')}?status=ativos")


class MovimentacaoListView(LoginRequiredMixin, ListView):
    model = MovimentacaoEstoque
    template_name = 'estoque/movimentacao_list.html'
    context_object_name = 'movimentacoes'
    paginate_by = 20

    def get_queryset(self):
        return MovimentacaoEstoque.objects.select_related('produto', 'usuario').order_by('-data')


class MovimentacaoCreateView(LoginRequiredMixin, CreateView):
    model = MovimentacaoEstoque
    form_class = MovimentacaoForm
    template_name = 'estoque/movimentacao_form.html'
    success_url = reverse_lazy('estoque:movimentacao_list')

    def _produto_da_querystring(self):
        pk = self.request.GET.get('produto')
        if pk:
            try:
                return Produto.objects.get(pk=pk, ativo=True)
            except Produto.DoesNotExist:
                pass
        return None

    def get_initial(self):
        initial = super().get_initial()
        produto = self._produto_da_querystring()
        if produto:
            deficit = max(produto.estoque_minimo - produto.estoque_atual, 0)
            initial.update({
                'produto':       produto.pk,
                'tipo':          'entrada',
                'quantidade':    deficit if deficit > 0 else None,
                'custo_unitario': produto.preco_custo,
                'observacao':    f'Reposição de estoque — {produto.nome}',
            })
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['produto_reposicao'] = self._produto_da_querystring()
        return ctx

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'Movimentação registrada com sucesso!')
            if getattr(self.object, 'preco_venda_nao_recalculado', False):
                messages.warning(
                    self.request,
                    f'O preço de venda de "{self.object.produto.nome}" não foi recalculado: '
                    'com o novo custo e a margem cadastrada, ele passaria do limite do sistema. '
                    'Revise a margem no cadastro do produto.',
                )
            return response
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)


class FornecedorListView(LoginRequiredMixin, ListView):
    model = Fornecedor
    template_name = 'estoque/fornecedor_list.html'
    context_object_name = 'fornecedores'
    paginate_by = 20

    def get_queryset(self):
        status = self.request.GET.get('status', 'ativos')
        qs = Fornecedor.objects.filter(ativo=(status != 'inativos'))
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cnpj__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q']              = self.request.GET.get('q', '')
        ctx['status_filtro']  = self.request.GET.get('status', 'ativos')
        ctx['total_inativos'] = Fornecedor.objects.filter(ativo=False).count()
        return ctx


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


class FornecedorDeleteView(LoginRequiredMixin, View):
    def _get_fornecedor(self, pk):
        return get_object_or_404(Fornecedor, pk=pk)

    def get(self, request, pk):
        fornecedor  = self._get_fornecedor(pk)
        n_produtos  = fornecedor.produtos.count()
        return render(request, 'estoque/fornecedor_confirm_delete.html', {
            'fornecedor': fornecedor,
            'n_produtos': n_produtos,
        })

    def post(self, request, pk):
        fornecedor = self._get_fornecedor(pk)
        acao       = request.POST.get('acao')

        if acao == 'excluir':
            nome = fornecedor.nome
            # SET_NULL: a exclusão sempre funciona — produtos ficam sem fornecedor
            fornecedor.delete()
            messages.success(request, f'Fornecedor "{nome}" excluído permanentemente.')
            return redirect('estoque:fornecedor_list')

        elif acao == 'inativar':
            fornecedor.ativo = False
            fornecedor.save(update_fields=['ativo'])
            messages.success(
                request,
                f'Fornecedor "{fornecedor.nome}" inativado. '
                'Ele não aparecerá em novos cadastros de produto.'
            )
            return redirect('estoque:fornecedor_list')

        messages.error(request, 'Ação inválida.')
        return redirect('estoque:fornecedor_list')


class FornecedorReativarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        fornecedor = get_object_or_404(Fornecedor, pk=pk, ativo=False)
        fornecedor.ativo = True
        fornecedor.save(update_fields=['ativo'])
        messages.success(request, f'Fornecedor "{fornecedor.nome}" reativado com sucesso!')
        return redirect(f"{reverse_lazy('estoque:fornecedor_list')}?status=ativos")


class EstoqueAlertasView(LoginRequiredMixin, TemplateView):
    template_name = 'estoque/alertas.html'

    def get_context_data(self, **kwargs):
        from django.db.models import ExpressionWrapper, DecimalField
        ctx = super().get_context_data(**kwargs)
        ctx['produtos'] = Produto.objects.filter(
            estoque_atual__lte=F('estoque_minimo'), ativo=True
        ).select_related('fornecedor', 'categoria').annotate(
            deficit=ExpressionWrapper(
                F('estoque_minimo') - F('estoque_atual'),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
        )
        return ctx


@login_required
@rate_limit_ajax(max_calls=60, window=60)
def produto_info_ajax(request, pk):
    """Retorna dados do produto para o painel dinâmico do formulário de movimentação."""
    try:
        p = Produto.objects.get(pk=pk, ativo=True)
        dados = {
            'id':             p.pk,
            'nome':           p.nome,
            'estoque_atual':  float(p.estoque_atual),
            'estoque_minimo': float(p.estoque_minimo),
            'unidade':        p.get_unidade_display(),
            'abaixo_minimo':  p.abaixo_minimo,
        }
        # preco_custo é dado financeiro sensível — apenas admin e recepcionista
        if getattr(request.user, 'role', '') in ('admin', 'recepcionista'):
            dados['preco_custo'] = float(p.preco_custo)
        return JsonResponse(dados)
    except Produto.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)


@login_required
@rate_limit_ajax(max_calls=60, window=60)
def produto_search_ajax(request):
    q = request.GET.get('q', '')
    produtos = Produto.objects.filter(
        Q(nome__icontains=q) | Q(codigo__icontains=q), ativo=True
    )[:15]
    data = [{'id': p.id, 'text': str(p), 'preco': float(p.preco_venda)} for p in produtos]
    return JsonResponse({'results': data})
