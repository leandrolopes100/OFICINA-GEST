from django.contrib import admin
from .models import OrdemServico, ItemOSServico, ItemOSPeca


class ItemServicoInline(admin.TabularInline):
    model = ItemOSServico
    extra = 0


class ItemPecaInline(admin.TabularInline):
    model = ItemOSPeca
    extra = 0


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente', 'veiculo', 'mecanico', 'status', 'total', 'data_abertura')
    list_filter = ('status',)
    search_fields = ('numero', 'cliente__nome', 'veiculo__placa')
    inlines = [ItemServicoInline, ItemPecaInline]
    readonly_fields = ('numero', 'data_abertura')
