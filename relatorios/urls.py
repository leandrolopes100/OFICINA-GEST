from django.urls import path
from . import views

app_name = 'relatorios'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('faturamento/', views.RelatorioFaturamentoView.as_view(), name='faturamento'),
    path('orcamentos/', views.RelatorioOrcamentosView.as_view(), name='orcamentos_rel'),
    path('servicos/', views.RelatorioServicosView.as_view(), name='servicos'),
    path('api/dashboard/', views.dashboard_data_api, name='dashboard_api'),
]
