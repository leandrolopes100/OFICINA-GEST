from django.urls import path
from . import views

app_name = 'estoque'

urlpatterns = [
    path('', views.ProdutoListView.as_view(), name='list'),
    path('novo/', views.ProdutoCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ProdutoDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='update'),
    path('movimentacoes/', views.MovimentacaoListView.as_view(), name='movimentacao_list'),
    path('movimentacoes/nova/', views.MovimentacaoCreateView.as_view(), name='movimentacao_create'),
    path('fornecedores/', views.FornecedorListView.as_view(), name='fornecedor_list'),
    path('fornecedores/novo/', views.FornecedorCreateView.as_view(), name='fornecedor_create'),
    path('fornecedores/<int:pk>/editar/', views.FornecedorUpdateView.as_view(), name='fornecedor_update'),
    path('alertas/', views.estoque_alertas, name='alertas'),
    path('ajax/busca/', views.produto_search_ajax, name='search_ajax'),
]
