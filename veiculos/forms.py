from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import Veiculo, Marca, Modelo


class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = [
            'cliente', 'marca', 'modelo',
            'ano_fabricacao', 'ano_modelo', 'cor',
            'placa', 'renavam', 'chassi', 'combustivel',
            'km_atual', 'km_proxima_revisao', 'data_proxima_revisao',
            'observacoes', 'ativo',
        ]
        widgets = {
            'data_proxima_revisao': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        cliente_id = kwargs.pop('cliente_id', None)
        super().__init__(*args, **kwargs)
        if cliente_id:
            from clientes.models import Cliente
            self.fields['cliente'].initial = cliente_id
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('cliente', css_class='col-md-12')),
            Row(
                Column('marca', css_class='col-md-4'),
                Column('modelo', css_class='col-md-4'),
                Column('combustivel', css_class='col-md-4'),
            ),
            Row(
                Column('ano_fabricacao', css_class='col-md-3'),
                Column('ano_modelo', css_class='col-md-3'),
                Column('cor', css_class='col-md-3'),
                Column('placa', css_class='col-md-3'),
            ),
            Row(
                Column('renavam', css_class='col-md-4'),
                Column('chassi', css_class='col-md-4'),
                Column('km_atual', css_class='col-md-4'),
            ),
            Row(
                Column('km_proxima_revisao', css_class='col-md-4'),
                Column('data_proxima_revisao', css_class='col-md-4'),
                Column('ativo', css_class='col-md-4'),
            ),
            'observacoes',
            Submit('submit', 'Salvar Veículo', css_class='btn btn-primary'),
        )


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ['nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].widget.attrs['class'] = 'form-control'


class ModeloForm(forms.ModelForm):
    class Meta:
        model = Modelo
        fields = ['marca', 'nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'
