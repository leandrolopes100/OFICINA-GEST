from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    path('', views.LancamentoListView.as_view(), name='list'),
    path('novo/', views.LancamentoCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.LancamentoUpdateView.as_view(), name='update'),
    path('<int:pk>/pagar/',   views.LancamentoPagarView.as_view(),  name='pagar'),
    path('<int:pk>/excluir/', views.LancamentoDeleteView.as_view(), name='delete'),
    path('fluxo-caixa/', views.FluxoCaixaView.as_view(), name='fluxo_caixa'),
    path('formas-pagamento/', views.FormaPagamentoListView.as_view(), name='formas_list'),
    path('formas-pagamento/nova/', views.FormaPagamentoCreateView.as_view(), name='formas_create'),
    path('formas-pagamento/<int:pk>/editar/', views.FormaPagamentoUpdateView.as_view(), name='formas_update'),
    path('formas-pagamento/<int:pk>/excluir/', views.FormaPagamentoDeleteView.as_view(), name='formas_delete'),
]
