from django.db import models
from clientes.models import Cliente


class Marca(models.Model):
    nome = models.CharField('Nome', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Modelo(models.Model):
    marca = models.ForeignKey(Marca, on_delete=models.CASCADE, related_name='modelos')
    nome = models.CharField('Nome', max_length=100)

    class Meta:
        verbose_name = 'Modelo'
        verbose_name_plural = 'Modelos'
        unique_together = ('marca', 'nome')
        ordering = ['nome']

    def __str__(self):
        return f'{self.marca} {self.nome}'


class Veiculo(models.Model):
    COMBUSTIVEL_CHOICES = [
        ('gasolina', 'Gasolina'),
        ('etanol', 'Etanol'),
        ('flex', 'Flex'),
        ('diesel', 'Diesel'),
        ('gnv', 'GNV'),
        ('eletrico', 'Elétrico'),
        ('hibrido', 'Híbrido'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='veiculos', verbose_name='Cliente')
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name='Marca')
    modelo = models.ForeignKey(Modelo, on_delete=models.PROTECT, verbose_name='Modelo')
    ano_fabricacao = models.PositiveSmallIntegerField('Ano de Fabricação')
    ano_modelo = models.PositiveSmallIntegerField('Ano do Modelo')
    cor = models.CharField('Cor', max_length=50)
    placa = models.CharField('Placa', max_length=8, unique=True)
    renavam = models.CharField('RENAVAM', max_length=11, blank=True)
    chassi = models.CharField('Chassi', max_length=17, blank=True)
    combustivel = models.CharField('Combustível', max_length=20, choices=COMBUSTIVEL_CHOICES, default='flex')
    km_atual = models.PositiveIntegerField('KM Atual', default=0)
    km_proxima_revisao = models.PositiveIntegerField('KM Próxima Revisão', null=True, blank=True)
    data_proxima_revisao = models.DateField('Data Próxima Revisão', null=True, blank=True)
    observacoes = models.TextField('Observações', blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'
        ordering = ['placa']

    def __str__(self):
        return f'{self.placa} — {self.modelo} ({self.ano_modelo})'
