from django.db import models, transaction
from django.utils import timezone

from clientes.models import Cliente
from veiculos.models import Veiculo
from orcamentos.models import Orcamento, TipoServico
from estoque.models import Produto


class OrdemServico(models.Model):
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('em_andamento', 'Em Andamento'),
        ('aguardando', 'Aguardando Peça/Aprovação'),
        ('concluida', 'Concluída'),
        ('entregue', 'Entregue'),
        ('cancelada', 'Cancelada'),
    ]

    # Transições válidas de status — estados terminais (entregue, cancelada)
    # não permitem nenhuma mudança posterior.
    TRANSICOES_VALIDAS = {
        'aberta':       {'em_andamento', 'aguardando', 'cancelada'},
        'em_andamento': {'aberta', 'aguardando', 'concluida', 'cancelada'},
        'aguardando':   {'aberta', 'em_andamento', 'concluida', 'cancelada'},
        'concluida':    {'entregue'},
        'entregue':     set(),
        'cancelada':    set(),
    }

    numero = models.CharField('Número', max_length=20, unique=True, editable=False)
    orcamento = models.OneToOneField(
        Orcamento, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordem_servico'
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ordens_servico')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name='ordens_servico')
    mecanico = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'mecanico'},
        related_name='ordens_como_mecanico',
        verbose_name='Mecânico'
    )
    criado_por = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_criadas'
    )
    status = models.CharField('Status', max_length=15, choices=STATUS_CHOICES, default='aberta', db_index=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_previsao = models.DateField('Previsão de Conclusão', null=True, blank=True, db_index=True)
    data_conclusao = models.DateTimeField('Data de Conclusão', null=True, blank=True)
    data_entrega = models.DateTimeField('Data de Entrega', null=True, blank=True)
    km_entrada = models.PositiveIntegerField('KM na Entrada', default=0)
    km_saida = models.PositiveIntegerField('KM na Saída', null=True, blank=True)
    subtotal_servicos = models.DecimalField('Subtotal Serviços', max_digits=10, decimal_places=2, default=0)
    subtotal_pecas = models.DecimalField('Subtotal Peças', max_digits=10, decimal_places=2, default=0)
    desconto_valor = models.DecimalField('Desconto (R$)', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)
    defeito_relatado = models.TextField('Defeito Relatado pelo Cliente')
    diagnostico = models.TextField('Diagnóstico do Mecânico', blank=True)
    servicos_realizados = models.TextField('Observações dos Serviços', blank=True)
    observacoes_entrega = models.TextField('Observações na Entrega', blank=True)

    class Meta:
        verbose_name = 'Ordem de Serviço'
        verbose_name_plural = 'Ordens de Serviço'
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['status', 'data_previsao'], name='os_status_previsao_idx'),
            models.Index(fields=['cliente', 'status'], name='os_cliente_status_idx'),
        ]

    def __str__(self):
        return f'OS-{self.numero}'

    def save(self, *args, **kwargs):
        if not self.numero:
            # Envolve a leitura do último ID e o INSERT numa transação para
            # evitar race condition na geração do número sequencial.
            with transaction.atomic():
                ultimo = OrdemServico.objects.order_by('-id').first()
                self.numero = str((ultimo.id if ultimo else 0) + 1).zfill(6)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def recalcular_totais(self):
        from decimal import Decimal
        from django.db.models import Sum
        subtotal_srv = self.itens_servico.aggregate(t=Sum('total'))['t'] or Decimal('0')
        subtotal_pca = self.itens_peca.aggregate(t=Sum('total'))['t'] or Decimal('0')
        self.subtotal_servicos = subtotal_srv
        self.subtotal_pecas = subtotal_pca
        self.total = subtotal_srv + subtotal_pca - self.desconto_valor
        self.save(update_fields=['subtotal_servicos', 'subtotal_pecas', 'total'])

    def pode_mudar_para(self, novo_status: str) -> bool:
        """Valida se a transição de status é permitida pela máquina de estados."""
        return novo_status in self.TRANSICOES_VALIDAS.get(self.status, set())

    @property
    def pode_editar(self):
        return self.status in ('aberta', 'em_andamento', 'aguardando')


class ItemOSServico(models.Model):
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='itens_servico')
    tipo_servico = models.ForeignKey(TipoServico, on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=300)
    quantidade = models.DecimalField('Quantidade', max_digits=6, decimal_places=2, default=1)
    preco_unitario = models.DecimalField('Preço Unitário', max_digits=10, decimal_places=2)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Item de Serviço (OS)'

    def save(self, *args, **kwargs):
        self.total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)


class ItemOSPeca(models.Model):
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='itens_peca')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=300)
    quantidade = models.DecimalField('Quantidade', max_digits=10, decimal_places=3)
    preco_unitario = models.DecimalField('Preço Unitário', max_digits=10, decimal_places=2)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Item de Peça (OS)'

    def save(self, *args, **kwargs):
        self.total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
