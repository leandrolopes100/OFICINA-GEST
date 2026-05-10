"""
ordens_servico/forms.py
"""
from django import forms
from django.forms import inlineformset_factory
from decimal import Decimal

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field

from .models import OrdemServico, ItemOSServico, ItemOSPeca
from clientes.models import Cliente
from veiculos.models import Veiculo
from orcamentos.models import TipoServico
from estoque.models import Produto
from core.forms import VeiculoChoiceField


# ─────────────────────────────────────────────────────────────
# Formulário principal da OS
# ─────────────────────────────────────────────────────────────
class OrdemServicoForm(forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            'cliente', 'veiculo', 'mecanico',
            'km_entrada', 'data_previsao',
            'defeito_relatado', 'diagnostico',
            'servicos_realizados', 'observacoes_entrega',
            'desconto_valor',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs['class'] = 'form-select'
            elif isinstance(w, forms.Textarea):
                w.attrs.update({'class': 'form-control', 'rows': 3})
            else:
                w.attrs['class'] = 'form-control'

        # Clientes ativos
        self.fields['cliente'].queryset = Cliente.objects.filter(ativo=True).order_by('nome')
        self.fields['cliente'].empty_label = '— Selecione o cliente —'
        self.fields['cliente'].widget.attrs.update({'id': 'id_cliente'})

        # Veículos: usa VeiculoChoiceField para renderizar só o veículo atual
        # (edição) ou nada (criação). O JS popula via AJAX e o to_python
        # valida contra todos os veículos ativos independente do queryset.
        veiculo_id = self.instance.veiculo_id if (self.instance and self.instance.pk) else None
        render_qs = Veiculo.objects.filter(pk=veiculo_id) if veiculo_id else Veiculo.objects.none()
        self.fields['veiculo'] = VeiculoChoiceField(
            queryset=render_qs,
            label='Veículo',
            required=True,
            empty_label='— Selecione o veículo —',
            widget=forms.Select(attrs={'id': 'id_veiculo', 'class': 'form-select'}),
        )

        # Mecânicos
        try:
            from accounts.models import CustomUser
            self.fields['mecanico'].queryset = CustomUser.objects.filter(
                is_active=True, role='mecanico'
            )
        except Exception:
            pass
        self.fields['mecanico'].required = False
        self.fields['mecanico'].empty_label = '— Não atribuído —'

        # Data
        self.fields['data_previsao'].widget = forms.DateInput(
            attrs={'class': 'form-control', 'type': 'date'}
        )
        self.fields['data_previsao'].required = False

        # km_entrada: não obrigatório no formulário (padrão 0)
        self.fields['km_entrada'].required = False
        self.fields['km_entrada'].initial  = 0
        self.fields['km_entrada'].widget.attrs.update({'placeholder': '0'})

        # Opcionais
        for campo in ['diagnostico', 'servicos_realizados',
                      'observacoes_entrega', 'desconto_valor']:
            self.fields[campo].required = False

        # defeito_relatado: destaque visual para campo obrigatório
        self.fields['defeito_relatado'].widget.attrs.update({
            'placeholder': 'Descreva o problema relatado pelo cliente...',
            'rows': 3,
        })

        # ── FormHelper: NÃO gera tag <form> (evita form aninhado) ──
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('cliente', css_class='col-md-6'),
                Column('veiculo', css_class='col-md-6'),
            ),
            Row(
                Column('mecanico', css_class='col-md-4'),
                Column('km_entrada', css_class='col-md-4'),
                Column('data_previsao', css_class='col-md-4'),
            ),
            Field('defeito_relatado'),
            Row(
                Column('diagnostico', css_class='col-md-6'),
                Column('servicos_realizados', css_class='col-md-6'),
            ),
            Row(
                Column('observacoes_entrega', css_class='col-md-9'),
                Column('desconto_valor', css_class='col-md-3'),
            ),
        )


# ─────────────────────────────────────────────────────────────
# Formulário de atualização de status
# ─────────────────────────────────────────────────────────────
class AtualizarStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=OrdemServico.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observação opcional...',
        })
    )


