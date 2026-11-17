"""
ordens_servico/urls.py
"""
from django.urls import path
from . import views

app_name = 'ordens_servico'

urlpatterns = [
    path('',                   views.OrdemServicoListView.as_view(),   name='os_lista'),
    path('nova/',              views.OrdemServicoCreateView.as_view(), name='os_criar'),
    path('<int:pk>/',          views.OrdemServicoDetailView.as_view(), name='os_detalhe'),
    path('<int:pk>/editar/',   views.OrdemServicoUpdateView.as_view(), name='os_editar'),
    path('<int:pk>/status/',   views.AtualizarStatusView.as_view(),    name='os_status'),
    path('<int:pk>/entregar/', views.EntregarOSView.as_view(),         name='os_entregar'),
    path('<int:pk>/cancelar/', views.CancelarOSView.as_view(),         name='os_cancelar'),
    path('<int:pk>/pagar/',            views.RegistrarPagamentoView.as_view(), name='os_pagar'),
    path('<int:pk>/whatsapp/<str:tipo>/', views.OSEnviarWhatsAppView.as_view(), name='os_enviar_whatsapp'),
    path('<int:pk>/novo-link/',        views.OSNovoLinkView.as_view(),       name='os_novo_link'),
    path('<int:pk>/pdf/',      views.OSPdfView.as_view(),   name='os_pdf'),
    path('<int:pk>/imprimir/', views.OSPrintView.as_view(), name='os_imprimir'),
    path('<int:pk>/adicionar-servico/', views.AdicionarServicoView.as_view(), name='os_add_servico'),
    path('<int:pk>/adicionar-peca/',    views.AdicionarPecaView.as_view(),    name='os_add_peca'),
]
