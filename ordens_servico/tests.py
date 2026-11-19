from datetime import timedelta
from decimal import Decimal
from urllib.parse import unquote

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from clientes.models import Cliente
from core.models import Historico
from estoque.models import Produto
from orcamentos.models import TipoServico
from veiculos.models import Marca, Modelo, Veiculo

from .models import ItemOSPeca, ItemOSServico, OrdemServico


class BaseOrdemTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(
            username='atendente', password='senha-forte-123', role='admin',
        )
        cls.cliente = Cliente.objects.create(
            nome='joão da silva', cpf_cnpj='529.982.247-25',
            telefone='(51) 3333-4444', celular='(51) 99876-5432', whatsapp=True,
        )
        marca = Marca.objects.create(nome='Volkswagen')
        modelo = Modelo.objects.create(marca=marca, nome='Gol')
        cls.veiculo = Veiculo.objects.create(
            cliente=cls.cliente, marca=marca, modelo=modelo,
            ano_fabricacao=2020, ano_modelo=2021, cor='Prata', placa='ABC1D23',
        )
        cls.tipo_servico = TipoServico.objects.create(nome='Troca de óleo', preco_padrao=Decimal('80'))
        cls.produto = Produto.objects.create(codigo='OL-01', nome='Óleo 5W30', preco_venda=Decimal('45'))

    def setUp(self):
        cache.clear()

    def criar_ordem(self, status='em_andamento', com_link=True, **campos):
        ordem = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, criado_por=self.usuario,
            status=status, defeito_relatado='Barulho no motor',
            diagnostico='Texto interno do mecânico', **campos,
        )
        ItemOSServico.objects.create(
            ordem_servico=ordem, tipo_servico=self.tipo_servico,
            descricao='Troca de óleo', quantidade=Decimal('1'), preco_unitario=Decimal('80'),
        )
        ItemOSPeca.objects.create(
            ordem_servico=ordem, produto=self.produto,
            descricao='Óleo 5W30', quantidade=Decimal('4'), preco_unitario=Decimal('45'),
        )
        ordem.recalcular_totais()
        if com_link:
            ordem.garantir_link_publico()
        return OrdemServico.objects.get(pk=ordem.pk)

    def url_publica(self, ordem):
        return reverse('acompanhamento_publico:detalhe', kwargs={'token': ordem.token_publico})


class LinkPublicoModelTests(BaseOrdemTestCase):
    def test_garantir_link_nao_troca_token_existente(self):
        ordem = self.criar_ordem()
        token = ordem.token_publico
        self.assertEqual(ordem.garantir_link_publico(), token)
        self.assertGreaterEqual(len(token), 32)

    def test_regenerar_troca_token(self):
        ordem = self.criar_ordem()
        token = ordem.token_publico
        self.assertNotEqual(ordem.regenerar_link_publico(), token)

    def test_sem_token_nao_e_visivel(self):
        self.assertFalse(self.criar_ordem(com_link=False).link_visivel_ao_cliente)

    def test_os_em_aberto_sempre_visivel(self):
        for status in ('aberta', 'em_andamento', 'aguardando', 'concluida'):
            ordem = self.criar_ordem(status=status)
            self.assertTrue(ordem.link_visivel_ao_cliente, status)
            self.assertIsNone(ordem.link_expira_em)

    def test_entregue_visivel_ate_30_dias(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=29))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=40))
        ordem.refresh_from_db()
        self.assertTrue(ordem.link_visivel_ao_cliente)

    def test_entregue_ha_mais_de_30_dias_expira(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=31))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=40))
        ordem.refresh_from_db()
        self.assertFalse(ordem.link_visivel_ao_cliente)

    def test_novo_link_apos_expirar_vale_mais_30_dias(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=60))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=60))
        ordem.refresh_from_db()
        ordem.regenerar_link_publico()
        self.assertTrue(ordem.link_visivel_ao_cliente)

    def test_cancelada_sem_data_e_sem_link_gerado_nao_e_visivel(self):
        ordem = self.criar_ordem(status='cancelada')
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=None)
        ordem.refresh_from_db()
        self.assertFalse(ordem.link_visivel_ao_cliente)

    def test_registrar_mudanca_status_preenche_datas(self):
        ordem = self.criar_ordem(status='aberta')
        ordem.registrar_mudanca_status('cancelada')
        self.assertEqual(ordem.status, 'cancelada')
        self.assertIsNotNone(ordem.data_cancelamento)

    def test_etapas_ocultam_aguardando_quando_nao_e_o_status(self):
        ordem = self.criar_ordem(status='em_andamento')
        rotulos = [etapa['rotulo'] for etapa in ordem.etapas_acompanhamento]
        self.assertNotIn('Aguardando peça/aprovação', rotulos)
        atual = [etapa['rotulo'] for etapa in ordem.etapas_acompanhamento if etapa['atual']]
        self.assertEqual(atual, ['Em serviço'])

    def test_etapas_mostram_aguardando_quando_e_o_status(self):
        ordem = self.criar_ordem(status='aguardando')
        etapas = ordem.etapas_acompanhamento
        self.assertEqual(len(etapas), 5)
        self.assertEqual([e['concluida'] for e in etapas], [True, True, False, False, False])


