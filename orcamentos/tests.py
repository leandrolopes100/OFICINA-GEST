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
from veiculos.models import Marca, Modelo, Veiculo

from .models import (
    ConteudoAlterado, ItemOrcamentoPeca, ItemOrcamentoServico, LinkIndisponivel,
    Orcamento, RespostaCliente, TipoServico, TransicaoStatusInvalida,
)


class BaseOrcamentoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(
            username='atendente', password='senha-forte-123', role='admin',
        )
        cls.cliente = Cliente.objects.create(
            nome='João da Silva', cpf_cnpj='529.982.247-25',
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

    def criar_orcamento(self, status='enviado', validade_dias=10, com_link=True):
        orcamento = Orcamento.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, criado_por=self.usuario,
            status=status, data_validade=timezone.localdate() + timedelta(days=validade_dias),
        )
        ItemOrcamentoServico.objects.create(
            orcamento=orcamento, tipo_servico=self.tipo_servico,
            descricao='Troca de óleo', quantidade=Decimal('1'), preco_unitario=Decimal('80'),
        )
        ItemOrcamentoPeca.objects.create(
            orcamento=orcamento, produto=self.produto,
            descricao='Óleo 5W30', quantidade=Decimal('4'), preco_unitario=Decimal('45'),
        )
        orcamento.recalcular_totais()
        if com_link:
            orcamento.garantir_link_publico()
        return Orcamento.objects.get(pk=orcamento.pk)


class TransicoesDeStatusTests(BaseOrcamentoTestCase):
    def test_aprovar_a_partir_de_rascunho_e_enviado(self):
        for status in ('rascunho', 'enviado'):
            orcamento = self.criar_orcamento(status=status)
            orcamento.aprovar()
            orcamento.refresh_from_db()
            self.assertEqual(orcamento.status, 'aprovado')
            self.assertIsNotNone(orcamento.data_aprovacao)

    def test_aprovar_bloqueado_em_status_finais(self):
        for status in ('aprovado', 'reprovado', 'cancelado', 'expirado'):
            orcamento = self.criar_orcamento(status=status)
            with self.assertRaises(TransicaoStatusInvalida):
                orcamento.aprovar()
            orcamento.refresh_from_db()
            self.assertEqual(orcamento.status, status)

    def test_reprovar_orcamento_aprovado_bloqueado(self):
        orcamento = self.criar_orcamento(status='aprovado')
        with self.assertRaises(TransicaoStatusInvalida):
            orcamento.reprovar()

    def test_enviar_nao_volta_orcamento_aprovado(self):
        orcamento = self.criar_orcamento(status='aprovado')
        with self.assertRaises(TransicaoStatusInvalida):
            orcamento.marcar_enviado()
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'aprovado')

    def test_view_interna_de_aprovar_respeita_status(self):
        orcamento = self.criar_orcamento(status='cancelado')
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('orcamentos:aprovar', args=[orcamento.pk]), follow=True)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'cancelado')
        self.assertContains(resposta, 'não pode passar para')

    def test_view_interna_de_aprovar_rascunho_continua_funcionando(self):
        orcamento = self.criar_orcamento(status='rascunho')
        self.client.force_login(self.usuario)
        self.client.post(reverse('orcamentos:aprovar', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'aprovado')
        self.assertTrue(orcamento.historico.filter(descricao='Status: Rascunho → Aprovado.').exists())


class HashConteudoTests(BaseOrcamentoTestCase):
    def test_hash_estavel_entre_leituras(self):
        orcamento = self.criar_orcamento()
        self.assertEqual(orcamento.hash_conteudo(), Orcamento.objects.get(pk=orcamento.pk).hash_conteudo())

    def test_hash_muda_quando_preco_muda(self):
        orcamento = self.criar_orcamento()
        antes = orcamento.hash_conteudo()
        item = orcamento.itens_servico.get()
        item.preco_unitario = Decimal('90')
        item.save()
        orcamento.recalcular_totais()
        self.assertNotEqual(antes, Orcamento.objects.get(pk=orcamento.pk).hash_conteudo())


class RespostaClienteModelTests(BaseOrcamentoTestCase):
    def responder(self, orcamento, decisao=RespostaCliente.APROVADO, hash_visto=None):
        return orcamento.registrar_resposta_cliente(
            decisao=decisao, nome='João da Silva', motivo='',
            hash_visto=hash_visto if hash_visto is not None else orcamento.hash_conteudo(),
            ip='200.100.50.25', user_agent='Teste',
        )

    def test_aprovacao_registra_prova_e_muda_status(self):
        orcamento = self.criar_orcamento()
        resposta = self.responder(orcamento)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'aprovado')
        self.assertIsNotNone(orcamento.data_aprovacao)
        self.assertEqual(resposta.total_no_momento, orcamento.total)
        self.assertEqual(resposta.hash_conteudo, orcamento.hash_conteudo())

    def test_conteudo_alterado_bloqueia_resposta(self):
        orcamento = self.criar_orcamento()
        with self.assertRaises(ConteudoAlterado):
            self.responder(orcamento, hash_visto='0' * 64)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'enviado')
        self.assertFalse(RespostaCliente.objects.exists())

    def test_orcamento_vencido_nao_aceita_resposta(self):
        orcamento = self.criar_orcamento(validade_dias=-1)
        with self.assertRaises(LinkIndisponivel):
            self.responder(orcamento)

    def test_segunda_resposta_e_recusada(self):
        orcamento = self.criar_orcamento()
        hash_visto = orcamento.hash_conteudo()
        self.responder(orcamento, hash_visto=hash_visto)
        with self.assertRaises(LinkIndisponivel):
            self.responder(orcamento, decisao=RespostaCliente.RECUSADO, hash_visto=hash_visto)
        self.assertEqual(RespostaCliente.objects.count(), 1)


