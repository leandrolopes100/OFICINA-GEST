from django.contrib import admin
from .models import Categoria, Fornecedor, Produto, MovimentacaoEstoque


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome',)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'telefone', 'email', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cnpj')


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'unidade', 'preco_venda', 'estoque_atual', 'estoque_minimo', 'ativo')
    list_filter = ('categoria', 'fornecedor', 'ativo', 'unidade')
    search_fields = ('codigo', 'nome')


@admin.register(MovimentacaoEstoque)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'custo_unitario', 'usuario', 'data')
    list_filter = ('tipo',)
    readonly_fields = ('data',)
