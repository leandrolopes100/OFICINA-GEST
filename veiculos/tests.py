from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from clientes.models import Cliente
from estoque.models import Produto
from orcamentos.models import TipoServico
from ordens_servico.models import ItemOSPeca, ItemOSServico, OrdemServico

from .models import Marca, Modelo, Veiculo


class BaseHistoricoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(
            username='atendente', password='senha-forte-123', role='recepcionista',
        )
        cls.cliente = Cliente.objects.create(
            nome='joão da silva', cpf_cnpj='529.982.247-25',
            telefone='(51) 3333-4444', celular='(51) 99876-5432',
        )
        marca = Marca.objects.create(nome='Volkswagen')
        modelo = Modelo.objects.create(marca=marca, nome='Gol')
        cls.veiculo = Veiculo.objects.create(
            cliente=cls.cliente, marca=marca, modelo=modelo,
            ano_fabricacao=2020, ano_modelo=2021, cor='Prata', placa='ABC1D23',
        )
        cls.outro_veiculo = Veiculo.objects.create(
            cliente=cls.cliente, marca=marca, modelo=modelo,
            ano_fabricacao=2018, ano_modelo=2018, cor='Preto', placa='XYZ9K87',
        )
        cls.tipo_servico = TipoServico.objects.create(nome='Freios', preco_padrao=Decimal('100'))
        cls.produto = Produto.objects.create(codigo='PF-01', nome='Pastilha', preco_venda=Decimal('50'))

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse('veiculos:detail', kwargs={'pk': self.veiculo.pk})

    def criar_ordem(self, status, dias_atras, km, veiculo=None, servico='Troca de pastilhas',
                    peca='Pastilha de freio', valor_servico='100'):
        ordem = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=veiculo or self.veiculo, status=status,
            defeito_relatado='Barulho ao frear', km_entrada=km,
        )
        OrdemServico.objects.filter(pk=ordem.pk).update(
            data_abertura=timezone.now() - timedelta(days=dias_atras)
        )
        ItemOSServico.objects.create(
            ordem_servico=ordem, tipo_servico=self.tipo_servico, descricao=servico,
            quantidade=Decimal('1'), preco_unitario=Decimal(valor_servico),
        )
        ItemOSPeca.objects.create(
            ordem_servico=ordem, produto=self.produto, descricao=peca,
            quantidade=Decimal('1.5'), preco_unitario=Decimal('50'),
        )
        ordem.recalcular_totais()
        return ordem


