from django.urls import path
from . import views

app_name = 'ordens_servico'

urlpatterns = [
    path('', views.OSListView.as_view(), name='list'),
    path('nova/', views.OSCreateView.as_view(), name='create'),
    path('<int:pk>/', views.OSDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.OSUpdateView.as_view(), name='update'),
    path('<int:pk>/em-andamento/', views.os_em_andamento, name='em_andamento'),
    path('<int:pk>/concluir/', views.os_concluir, name='concluir'),
    path('<int:pk>/entregar/', views.os_entregar, name='entregar'),
    path('<int:pk>/cancelar/', views.os_cancelar, name='cancelar'),
    path('<int:pk>/pdf/', views.os_pdf, name='pdf'),
]
