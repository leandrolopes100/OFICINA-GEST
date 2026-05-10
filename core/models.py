from django.db import models


class Historico(models.Model):
    TIPO_CHOICES = [
        ('criacao',   'Criação'),
        ('edicao',    'Edição'),
        ('status',    'Mudança de Status'),
        ('item_add',  'Item Adicionado'),
        ('item_rem',  'Item Removido'),
        ('pagamento', 'Pagamento Registrado'),
        ('entrega',   'Entrega'),
        ('os_gerada', 'OS Gerada'),
        ('outro',     'Outro'),
    ]
    # Exatamente um dos dois FKs estará preenchido
    orcamento = models.ForeignKey(
        'orcamentos.Orcamento',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='historico',
        verbose_name='Orçamento',
    )
    ordem_servico = models.ForeignKey(
        'ordens_servico.OrdemServico',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='historico',
        verbose_name='Ordem de Serviço',
    )
    tipo      = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default='outro')
    descricao = models.TextField('Descrição')
    usuario   = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='historico_registrado',
        verbose_name='Usuário',
    )
    criado_em = models.DateTimeField('Registrado em', auto_now_add=True)

    class Meta:
        verbose_name        = 'Histórico'
        verbose_name_plural = 'Histórico'
        ordering            = ['-criado_em']
        indexes             = [
            models.Index(fields=['orcamento',     'criado_em'], name='historico_orc_idx'),
            models.Index(fields=['ordem_servico', 'criado_em'], name='historico_os_idx'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.criado_em:%d/%m/%Y %H:%M}'
