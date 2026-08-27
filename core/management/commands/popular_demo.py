import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente
from veiculos.models import Veiculo, Modelo
from orcamentos.models import Orcamento, TipoServico, ItemOrcamentoServico
from ordens_servico.models import OrdemServico, ItemOSServico
from financeiro.models import Lancamento
from accounts.models import CustomUser

NOVOS_CLIENTES = [
    ('F', 'Bruno Tavares', '(51) 3211-4455', '(51) 99111-2233', 'Novo Hamburgo'),
    ('F', 'Camila Duarte', '(51) 3222-5566', '(51) 99222-3344', 'Sapucaia do Sul'),
    ('J', 'Distribuidora Rio Grande LTDA', '(51) 3233-6677', '', 'Esteio'),
    ('F', 'Diego Fontoura', '(51) 3244-7788', '(51) 99333-4455', 'Cachoeirinha'),
    ('F', 'Elisa Nogueira', '(51) 3255-8899', '(51) 99444-5566', 'Guaíba'),
    ('J', 'Transportadora Vale Verde LTDA', '(51) 3266-9900', '', 'Eldorado do Sul'),
    ('F', 'Felipe Rocha', '(51) 3277-0011', '(51) 99555-6677', 'Portão'),
    ('F', 'Gabriela Lins', '(51) 3288-1122', '(51) 99666-7788', 'Ivoti'),
    ('J', 'Comércio Santa Fé LTDA', '(51) 3299-2233', '', 'Dois Irmãos'),
    ('F', 'Henrique Barcelos', '(51) 3300-3344', '(51) 99777-8899', 'Nova Santa Rita'),
]

RUAS = ['Rua das Hortências', 'Rua Marechal Deodoro', 'Av. Getúlio Vargas', 'Rua Sete de Setembro',
        'Rua XV de Novembro', 'Av. Farrapos', 'Rua São Jorge', 'Rua Independência',
        'Av. Presidente Vargas', 'Rua Duque de Caxias']


def _dv_cpf(digitos):
    soma = sum(d * (len(digitos) + 1 - i) for i, d in enumerate(digitos))
    resto = (soma * 10) % 11
    return resto if resto < 10 else 0


def gerar_cpf(seed):
    base = [int(c) for c in f'{seed:09d}']
    dv1 = _dv_cpf(base)
    dv2 = _dv_cpf(base + [dv1])
    n = base + [dv1, dv2]
    s = ''.join(str(d) for d in n)
    return f'{s[0:3]}.{s[3:6]}.{s[6:9]}-{s[9:11]}'


def gerar_cnpj(seed):
    base = [int(c) for c in f'{seed:08d}'] + [0, 0, 0, 1]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(d * p for d, p in zip(base, pesos1))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    soma = sum(d * p for d, p in zip(base + [dv1], pesos2))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    n = base + [dv1, dv2]
    s = ''.join(str(d) for d in n)
    return f'{s[0:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:14]}'


def gerar_placa(indice):
    letras = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(3))
    return f'{letras}{1000 + indice}'


