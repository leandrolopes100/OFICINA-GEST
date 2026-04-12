from django.contrib import admin
from .models import TipoServico, Orcamento, ItemOrcamentoServico, ItemOrcamentoPeca


@admin.register(TipoServico)
class TipoServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'preco_padrao', 'tempo_estimado', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome',)


class ItemServicoInline(admin.TabularInline):
    model = ItemOrcamentoServico
    extra = 0


class ItemPecaInline(admin.TabularInline):
    model = ItemOrcamentoPeca
    extra = 0


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente', 'veiculo', 'status', 'total', 'data_criacao', 'data_validade')
    list_filter = ('status',)
    search_fields = ('numero', 'cliente__nome')
    inlines = [ItemServicoInline, ItemPecaInline]
    readonly_fields = ('numero', 'data_criacao')
