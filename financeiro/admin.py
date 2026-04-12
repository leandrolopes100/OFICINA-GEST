from django.contrib import admin
from .models import FormaPagamento, Lancamento


@admin.register(FormaPagamento)
class FormaPagamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'taxa', 'prazo_dias', 'ativo')


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'categoria', 'valor', 'data_competencia', 'status')
    list_filter = ('tipo', 'status', 'categoria')
    search_fields = ('descricao',)
