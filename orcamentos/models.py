from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from clientes.models import Cliente
from veiculos.models import Veiculo
from estoque.models import Produto


class TipoServico(models.Model):
    nome = models.CharField('Nome', max_length=200)
    descricao = models.TextField('Descrição', blank=True)
    preco_padrao = models.DecimalField('Preço Padrão', max_digits=10, decimal_places=2, default=0)
    tempo_estimado = models.PositiveSmallIntegerField('Tempo Estimado (min)', default=60)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Tipo de Serviço'
        verbose_name_plural = 'Tipos de Serviço'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Orcamento(models.Model):
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('enviado', 'Enviado ao Cliente'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('expirado', 'Expirado'),
        ('cancelado', 'Cancelado'),
    ]
    numero = models.CharField('Número', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='orcamentos')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name='orcamentos')
    criado_por = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orcamentos_criados'
    )
    status = models.CharField('Status', max_length=10, choices=STATUS_CHOICES, default='rascunho')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_validade = models.DateField('Válido até')
    data_aprovacao = models.DateTimeField('Data de Aprovação', null=True, blank=True)
    km_entrada = models.PositiveIntegerField('KM na Entrada', default=0)
    subtotal_servicos = models.DecimalField('Subtotal Serviços', max_digits=10, decimal_places=2, default=0)
    subtotal_pecas = models.DecimalField('Subtotal Peças', max_digits=10, decimal_places=2, default=0)
    desconto_percentual = models.DecimalField('Desconto (%)', max_digits=5, decimal_places=2, default=0)
    desconto_valor = models.DecimalField('Desconto (R$)', max_digits=10, decimal_places=2, default=0)
    taxa_valor = models.DecimalField('Taxa / Acréscimo (R$)', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)
    observacoes = models.TextField('Observações', blank=True)
    condicoes = models.TextField('Condições / Garantia', blank=True)

    class Meta:
        verbose_name = 'Orçamento'
        verbose_name_plural = 'Orçamentos'
        ordering = ['-data_criacao']

    def __str__(self):
        return f'ORC-{self.numero}'

    def save(self, *args, **kwargs):
        if not self.numero:
            # Envolve a leitura do último ID e o INSERT numa transação para
            # evitar race condition na geração do número sequencial.
            with transaction.atomic():
                ultimo = Orcamento.objects.order_by('-id').first()
                self.numero = str((ultimo.id if ultimo else 0) + 1).zfill(6)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def recalcular_totais(self):
        # Usa agregação SQL para evitar N queries em listas grandes de itens
        subtotal_srv = self.itens_servico.aggregate(t=Sum('total'))['t'] or Decimal('0')
        subtotal_pca = self.itens_peca.aggregate(t=Sum('total'))['t'] or Decimal('0')
        self.subtotal_servicos = subtotal_srv
        self.subtotal_pecas = subtotal_pca
        base = subtotal_srv + subtotal_pca

        if self.desconto_percentual:
            # Percentual tem prioridade; recalcula o valor monetário
            self.desconto_valor = (
                base * self.desconto_percentual / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Garante que o total nunca fique negativo
        self.total = max(Decimal('0'), base - self.desconto_valor + self.taxa_valor)
        self.save(update_fields=['subtotal_servicos', 'subtotal_pecas', 'desconto_valor', 'total'])

    @property
    def esta_expirado(self):
        return self.data_validade < timezone.now().date() and self.status == 'enviado'

    @property
    def pode_editar(self):
        return self.status in ('rascunho', 'enviado')

    @property
    def pode_gerar_os(self):
        if self.status != 'aprovado':
            return False
        # Usa acesso direto ao descritor para aproveitar cache de prefetch
        # quando disponível, evitando query extra em listagens.
        try:
            _ = self.ordem_servico
            return False
        except ObjectDoesNotExist:
            return True


class ItemOrcamentoServico(models.Model):
    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='itens_servico')
    tipo_servico = models.ForeignKey(TipoServico, on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=300)
    quantidade = models.DecimalField('Quantidade', max_digits=6, decimal_places=2, default=1)
    preco_unitario = models.DecimalField('Preço Unitário', max_digits=10, decimal_places=2)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Item de Serviço'

    def save(self, *args, **kwargs):
        self.total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return self.descricao


class ItemOrcamentoPeca(models.Model):
    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='itens_peca')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=300)
    quantidade = models.DecimalField('Quantidade', max_digits=10, decimal_places=3)
    preco_unitario = models.DecimalField('Preço Unitário', max_digits=10, decimal_places=2)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Item de Peça'

    def save(self, *args, **kwargs):
        self.total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return self.descricao
