from django.contrib import admin
from .models import OrdemServico, ItemOSServico, ItemOSPeca


class ItensTravadosAposConclusaoMixin:
    extra = 0

    def _editavel(self, obj):
        return obj is None or obj.pode_editar

    def has_add_permission(self, request, obj=None):
        return self._editavel(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editavel(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editavel(obj) and super().has_delete_permission(request, obj)


class ItemServicoInline(ItensTravadosAposConclusaoMixin, admin.TabularInline):
    model = ItemOSServico


class ItemPecaInline(ItensTravadosAposConclusaoMixin, admin.TabularInline):
    model = ItemOSPeca
    readonly_fields = ('custo_unitario', 'custo_estimado')


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente', 'veiculo', 'mecanico', 'status', 'total', 'data_abertura')
    list_filter = ('status',)
    search_fields = ('numero', 'cliente__nome', 'veiculo__placa')
    inlines = [ItemServicoInline, ItemPecaInline]
    readonly_fields = (
        'numero', 'data_abertura', 'status', 'data_conclusao', 'data_entrega', 'data_cancelamento',
        'subtotal_servicos', 'subtotal_pecas', 'total',
    )
