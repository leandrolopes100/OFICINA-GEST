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


class EnvioPdfTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def url_pdf(self, ordem):
        return reverse('acompanhamento_publico:pdf', kwargs={'token': ordem.token_publico})

    def url_documento(self, ordem):
        return reverse('acompanhamento_publico:documento', kwargs={'token': ordem.token_publico})

    def test_envio_gera_link_do_pdf_e_registra_historico(self):
        ordem = self.criar_ordem(com_link=False)
        resposta = self.client.post(reverse('ordens_servico:os_enviar_whatsapp', args=[ordem.pk, 'pdf']))
        ordem.refresh_from_db()
        self.assertTrue(resposta['Location'].startswith('https://wa.me/5551998765432?text='))
        texto = unquote(resposta['Location'])
        self.assertIn(f'Segue a ordem de serviço OS-{ordem.numero}', texto)
        self.assertIn('260,00', texto)
        self.assertIn(self.url_documento(ordem), texto)
        self.assertTrue(Historico.objects.filter(
            ordem_servico=ordem, descricao__startswith='PDF da OS enviado pelo WhatsApp',
        ).exists())

    def test_cancelada_bloqueia_envio_do_pdf(self):
        ordem = self.criar_ordem(status='cancelada', com_link=False)
        resposta = self.client.post(reverse('ordens_servico:os_enviar_whatsapp', args=[ordem.pk, 'pdf']))
        self.assertRedirects(resposta, reverse('ordens_servico:os_detalhe', args=[ordem.pk]))

    def test_pdf_publico_abre_sem_login(self):
        self.client.logout()
        ordem = self.criar_ordem()
        resposta = self.client.get(self.url_pdf(ordem))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta.content.startswith(b'%PDF'))
        self.assertEqual(resposta['Cache-Control'], 'no-store')

    def test_pagina_do_pdf_tem_previa_e_botoes_sem_dados_do_cliente(self):
        import re
        self.client.logout()
        ordem = self.criar_ordem()
        resposta = self.client.get(self.url_documento(ordem), secure=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.url_pdf(ordem))
        self.assertContains(resposta, f'{self.url_pdf(ordem)}?baixar=1')
        self.assertContains(resposta, '260,00')
        self.assertNotContains(resposta, 'Texto interno do mecânico')
        html = resposta.content.decode()
        conteudos = ' | '.join(re.findall(r'<meta property="og:[^"]+" content="([^"]*)"', html))
        self.assertIn(f'Ordem de serviço OS-{ordem.numero}', conteudos)
        self.assertIn('https://testserver/static/og-os.png', conteudos)
        for dado in ('ABC1D23', '260', 'João', 'Barulho'):
            self.assertNotIn(dado, conteudos)

    def test_pagina_do_pdf_com_link_expirado_retorna_410(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=31))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=40))
        self.assertEqual(self.client.get(self.url_documento(ordem)).status_code, 410)

    def test_pdf_publico_baixar_vem_como_anexo(self):
        ordem = self.criar_ordem()
        resposta = self.client.get(self.url_pdf(ordem) + '?baixar=1')
        self.assertEqual(resposta['Content-Disposition'], f'attachment; filename="OS-{ordem.numero}.pdf"')

    def test_texto_com_marcacao_aparece_literal_e_nao_quebra_os_pdfs(self):
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph
        from core.pdf import texto_seguro
        from orcamentos.pdf import gerar_pdf_orcamento
        from orcamentos.tests import BaseOrcamentoTestCase
        from .pdf import gerar_pdf_os

        texto = 'luz <b>acesa & barulho <forte>\r\nsegunda linha'
        paragrafo = Paragraph(texto_seguro(texto), getSampleStyleSheet()['Normal'])
        self.assertEqual(paragrafo.getPlainText(), 'luz <b>acesa & barulho <forte>segunda linha')
        self.assertIn('&lt;forte&gt;<br/>segunda', texto_seguro(texto))

        ordem = self.criar_ordem()
        OrdemServico.objects.filter(pk=ordem.pk).update(defeito_relatado=texto, diagnostico=texto)
        ordem.refresh_from_db()
        self.assertTrue(gerar_pdf_os(ordem).startswith(b'%PDF'))

        orcamento = BaseOrcamentoTestCase.criar_orcamento(self)
        orcamento.observacoes = texto
        orcamento.condicoes = texto
        self.assertTrue(gerar_pdf_orcamento(orcamento).startswith(b'%PDF'))

    def test_pdf_do_cliente_nao_traz_diagnostico(self):
        from .pdf import gerar_pdf_os
        ordem = self.criar_ordem()
        self.assertGreater(len(gerar_pdf_os(ordem)), len(gerar_pdf_os(ordem, para_cliente=True)))

    def test_pdf_publico_com_link_expirado_retorna_404(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now() - timedelta(days=31))
        OrdemServico.objects.filter(pk=ordem.pk).update(link_gerado_em=timezone.now() - timedelta(days=40))
        self.assertEqual(self.client.get(self.url_pdf(ordem)).status_code, 404)

    def test_pdf_publico_token_inexistente_retorna_404(self):
        url = reverse('acompanhamento_publico:pdf', kwargs={'token': 'x' * 43})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_lista_mostra_botao_de_envio_do_pdf(self):
        ordem = self.criar_ordem()
        resposta = self.client.get(reverse('ordens_servico:os_lista'))
        self.assertContains(resposta, reverse('ordens_servico:os_enviar_whatsapp', args=[ordem.pk, 'pdf']))

    def test_lista_desabilita_botao_quando_cliente_sem_whatsapp(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(whatsapp=False)
        ordem = self.criar_ordem()
        resposta = self.client.get(reverse('ordens_servico:os_lista'))
        self.assertNotContains(resposta, reverse('ordens_servico:os_enviar_whatsapp', args=[ordem.pk, 'pdf']))
        self.assertContains(resposta, 'sem WhatsApp')


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


class OrdemDaListaTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def criar(self, status, dias_atras, pago=False):
        from financeiro.models import Lancamento
        ordem = self.criar_ordem(status=status, com_link=False)
        OrdemServico.objects.filter(pk=ordem.pk).update(
            data_abertura=timezone.now() - timedelta(days=dias_atras),
        )
        if pago:
            Lancamento.objects.create(
                tipo='receita', categoria='servico', ordem_servico=ordem, descricao='x',
                valor=ordem.total, data_competencia=timezone.localdate(),
                data_pagamento=timezone.localdate(), status='pago',
            )
        return ordem

    def listar(self, **params):
        resposta = self.client.get(reverse('ordens_servico:os_lista'), params)
        self.assertEqual(resposta.status_code, 200)
        return [o.pk for o in resposta.context['ordens']]

    def test_pendentes_ficam_acima_mesmo_quando_mais_antigas(self):
        entregue_paga = self.criar('entregue', 1, pago=True)
        cancelada = self.criar('cancelada', 2)
        aberta = self.criar('aberta', 30)
        andamento = self.criar('em_andamento', 40)
        aguardando = self.criar('aguardando', 45)
        pronta = self.criar('concluida', 50)
        entregue_a_receber = self.criar('entregue', 60)
        self.assertEqual(
            self.listar(),
            [aberta.pk, andamento.pk, aguardando.pk, pronta.pk, entregue_a_receber.pk,
             entregue_paga.pk, cancelada.pk],
        )

    def test_pendentes_ocupam_a_primeira_pagina(self):
        for dias in range(1, 21):
            self.criar('entregue', dias, pago=True)
        antiga_aberta = self.criar('aberta', 365)
        self.assertEqual(self.listar()[0], antiga_aberta.pk)
        self.assertNotIn(antiga_aberta.pk, self.listar(page=2))

    def test_filtro_de_status_continua_funcionando(self):
        self.criar('aberta', 1)
        entregue_paga = self.criar('entregue', 2, pago=True)
        self.assertEqual(self.listar(status='entregue'), [entregue_paga.pk])


class CustoELucroDaOSTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('20'), estoque_atual=Decimal('50'))

    def concluir(self, ordem):
        return self.client.post(reverse('ordens_servico:os_status', args=[ordem.pk]), {'status': 'concluida'})

    def receber(self, ordem, valor, taxa=Decimal('0')):
        from financeiro.models import Lancamento
        return Lancamento.objects.create(
            tipo='receita', categoria='servico', ordem_servico=ordem, descricao=f'OS-{ordem.numero}',
            valor=valor, valor_taxa=taxa, data_competencia=timezone.localdate(),
            data_pagamento=timezone.localdate(), status='pago',
        )

    def test_conclusao_congela_custo_e_liga_saida_a_os(self):
        from estoque.models import MovimentacaoEstoque
        ordem = self.criar_ordem(status='em_andamento')
        self.concluir(ordem)
        item = ordem.itens_peca.get()
        self.assertEqual(item.custo_unitario, Decimal('20.00'))
        self.assertFalse(item.custo_estimado)
        saida = MovimentacaoEstoque.objects.get(tipo='saida', produto=self.produto)
        self.assertEqual(saida.ordem_servico, ordem)
        self.assertEqual(saida.custo_unitario, Decimal('20.00'))

    def test_compra_nova_nao_muda_o_custo_de_os_concluida(self):
        from estoque.models import MovimentacaoEstoque
        ordem = self.criar_ordem(status='em_andamento')
        self.concluir(ordem)
        MovimentacaoEstoque.objects.create(
            produto=self.produto, tipo='entrada', quantidade=Decimal('10'), custo_unitario=Decimal('35'),
        )
        ordem.refresh_from_db()
        self.assertEqual(ordem.resultado().custo_pecas, Decimal('80.00'))

    def test_os_em_aberto_mostra_lucro_previsto_com_custo_atual(self):
        ordem = self.criar_ordem(status='em_andamento')
        resultado = ordem.resultado()
        self.assertFalse(resultado.realizado)
        self.assertTrue(resultado.custo_previsto)
        self.assertEqual(resultado.receita, Decimal('260.00'))
        self.assertEqual(resultado.custo_pecas, Decimal('80.00'))
        self.assertEqual(resultado.lucro, Decimal('180.00'))
        self.assertEqual(resultado.margem, Decimal('69.2'))

    def test_os_paga_usa_valor_recebido_e_desconta_taxa(self):
        ordem = self.criar_ordem(status='em_andamento')
        self.concluir(ordem)
        self.receber(ordem, Decimal('250.00'), taxa=Decimal('7.50'))
        resultado = OrdemServico.objects.get(pk=ordem.pk).resultado()
        self.assertTrue(resultado.realizado)
        self.assertFalse(resultado.custo_previsto)
        self.assertEqual(resultado.receita, Decimal('250.00'))
        self.assertEqual(resultado.taxa, Decimal('7.50'))
        self.assertEqual(resultado.lucro, Decimal('162.50'))

    def test_peca_vendida_abaixo_do_custo_e_sinalizada(self):
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('50'))
        ordem = self.criar_ordem(status='em_andamento')
        resultado = ordem.resultado()
        self.assertEqual([i.descricao for i in resultado.itens_abaixo_do_custo], ['Óleo 5W30'])


