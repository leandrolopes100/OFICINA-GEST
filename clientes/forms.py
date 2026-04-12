from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Div, HTML
from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'tipo_pessoa', 'nome', 'cpf_cnpj', 'rg_ie', 'data_nascimento',
            'email', 'telefone', 'celular', 'whatsapp',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'observacoes', 'ativo',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('tipo_pessoa', css_class='col-md-3'),
                Column('nome', css_class='col-md-6'),
                Column('cpf_cnpj', css_class='col-md-3'),
            ),
            Row(
                Column('rg_ie', css_class='col-md-3'),
                Column('data_nascimento', css_class='col-md-3'),
                Column('email', css_class='col-md-6'),
            ),
            Row(
                Column('telefone', css_class='col-md-4'),
                Column('celular', css_class='col-md-4'),
                Column('whatsapp', css_class='col-md-4'),
            ),
            HTML('<hr><h6 class="text-muted">Endereço</h6>'),
            Row(
                Column('cep', css_class='col-md-3'),
                Column('logradouro', css_class='col-md-6'),
                Column('numero', css_class='col-md-3'),
            ),
            Row(
                Column('complemento', css_class='col-md-4'),
                Column('bairro', css_class='col-md-4'),
                Column('cidade', css_class='col-md-3'),
                Column('estado', css_class='col-md-1'),
            ),
            HTML('<hr>'),
            Row(
                Column('observacoes', css_class='col-md-9'),
                Column('ativo', css_class='col-md-3'),
            ),
            Submit('submit', 'Salvar Cliente', css_class='btn btn-primary'),
        )
