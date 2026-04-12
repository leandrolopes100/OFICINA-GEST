from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import OrdemServico, ItemOSServico, ItemOSPeca


class OrdemServicoForm(forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            'cliente', 'veiculo', 'mecanico',
            'km_entrada', 'data_previsao',
            'defeito_relatado', 'diagnostico',
            'desconto_valor', 'observacoes_entrega',
        ]
        widgets = {
            'data_previsao': forms.DateInput(attrs={'type': 'date'}),
            'defeito_relatado': forms.Textarea(attrs={'rows': 3}),
            'diagnostico': forms.Textarea(attrs={'rows': 3}),
            'observacoes_entrega': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(Column('cliente', css_class='col-md-6'), Column('veiculo', css_class='col-md-6')),
            Row(Column('mecanico', css_class='col-md-4'), Column('km_entrada', css_class='col-md-4'), Column('data_previsao', css_class='col-md-4')),
            Row(Column('defeito_relatado', css_class='col-md-6'), Column('diagnostico', css_class='col-md-6')),
            Row(Column('desconto_valor', css_class='col-md-4'), Column('observacoes_entrega', css_class='col-md-8')),
        )


class ItemOSServicoForm(forms.ModelForm):
    class Meta:
        model = ItemOSServico
        fields = ['tipo_servico', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'


class ItemOSPecaForm(forms.ModelForm):
    class Meta:
        model = ItemOSPeca
        fields = ['produto', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'


ItemOSServicoFormSet = inlineformset_factory(
    OrdemServico, ItemOSServico,
    form=ItemOSServicoForm,
    fields=['tipo_servico', 'descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)

ItemOSPecaFormSet = inlineformset_factory(
    OrdemServico, ItemOSPeca,
    form=ItemOSPecaForm,
    fields=['produto', 'descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)
