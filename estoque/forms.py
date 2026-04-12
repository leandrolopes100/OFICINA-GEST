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
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('nome', css_class='col-md-8'), Column('cnpj', css_class='col-md-4')),
            Row(Column('contato', css_class='col-md-4'), Column('telefone', css_class='col-md-4'), Column('email', css_class='col-md-4')),
            'observacoes',
            'ativo',
            Submit('submit', 'Salvar Fornecedor', css_class='btn btn-primary'),
        )


class ProdutoForm(forms.ModelForm):
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
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('codigo', css_class='col-md-3'), Column('nome', css_class='col-md-6'), Column('unidade', css_class='col-md-3')),
            Row(Column('categoria', css_class='col-md-4'), Column('fornecedor', css_class='col-md-4'), Column('localizacao', css_class='col-md-4')),
            'descricao',
            Row(Column('preco_custo', css_class='col-md-4'), Column('margem_lucro', css_class='col-md-4'), Column('preco_venda', css_class='col-md-4')),
            Row(Column('estoque_minimo', css_class='col-md-4'), Column('estoque_maximo', css_class='col-md-4'), Column('ativo', css_class='col-md-4')),
            Submit('submit', 'Salvar Produto', css_class='btn btn-primary'),
        )


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'tipo', 'quantidade', 'custo_unitario', 'nota_fiscal', 'observacao']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'produto',
            Row(Column('tipo', css_class='col-md-4'), Column('quantidade', css_class='col-md-4'), Column('custo_unitario', css_class='col-md-4')),
            Row(Column('nota_fiscal', css_class='col-md-6'), Column('observacao', css_class='col-md-6')),
            Submit('submit', 'Registrar Movimentação', css_class='btn btn-primary'),
        )