class Command(BaseCommand):
    help = 'Popula dados de demonstração: clientes, OS em aberto, orçamentos pendentes e faturamento do mês'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        mecanico = CustomUser.objects.filter(role='mecanico').first()
        admin = CustomUser.objects.filter(role='admin').first()
        criado_por = admin or mecanico

        with transaction.atomic():
            clientes_novos = self._criar_clientes()
            veiculos_novos = self._criar_veiculos(clientes_novos)
            self._completar_os_abertas(clientes_novos, veiculos_novos, mecanico, criado_por)
            self._completar_orcamentos_pendentes(clientes_novos, veiculos_novos, criado_por, hoje)
            self._completar_faturamento_mes(hoje)

        self.stdout.write(self.style.SUCCESS('\nDados de demonstração populados com sucesso.'))

    def _criar_clientes(self):
        criados = []
        seed_cpf = 100000000
        seed_cnpj = 10000000
        for i, (tipo, nome, tel, cel, cidade) in enumerate(NOVOS_CLIENTES):
            if tipo == 'F':
                doc = gerar_cpf(seed_cpf + i * 37)
            else:
                doc = gerar_cnpj(seed_cnpj + i * 53)
            cliente, criado = Cliente.objects.get_or_create(
                cpf_cnpj=doc,
                defaults=dict(
                    tipo_pessoa=tipo,
                    nome=nome,
                    telefone=tel,
                    celular=cel,
                    whatsapp=bool(cel),
                    email=f'{nome.split()[0].lower()}@email.com',
                    cep='93000-000',
                    logradouro=RUAS[i % len(RUAS)],
                    numero=str(100 + i * 11),
                    bairro='Centro',
                    cidade=cidade,
                    estado='RS',
                    ativo=True,
                ),
            )
            criados.append(cliente)
            if criado:
                self.stdout.write(f'  + Cliente: {cliente.nome}')
        return criados

    def _criar_veiculos(self, clientes):
        modelos = list(Modelo.objects.select_related('marca').all())
        cores = ['Prata', 'Preto', 'Branco', 'Vermelho', 'Cinza']
        criados = []
        for i, cliente in enumerate(clientes[:6]):
            modelo = random.choice(modelos)
            placa = gerar_placa(i)
            while Veiculo.objects.filter(placa=placa).exists():
                placa = gerar_placa(i + random.randint(1, 99))
            veiculo = Veiculo.objects.create(
                cliente=cliente,
                marca=modelo.marca,
                modelo=modelo,
                ano_fabricacao=2018 + (i % 6),
                ano_modelo=2019 + (i % 6),
                cor=random.choice(cores),
                placa=placa,
                combustivel='flex',
                km_atual=random.randint(15000, 120000),
                ativo=True,
            )
            criados.append(veiculo)
            self.stdout.write(f'  + Veículo: {veiculo.placa} ({cliente.nome})')
        return criados

    def _completar_os_abertas(self, clientes_novos, veiculos_novos, mecanico, criado_por):
        alvo = 9
        atuais = OrdemServico.objects.filter(
            status__in=['aberta', 'em_andamento', 'aguardando']
        ).count()
        faltam = max(0, alvo - atuais)

        tipo_servico = TipoServico.objects.filter(ativo=True).first()
        pool_clientes = clientes_novos + [v.cliente for v in veiculos_novos]
        pool_veiculos = veiculos_novos + list(Veiculo.objects.exclude(id__in=[v.id for v in veiculos_novos]))

        for i in range(faltam):
            veiculo = pool_veiculos[i % len(pool_veiculos)]
            os_nova = OrdemServico.objects.create(
                cliente=veiculo.cliente,
                veiculo=veiculo,
                mecanico=mecanico,
                criado_por=criado_por,
                status='aberta',
                data_previsao=timezone.now().date() + timedelta(days=random.randint(1, 5)),
                km_entrada=veiculo.km_atual,
                defeito_relatado='Cliente relata ruído e revisão pendente.',
            )
            if tipo_servico:
                ItemOSServico.objects.create(
                    ordem_servico=os_nova,
                    tipo_servico=tipo_servico,
                    descricao=tipo_servico.nome,
                    quantidade=1,
                    preco_unitario=Decimal(random.choice([180, 220, 250, 300, 350])),
                )
                os_nova.recalcular_totais()
            self.stdout.write(f'  + OS aberta: {os_nova.numero} ({veiculo.cliente.nome})')

    def _completar_orcamentos_pendentes(self, clientes_novos, veiculos_novos, criado_por, hoje):
        alvo = 4
        atuais = Orcamento.objects.filter(status__in=['rascunho', 'enviado']).count()
        faltam = max(0, alvo - atuais)

        tipo_servico = TipoServico.objects.filter(ativo=True).first()
        pool_veiculos = veiculos_novos or list(Veiculo.objects.all())
        status_ciclo = ['rascunho', 'enviado']

        for i in range(faltam):
            veiculo = pool_veiculos[i % len(pool_veiculos)]
            orc = Orcamento.objects.create(
                cliente=veiculo.cliente,
                veiculo=veiculo,
                criado_por=criado_por,
                status=status_ciclo[i % len(status_ciclo)],
                data_validade=hoje + timedelta(days=15),
                km_entrada=veiculo.km_atual,
            )
            if tipo_servico:
                ItemOrcamentoServico.objects.create(
                    orcamento=orc,
                    tipo_servico=tipo_servico,
                    descricao=tipo_servico.nome,
                    quantidade=1,
                    preco_unitario=Decimal(random.choice([250, 320, 400, 480])),
                )
                orc.recalcular_totais()
            self.stdout.write(f'  + Orçamento pendente: {orc.numero} ({veiculo.cliente.nome})')

    def _completar_faturamento_mes(self, hoje):
        from django.db.models import Sum
        alvo = Decimal('56000')
        atual = Lancamento.objects.filter(
            tipo='receita', status='pago',
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        falta = alvo - atual
        if falta <= 0:
            self.stdout.write('  Faturamento do mês já atinge a meta de R$ 56.000,00.')
            return

        primeiro_dia = hoje.replace(day=1)
        n_lancamentos = 6
        valores = []
        restante = falta
        for i in range(n_lancamentos - 1):
            parte = (restante / (n_lancamentos - i)).quantize(Decimal('1'))
            valores.append(parte)
            restante -= parte
        valores.append(restante)

        for i, valor in enumerate(valores):
            dia_max = max((hoje - primeiro_dia).days, 0)
            dia = primeiro_dia + timedelta(days=random.randint(0, dia_max))
            Lancamento.objects.create(
                tipo='receita',
                categoria='servico',
                descricao=f'Recebimento de serviços — lote demo {i + 1}',
                valor=valor,
                data_competencia=dia,
                data_pagamento=dia,
                status='pago',
            )
            self.stdout.write(f'  + Lançamento: R$ {valor} em {dia}')
