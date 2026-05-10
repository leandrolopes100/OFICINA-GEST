from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Div, HTML
from .models import Cliente
from .validators import _validar_cpf, _validar_cnpj

UF_CHOICES = [
    ('', '— UF —'),
    ('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'),
    ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'),
    ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'),
    ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'),
    ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'),
    ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'),
    ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO'),
]


class ClienteForm(forms.ModelForm):
    estado = forms.ChoiceField(
        label='Estado',
        choices=UF_CHOICES,
        required=False,
    )

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
        self.fields['cep'].widget.attrs['data-mask'] = 'cep'
        self.fields['telefone'].widget.attrs['data-mask'] = 'telefone'
        self.fields['celular'].widget.attrs['data-mask'] = 'celular'
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
                Column('telefone', css_class='col-md-5'),
                Column('celular', css_class='col-md-5'),
                Column('whatsapp', css_class='col-md-2 d-flex align-items-end pb-2'),
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
            HTML("""
                <div class="d-flex gap-2 mt-2">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-check-lg"></i> Salvar Cliente
                    </button>
                    <a href="{% url 'clientes:list' %}" class="btn btn-outline-secondary">
                        <i class="bi bi-x-lg"></i> Cancelar
                    </a>
                </div>
            """),
        )

    def clean_cpf_cnpj(self):
        cpf_cnpj = self.cleaned_data.get('cpf_cnpj', '')
        tipo = self.cleaned_data.get('tipo_pessoa') or self.data.get('tipo_pessoa', 'F')
        if tipo == 'F':
            if not _validar_cpf(cpf_cnpj):
                raise forms.ValidationError('CPF inválido. Verifique os dígitos informados.')
        else:
            if not _validar_cnpj(cpf_cnpj):
                raise forms.ValidationError('CNPJ inválido. Verifique os dígitos informados.')
        return cpf_cnpj
