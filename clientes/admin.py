from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj', 'telefone', 'cidade', 'ativo', 'criado_em')
    list_filter = ('tipo_pessoa', 'ativo', 'estado')
    search_fields = ('nome', 'cpf_cnpj', 'telefone', 'email')
    list_editable = ('ativo',)