# ─────────────────────────────────────────────────────────────
# Itens de SERVIÇO
# ─────────────────────────────────────────────────────────────
class ItemOSServicoForm(forms.ModelForm):
    class Meta:
        model = ItemOSServico
        fields = ['tipo_servico', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs['class'] = 'form-select sel-servico'
            else:
                w.attrs['class'] = 'form-control'

        self.fields['tipo_servico'].queryset = TipoServico.objects.filter(ativo=True).order_by('nome')
        self.fields['tipo_servico'].required = False
        self.fields['tipo_servico'].empty_label = '— catálogo (opcional) —'

        self.fields['descricao'].required = False
        self.fields['descricao'].widget.attrs['placeholder'] = 'Descreva o serviço'

        # Classe 'qtd' e 'preco' devem bater com os seletores de calcLinha() no JS
        self.fields['quantidade'].widget.attrs.update({
            'step': '0.01', 'min': '0.01', 'class': 'form-control qtd',
        })
        if not self.initial.get('quantidade'):
            self.fields['quantidade'].initial = Decimal('1')

        self.fields['preco_unitario'].required = False
        self.fields['preco_unitario'].widget.attrs.update({
            'step': '0.01', 'min': '0', 'placeholder': '0,00',
            'class': 'form-control preco',
        })

    def has_changed(self):
        # Linhas extras com só quantidade pré-preenchida (default 1) não devem
        # ser validadas. Só considera a linha preenchida se tipo_servico ou
        # descricao tiverem valor.
        if not self.instance.pk:
            tipo = self.data.get(self.add_prefix('tipo_servico'), '')
            desc = self.data.get(self.add_prefix('descricao'), '').strip()
            return bool(tipo or desc)
        return super().has_changed()

    def clean(self):
        cleaned_data = super().clean()
        tipo_servico = cleaned_data.get('tipo_servico')
        if tipo_servico:
            if not cleaned_data.get('descricao'):
                cleaned_data['descricao'] = tipo_servico.nome
            if not cleaned_data.get('preco_unitario'):
                cleaned_data['preco_unitario'] = tipo_servico.preco_padrao
        return cleaned_data

    def clean_quantidade(self):
        qtd = self.cleaned_data.get('quantidade')
        if not qtd or qtd <= 0:
            return Decimal('1')
        return qtd

    def clean_preco_unitario(self):
        preco = self.cleaned_data.get('preco_unitario')
        if preco is None:
            return Decimal('0')
        return preco


ItemOSServicoFormSet = inlineformset_factory(
    OrdemServico,
    ItemOSServico,
    form=ItemOSServicoForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ─────────────────────────────────────────────────────────────
# Itens de PEÇA
# ─────────────────────────────────────────────────────────────
class ItemOSPecaForm(forms.ModelForm):
    class Meta:
        model = ItemOSPeca
        fields = ['produto', 'descricao', 'quantidade', 'preco_unitario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs['class'] = 'form-select sel-produto'
            else:
                w.attrs['class'] = 'form-control'

        self.fields['produto'].queryset = Produto.objects.filter(ativo=True).order_by('nome')
        self.fields['produto'].required = False
        self.fields['produto'].empty_label = '— selecione a peça —'

        self.fields['descricao'].required = False
        self.fields['descricao'].widget.attrs['placeholder'] = 'Descreva a peça ou produto'

        # Classe 'qtd' e 'preco' devem bater com os seletores de calcLinha() no JS
        self.fields['quantidade'].widget.attrs.update({
            'step': '0.001', 'min': '0.001', 'class': 'form-control qtd',
        })
        if not self.initial.get('quantidade'):
            self.fields['quantidade'].initial = Decimal('1')

        self.fields['preco_unitario'].required = False
        self.fields['preco_unitario'].widget.attrs.update({
            'step': '0.01', 'min': '0', 'placeholder': '0,00',
            'class': 'form-control preco',
        })

    def has_changed(self):
        if not self.instance.pk:
            produto = self.data.get(self.add_prefix('produto'), '')
            desc    = self.data.get(self.add_prefix('descricao'), '').strip()
            return bool(produto or desc)
        return super().has_changed()

    def clean(self):
        cleaned_data = super().clean()
        produto = cleaned_data.get('produto')
        if produto:
            if not cleaned_data.get('descricao'):
                cleaned_data['descricao'] = produto.nome
            if not cleaned_data.get('preco_unitario'):
                cleaned_data['preco_unitario'] = produto.preco_venda
            # Valida estoque disponível — erro associado ao campo quantidade
            # para que o template possa exibi-lo inline na célula correta
            quantidade = cleaned_data.get('quantidade') or Decimal('0')
            if quantidade > 0 and produto.estoque_atual < quantidade:
                self.add_error(
                    'quantidade',
                    f'Estoque insuficiente para "{produto.nome}": '
                    f'disponível {float(produto.estoque_atual):g} '
                    f'{produto.get_unidade_display()}, '
                    f'solicitado {float(quantidade):g}.',
                )
        return cleaned_data

    def clean_quantidade(self):
        qtd = self.cleaned_data.get('quantidade')
        if not qtd or qtd <= 0:
            return Decimal('1')
        return qtd

    def clean_preco_unitario(self):
        preco = self.cleaned_data.get('preco_unitario')
        if preco is None:
            return Decimal('0')
        return preco


ItemOSPecaFormSet = inlineformset_factory(
    OrdemServico,
    ItemOSPeca,
    form=ItemOSPecaForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)
