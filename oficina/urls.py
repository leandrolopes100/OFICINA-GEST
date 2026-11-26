from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

handler400 = 'core.views_erro.requisicao_invalida'
handler403 = 'core.views_erro.sem_permissao'
handler404 = 'core.views_erro.nao_encontrada'
handler500 = 'core.views_erro.erro_interno'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('clientes/', include('clientes.urls')),
    path('veiculos/', include('veiculos.urls')),
    path('orcamentos/', include('orcamentos.urls')),
    path('ordens-servico/', include('ordens_servico.urls')),
    path('estoque/', include('estoque.urls')),
    path('financeiro/', include('financeiro.urls')),
    path('relatorios/', include('relatorios.urls')),
    path('o/', include('orcamentos.urls_publicas')),
    path('a/', include('ordens_servico.urls_publicas')),
    path('', RedirectView.as_view(url='/relatorios/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
