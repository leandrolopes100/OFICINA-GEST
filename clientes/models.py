from django.db import models


class Cliente(models.Model):
    TIPO_PESSOA = [
        ('F', 'Pessoa Física'),
        ('J', 'Pessoa Jurídica'),
    ]
    tipo_pessoa = models.CharField('Tipo', max_length=1, choices=TIPO_PESSOA, default='F')
    nome = models.CharField('Nome / Razão Social', max_length=200)
    cpf_cnpj = models.CharField('CPF / CNPJ', max_length=18, unique=True)
    rg_ie = models.CharField('RG / Insc. Estadual', max_length=30, blank=True)
    data_nascimento = models.DateField('Data de Nascimento', null=True, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField('Telefone', max_length=20)
    celular = models.CharField('Celular', max_length=20, blank=True)
    whatsapp = models.BooleanField('Tem WhatsApp?', default=True)
    cep = models.CharField('CEP', max_length=9, blank=True)
    logradouro = models.CharField('Logradouro', max_length=200, blank=True)
    numero = models.CharField('Número', max_length=10, blank=True)
    complemento = models.CharField('Complemento', max_length=100, blank=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True)
    estado = models.CharField('Estado', max_length=2, blank=True)
    observacoes = models.TextField('Observações', blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def endereco_completo(self):
        parts = [self.logradouro]
        if self.numero:
            parts.append(self.numero)
        if self.complemento:
            parts.append(self.complemento)
        if self.bairro:
            parts.append(self.bairro)
        if self.cidade:
            parts.append(f'{self.cidade}/{self.estado}')
        return ', '.join(filter(None, parts))
