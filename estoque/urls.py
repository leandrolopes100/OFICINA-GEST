from django.urls import path
from . import views

app_name = 'estoque'

urlpatterns = [
    path('', views.ProdutoListView.as_view(), name='list'),
    path('novo/', views.ProdutoCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ProdutoDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/',  views.ProdutoUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/',  views.ProdutoDeleteView.as_view(),   name='delete'),
    path('<int:pk>/reativar/', views.ProdutoReativarView.as_view(), name='reativar'),
    path('movimentacoes/', views.MovimentacaoListView.as_view(), name='movimentacao_list'),
    path('movimentacoes/nova/', views.MovimentacaoCreateView.as_view(), name='movimentacao_create'),
    path('fornecedores/', views.FornecedorListView.as_view(), name='fornecedor_list'),
    path('fornecedores/novo/', views.FornecedorCreateView.as_view(), name='fornecedor_create'),
    path('fornecedores/<int:pk>/editar/',   views.FornecedorUpdateView.as_view(),   name='fornecedor_update'),
    path('fornecedores/<int:pk>/excluir/',  views.FornecedorDeleteView.as_view(),   name='fornecedor_delete'),
    path('fornecedores/<int:pk>/reativar/', views.FornecedorReativarView.as_view(), name='fornecedor_reativar'),
    path('alertas/', views.EstoqueAlertasView.as_view(), name='alertas'),
    path('ajax/busca/',          views.produto_search_ajax, name='search_ajax'),
    path('ajax/produto/<int:pk>/', views.produto_info_ajax,   name='produto_info_ajax'),
]
