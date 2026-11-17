from django.contrib import admin
from .models import TipoServico, Orcamento, ItemOrcamentoServico, ItemOrcamentoPeca, RespostaCliente


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
    readonly_fields = ('numero', 'data_criacao', 'token_publico', 'link_gerado_em')


@admin.register(RespostaCliente)
class RespostaClienteAdmin(admin.ModelAdmin):
    list_display = ('orcamento', 'decisao', 'nome_informado', 'total_no_momento', 'respondido_em')
    list_filter = ('decisao',)
    search_fields = ('orcamento__numero', 'nome_informado')

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
