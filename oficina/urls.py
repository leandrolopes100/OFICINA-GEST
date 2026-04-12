from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

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
    path('', RedirectView.as_view(url='/relatorios/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