class HistoricoDoVeiculoTests(BaseHistoricoTestCase):
    def test_resumo_conta_visitas_sem_canceladas_e_soma_so_entregues(self):
        self.criar_ordem('entregue', 30, 70000)
        self.criar_ordem('entregue', 20, 75000, valor_servico='200')
        self.criar_ordem('concluida', 10, 80000)
        self.criar_ordem('cancelada', 5, 81000)

        historico = OrdemServico.historico_do_veiculo(self.veiculo)

        self.assertEqual(len(historico.ordens), 4)
        self.assertEqual(historico.visitas, 3)
        self.assertEqual(historico.total_entregue, Decimal('175') + Decimal('275'))

    def test_ultima_visita_ignora_cancelada(self):
        concluida = self.criar_ordem('concluida', 10, 80000)
        self.criar_ordem('cancelada', 1, 81000)

        historico = OrdemServico.historico_do_veiculo(self.veiculo)

        self.assertEqual(historico.ultima_visita.pk, concluida.pk)
        self.assertEqual(historico.ordens[0].status, 'cancelada')

    def test_veiculo_sem_os(self):
        historico = OrdemServico.historico_do_veiculo(self.veiculo)

        self.assertEqual(historico.ordens, [])
        self.assertEqual(historico.visitas, 0)
        self.assertEqual(historico.total_entregue, Decimal('0'))
        self.assertIsNone(historico.ultima_visita)

        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Nenhuma OS registrada para este veículo.')
        self.assertNotContains(resposta, 'id="busca-historico"')

    def test_nao_mistura_os_de_outro_veiculo(self):
        self.criar_ordem('entregue', 5, 50000, veiculo=self.outro_veiculo, servico='Alinhamento')

        historico = OrdemServico.historico_do_veiculo(self.veiculo)

        self.assertEqual(historico.ordens, [])
        self.assertNotContains(self.client.get(self.url), 'Alinhamento')

    def test_pagina_mostra_todas_as_os_com_servicos_e_pecas(self):
        for indice in range(12):
            self.criar_ordem('entregue', 100 - indice, 60000 + indice * 1000,
                             servico=f'Servico numero {indice}')

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        for indice in range(12):
            self.assertContains(resposta, f'Servico numero {indice}')
        self.assertContains(resposta, 'Pastilha de freio (1,500)')
        self.assertContains(resposta, 'Barulho ao frear')
        self.assertContains(resposta, 'id="busca-historico"')

    def test_numero_de_consultas_nao_cresce_com_o_historico(self):
        self.criar_ordem('entregue', 10, 70000)
        with CaptureQueriesContext(connection) as poucas:
            self.client.get(self.url)

        for indice in range(10):
            self.criar_ordem('entregue', 50 + indice, 50000)
        with CaptureQueriesContext(connection) as muitas:
            self.client.get(self.url)

        self.assertEqual(len(poucas.captured_queries), len(muitas.captured_queries))

    def test_texto_do_cliente_e_escapado(self):
        ordem = self.criar_ordem('aberta', 1, 1000)
        OrdemServico.objects.filter(pk=ordem.pk).update(defeito_relatado='<script>alert(1)</script>')

        resposta = self.client.get(self.url)

        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_exige_login(self):
        self.client.logout()

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 302)


class PdfHistoricoDoVeiculoTests(BaseHistoricoTestCase):
    def setUp(self):
        super().setUp()
        self.url_pdf = reverse('veiculos:historico_pdf', kwargs={'pk': self.veiculo.pk})
        self.dono_anterior = Cliente.objects.create(
            nome='Maria Souza', cpf_cnpj='111.444.777-35', telefone='(51) 3222-1111',
        )

    def texto_do_pdf(self):
        from unittest import mock
        from reportlab import rl_config

        with mock.patch.object(rl_config, 'pageCompression', 0):
            resposta = self.client.get(self.url_pdf)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta.content.startswith(b'%PDF'))
        return resposta.content.decode('latin-1')

    def criar_ordem_do_dono_anterior(self, **kwargs):
        ordem = self.criar_ordem('entregue', 400, 20000, **kwargs)
        OrdemServico.objects.filter(pk=ordem.pk).update(cliente=self.dono_anterior)
        return ordem

    def test_pdf_abre_com_nome_do_arquivo_pela_placa(self):
        self.criar_ordem('entregue', 10, 70000)

        resposta = self.client.get(self.url_pdf)

        self.assertEqual(resposta['Content-Disposition'], 'inline; filename="historico-ABC1D23.pdf"')

    def test_pdf_lista_servicos_e_total_do_dono_atual(self):
        self.criar_ordem('entregue', 10, 70000, servico='Troca de oleo')
        self.criar_ordem('entregue', 5, 75000, valor_servico='200')

        texto = self.texto_do_pdf()

        self.assertIn('Troca de oleo', texto)
        self.assertIn('Barulho ao frear', texto)
        self.assertIn('R$ 450,00', texto)
        self.assertIn('R$ 175,00', texto)

    def test_os_do_dono_anterior_sai_sem_nome_e_sem_valores(self):
        self.criar_ordem('entregue', 10, 70000)
        self.criar_ordem_do_dono_anterior(servico='Embreagem completa', valor_servico='777')

        texto = self.texto_do_pdf()

        self.assertIn('Embreagem completa', texto)
        self.assertIn('anterior', texto)
        self.assertNotIn('Maria Souza', texto)
        self.assertNotIn('R$ 777', texto)
        self.assertNotIn('R$ 852', texto)
        self.assertIn('R$ 175,00', texto)

    def test_cancelada_nao_aparece_no_pdf(self):
        self.criar_ordem('entregue', 10, 70000)
        self.criar_ordem('cancelada', 2, 71000, servico='Servico desistido')

        self.assertNotIn('Servico desistido', self.texto_do_pdf())

    def test_pdf_sem_os(self):
        self.assertIn('Nenhuma ordem de servi', self.texto_do_pdf())

    def test_pdf_escapa_marcacao(self):
        self.criar_ordem('entregue', 10, 70000, servico='<b>Freio</b> & cia')

        self.assertIn('Freio', self.texto_do_pdf())

    def test_pdf_exige_login(self):
        self.client.logout()

        self.assertEqual(self.client.get(self.url_pdf).status_code, 302)

    def test_ficha_mostra_botao_do_pdf(self):
        self.assertContains(self.client.get(self.url), self.url_pdf)