class PaginaPublicaTests(BaseOrcamentoTestCase):
    def url(self, orcamento):
        return reverse('orcamento_publico:detalhe', kwargs={'token': orcamento.token_publico})

    def dados(self, orcamento, acao=RespostaCliente.APROVADO, **extras):
        dados = {
            'acao': acao,
            f'{acao}-nome': 'João da Silva',
            f'{acao}-hash_conteudo': orcamento.hash_conteudo(),
        }
        if acao == RespostaCliente.APROVADO:
            dados[f'{acao}-confirmo'] = 'on'
        dados.update(extras)
        return dados

    def test_token_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('orcamento_publico:detalhe', kwargs={'token': 'x' * 43}))
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_abre_sem_login_e_nao_expoe_dados_sensiveis(self):
        orcamento = self.criar_orcamento()
        resposta = self.client.get(self.url(orcamento))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'ORC-{orcamento.numero}')
        self.assertContains(resposta, 'ABC1D23')
        self.assertNotContains(resposta, '529.982.247-25')
        self.assertNotContains(resposta, '52998224725')
        self.assertNotContains(resposta, '99876-5432')
        self.assertEqual(resposta['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(resposta['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-store', resposta['Cache-Control'])

    def test_rascunho_e_cancelado_nao_ficam_visiveis(self):
        for status in ('rascunho', 'cancelado'):
            orcamento = self.criar_orcamento(status=status)
            resposta = self.client.get(self.url(orcamento))
            self.assertEqual(resposta.status_code, 410)
            self.assertNotContains(resposta, 'ABC1D23', status_code=410)

    def test_aprovacao_pelo_cliente(self):
        orcamento = self.criar_orcamento()
        resposta = self.client.post(
            self.url(orcamento), self.dados(orcamento),
            HTTP_X_FORWARDED_FOR='10.0.0.1, 200.100.50.25',
        )
        self.assertRedirects(resposta, self.url(orcamento))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'aprovado')
        registro = RespostaCliente.objects.get()
        self.assertEqual(registro.decisao, RespostaCliente.APROVADO)
        self.assertEqual(registro.ip, '200.100.50.25')
        historico = Historico.objects.get(orcamento=orcamento, tipo='status')
        self.assertIsNone(historico.usuario)
        self.assertIn('Aprovado pelo cliente via link', historico.descricao)
        self.assertContains(self.client.get(self.url(orcamento)), 'Orçamento aprovado.')

    def test_aprovacao_exige_confirmacao(self):
        orcamento = self.criar_orcamento()
        dados = self.dados(orcamento)
        del dados['aprovado-confirmo']
        resposta = self.client.post(self.url(orcamento), dados)
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, 'Marque a confirmação', status_code=400)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'enviado')

    def test_recusa_com_motivo(self):
        orcamento = self.criar_orcamento()
        self.client.post(self.url(orcamento), self.dados(
            orcamento, acao=RespostaCliente.RECUSADO, **{'recusado-motivo': 'Achei caro'}))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'reprovado')
        self.assertEqual(RespostaCliente.objects.get().motivo, 'Achei caro')
        self.assertIn('Achei caro', Historico.objects.get(orcamento=orcamento, tipo='status').descricao)

    def test_conteudo_alterado_nao_aprova(self):
        orcamento = self.criar_orcamento()
        dados = self.dados(orcamento)
        item = orcamento.itens_peca.get()
        item.quantidade = Decimal('5')
        item.save()
        orcamento.recalcular_totais()
        resposta = self.client.post(self.url(orcamento), dados, follow=True)
        self.assertContains(resposta, 'atualizou este orçamento')
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'enviado')
        self.assertFalse(RespostaCliente.objects.exists())

    def test_vencido_mostra_aviso_sem_formulario(self):
        orcamento = self.criar_orcamento(validade_dias=-1)
        resposta = self.client.get(self.url(orcamento))
        self.assertContains(resposta, 'Este orçamento venceu')
        self.assertNotContains(resposta, 'Aprovar orçamento')

    def test_link_regenerado_invalida_o_anterior(self):
        orcamento = self.criar_orcamento()
        url_antiga = self.url(orcamento)
        orcamento.regenerar_link_publico()
        self.assertEqual(self.client.get(url_antiga).status_code, 404)
        self.assertEqual(self.client.get(self.url(orcamento)).status_code, 200)

    def test_pdf_pelo_token(self):
        orcamento = self.criar_orcamento()
        resposta = self.client.get(reverse('orcamento_publico:pdf', kwargs={'token': orcamento.token_publico}))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')

    def test_pdf_de_orcamento_cancelado_retorna_404(self):
        orcamento = self.criar_orcamento(status='cancelado')
        resposta = self.client.get(reverse('orcamento_publico:pdf', kwargs={'token': orcamento.token_publico}))
        self.assertEqual(resposta.status_code, 404)

    def test_limite_de_requisicoes(self):
        orcamento = self.criar_orcamento()
        for _ in range(60):
            self.client.get(self.url(orcamento))
        self.assertEqual(self.client.get(self.url(orcamento)).status_code, 429)


