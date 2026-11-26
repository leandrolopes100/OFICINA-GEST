from django.urls import path
from . import views

app_name = 'veiculos'

urlpatterns = [
    path('', views.VeiculoListView.as_view(), name='list'),
    path('novo/', views.VeiculoCreateView.as_view(), name='create'),
    path('<int:pk>/', views.VeiculoDetailView.as_view(), name='detail'),
    path('<int:pk>/historico/pdf/', views.VeiculoHistoricoPdfView.as_view(), name='historico_pdf'),
    path('<int:pk>/editar/', views.VeiculoUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/',  views.VeiculoDeleteView.as_view(),   name='delete'),
    path('<int:pk>/reativar/', views.VeiculoReativarView.as_view(), name='reativar'),
    path('marcas/', views.MarcaListView.as_view(), name='marca_list'),
    path('marcas/nova/', views.MarcaCreateView.as_view(), name='marca_create'),
    path('marcas/modelo/novo/', views.ModeloCreateView.as_view(), name='modelo_create'),
    path('marcas/modelo/<int:pk>/excluir/', views.ModeloDeleteView.as_view(), name='modelo_delete'),
    path('ajax/por-cliente/<int:cliente_pk>/', views.veiculos_por_cliente_ajax, name='por_cliente'),
    path('ajax/modelos/<int:marca_pk>/', views.modelos_por_marca_ajax, name='modelos'),
]