class UltimaVisitaNoFormularioTests(BaseHistoricoTestCase):
    def setUp(self):
        super().setUp()
        self.url_ajax = reverse('veiculos:por_cliente', kwargs={'cliente_pk': self.cliente.pk})

    def resultados(self):
        resposta = self.client.get(self.url_ajax)
        self.assertEqual(resposta.status_code, 200)
        return {item['id']: item for item in resposta.json()['results']}

    def test_ajax_traz_ultima_visita_ignorando_cancelada(self):
        self.criar_ordem('entregue', 30, 70000)
        recente = self.criar_ordem('concluida', 10, 85000)
        self.criar_ordem('cancelada', 1, 86000)

        visita = self.resultados()[self.veiculo.pk]['ultima_visita']

        self.assertEqual(visita['numero'], recente.numero)
        self.assertEqual(visita['km'], '85.000')
        self.assertEqual(visita['relatado'], 'Barulho ao frear')
        self.assertEqual(visita['url'], self.url)

    def test_ajax_sem_visita_e_sem_mistura_entre_veiculos(self):
        self.criar_ordem('entregue', 5, 50000, veiculo=self.outro_veiculo)

        resultados = self.resultados()

        self.assertIsNone(resultados[self.veiculo.pk]['ultima_visita'])
        self.assertIsNotNone(resultados[self.outro_veiculo.pk]['ultima_visita'])

    def test_ajax_relatado_longo_e_cortado(self):
        ordem = self.criar_ordem('entregue', 5, 50000)
        OrdemServico.objects.filter(pk=ordem.pk).update(defeito_relatado='x' * 500)

        self.assertLessEqual(len(self.resultados()[self.veiculo.pk]['ultima_visita']['relatado']), 120)

    def test_ajax_numero_de_consultas_fixo(self):
        self.criar_ordem('entregue', 5, 50000)
        with CaptureQueriesContext(connection) as poucas:
            self.client.get(self.url_ajax)

        for indice in range(5):
            self.criar_ordem('entregue', 10 + indice, 40000, veiculo=self.outro_veiculo)
        with CaptureQueriesContext(connection) as muitas:
            self.client.get(self.url_ajax)

        self.assertEqual(len(poucas.captured_queries), len(muitas.captured_queries))

    def test_aviso_so_no_formulario_de_os_nova(self):
        ordem = self.criar_ordem('aberta', 1, 1000)

        self.assertContains(self.client.get(reverse('ordens_servico:os_criar')), 'id="aviso-ultima-visita"')
        resposta_edicao = self.client.get(reverse('ordens_servico:os_editar', args=[ordem.pk]))
        self.assertEqual(resposta_edicao.status_code, 200)
        self.assertNotContains(resposta_edicao, 'id="aviso-ultima-visita"')
