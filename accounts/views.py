from django.contrib.auth import login, logout
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404

from .models import CustomUser
from .forms import CustomAuthenticationForm, CustomUserCreationForm, CustomUserChangeForm, ProfileUpdateForm
from core.mixins import RoleRequiredMixin


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True


class UserListView(RoleRequiredMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    allowed_roles = ['admin']
    paginate_by = 20


class UserCreateView(RoleRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Usuário criado com sucesso!')
        return super().form_valid(form)


class UserUpdateView(RoleRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    allowed_roles = ['admin']

    def form_valid(self, form):
        messages.success(self.request, 'Usuário atualizado com sucesso!')
        return super().form_valid(form)


class AdminPasswordResetView(RoleRequiredMixin, View):
    """Permite ao administrador redefinir a senha de qualquer usuário."""
    allowed_roles = ['admin']

    def get(self, request, pk):
        target_user = get_object_or_404(CustomUser, pk=pk)
        # Impede que o admin use esta view para a própria senha (tem a view padrão para isso)
        if target_user == request.user:
            messages.info(request, 'Para alterar sua própria senha, use a página de perfil.')
            return redirect(reverse_lazy('accounts:password_change'))
        form = SetPasswordForm(target_user)
        return render(request, 'accounts/admin_password_reset.html', {
            'form': form,
            'target_user': target_user,
        })

    def post(self, request, pk):
        target_user = get_object_or_404(CustomUser, pk=pk)
        if target_user == request.user:
            return redirect(reverse_lazy('accounts:password_change'))
        form = SetPasswordForm(target_user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Senha do usuário "{target_user.username}" redefinida com sucesso!'
            )
            return redirect(reverse_lazy('accounts:user_update', kwargs={'pk': pk}))
        return render(request, 'accounts/admin_password_reset.html', {
            'form': form,
            'target_user': target_user,
        })


class ProfileView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Perfil atualizado com sucesso!')
        return super().form_valid(form)


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, 'Senha alterada com sucesso!')
        return super().form_valid(form)
