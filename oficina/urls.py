from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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
    path('', include('relatorios.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