class PreenchimentoDeCustoAntigoTests(BaseOrdemTestCase):
    def preencher(self):
        import importlib
        from django.apps import apps
        migracao = importlib.import_module('ordens_servico.migrations.0005_preencher_custo_das_pecas')
        migracao.preencher_custos(apps, None)

    def saida_antiga(self, ordem, quantidade, custo):
        from estoque.models import MovimentacaoEstoque
        Produto.objects.filter(pk=self.produto.pk).update(estoque_atual=Decimal('50'))
        return MovimentacaoEstoque.objects.create(
            produto=self.produto, tipo='saida', quantidade=quantidade, custo_unitario=custo,
            observacao=f'OS-{ordem.numero} — {ordem.cliente.nome} (Óleo 5W30)',
        )

    def test_usa_o_custo_da_saida_de_estoque_e_liga_a_os(self):
        ordem = self.criar_ordem(status='entregue', data_entrega=timezone.now())
        saida = self.saida_antiga(ordem, Decimal('4'), Decimal('18.00'))
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('30'))
        self.preencher()
        item = ordem.itens_peca.get()
        self.assertEqual(item.custo_unitario, Decimal('18.00'))
        self.assertFalse(item.custo_estimado)
        saida.refresh_from_db()
        self.assertEqual(saida.ordem_servico_id, ordem.pk)

    def test_sem_saida_usa_custo_atual_e_marca_estimado(self):
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('30'))
        ordem = self.criar_ordem(status='concluida')
        self.preencher()
        item = ordem.itens_peca.get()
        self.assertEqual(item.custo_unitario, Decimal('30.00'))
        self.assertTrue(item.custo_estimado)
        self.assertTrue(OrdemServico.objects.get(pk=ordem.pk).resultado().custo_estimado)

    def test_nao_mexe_em_os_em_aberto_nem_em_saida_de_outra_os(self):
        ordem = self.criar_ordem(status='em_andamento')
        outra = self.criar_ordem(status='entregue', data_entrega=timezone.now())
        saida_outra = self.saida_antiga(outra, Decimal('4'), Decimal('18.00'))
        self.preencher()
        self.assertIsNone(ordem.itens_peca.get().custo_unitario)
        saida_outra.refresh_from_db()
        self.assertEqual(saida_outra.ordem_servico_id, outra.pk)


class IntegridadePagamentoEConclusaoTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('20'), estoque_atual=Decimal('50'))
        from financeiro.models import FormaPagamento
        self.forma = FormaPagamento.objects.create(nome='Crédito', taxa=Decimal('3'))

    def pagar(self, ordem, valor='260.00'):
        return self.client.post(
            reverse('ordens_servico:os_pagar', args=[ordem.pk]),
            {'valor_pago': valor, 'forma_pagamento': self.forma.pk},
        )

    def receitas(self, ordem):
        from financeiro.models import Lancamento
        return Lancamento.objects.filter(ordem_servico=ordem, tipo='receita')

    def test_pagamento_bloqueado_com_os_em_andamento(self):
        ordem = self.criar_ordem(status='em_andamento')
        self.pagar(ordem)
        self.assertFalse(self.receitas(ordem).exists())

    def test_pagamento_bloqueado_com_os_cancelada(self):
        ordem = self.criar_ordem(status='cancelada', data_cancelamento=timezone.now())
        self.pagar(ordem)
        self.assertFalse(self.receitas(ordem).exists())

    def test_segundo_pagamento_nao_sobrescreve_valor_nem_data(self):
        ordem = self.criar_ordem(status='concluida')
        self.pagar(ordem, '260.00')
        self.receitas(ordem).update(data_pagamento=timezone.localdate() - timedelta(days=40))
        self.pagar(ordem, '10.00')
        receita = self.receitas(ordem).get()
        self.assertEqual(receita.valor, Decimal('260.00'))
        self.assertEqual(receita.data_pagamento, timezone.localdate() - timedelta(days=40))

    def test_pagamento_em_os_concluida_calcula_taxa(self):
        ordem = self.criar_ordem(status='concluida')
        self.pagar(ordem, '260.00')
        self.assertEqual(self.receitas(ordem).get().valor_taxa, Decimal('7.80'))

    def test_concluir_duas_vezes_baixa_estoque_uma_vez(self):
        from estoque.models import MovimentacaoEstoque
        ordem = self.criar_ordem(status='em_andamento')
        url = reverse('ordens_servico:os_status', args=[ordem.pk])
        self.client.post(url, {'status': 'concluida'})
        self.client.post(url, {'status': 'concluida'})
        self.assertEqual(MovimentacaoEstoque.objects.filter(ordem_servico=ordem).count(), 1)
        self.assertEqual(Produto.objects.get(pk=self.produto.pk).estoque_atual, Decimal('46'))

    def test_os_cancelada_nao_tem_receita_nem_custo(self):
        ordem = self.criar_ordem(status='cancelada', data_cancelamento=timezone.now())
        resultado = ordem.resultado()
        self.assertEqual(resultado.receita, Decimal('0'))
        self.assertEqual(resultado.custo_pecas, Decimal('0'))
        self.assertEqual(resultado.lucro, Decimal('0'))
        self.assertIsNone(resultado.margem)

    def test_lancamento_pago_exige_data_de_pagamento(self):
        from financeiro.forms import LancamentoForm
        form = LancamentoForm(data={
            'tipo': 'despesa', 'categoria': 'aluguel', 'descricao': 'Aluguel', 'valor': '1000',
            'data_competencia': timezone.localdate().isoformat(), 'status': 'pago',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('data_pagamento', form.errors)


class CardResultadoDaOSTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('20'))

    def detalhe(self, ordem):
        return self.client.get(reverse('ordens_servico:os_detalhe', args=[ordem.pk]))

    def test_admin_ve_lucro_previsto(self):
        self.client.force_login(self.usuario)
        resposta = self.detalhe(self.criar_ordem())
        self.assertContains(resposta, 'Resultado da OS')
        self.assertContains(resposta, 'Previsto')
        self.assertContains(resposta, '180,00')
        self.assertContains(resposta, '69,2%')

    def test_recepcionista_e_mecanico_nao_veem_custo_nem_lucro(self):
        ordem = self.criar_ordem()
        for papel in ('recepcionista', 'mecanico'):
            with self.subTest(papel=papel):
                usuario = CustomUser.objects.create_user(username=papel, password='senha-forte-123', role=papel)
                self.client.force_login(usuario)
                resposta = self.detalhe(ordem)
                self.assertEqual(resposta.status_code, 200)
                self.assertNotContains(resposta, 'Resultado da OS')
                self.assertNotContains(resposta, 'Custo das peças')

    def test_alerta_de_peca_abaixo_do_custo(self):
        Produto.objects.filter(pk=self.produto.pk).update(preco_custo=Decimal('50'))
        self.client.force_login(self.usuario)
        self.assertContains(self.detalhe(self.criar_ordem()), 'Peça vendida abaixo do custo')


class AdminNaoContornaFluxoTests(BaseOrdemTestCase):
    def setUp(self):
        super().setUp()
        self.superusuario = CustomUser.objects.create_superuser(
            username='root', password='senha-forte-123', email='', role='admin',
        )
        self.client.force_login(self.superusuario)

    def test_status_e_totais_sao_somente_leitura(self):
        from django.contrib.admin.sites import site
        modelo_admin = site._registry[OrdemServico]
        for campo in ('status', 'total', 'subtotal_pecas'):
            self.assertIn(campo, modelo_admin.get_readonly_fields(None))

    def test_itens_de_os_concluida_nao_podem_ser_alterados(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        ordem = self.criar_ordem(status='concluida')
        aberta = self.criar_ordem(status='em_andamento')
        requisicao = RequestFactory().get('/')
        requisicao.user = self.superusuario
        for inline in site._registry[OrdemServico].get_inline_instances(requisicao, ordem):
            self.assertFalse(inline.has_add_permission(requisicao, ordem))
            self.assertFalse(inline.has_change_permission(requisicao, ordem))
            self.assertFalse(inline.has_delete_permission(requisicao, ordem))
            self.assertTrue(inline.has_change_permission(requisicao, aberta))
        resposta = self.client.get(reverse('admin:ordens_servico_ordemservico_change', args=[ordem.pk]))
        self.assertEqual(resposta.status_code, 200)


class UmaReceitaPorOSTests(BaseOrdemTestCase):
    def receita(self, ordem, status='pago'):
        from financeiro.models import Lancamento
        return Lancamento.objects.create(
            tipo='receita', categoria='servico', ordem_servico=ordem, descricao='x', valor=Decimal('260'),
            data_competencia=timezone.localdate(), data_pagamento=timezone.localdate(), status=status,
        )

    def test_banco_recusa_segunda_receita_da_mesma_os(self):
        from django.db import IntegrityError, transaction
        ordem = self.criar_ordem(status='concluida')
        self.receita(ordem)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.receita(ordem)

    def test_despesas_e_receitas_sem_os_nao_sao_afetadas(self):
        from financeiro.models import Lancamento
        for _ in range(2):
            Lancamento.objects.create(
                tipo='receita', categoria='venda_peca', descricao='balcão', valor=Decimal('10'),
                data_competencia=timezone.localdate(),
            )
        self.assertEqual(Lancamento.objects.filter(ordem_servico__isnull=True).count(), 2)

    def test_pagamento_aproveita_receita_pendente_sem_duplicar(self):
        from financeiro.models import FormaPagamento, Lancamento
        self.client.force_login(self.usuario)
        ordem = self.criar_ordem(status='concluida')
        self.receita(ordem, status='pendente')
        forma = FormaPagamento.objects.create(nome='Pix')
        self.client.post(
            reverse('ordens_servico:os_pagar', args=[ordem.pk]),
            {'valor_pago': '260.00', 'forma_pagamento': forma.pk},
        )
        [receita] = Lancamento.objects.filter(ordem_servico=ordem)
        self.assertEqual(receita.status, 'pago')
        self.assertEqual(receita.data_pagamento, timezone.localdate())


class DataDoPagamentoNoFusoLocalTests(BaseOrdemTestCase):
    def test_pagamento_as_23h30_do_ultimo_dia_fica_no_mesmo_mes(self):
        from datetime import date, datetime
        from unittest import mock
        from zoneinfo import ZoneInfo
        from financeiro.models import FormaPagamento, Lancamento
        self.client.force_login(self.usuario)
        ordem = self.criar_ordem(status='concluida')
        forma = FormaPagamento.objects.create(nome='Pix')
        noite = datetime(2026, 12, 1, 2, 30, tzinfo=ZoneInfo('UTC'))
        with mock.patch('django.utils.timezone.now', return_value=noite):
            self.client.post(
                reverse('ordens_servico:os_pagar', args=[ordem.pk]),
                {'valor_pago': '260.00', 'forma_pagamento': forma.pk},
            )
        self.assertEqual(Lancamento.objects.get(ordem_servico=ordem).data_pagamento, date(2026, 11, 30))
