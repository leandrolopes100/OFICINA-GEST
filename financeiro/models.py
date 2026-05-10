from django.db import models


class FormaPagamento(models.Model):
    nome = models.CharField('Nome', max_length=100)
    taxa = models.DecimalField('Taxa (%)', max_digits=5, decimal_places=2, default=0)
    prazo_dias = models.PositiveSmallIntegerField('Prazo (dias)', default=0)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Forma de Pagamento'
        verbose_name_plural = 'Formas de Pagamento'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Lancamento(models.Model):
    TIPO_CHOICES = [
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
    ]
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago / Recebido'),
        ('vencido', 'Vencido'),
        ('cancelado', 'Cancelado'),
    ]
    CATEGORIA_CHOICES = [
        ('servico', 'Serviço'),
        ('venda_peca', 'Venda de Peça'),
        ('fornecedor', 'Fornecedor / Compra'),
        ('salario', 'Salário'),
        ('aluguel', 'Aluguel'),
        ('utilidades', 'Água / Luz / Internet'),
        ('manutencao', 'Manutenção'),
        ('outros', 'Outros'),
    ]
    tipo = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES, db_index=True)
    categoria = models.CharField('Categoria', max_length=20, choices=CATEGORIA_CHOICES, default='outros')
    ordem_servico = models.ForeignKey(
        'ordens_servico.OrdemServico', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lancamentos', verbose_name='Ordem de Serviço'
    )
    forma_pagamento = models.ForeignKey(
        FormaPagamento, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Forma de Pagamento'
    )
    descricao = models.CharField('Descrição', max_length=300)
    valor = models.DecimalField('Valor', max_digits=12, decimal_places=2)
    valor_taxa = models.DecimalField('Taxa Cobrada (R$)', max_digits=10, decimal_places=2, default=0)
    data_competencia = models.DateField('Data de Competência', db_index=True)
    data_vencimento = models.DateField('Data de Vencimento', null=True, blank=True)
    data_pagamento = models.DateField('Data de Pagamento', null=True, blank=True, db_index=True)
    status = models.CharField('Status', max_length=10, choices=STATUS_CHOICES, default='pendente', db_index=True)
    observacoes = models.TextField('Observações', blank=True)
    documento = models.CharField('Nº Documento/NF', max_length=50, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento'
        verbose_name_plural = 'Lançamentos'
        ordering = ['-data_competencia']
        indexes = [
            models.Index(fields=['tipo', 'status'], name='lancamento_tipo_status_idx'),
            models.Index(fields=['data_pagamento', 'tipo'], name='lancamento_pgto_tipo_idx'),
            models.Index(fields=['data_competencia', 'tipo'], name='lancamento_comp_tipo_idx'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.descricao} — R$ {self.valor}'
