from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from .models import Orcamento, ItemOrcamentoServico, ItemOrcamentoPeca, TipoServico
from clientes.models import Cliente
from veiculos.models import Veiculo
from core.forms import VeiculoChoiceField


class TipoServicoForm(forms.ModelForm):
    class Meta:
        model = TipoServico
        fields = ['nome', 'descricao', 'preco_padrao', 'tempo_estimado', 'ativo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'nome',
            'descricao',
            Row(
                Column('preco_padrao', css_class='col-md-6'),
                Column('tempo_estimado', css_class='col-md-6'),
            ),
            'ativo',
            Submit('submit', 'Salvar Tipo de Serviço', css_class='btn btn-primary mt-2'),
        )


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = [
            'cliente', 'veiculo', 'km_entrada', 'data_validade',
            'status',
            'desconto_percentual', 'desconto_valor', 'taxa_valor',
            'observacoes', 'condicoes',
        ]
        widgets = {
            'data_validade': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
            'condicoes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].widget.attrs['class'] = 'form-select'

        # Ativos + cliente atual caso esteja inativo (edição de orçamento existente)
        cliente_qs = Cliente.objects.filter(ativo=True)
        if self.instance and self.instance.pk and self.instance.cliente_id:
            cliente_qs = Cliente.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.cliente_id)
            )
        self.fields['cliente'].queryset = cliente_qs.order_by('nome')
        self.fields['cliente'].empty_label = '— Selecione o cliente —'

        # Veículo: VeiculoChoiceField renderiza apenas o veículo atual (edição)
        # ou nada (criação). O JS popula via AJAX quando o cliente é selecionado.
        veiculo_id = self.instance.veiculo_id if (self.instance and self.instance.pk) else None
        render_qs_v = Veiculo.objects.filter(pk=veiculo_id) if veiculo_id else Veiculo.objects.none()
        self.fields['veiculo'] = VeiculoChoiceField(
            queryset=render_qs_v,
            label='Veículo',
            required=True,
            empty_label='— Selecione o veículo —',
            widget=forms.Select(attrs={'class': 'form-select'}),
        )

        self.helper = FormHelper()
        self.helper.form_tag = False

        is_edit = bool(self.instance and self.instance.pk)

        if is_edit:
            self.helper.layout = Layout(
                Row(Column('cliente', css_class='col-md-6'), Column('veiculo', css_class='col-md-6')),
                Row(
                    Column('km_entrada', css_class='col-md-3'),
                    Column('data_validade', css_class='col-md-3'),
                    Column('status', css_class='col-md-3'),
                ),
                Row(Column('desconto_percentual', css_class='col-md-4'), Column('desconto_valor', css_class='col-md-4'), Column('taxa_valor', css_class='col-md-4')),
                Row(Column('observacoes', css_class='col-md-6'), Column('condicoes', css_class='col-md-6')),
            )
        else:
            # Na criação, status não é exibido; o model já define default='rascunho'
            del self.fields['status']
            self.helper.layout = Layout(
                Row(Column('cliente', css_class='col-md-6'), Column('veiculo', css_class='col-md-6')),
                Row(Column('km_entrada', css_class='col-md-4'), Column('data_validade', css_class='col-md-4')),
                Row(Column('desconto_percentual', css_class='col-md-4'), Column('desconto_valor', css_class='col-md-4'), Column('taxa_valor', css_class='col-md-4')),
                Row(Column('observacoes', css_class='col-md-6'), Column('condicoes', css_class='col-md-6')),
            )

    def clean(self):
        cleaned = super().clean()
        d_pct = cleaned.get('desconto_percentual') or Decimal('0')
        d_val = cleaned.get('desconto_valor') or Decimal('0')

        if d_pct < 0 or d_pct > 100:
            self.add_error('desconto_percentual', 'Desconto percentual deve estar entre 0% e 100%.')

        if d_val < 0:
            self.add_error('desconto_valor', 'Desconto em valor não pode ser negativo.')

        return cleaned


class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemOrcamentoServico
        fields = ['tipo_servico', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'
        self.fields['descricao'].required = False
        self.fields['preco_unitario'].required = False

    def has_changed(self):
        # O campo `quantidade` tem default=1 no modelo, o que faz o Django
        # considerar a linha extra "modificada" mesmo sem o usuário preencher nada.
        # Só tratamos a linha como preenchida quando tipo_servico foi selecionado.
        if not self.instance.pk:
            return bool(self.data.get(self.add_prefix('tipo_servico')))
        return super().has_changed()

    def clean(self):
        cleaned_data = super().clean()
        tipo_servico = cleaned_data.get('tipo_servico')
        if tipo_servico:
            if not cleaned_data.get('descricao'):
                cleaned_data['descricao'] = tipo_servico.nome
            if cleaned_data.get('preco_unitario') is None:
                cleaned_data['preco_unitario'] = tipo_servico.preco_padrao
        return cleaned_data


class ItemPecaForm(forms.ModelForm):
    class Meta:
        model = ItemOrcamentoPeca
        fields = ['produto', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control form-control-sm'
        self.fields['descricao'].required = False
        self.fields['quantidade'].required = False
        self.fields['quantidade'].widget.attrs['placeholder'] = '1'
        self.fields['preco_unitario'].required = False

    def has_changed(self):
        if not self.instance.pk:
            return bool(self.data.get(self.add_prefix('produto')))
        return super().has_changed()

    def clean(self):
        cleaned_data = super().clean()
        produto = cleaned_data.get('produto')
        if produto:
            if not cleaned_data.get('descricao'):
                cleaned_data['descricao'] = produto.nome
            if cleaned_data.get('preco_unitario') is None:
                cleaned_data['preco_unitario'] = produto.preco_venda
            if cleaned_data.get('quantidade') is None:
                cleaned_data['quantidade'] = Decimal('1')
        return cleaned_data


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
