import hashlib
import json
import secrets
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


class TransicaoStatusInvalida(Exception):
    pass


class LinkIndisponivel(Exception):
    pass


class ConteudoAlterado(Exception):
    pass


def _serializar_decimal(valor):
    if isinstance(valor, Decimal):
        return format(valor.normalize(), 'f')
    return str(valor)


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
    token_publico = models.CharField(
        'Token do link do cliente', max_length=64,
        unique=True, null=True, blank=True, editable=False,
    )
    link_gerado_em = models.DateTimeField('Link gerado em', null=True, blank=True, editable=False)

    STATUS_EM_ABERTO = frozenset({'rascunho', 'enviado'})
    STATUS_LINK_VISIVEL = frozenset({'enviado', 'aprovado', 'reprovado'})

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
    def validade_vencida(self):
        return self.data_validade < timezone.localdate()

    @property
    def esta_expirado(self):
        return self.status == 'enviado' and self.validade_vencida

    @property
    def pode_editar(self):
        return self.status in self.STATUS_EM_ABERTO

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

    def _transicionar(self, novo_status, permitidos, campos_extras=None):
        with transaction.atomic():
            travado = Orcamento.objects.select_for_update().get(pk=self.pk)
            if travado.status not in permitidos:
                raise TransicaoStatusInvalida(
                    f'O orçamento ORC-{travado.numero} está "{travado.get_status_display()}" '
                    f'e não pode passar para "{dict(self.STATUS_CHOICES)[novo_status]}".'
                )
            status_anterior = travado.get_status_display()
            travado.status = novo_status
            campos = ['status']
            for campo, valor in (campos_extras or {}).items():
                setattr(travado, campo, valor)
                campos.append(campo)
            travado.save(update_fields=campos)
        self.status = travado.status
        for campo in (campos_extras or {}):
            setattr(self, campo, getattr(travado, campo))
        return status_anterior

    def aprovar(self):
        return self._transicionar('aprovado', self.STATUS_EM_ABERTO,
                                  {'data_aprovacao': timezone.now()})

    def reprovar(self):
        return self._transicionar('reprovado', self.STATUS_EM_ABERTO)

    def marcar_enviado(self):
        return self._transicionar('enviado', self.STATUS_EM_ABERTO)

    def garantir_link_publico(self):
        Orcamento.objects.filter(pk=self.pk, token_publico__isnull=True).update(
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
    def link_visivel_ao_cliente(self):
        return bool(self.token_publico) and self.status in self.STATUS_LINK_VISIVEL

    @property
    def aceita_resposta_cliente(self):
        return self.status == 'enviado' and not self.validade_vencida

    def hash_conteudo(self):
        campos_item = ('pk', 'descricao', 'quantidade', 'preco_unitario', 'total')
        dados = {
            'cliente': self.cliente_id,
            'veiculo': self.veiculo_id,
            'servicos': list(self.itens_servico.order_by('pk').values_list(*campos_item)),
            'pecas': list(self.itens_peca.order_by('pk').values_list(*campos_item)),
            'desconto': self.desconto_valor,
            'taxa': self.taxa_valor,
            'total': self.total,
            'validade': self.data_validade,
            'observacoes': self.observacoes,
            'condicoes': self.condicoes,
        }
        bruto = json.dumps(dados, default=_serializar_decimal, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(bruto.encode('utf-8')).hexdigest()

    def registrar_resposta_cliente(self, *, decisao, nome, motivo, hash_visto, ip, user_agent):
        with transaction.atomic():
            travado = Orcamento.objects.select_for_update().get(pk=self.pk)
            if not travado.aceita_resposta_cliente:
                raise LinkIndisponivel
            if not secrets.compare_digest(travado.hash_conteudo(), hash_visto or ''):
                raise ConteudoAlterado
            resposta = RespostaCliente.objects.create(
                orcamento=travado,
                decisao=decisao,
                nome_informado=nome,
                motivo=motivo,
                total_no_momento=travado.total,
                hash_conteudo=hash_visto,
                ip=ip,
                user_agent=(user_agent or '')[:300],
            )
            if decisao == RespostaCliente.APROVADO:
                travado.aprovar()
            else:
                travado.reprovar()
        self.refresh_from_db(fields=['status', 'data_aprovacao'])
        return resposta


class RespostaCliente(models.Model):
    APROVADO = 'aprovado'
    RECUSADO = 'recusado'
    DECISAO_CHOICES = [
        (APROVADO, 'Aprovado pelo cliente'),
        (RECUSADO, 'Recusado pelo cliente'),
    ]
    orcamento = models.ForeignKey(
        Orcamento, on_delete=models.PROTECT,
        related_name='respostas_cliente', verbose_name='Orçamento',
    )
    decisao = models.CharField('Decisão', max_length=10, choices=DECISAO_CHOICES)
    nome_informado = models.CharField('Nome informado', max_length=150)
    motivo = models.TextField('Motivo', blank=True)
    total_no_momento = models.DecimalField('Total no momento da resposta', max_digits=10, decimal_places=2)
    hash_conteudo = models.CharField('Hash do conteúdo respondido', max_length=64)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.CharField('Navegador', max_length=300, blank=True)
    respondido_em = models.DateTimeField('Respondido em', auto_now_add=True)

    class Meta:
        verbose_name = 'Resposta do Cliente'
        verbose_name_plural = 'Respostas do Cliente'
        ordering = ['-respondido_em']

    def __str__(self):
        return f'{self.get_decisao_display()} — ORC-{self.orcamento.numero}'


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
