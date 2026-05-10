from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from . import views

app_name = 'accounts'

urlpatterns = [
    # Autenticação
    path('login/',  views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Perfil e senha do próprio usuário
    path('perfil/', views.ProfileView.as_view(), name='profile'),
    path('senha/',  views.CustomPasswordChangeView.as_view(), name='password_change'),

    # ── Redefinição de senha (self-service) ───────────────────────────────────
    # 1. Usuário informa o e-mail cadastrado
    path(
        'senha/redefinir/',
        PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    # 2. Confirmação de envio (página genérica — não revela se e-mail existe)
    path(
        'senha/redefinir/enviado/',
        PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    # 3. Usuário clica no link do e-mail e define nova senha
    path(
        'senha/redefinir/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    # 4. Senha redefinida com sucesso
    path(
        'senha/redefinir/concluido/',
        PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # Gestão de usuários (admin)
    path('usuarios/',                   views.UserListView.as_view(),         name='user_list'),
    path('usuarios/novo/',              views.UserCreateView.as_view(),        name='user_create'),
    path('usuarios/<int:pk>/editar/',   views.UserUpdateView.as_view(),        name='user_update'),
    path('usuarios/<int:pk>/senha/',    views.AdminPasswordResetView.as_view(), name='user_password_reset'),
]
