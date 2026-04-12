from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from .models import Orcamento, ItemOrcamentoServico, ItemOrcamentoPeca, TipoServico


class TipoServicoForm(forms.ModelForm):
    class Meta:
        model = TipoServico
        fields = ['nome', 'descricao', 'preco_padrao', 'tempo_estimado', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = [
            'cliente', 'veiculo', 'km_entrada', 'data_validade',
            'desconto_percentual', 'desconto_valor', 'taxa_valor',
            'observacoes', 'condicoes',
        ]
        widgets = {
            'data_validade': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
            'condicoes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(Column('cliente', css_class='col-md-6'), Column('veiculo', css_class='col-md-6')),
            Row(Column('km_entrada', css_class='col-md-4'), Column('data_validade', css_class='col-md-4')),
            Row(Column('desconto_percentual', css_class='col-md-4'), Column('desconto_valor', css_class='col-md-4'), Column('taxa_valor', css_class='col-md-4')),
            Row(Column('observacoes', css_class='col-md-6'), Column('condicoes', css_class='col-md-6')),
        )


class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemOrcamentoServico
        fields = ['tipo_servico', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'


class ItemPecaForm(forms.ModelForm):
    class Meta:
        model = ItemOrcamentoPeca
        fields = ['produto', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'


ItemServicoFormSet = inlineformset_factory(
    Orcamento, ItemOrcamentoServico,
    form=ItemServicoForm,
    fields=['tipo_servico', 'descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)

ItemPecaFormSet = inlineformset_factory(
    Orcamento, ItemOrcamentoPeca,
    form=ItemPecaForm,
    fields=['produto', 'descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)