class PaginaPublicaTests(BaseOrdemTestCase):
    def test_mostra_status_itens_e_total_sem_diagnostico(self):
        ordem = self.criar_ordem(status='em_andamento')
        resposta = self.client.get(self.url_publica(ordem))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'OS-{ordem.numero}')
        self.assertContains(resposta, 'Em serviço')
        self.assertContains(resposta, 'Óleo 5W30')
        self.assertContains(resposta, 'Barulho no motor')
        self.assertContains(resposta, '260,00')
        self.assertNotContains(resposta, 'Texto interno do mecânico')
        self.assertEqual(resposta['Cache-Control'], 'no-store')
        self.assertEqual(resposta['X-Robots-Tag'], 'noindex, nofollow')

    def test_concluida_mostra_pronto_para_retirada(self):
        ordem = self.criar_ordem(status='concluida')
        self.assertContains(self.client.get(self.url_publica(ordem)), 'pronto para retirada')

    def test_cancelada_recente_mostra_aviso(self):
        ordem = self.criar_ordem(status='cancelada', data_cancelamento=timezone.now())
        self.assertContains(self.client.get(self.url_publica(ordem)), 'Este serviço foi cancelado')

    def test_link_expirado_retorna_410(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=31))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=40))
        resposta = self.client.get(self.url_publica(ordem))
        self.assertEqual(resposta.status_code, 410)
        self.assertNotContains(resposta, 'Óleo 5W30', status_code=410)

    def test_token_inexistente_retorna_404(self):
        resposta = self.client.get(
            reverse('acompanhamento_publico:detalhe', kwargs={'token': 'x' * 43})
        )
        self.assertEqual(resposta.status_code, 404)

    def test_token_antigo_deixa_de_funcionar(self):
        ordem = self.criar_ordem()
        url_antiga = self.url_publica(ordem)
        ordem.regenerar_link_publico()
        self.assertEqual(self.client.get(url_antiga).status_code, 404)

    def test_limite_de_requisicoes(self):
        ordem = self.criar_ordem()
        for _ in range(60):
            self.client.get(self.url_publica(ordem))
        self.assertEqual(self.client.get(self.url_publica(ordem)).status_code, 429)


class EnvioWhatsAppTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def enviar(self, ordem, tipo):
        return self.client.post(reverse('ordens_servico:os_enviar_whatsapp', args=[ordem.pk, tipo]))

    def test_acompanhamento_gera_link_registra_historico_e_redireciona(self):
        ordem = self.criar_ordem(com_link=False)
        resposta = self.enviar(ordem, 'acompanhamento')
        ordem.refresh_from_db()
        self.assertIsNotNone(ordem.token_publico)
        self.assertTrue(resposta['Location'].startswith('https://wa.me/5551998765432?text='))
        texto = unquote(resposta['Location'])
        self.assertIn('Olá, João!', texto)
        self.assertIn('Situação atual: Em serviço', texto)
        self.assertIn(self.url_publica(ordem), texto)
        self.assertTrue(Historico.objects.filter(
            ordem_servico=ordem, descricao__startswith='Link de acompanhamento enviado',
        ).exists())

    def test_pronto_so_com_os_concluida(self):
        ordem = self.criar_ordem(status='em_andamento', com_link=False)
        resposta = self.enviar(ordem, 'pronto')
        self.assertRedirects(resposta, reverse('ordens_servico:os_detalhe', args=[ordem.pk]))
        ordem.refresh_from_db()
        self.assertIsNone(ordem.token_publico)

    def test_pronto_com_os_concluida_inclui_total(self):
        ordem = self.criar_ordem(status='concluida')
        texto = unquote(self.enviar(ordem, 'pronto')['Location'])
        self.assertIn('está pronto para retirada', texto)
        self.assertIn('260,00', texto)

    def test_cancelada_bloqueia_envio(self):
        ordem = self.criar_ordem(status='cancelada', com_link=False)
        resposta = self.enviar(ordem, 'acompanhamento')
        self.assertRedirects(resposta, reverse('ordens_servico:os_detalhe', args=[ordem.pk]))

    def test_cliente_sem_whatsapp_bloqueia_envio(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(whatsapp=False)
        ordem = self.criar_ordem(com_link=False)
        resposta = self.enviar(ordem, 'acompanhamento')
        self.assertRedirects(resposta, reverse('ordens_servico:os_detalhe', args=[ordem.pk]))

    def test_tipo_invalido_volta_para_detalhe(self):
        ordem = self.criar_ordem()
        resposta = self.enviar(ordem, 'qualquer')
        self.assertRedirects(resposta, reverse('ordens_servico:os_detalhe', args=[ordem.pk]))

    def test_exige_login(self):
        self.client.logout()
        ordem = self.criar_ordem(com_link=False)
        self.assertEqual(self.enviar(ordem, 'acompanhamento').status_code, 302)
        ordem.refresh_from_db()
        self.assertIsNone(ordem.token_publico)

    def test_novo_link_invalida_anterior(self):
        ordem = self.criar_ordem()
        token = ordem.token_publico
        self.client.post(reverse('ordens_servico:os_novo_link', args=[ordem.pk]))
        ordem.refresh_from_db()
        self.assertNotEqual(ordem.token_publico, token)

    def test_detalhe_mostra_link_e_botoes(self):
        ordem = self.criar_ordem(status='concluida')
        resposta = self.client.get(reverse('ordens_servico:os_detalhe', args=[ordem.pk]))
        self.assertContains(resposta, self.url_publica(ordem))
        self.assertContains(resposta, 'Avisar que está pronto')
        self.assertContains(resposta, 'Enviar acompanhamento')


class DataCancelamentoTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_cancelar_os_grava_data(self):
        ordem = self.criar_ordem(status='aberta')
        self.client.post(reverse('ordens_servico:os_cancelar', args=[ordem.pk]))
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, 'cancelada')
        self.assertIsNotNone(ordem.data_cancelamento)

    def test_cancelar_pelo_status_grava_data(self):
        ordem = self.criar_ordem(status='aberta')
        self.client.post(reverse('ordens_servico:os_status', args=[ordem.pk]), {'status': 'cancelada'})
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, 'cancelada')
        self.assertIsNotNone(ordem.data_cancelamento)


class PrecoNasListasDeSelecaoTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_telas_carregam_a_exibicao_de_preco(self):
        ordem = self.criar_ordem()
        urls = [
            reverse('orcamentos:create'),
            reverse('ordens_servico:os_criar'),
            reverse('ordens_servico:os_editar', args=[ordem.pk]),
            reverse('ordens_servico:os_detalhe', args=[ordem.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'window.select2OpcaoComPreco', count=1)
                self.assertContains(resposta, 'templateResult: select2OpcaoComPreco(')


class PreviaDoLinkTests(BaseOrdemTestCase):
    def tags_og(self, html):
        import re
        return re.findall(r'<meta property="og:[^"]+" content="([^"]*)"', html)

    def test_acompanhamento_tem_previa_sem_dados_do_cliente(self):
        ordem = self.criar_ordem()
        html = self.client.get(self.url_publica(ordem), secure=True).content.decode()
        conteudos = ' | '.join(self.tags_og(html))
        self.assertIn(f'Acompanhamento OS-{ordem.numero}', conteudos)
        self.assertIn('https://testserver/static/og-acompanhamento.png', conteudos)
        for dado in ('ABC1D23', '260', 'João', 'Barulho'):
            self.assertNotIn(dado, conteudos)

    def test_orcamento_tem_previa_sem_dados_do_cliente(self):
        from orcamentos.tests import BaseOrcamentoTestCase
        caso = BaseOrcamentoTestCase
        orcamento = caso.criar_orcamento(self)
        html = self.client.get(
            reverse('orcamento_publico:detalhe', kwargs={'token': orcamento.token_publico}), secure=True,
        ).content.decode()
        conteudos = ' | '.join(self.tags_og(html))
        self.assertIn(f'Orçamento ORC-{orcamento.numero}', conteudos)
        self.assertIn('https://testserver/static/og-orcamento.png', conteudos)
        for dado in ('ABC1D23', '260', 'João'):
            self.assertNotIn(dado, conteudos)


class FiltroListaOrdensTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        outro_cliente = Cliente.objects.create(nome='Maria Souza', cpf_cnpj='111.444.777-35')
        outro_veiculo = Veiculo.objects.create(
            cliente=outro_cliente, marca=self.veiculo.marca, modelo=self.veiculo.modelo,
            ano_fabricacao=2019, ano_modelo=2019, cor='Preto', placa='XYZ9876',
        )
        self.os_outubro = self.criar_ordem(com_link=False)
        self.os_novembro = self.criar_ordem(com_link=False)
        self.os_maria = OrdemServico.objects.create(
            cliente=outro_cliente, veiculo=outro_veiculo, criado_por=self.usuario,
            status='em_andamento', defeito_relatado='Freio',
        )
        self.definir_abertura(self.os_outubro, 2026, 10, 15)
        self.definir_abertura(self.os_novembro, 2026, 11, 10)
        self.definir_abertura(self.os_maria, 2026, 11, 12)

    def definir_abertura(self, ordem, ano, mes, dia, hora=12):
        momento = timezone.make_aware(timezone.datetime(ano, mes, dia, hora, 0))
        OrdemServico.objects.filter(pk=ordem.pk).update(data_abertura=momento)

    def listar(self, **params):
        resposta = self.client.get(reverse('ordens_servico:os_lista'), params)
        self.assertEqual(resposta.status_code, 200)
        return {o.pk for o in resposta.context['ordens']}

    def test_periodo_filtra_pela_data_de_abertura(self):
        self.assertEqual(
            self.listar(de='2026-11-01', ate='2026-11-30'),
            {self.os_novembro.pk, self.os_maria.pk},
        )

    def test_ate_inclui_o_dia_inteiro(self):
        self.definir_abertura(self.os_novembro, 2026, 11, 10, hora=23)
        self.assertIn(self.os_novembro.pk, self.listar(ate='2026-11-10'))

    def test_so_um_dos_lados(self):
        self.assertEqual(self.listar(de='2026-11-11'), {self.os_maria.pk})
        self.assertEqual(self.listar(ate='2026-10-31'), {self.os_outubro.pk})

    def test_periodo_invertido_e_desinvertido(self):
        self.assertEqual(
            self.listar(de='2026-11-30', ate='2026-11-01'),
            {self.os_novembro.pk, self.os_maria.pk},
        )

    def test_data_invalida_e_ignorada(self):
        self.assertEqual(len(self.listar(de='31/02/2026', ate='lixo')), 3)

    def test_busca_por_placa_com_ou_sem_hifen(self):
        esperado = {self.os_maria.pk}
        self.assertEqual(self.listar(q='XYZ9876'), esperado)
        self.assertEqual(self.listar(q='xyz-9876'), esperado)

    def test_busca_por_numero_com_prefixo(self):
        self.assertEqual(self.listar(q=f'OS-{self.os_outubro.numero}'), {self.os_outubro.pk})

    def test_periodo_combinado_com_busca_e_status(self):
        OrdemServico.objects.filter(pk=self.os_outubro.pk).update(status='entregue')
        self.assertEqual(
            self.listar(q='joão', status='em_andamento', de='2026-10-01', ate='2026-11-30'),
            {self.os_novembro.pk},
        )

    def test_paginacao_preserva_filtros(self):
        for _ in range(20):
            nova = self.criar_ordem(com_link=False)
            self.definir_abertura(nova, 2026, 11, 5)
        resposta = self.client.get(
            reverse('ordens_servico:os_lista'), {'q': 'joão', 'de': '2026-11-01', 'status': 'abertas'},
        )
        self.assertContains(resposta, 'href="?q=jo%C3%A3o&amp;de=2026-11-01&amp;status=abertas&amp;page=2"')
