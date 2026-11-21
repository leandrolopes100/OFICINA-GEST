from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction


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
    nome = models.CharField('Nome', max_length=200, db_index=True)
    descricao = models.TextField('Descrição', blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos')
    preco_custo = models.DecimalField('Preço de Custo', max_digits=10, decimal_places=2, default=0)
    preco_venda = models.DecimalField('Preço de Venda', max_digits=10, decimal_places=2, default=0)
    margem_lucro = models.DecimalField('Margem de Lucro (%)', max_digits=10, decimal_places=2, default=0)
    unidade = models.CharField('Unidade', max_length=2, choices=UNIDADE_CHOICES, default='un')
    estoque_atual = models.DecimalField('Estoque Atual', max_digits=10, decimal_places=3, default=0, db_index=True)
    estoque_minimo = models.DecimalField('Estoque Mínimo', max_digits=10, decimal_places=3, default=0)
    estoque_maximo = models.DecimalField('Estoque Máximo', max_digits=10, decimal_places=3, default=0)
    localizacao = models.CharField('Localização', max_length=50, blank=True)
    ativo = models.BooleanField('Ativo', default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']
        indexes = [
            models.Index(fields=['ativo', 'estoque_atual'], name='produto_ativo_estoque_idx'),
            models.Index(fields=['ativo', 'nome'], name='produto_ativo_nome_idx'),
        ]

    VALOR_MAXIMO = Decimal('99999999.99')

    def __str__(self):
        return f'[{self.codigo}] {self.nome}'

    @classmethod
    def preco_venda_pela_margem(cls, custo, margem):
        preco = (custo * (1 + margem / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if preco > cls.VALOR_MAXIMO:
            return None
        return preco

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
    ordem_servico = models.ForeignKey(
        'ordens_servico.OrdemServico', on_delete=models.SET_NULL,
        null=True, blank=True, editable=False,
        related_name='movimentacoes_estoque', verbose_name='Ordem de Serviço',
    )
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
        # Prepara observação automática para movimentações de ajuste
        if self.pk is None and self.tipo == 'ajuste' and not self.observacao:
            try:
                anterior = Produto.objects.values_list(
                    'estoque_atual', flat=True
                ).get(pk=self.produto_id)
                diferenca = self.quantidade - anterior
                sinal     = '+' if diferenca >= 0 else ''
                self.observacao = (
                    f'Inventário físico: de {float(anterior):g} para '
                    f'{float(self.quantidade):g} unidade(s) '
                    f'(diferença: {sinal}{float(diferenca):g})'
                )
            except Produto.DoesNotExist:
                pass

        # Envolve o INSERT da movimentação e o UPDATE do estoque numa transação
        # atômica com select_for_update() — agora com PostgreSQL, o lock de linha
        # real previne race conditions em movimentações simultâneas.
        with transaction.atomic():
            super().save(*args, **kwargs)
            produto = Produto.objects.select_for_update().get(pk=self.produto_id)

            # Bloqueia saída com estoque insuficiente
            if self.tipo == 'saida' and produto.estoque_atual < self.quantidade:
                raise ValueError(
                    f'Estoque insuficiente para "{produto.nome}": '
                    f'disponível {float(produto.estoque_atual):g}, '
                    f'solicitado {float(self.quantidade):g}.'
                )

            # Atualiza estoque
            if self.tipo in ('entrada', 'devolucao'):
                produto.estoque_atual += self.quantidade
            elif self.tipo == 'saida':
                produto.estoque_atual -= self.quantidade
            elif self.tipo == 'ajuste':
                produto.estoque_atual = self.quantidade

            # Atualiza custo e recalcula preço de venda em novas entradas com custo diferente
            update_fields = ['estoque_atual']
            novo_custo = self.custo_unitario
            if (self.tipo == 'entrada'
                    and novo_custo > 0
                    and novo_custo != produto.preco_custo):
                produto.preco_custo = novo_custo
                update_fields.append('preco_custo')
                if produto.margem_lucro > 0:
                    novo_preco = Produto.preco_venda_pela_margem(novo_custo, produto.margem_lucro)
                    if novo_preco is None:
                        self.preco_venda_nao_recalculado = True
                    else:
                        produto.preco_venda = novo_preco
                        update_fields.append('preco_venda')

            produto.save(update_fields=update_fields)
