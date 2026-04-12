from django.contrib import admin
from .models import Marca, Modelo, Veiculo


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(Modelo)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ('marca', 'nome')
    list_filter = ('marca',)
    search_fields = ('nome',)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'cliente', 'modelo', 'ano_modelo', 'combustivel', 'km_atual', 'ativo')
    list_filter = ('combustivel', 'ativo', 'marca')
    search_fields = ('placa', 'cliente__nome', 'chassi', 'renavam')
