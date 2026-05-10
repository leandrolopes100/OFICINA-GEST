from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import Produto, Fornecedor, Categoria, MovimentacaoEstoque


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'cnpj', 'contato', 'telefone', 'email', 'observacoes', 'ativo']
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cnpj'].widget.attrs['data-mask'] = 'cnpj'
        self.fields['telefone'].widget.attrs['data-mask'] = 'telefone'
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('nome', css_class='col-md-8'), Column('cnpj', css_class='col-md-4')),
            Row(Column('contato', css_class='col-md-4'), Column('telefone', css_class='col-md-4'), Column('email', css_class='col-md-4')),
            'observacoes',
            'ativo',
            Submit('submit', 'Salvar Fornecedor', css_class='btn btn-primary'),
        )


class ProdutoForm(forms.ModelForm):
    # Campo extra (não é campo do model); só aparece na criação
    quantidade_inicial = forms.DecimalField(
        label='Quantidade Inicial em Estoque',
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001',
            'placeholder': '0',
        }),
    )

    class Meta:
        model = Produto
        fields = [
            'codigo', 'nome', 'descricao', 'categoria', 'fornecedor',
            'preco_custo', 'preco_venda', 'margem_lucro',
            'unidade', 'estoque_minimo', 'estoque_maximo', 'localizacao', 'ativo',
        ]
        widgets = {'descricao': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_edit = bool(self.instance and self.instance.pk)

        # Na edição o estoque só muda via movimentações
        if is_edit:
            del self.fields['quantidade_inicial']

        rows = [
            Row(Column('codigo', css_class='col-md-3'), Column('nome', css_class='col-md-6'), Column('unidade', css_class='col-md-3')),
            Row(Column('categoria', css_class='col-md-4'), Column('fornecedor', css_class='col-md-4'), Column('localizacao', css_class='col-md-4')),
            'descricao',
            Row(Column('preco_custo', css_class='col-md-4'), Column('margem_lucro', css_class='col-md-4'), Column('preco_venda', css_class='col-md-4')),
            Row(Column('estoque_minimo', css_class='col-md-4'), Column('estoque_maximo', css_class='col-md-4'), Column('ativo', css_class='col-md-4')),
        ]

        if not is_edit:
            rows += [
                HTML(
                    '<hr>'
                    '<div class="alert alert-info py-2 small mb-2">'
                    '<i class="bi bi-info-circle"></i> '
                    'Informe o estoque atual do produto. Uma movimentação de <strong>entrada</strong> '
                    'será registrada automaticamente no histórico.'
                    '</div>'
                ),
                Row(Column('quantidade_inicial', css_class='col-md-4')),
            ]

        rows.append(Submit('submit', 'Salvar Produto', css_class='btn btn-primary mt-2'))

        self.helper = FormHelper()
        self.helper.layout = Layout(*rows)


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'tipo', 'quantidade', 'custo_unitario', 'nota_fiscal', 'observacao']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Exibe estoque atual e unidade diretamente no texto de cada opção do select,
        # permitindo ao usuário ver o saldo disponível antes de selecionar o produto.
        self.fields['produto'].queryset = (
            Produto.objects.filter(ativo=True).order_by('nome')
        )
        self.fields['produto'].label_from_instance = (
            lambda p: f"{p.nome} [{p.codigo}] — {float(p.estoque_atual):g} {p.get_unidade_display()}"
        )
        self.fields['produto'].empty_label = '— Selecione o produto —'

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'produto',
            Row(Column('tipo', css_class='col-md-4'), Column('quantidade', css_class='col-md-4'), Column('custo_unitario', css_class='col-md-4')),
            Row(Column('nota_fiscal', css_class='col-md-6'), Column('observacao', css_class='col-md-6')),
            Submit('submit', 'Registrar Movimentação', css_class='btn btn-primary'),
        )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        produto = cleaned.get('produto')
        quantidade = cleaned.get('quantidade')
        if tipo == 'saida' and produto and quantidade:
            if produto.estoque_atual < quantidade:
                raise forms.ValidationError(
                    f'Estoque insuficiente para "{produto.nome}". '
                    f'Disponível: {float(produto.estoque_atual):g} {produto.get_unidade_display()}. '
                    f'Solicitado: {float(quantidade):g}.'
                )
        return cleaned
