from django.db import models
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
            ultimo = Orcamento.objects.order_by('-id').first()
            self.numero = str((ultimo.id if ultimo else 0) + 1).zfill(6)
        super().save(*args, **kwargs)

    def recalcular_totais(self):
        self.subtotal_servicos = sum(i.total for i in self.itens_servico.all())
        self.subtotal_pecas = sum(i.total for i in self.itens_peca.all())
        base = self.subtotal_servicos + self.subtotal_pecas
        if self.desconto_percentual:
            self.desconto_valor = round(base * (self.desconto_percentual / 100), 2)
        self.total = base - self.desconto_valor + self.taxa_valor
        self.save(update_fields=['subtotal_servicos', 'subtotal_pecas', 'desconto_valor', 'total'])

    @property
    def esta_expirado(self):
        return self.data_validade < timezone.now().date() and self.status == 'enviado'

    @property
    def pode_editar(self):
        return self.status in ('rascunho', 'enviado')

    @property
    def pode_gerar_os(self):
        return self.status == 'aprovado' and not hasattr(self, 'ordem_servico')


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