class EnvioWhatsAppTests(BaseOrcamentoTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_envio_gera_link_marca_enviado_e_redireciona_para_wa_me(self):
        orcamento = self.criar_orcamento(status='rascunho', com_link=False)
        resposta = self.client.post(reverse('orcamentos:enviar_whatsapp', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'enviado')
        self.assertIsNotNone(orcamento.token_publico)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta['Location'].startswith('https://wa.me/5551998765432?text='))
        texto = unquote(resposta['Location'])
        self.assertIn(f'ORC-{orcamento.numero}', texto)
        self.assertIn(f'/o/{orcamento.token_publico}/', texto)
        self.assertIn('Olá, João!', texto)
        self.assertTrue(orcamento.historico.filter(descricao__contains='(51) 99876-5432').exists())

    def test_reenvio_mantem_o_mesmo_link(self):
        orcamento = self.criar_orcamento(status='enviado')
        token = orcamento.token_publico
        self.client.post(reverse('orcamentos:enviar_whatsapp', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.token_publico, token)

    def test_cliente_sem_whatsapp_nao_envia(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(whatsapp=False)
        orcamento = self.criar_orcamento(status='rascunho', com_link=False)
        resposta = self.client.post(reverse('orcamentos:enviar_whatsapp', args=[orcamento.pk]))
        self.assertRedirects(resposta, reverse('orcamentos:detail', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'rascunho')
        self.assertIsNone(orcamento.token_publico)

    def test_orcamento_aprovado_nao_e_reenviado(self):
        orcamento = self.criar_orcamento(status='aprovado')
        self.client.post(reverse('orcamentos:enviar_whatsapp', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'aprovado')

    def test_novo_link_troca_token_e_marca_enviado(self):
        orcamento = self.criar_orcamento(status='rascunho')
        token_antigo = orcamento.token_publico
        self.client.post(reverse('orcamentos:novo_link', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertNotEqual(orcamento.token_publico, token_antigo)
        self.assertEqual(orcamento.status, 'enviado')

    def test_views_internas_exigem_login(self):
        self.client.logout()
        orcamento = self.criar_orcamento(status='rascunho')
        for nome in ('enviar_whatsapp', 'novo_link', 'aprovar', 'reprovar', 'enviar'):
            resposta = self.client.post(reverse(f'orcamentos:{nome}', args=[orcamento.pk]))
            self.assertEqual(resposta.status_code, 302)
            self.assertIn('/accounts/login/', resposta['Location'])
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'rascunho')

    def test_tela_de_detalhe_mostra_link_e_resposta(self):
        orcamento = self.criar_orcamento()
        orcamento.registrar_resposta_cliente(
            decisao=RespostaCliente.APROVADO, nome='João da Silva', motivo='',
            hash_visto=orcamento.hash_conteudo(), ip=None, user_agent='',
        )
        resposta = self.client.get(reverse('orcamentos:detail', args=[orcamento.pk]))
        self.assertContains(resposta, 'Resposta do cliente')
        self.assertContains(resposta, orcamento.token_publico)

    def test_exclusao_bloqueada_quando_ha_resposta_do_cliente(self):
        orcamento = self.criar_orcamento()
        orcamento.registrar_resposta_cliente(
            decisao=RespostaCliente.RECUSADO, nome='João da Silva', motivo='',
            hash_visto=orcamento.hash_conteudo(), ip=None, user_agent='',
        )
        self.client.post(reverse('orcamentos:delete', args=[orcamento.pk]), {'acao': 'excluir'})
        self.assertTrue(Orcamento.objects.filter(pk=orcamento.pk).exists())

    def test_dashboard_avisa_aprovados_pelo_cliente(self):
        orcamento = self.criar_orcamento()
        orcamento.registrar_resposta_cliente(
            decisao=RespostaCliente.APROVADO, nome='João da Silva', motivo='',
            hash_visto=orcamento.hash_conteudo(), ip=None, user_agent='',
        )
        resposta = self.client.get(reverse('relatorios:dashboard'))
        self.assertEqual(resposta.context['aprovados_cliente_sem_os'], 1)
        self.assertContains(resposta, 'aprovado(s) pelo cliente pelo link')


class CorrecoesDaRevisaoTests(BaseOrcamentoTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_orcamento_vencido_nao_e_enviado_pelo_whatsapp(self):
        orcamento = self.criar_orcamento(status='rascunho', validade_dias=-1, com_link=False)
        resposta = self.client.post(reverse('orcamentos:enviar_whatsapp', args=[orcamento.pk]), follow=True)
        self.assertContains(resposta, 'A validade venceu')
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, 'rascunho')
        self.assertIsNone(orcamento.token_publico)

    def test_orcamento_vencido_nao_gera_novo_link(self):
        orcamento = self.criar_orcamento(status='enviado', validade_dias=-1)
        token = orcamento.token_publico
        self.client.post(reverse('orcamentos:novo_link', args=[orcamento.pk]))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.token_publico, token)

    def test_garantir_link_nao_troca_token_existente(self):
        orcamento = self.criar_orcamento(com_link=False)
        desatualizado = Orcamento.objects.get(pk=orcamento.pk)
        token = orcamento.garantir_link_publico()
        self.assertEqual(desatualizado.garantir_link_publico(), token)
        self.assertEqual(Orcamento.objects.get(pk=orcamento.pk).token_publico, token)

    def test_esta_expirado_usa_data_local(self):
        orcamento = self.criar_orcamento(validade_dias=0)
        self.assertFalse(orcamento.esta_expirado)
        self.assertTrue(orcamento.aceita_resposta_cliente)

    def test_filtro_de_aprovados_pelo_cliente(self):
        pelo_cliente = self.criar_orcamento()
        pelo_cliente.registrar_resposta_cliente(
            decisao=RespostaCliente.APROVADO, nome='João da Silva', motivo='',
            hash_visto=pelo_cliente.hash_conteudo(), ip=None, user_agent='',
        )
        pela_equipe = self.criar_orcamento()
        pela_equipe.aprovar()
        url = reverse('orcamentos:list')
        todos = {o.pk for o in self.client.get(url, {'aguardando_os': '1'}).context['orcamentos']}
        so_cliente = {o.pk for o in self.client.get(url, {'aguardando_os': 'cliente'}).context['orcamentos']}
        self.assertEqual(todos, {pelo_cliente.pk, pela_equipe.pk})
        self.assertEqual(so_cliente, {pelo_cliente.pk})


class IpDoClienteTests(BaseOrcamentoTestCase):
    def ip_registrado(self, **cabecalhos):
        orcamento = self.criar_orcamento()
        dados = {
            'acao': 'aprovado', 'aprovado-nome': 'João da Silva', 'aprovado-confirmo': 'on',
            'aprovado-hash_conteudo': orcamento.hash_conteudo(),
        }
        self.client.post(
            reverse('orcamento_publico:detalhe', kwargs={'token': orcamento.token_publico}),
            dados, **cabecalhos,
        )
        return RespostaCliente.objects.get(orcamento=orcamento).ip

    def test_padrao_usa_ultimo_ip_do_x_forwarded_for(self):
        self.assertEqual(self.ip_registrado(HTTP_X_FORWARDED_FOR='1.1.1.1, 200.100.50.25'), '200.100.50.25')

    def test_sem_cabecalho_usa_remote_addr(self):
        self.assertEqual(self.ip_registrado(), '127.0.0.1')

    def test_cabecalho_configuravel_para_cloudflare(self):
        with self.settings(IP_CLIENTE_CABECALHO='HTTP_CF_CONNECTING_IP'):
            ip = self.ip_registrado(
                HTTP_CF_CONNECTING_IP='189.10.20.30', HTTP_X_FORWARDED_FOR='189.10.20.30, 172.70.1.1',
            )
        self.assertEqual(ip, '189.10.20.30')

    def test_valor_invalido_vira_nulo(self):
        self.assertIsNone(self.ip_registrado(HTTP_X_FORWARDED_FOR='nao-e-ip'))


class FiltroListaOrcamentosTests(BaseOrcamentoTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        marca = Marca.objects.get(nome='Volkswagen')
        outro_cliente = Cliente.objects.create(nome='Maria Souza', cpf_cnpj='111.444.777-35')
        outro_veiculo = Veiculo.objects.create(
            cliente=outro_cliente, marca=marca, modelo=Modelo.objects.get(nome='Gol'),
            ano_fabricacao=2019, ano_modelo=2019, cor='Preto', placa='XYZ9876',
        )
        self.orc_outubro = self.criar_orcamento(com_link=False)
        self.orc_novembro = self.criar_orcamento(com_link=False)
        self.orc_maria = Orcamento.objects.create(
            cliente=outro_cliente, veiculo=outro_veiculo, criado_por=self.usuario,
            data_validade=timezone.localdate(),
        )
        self.definir_criacao(self.orc_outubro, 2026, 10, 15)
        self.definir_criacao(self.orc_novembro, 2026, 11, 10)
        self.definir_criacao(self.orc_maria, 2026, 11, 12)

    def definir_criacao(self, orcamento, ano, mes, dia, hora=12):
        momento = timezone.make_aware(timezone.datetime(ano, mes, dia, hora, 0))
        Orcamento.objects.filter(pk=orcamento.pk).update(data_criacao=momento)

    def listar(self, **params):
        resposta = self.client.get(reverse('orcamentos:list'), params)
        self.assertEqual(resposta.status_code, 200)
        return {o.pk for o in resposta.context['orcamentos']}

    def test_periodo_filtra_pela_data_de_criacao(self):
        self.assertEqual(
            self.listar(de='2026-11-01', ate='2026-11-30'),
            {self.orc_novembro.pk, self.orc_maria.pk},
        )

    def test_ate_inclui_o_dia_inteiro(self):
        self.definir_criacao(self.orc_novembro, 2026, 11, 10, hora=23)
        self.assertIn(self.orc_novembro.pk, self.listar(ate='2026-11-10'))

    def test_so_um_dos_lados(self):
        self.assertEqual(self.listar(de='2026-11-11'), {self.orc_maria.pk})
        self.assertEqual(self.listar(ate='2026-10-31'), {self.orc_outubro.pk})

    def test_periodo_invertido_e_desinvertido(self):
        self.assertEqual(
            self.listar(de='2026-11-30', ate='2026-11-01'),
            {self.orc_novembro.pk, self.orc_maria.pk},
        )

    def test_data_invalida_e_ignorada(self):
        self.assertEqual(len(self.listar(de='31/02/2026', ate='lixo')), 3)

    def test_busca_por_placa_com_ou_sem_hifen(self):
        esperado = {self.orc_maria.pk}
        self.assertEqual(self.listar(q='XYZ9876'), esperado)
        self.assertEqual(self.listar(q='xyz-9876'), esperado)

    def test_busca_por_numero_com_prefixo(self):
        self.assertEqual(self.listar(q=f'ORC-{self.orc_outubro.numero}'), {self.orc_outubro.pk})

    def test_busca_combinada_com_periodo(self):
        self.assertEqual(
            self.listar(q='João', de='2026-11-01', ate='2026-11-30'),
            {self.orc_novembro.pk},
        )

    def test_paginacao_preserva_filtros(self):
        for _ in range(20):
            novo = self.criar_orcamento(com_link=False)
            self.definir_criacao(novo, 2026, 11, 5)
        resposta = self.client.get(
            reverse('orcamentos:list'), {'q': 'João & cia', 'de': '2026-11-01', 'page': '1'},
        )
        querystring = resposta.context['filtros_querystring']
        self.assertIn('de=2026-11-01', querystring)
        self.assertIn('q=Jo%C3%A3o+%26+cia', querystring)
        self.assertNotIn('page=', querystring)
