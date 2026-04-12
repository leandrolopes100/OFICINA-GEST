from django.urls import path
from . import views

app_name = 'orcamentos'

urlpatterns = [
    path('', views.OrcamentoListView.as_view(), name='list'),
    path('novo/', views.OrcamentoCreateView.as_view(), name='create'),
    path('<int:pk>/', views.OrcamentoDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.OrcamentoUpdateView.as_view(), name='update'),
    path('<int:pk>/aprovar/', views.orcamento_aprovar, name='aprovar'),
    path('<int:pk>/reprovar/', views.orcamento_reprovar, name='reprovar'),
    path('<int:pk>/enviar/', views.orcamento_enviar, name='enviar'),
    path('<int:pk>/gerar-os/', views.orcamento_gerar_os, name='gerar_os'),
    path('<int:pk>/pdf/', views.orcamento_pdf, name='pdf'),
    path('tipos/', views.TipoServicoListView.as_view(), name='tipo_list'),
    path('tipos/novo/', views.TipoServicoCreateView.as_view(), name='tipo_create'),
    path('tipos/<int:pk>/editar/', views.TipoServicoUpdateView.as_view(), name='tipo_update'),
]
