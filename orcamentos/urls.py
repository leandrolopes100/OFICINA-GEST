from django.urls import path
from . import views

app_name = 'orcamentos'

urlpatterns = [
    path('',                        views.OrcamentoListView.as_view(),    name='list'),
    path('novo/',                   views.OrcamentoCreateView.as_view(),  name='create'),
    path('<int:pk>/',               views.OrcamentoDetailView.as_view(),  name='detail'),
    path('<int:pk>/editar/',        views.OrcamentoUpdateView.as_view(),  name='update'),
    path('<int:pk>/aprovar/',       views.OrcamentoAprovarView.as_view(), name='aprovar'),
    path('<int:pk>/reprovar/',      views.OrcamentoReprovarView.as_view(),name='reprovar'),
    path('<int:pk>/enviar/',        views.OrcamentoEnviarView.as_view(),  name='enviar'),
    path('<int:pk>/enviar-whatsapp/', views.OrcamentoEnviarWhatsAppView.as_view(), name='enviar_whatsapp'),
    path('<int:pk>/novo-link/',     views.OrcamentoNovoLinkView.as_view(), name='novo_link'),
    path('<int:pk>/gerar-os/',      views.OrcamentoGerarOSView.as_view(), name='gerar_os'),
    path('<int:pk>/excluir/',       views.OrcamentoDeleteView.as_view(),  name='delete'),
    path('<int:pk>/pdf/',      views.OrcamentoPdfView.as_view(),   name='pdf'),
    path('<int:pk>/imprimir/', views.OrcamentoPrintView.as_view(), name='imprimir'),
    path('tipos/',                  views.TipoServicoListView.as_view(),  name='tipo_list'),
    path('tipos/novo/',             views.TipoServicoCreateView.as_view(),name='tipo_create'),
    path('tipos/<int:pk>/editar/',  views.TipoServicoUpdateView.as_view(),name='tipo_update'),
]
