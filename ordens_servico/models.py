import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone

from clientes.models import Cliente
from veiculos.models import Veiculo
from orcamentos.models import Orcamento, TipoServico
from estoque.models import Produto


@dataclass(frozen=True)
class ResultadoOS:
    receita: Decimal
    custo_pecas: Decimal
    taxa: Decimal
    lucro: Decimal
    margem: Decimal | None
    realizado: bool
    custo_previsto: bool
    custo_estimado: bool
    itens_abaixo_do_custo: list = field(default_factory=list)


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
    data_cancelamento = models.DateTimeField('Data de Cancelamento', null=True, blank=True)
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
    token_publico = models.CharField(
        'Token do link de acompanhamento', max_length=64,
        unique=True, null=True, blank=True, editable=False,
    )
    link_gerado_em = models.DateTimeField('Link gerado em', null=True, blank=True, editable=False)

    DIAS_LINK_APOS_ENCERRAMENTO = 30

    ETAPAS_ACOMPANHAMENTO = [
        ('aberta', 'Recebido'),
        ('em_andamento', 'Em serviço'),
        ('aguardando', 'Aguardando peça/aprovação'),
        ('concluida', 'Pronto para retirada'),
        ('entregue', 'Entregue'),
    ]

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

    def registrar_mudanca_status(self, novo_status):
        self.status = novo_status
        agora = timezone.now()
        if novo_status == 'concluida' and not self.data_conclusao:
            self.data_conclusao = agora
        elif novo_status == 'entregue' and not self.data_entrega:
            self.data_entrega = agora
        elif novo_status == 'cancelada' and not self.data_cancelamento:
            self.data_cancelamento = agora

    def garantir_link_publico(self):
        OrdemServico.objects.filter(pk=self.pk, token_publico__isnull=True).update(
            token_publico=secrets.token_urlsafe(32), link_gerado_em=timezone.now(),
        )
        self.refresh_from_db(fields=['token_publico', 'link_gerado_em'])
        return self.token_publico

    def regenerar_link_publico(self):
        self.token_publico = secrets.token_urlsafe(32)
        self.link_gerado_em = timezone.now()
        self.save(update_fields=['token_publico', 'link_gerado_em'])
        return self.token_publico

    @property
    def data_encerramento(self):
        if self.status == 'entregue':
            return self.data_entrega
        if self.status == 'cancelada':
            return self.data_cancelamento
        return None

    @property
    def link_expira_em(self):
        if self.status not in ('entregue', 'cancelada'):
            return None
        referencias = [data for data in (self.data_encerramento, self.link_gerado_em) if data]
        if not referencias:
            return None
        return max(referencias) + timedelta(days=self.DIAS_LINK_APOS_ENCERRAMENTO)

    @property
    def link_visivel_ao_cliente(self):
        if not self.token_publico:
            return False
        if self.status in ('entregue', 'cancelada'):
            expira = self.link_expira_em
            return expira is not None and timezone.now() <= expira
        return True

    @property
    def etapas_acompanhamento(self):
        codigos = [codigo for codigo, _ in self.ETAPAS_ACOMPANHAMENTO]
        atual = codigos.index(self.status) if self.status in codigos else -1
        return [
            {'rotulo': rotulo, 'concluida': indice < atual, 'atual': indice == atual}
            for indice, (codigo, rotulo) in enumerate(self.ETAPAS_ACOMPANHAMENTO)
            if codigo != 'aguardando' or self.status == 'aguardando'
        ]

    @property
    def pode_editar(self):
        return self.status in ('aberta', 'em_andamento', 'aguardando')

    def congelar_custos(self):
        itens = list(self.itens_peca.select_related('produto'))
        for item in itens:
            item.custo_unitario = item.produto.preco_custo
            item.custo_estimado = False
        ItemOSPeca.objects.bulk_update(itens, ['custo_unitario', 'custo_estimado'])
        return itens

    def resultado(self):
        from financeiro.models import Lancamento

        itens = [] if self.status == 'cancelada' else list(self.itens_peca.select_related('produto'))
        custo_pecas = sum((item.custo_total for item in itens), Decimal('0'))
        recebido = Lancamento.objects.filter(
            ordem_servico=self, tipo='receita', status='pago',
        ).aggregate(valor=models.Sum('valor'), taxa=models.Sum('valor_taxa'))

        realizado = recebido['valor'] is not None
        if realizado:
            receita = recebido['valor']
        else:
            receita = Decimal('0') if self.status == 'cancelada' else self.total
        taxa = (recebido['taxa'] or Decimal('0')) if realizado else Decimal('0')
        lucro = receita - custo_pecas - taxa
        return ResultadoOS(
            receita=receita,
            custo_pecas=custo_pecas,
            taxa=taxa,
            lucro=lucro,
            margem=(lucro / receita * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if receita else None,
            realizado=realizado,
            custo_previsto=any(item.custo_unitario is None for item in itens),
            custo_estimado=any(item.custo_estimado for item in itens),
            itens_abaixo_do_custo=[item for item in itens if item.abaixo_do_custo],
        )


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
    custo_unitario = models.DecimalField(
        'Custo Unitário', max_digits=10, decimal_places=2, null=True, blank=True, editable=False,
    )
    custo_estimado = models.BooleanField('Custo estimado', default=False, editable=False)

    class Meta:
        verbose_name = 'Item de Peça (OS)'

    def save(self, *args, **kwargs):
        self.total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)

    @property
    def custo_unitario_efetivo(self):
        if self.custo_unitario is not None:
            return self.custo_unitario
        return self.produto.preco_custo

    @property
    def custo_total(self):
        return (self.quantidade * self.custo_unitario_efetivo).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def abaixo_do_custo(self):
        return self.preco_unitario < self.custo_unitario_efetivo
