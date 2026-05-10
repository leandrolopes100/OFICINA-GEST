from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, HTML
from .models import CustomUser


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuário',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuário', 'autofocus': True})
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha'})
    )


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'telefone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aplica classes Bootstrap — checkbox recebe form-check-input, demais form-control
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

        # Máscaras
        if 'telefone' in self.fields:
            self.fields['telefone'].widget.attrs['data-mask'] = 'telefone'

        # Remove help_texts técnicos desnecessários para o administrador
        self.fields['username'].help_text = None
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None
        self.fields['password2'].label = 'Confirmar Senha'

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2">Dados de Acesso</h6>'),
            Row(
                Column('username', css_class='col-md-8'),
                Column('role', css_class='col-md-4'),
            ),
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Dados Pessoais</h6>'),
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            Row(
                Column('email', css_class='col-md-6'),
                Column('telefone', css_class='col-md-6'),
            ),
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Senha de Acesso</h6>'),
            Row(
                Column('password1', css_class='col-md-6'),
                Column('password2', css_class='col-md-6'),
            ),
            HTML("""
                <div class="d-flex gap-2 mt-4">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-person-plus-fill"></i> Criar Usuário
                    </button>
                    <a href="{% url 'accounts:user_list' %}" class="btn btn-outline-secondary">
                        <i class="bi bi-x-lg"></i> Cancelar
                    </a>
                </div>
            """),
        )


class CustomUserChangeForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'telefone', 'avatar', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

        if 'telefone' in self.fields:
            self.fields['telefone'].widget.attrs['data-mask'] = 'telefone'

        self.fields['username'].help_text = None

        # is_active: label mais clara para o administrador
        self.fields['is_active'].label = 'Usuário ativo'
        self.fields['is_active'].help_text = 'Desmarque para bloquear o acesso deste usuário ao sistema.'

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        self.helper.layout = Layout(
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2">Dados de Acesso</h6>'),
            Row(
                Column('username', css_class='col-md-8'),
                Column('role', css_class='col-md-4'),
            ),
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Dados Pessoais</h6>'),
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            Row(
                Column('email', css_class='col-md-6'),
                Column('telefone', css_class='col-md-6'),
            ),
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Configurações</h6>'),
            'avatar',
            HTML('<div class="mt-3">'),
            'is_active',
            HTML('</div>'),
            HTML("""
                <div class="d-flex gap-2 mt-4">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-check-lg"></i> Salvar Alterações
                    </button>
                    <a href="{% url 'accounts:user_list' %}" class="btn btn-outline-secondary">
                        <i class="bi bi-x-lg"></i> Cancelar
                    </a>
                </div>
            """),
        )


class ProfileUpdateForm(forms.ModelForm):

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'telefone', 'avatar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['username'].help_text = None
        if 'telefone' in self.fields:
            self.fields['telefone'].widget.attrs['data-mask'] = 'telefone'
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        self.helper.layout = Layout(
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2">Dados de Acesso</h6>'),
            'username',
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Dados Pessoais</h6>'),
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            Row(
                Column('email', css_class='col-md-6'),
                Column('telefone', css_class='col-md-6'),
            ),
            HTML('<h6 class="text-muted fw-semibold mb-3 border-bottom pb-2 mt-4">Foto de Perfil</h6>'),
            'avatar',
            HTML("""
                <div class="d-flex gap-2 mt-4">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-check-lg"></i> Salvar Alterações
                    </button>
                    <a href="{% url 'accounts:profile' %}" class="btn btn-outline-secondary">
                        <i class="bi bi-x-lg"></i> Cancelar
                    </a>
                </div>
            """),
        )
