from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from .models import Lancamento, FormaPagamento


class FormaPagamentoForm(forms.ModelForm):
    class Meta:
        model = FormaPagamento
        fields = ['nome', 'taxa', 'prazo_dias', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('nome', css_class='col-md-6'), Column('taxa', css_class='col-md-3'), Column('prazo_dias', css_class='col-md-3')),
            'ativo',
            Submit('submit', 'Salvar', css_class='btn btn-primary'),
        )


class LancamentoForm(forms.ModelForm):
    class Meta:
        model = Lancamento
        fields = [
            'tipo', 'categoria', 'descricao', 'valor',
            'data_competencia', 'data_vencimento', 'data_pagamento',
            'forma_pagamento', 'status', 'documento', 'observacoes',
        ]
        widgets = {
            'data_competencia': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_vencimento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_pagamento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Força seleção explícita — sem default silencioso para 'receita'
        self.fields['tipo'].choices = [('', '— Receita ou Despesa? —')] + list(Lancamento.TIPO_CHOICES)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('tipo', css_class='col-md-4'), Column('categoria', css_class='col-md-4'), Column('status', css_class='col-md-4')),
            Row(Column('descricao', css_class='col-md-8'), Column('valor', css_class='col-md-4')),
            Row(Column('data_competencia', css_class='col-md-4'), Column('data_vencimento', css_class='col-md-4'), Column('data_pagamento', css_class='col-md-4')),
            Row(Column('forma_pagamento', css_class='col-md-6'), Column('documento', css_class='col-md-6')),
            'observacoes',
            Submit('submit', 'Salvar Lançamento', css_class='btn btn-primary'),
        )

    def clean(self):
        dados = super().clean()
        if dados.get('status') == 'pago' and not dados.get('data_pagamento'):
            self.add_error('data_pagamento', 'Informe a data de pagamento para um lançamento pago.')
        return dados
