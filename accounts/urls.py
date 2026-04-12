from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('perfil/', views.ProfileView.as_view(), name='profile'),
    path('senha/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('usuarios/', views.UserListView.as_view(), name='user_list'),
    path('usuarios/novo/', views.UserCreateView.as_view(), name='user_create'),
    path('usuarios/<int:pk>/editar/', views.UserUpdateView.as_view(), name='user_update'),
]
