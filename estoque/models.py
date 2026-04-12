from django.db import models


class Fornecedor(models.Model):
    nome = models.CharField('Nome', max_length=200)
    cnpj = models.CharField('CNPJ', max_length=18, blank=True)
    contato = models.CharField('Contato', max_length=100, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    email = models.EmailField(blank=True)
    observacoes = models.TextField('Observações', blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Categoria(models.Model):
    nome = models.CharField('Nome', max_length=100, unique=True)
    descricao = models.TextField('Descrição', blank=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Produto(models.Model):
    UNIDADE_CHOICES = [
        ('un', 'Unidade'),
        ('kg', 'Quilograma'),
        ('lt', 'Litro'),
        ('mt', 'Metro'),
        ('cx', 'Caixa'),
        ('pc', 'Peça'),
    ]
    codigo = models.CharField('Código', max_length=50, unique=True)
    nome = models.CharField('Nome', max_length=200)
    descricao = models.TextField('Descrição', blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos')
    preco_custo = models.DecimalField('Preço de Custo', max_digits=10, decimal_places=2, default=0)
    preco_venda = models.DecimalField('Preço de Venda', max_digits=10, decimal_places=2, default=0)
    margem_lucro = models.DecimalField('Margem de Lucro (%)', max_digits=5, decimal_places=2, default=0)
    unidade = models.CharField('Unidade', max_length=2, choices=UNIDADE_CHOICES, default='un')
    estoque_atual = models.DecimalField('Estoque Atual', max_digits=10, decimal_places=3, default=0)
    estoque_minimo = models.DecimalField('Estoque Mínimo', max_digits=10, decimal_places=3, default=0)
    estoque_maximo = models.DecimalField('Estoque Máximo', max_digits=10, decimal_places=3, default=0)
    localizacao = models.CharField('Localização', max_length=50, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return f'[{self.codigo}] {self.nome}'

    @property
    def abaixo_minimo(self):
        return self.estoque_atual <= self.estoque_minimo

    @property
    def valor_estoque(self):
        return self.estoque_atual * self.preco_custo


class MovimentacaoEstoque(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
        ('ajuste', 'Ajuste de Inventário'),
        ('devolucao', 'Devolução'),
    ]
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='movimentacoes')
    tipo = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES)
    quantidade = models.DecimalField('Quantidade', max_digits=10, decimal_places=3)
    custo_unitario = models.DecimalField('Custo Unitário', max_digits=10, decimal_places=2, default=0)
    nota_fiscal = models.CharField('Nota Fiscal', max_length=50, blank=True)
    observacao = models.TextField('Observação', blank=True)
    usuario = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movimentacoes_estoque'
    )
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação de Estoque'
        verbose_name_plural = 'Movimentações de Estoque'
        ordering = ['-data']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.produto} ({self.quantidade})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        produto = Produto.objects.select_for_update().get(pk=self.produto_id)
        if self.tipo in ('entrada', 'devolucao'):
            produto.estoque_atual += self.quantidade
        elif self.tipo == 'saida':
            produto.estoque_atual -= self.quantidade
        elif self.tipo == 'ajuste':
            produto.estoque_atual = self.quantidade
        produto.save(update_fields=['estoque_atual'])
