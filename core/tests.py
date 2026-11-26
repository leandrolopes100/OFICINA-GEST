import subprocess
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import CustomUser
from core.versao import versao_sistema
from core.whatsapp import formatar_telefone_exibicao, normalizar_telefone_whatsapp


class NormalizarTelefoneWhatsAppTests(SimpleTestCase):
    def test_formatos_validos(self):
        casos = {
            '(51) 99876-5432': '5551998765432',
            '51998765432': '5551998765432',
            '+55 51 99876-5432': '5551998765432',
            '0055 51 99876-5432': '5551998765432',
            '051998765432': '5551998765432',
            '(51) 3333-4444': '555133334444',
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(normalizar_telefone_whatsapp(entrada), esperado)

    def test_formatos_invalidos(self):
        for entrada in ('', None, '99876-5432', '(51) 8876-5432', '(01) 99876-5432', '(51) 39876-54321', 'abc'):
            with self.subTest(entrada=entrada):
                self.assertIsNone(normalizar_telefone_whatsapp(entrada))

    def test_usa_o_primeiro_numero_valido(self):
        self.assertEqual(normalizar_telefone_whatsapp('', '123', '(51) 99876-5432'), '5551998765432')

    def test_formatacao_para_exibicao(self):
        self.assertEqual(formatar_telefone_exibicao('5551998765432'), '(51) 99876-5432')
        self.assertEqual(formatar_telefone_exibicao('555133334444'), '(51) 3333-4444')
        self.assertEqual(formatar_telefone_exibicao(None), '')


class VersaoSistemaTests(TestCase):
    def setUp(self):
        versao_sistema.cache_clear()
        self.addCleanup(versao_sistema.cache_clear)

    def simular_git(self, saida):
        return mock.patch('core.versao.subprocess.run', return_value=mock.Mock(stdout=saida))

    def test_le_data_do_commit_no_horario_local(self):
        with self.simular_git('2026-11-17T00:13:05+00:00\n'):
            versao = versao_sistema()
        self.assertEqual(versao.strftime('%d/%m/%Y %H:%M'), '16/11/2026 21:13')

    def test_sem_git_retorna_none(self):
        with mock.patch('core.versao.subprocess.run', side_effect=FileNotFoundError):
            self.assertIsNone(versao_sistema())

    def test_git_com_erro_retorna_none(self):
        erro = subprocess.CalledProcessError(128, 'git')
        with mock.patch('core.versao.subprocess.run', side_effect=erro):
            self.assertIsNone(versao_sistema())

    def test_saida_inesperada_retorna_none(self):
        with self.simular_git('lixo'):
            self.assertIsNone(versao_sistema())

    def test_le_uma_vez_por_processo(self):
        with self.simular_git('2026-11-17T00:13:05+00:00') as executar:
            versao_sistema()
            versao_sistema()
        self.assertEqual(executar.call_count, 1)

    def test_faixa_aparece_so_para_usuario_logado(self):
        usuario = CustomUser.objects.create_user(username='u', password='senha-forte-123', role='admin')
        with self.simular_git('2026-11-17T00:13:05+00:00'):
            self.assertNotContains(self.client.get(reverse('accounts:login')), 'Versão de')
            self.client.force_login(usuario)
            resposta = self.client.get(reverse('relatorios:dashboard'))
        self.assertContains(resposta, 'Versão de 16/11/2026 às 21:13 - LopSystem')

    def test_sem_versao_a_faixa_nao_aparece(self):
        usuario = CustomUser.objects.create_user(username='u', password='senha-forte-123', role='admin')
        self.client.force_login(usuario)
        with mock.patch('core.versao.subprocess.run', side_effect=FileNotFoundError):
            resposta = self.client.get(reverse('relatorios:dashboard'))
        self.assertNotContains(resposta, 'Versão de')


class ListagensPaginadasTests(TestCase):
    URLS = [
        '/clientes/', '/veiculos/', '/veiculos/marcas/', '/orcamentos/', '/ordens-servico/',
        '/estoque/', '/estoque/movimentacoes/', '/estoque/fornecedores/',
        '/financeiro/', '/financeiro/formas-pagamento/', '/accounts/usuarios/',
    ]

    def test_todas_as_listagens_abrem(self):
        from accounts.models import CustomUser
        usuario = CustomUser.objects.create_user(username='admin', password='senha-forte-123', role='admin')
        self.client.force_login(usuario)
        for url in self.URLS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.get(url, {'page': 1}).status_code, 200)


class PaginasDeErroTests(TestCase):
    def setUp(self):
        self.usuario = CustomUser.objects.create_user(
            username='atendente', password='senha-forte-123', role='recepcionista',
        )

    def test_404_logado_tem_marca_e_volta_ao_dashboard(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get('/nao-existe/')

        self.assertEqual(resposta.status_code, 404)
        self.assertTemplateUsed(resposta, 'erro/interno.html')
        self.assertContains(resposta, 'OFICINA<span class="marca-destaque">GEST</span>', status_code=404)
        self.assertContains(resposta, 'Página não encontrada', status_code=404)
        self.assertContains(resposta, 'Ir para o Dashboard', status_code=404)
        self.assertNotContains(resposta, 'Oficina<br>Simples', status_code=404)

    def test_404_sem_login_leva_ao_login(self):
        resposta = self.client.get('/nao-existe/')

        self.assertContains(resposta, 'Ir para o login', status_code=404)
        self.assertNotContains(resposta, 'Dashboard', status_code=404)

    def test_403_por_perfil(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse('accounts:user_list'))

        self.assertContains(resposta, 'Acesso restrito', status_code=403)
        self.assertContains(resposta, 'Erro 403', status_code=403)

    def test_link_publico_invalido_usa_visual_do_cliente(self):
        resposta = self.client.get('/o/link-quebrado/')

        self.assertEqual(resposta.status_code, 404)
        self.assertTemplateUsed(resposta, 'erro/publico.html')
        self.assertContains(resposta, 'Peça um novo para', status_code=404)
        self.assertNotContains(resposta, 'Dashboard', status_code=404)
        self.assertNotContains(resposta, 'Ir para o login', status_code=404)
        self.assertEqual(resposta['X-Robots-Tag'], 'noindex, nofollow')

    def test_falha_de_csrf_em_portugues(self):
        cliente = self.client_class(enforce_csrf_checks=True)

        resposta = cliente.post(reverse('accounts:login'), {'username': 'x', 'password': 'y'})

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, 'Formulário expirado', status_code=403)

    def test_500_interno_e_publico_sem_depender_do_usuario(self):
        from django.test import RequestFactory
        from core.views_erro import erro_interno

        with self.assertLogs('oficina.erros', level='ERROR'):
            interno = erro_interno(RequestFactory().get('/ordens-servico/'))
            publico = erro_interno(RequestFactory().get('/a/abc/'))

        self.assertEqual(interno.status_code, 500)
        self.assertIn('Erro no sistema', interno.content.decode())
        self.assertIn('Tentar de novo', interno.content.decode())
        self.assertEqual(publico.status_code, 500)
        self.assertNotIn('Tentar de novo', publico.content.decode())
        self.assertEqual(publico['X-Robots-Tag'], 'noindex, nofollow')

    def test_429_publico_e_pagina_html(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from core.publico import muitas_requisicoes

        requisicao = RequestFactory().get('/o/abc/')
        requisicao.user = AnonymousUser()
        resposta = muitas_requisicoes(requisicao)

        self.assertEqual(resposta.status_code, 429)
        self.assertIn('Muitas tentativas', resposta.content.decode())
        self.assertEqual(resposta['Cache-Control'], 'no-store')


    def test_404_mostra_endereco_e_atalhos_para_quem_esta_logado(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get('/ordens-servico/99999/')

        self.assertContains(resposta, '/ordens-servico/99999/', status_code=404)
        self.assertContains(resposta, 'Ou vá direto para', status_code=404)
        self.assertContains(resposta, 'href="/veiculos/"', status_code=404)

    def test_404_sem_login_nao_mostra_atalhos(self):
        resposta = self.client.get('/nao-existe/')

        self.assertNotContains(resposta, 'Ou vá direto para', status_code=404)

    def test_403_diz_usuario_perfil_e_perfil_exigido(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse('accounts:user_list'))

        self.assertContains(resposta, 'Você entrou como <strong>atendente</strong> (Recepcionista).',
                            status_code=403)
        self.assertContains(resposta, 'Esta página é só para Administrador.', status_code=403)

    def test_csrf_fora_do_login_volta_para_a_pagina_de_origem(self):
        cliente = self.client_class(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)

        mesma_origem = cliente.post('/clientes/novo/', HTTP_REFERER='http://testserver/clientes/novo/')
        externa = cliente.post('/clientes/novo/', HTTP_REFERER='https://site-externo.com/')

        self.assertContains(mesma_origem, 'href="http://testserver/clientes/novo/"', status_code=403)
        self.assertContains(mesma_origem, 'Abrir a página de novo', status_code=403)
        self.assertNotContains(externa, 'site-externo', status_code=403)

    def test_csrf_no_login_volta_ao_login(self):
        cliente = self.client_class(enforce_csrf_checks=True)

        resposta = cliente.post(reverse('accounts:login'), {'username': 'x', 'password': 'y'})

        self.assertContains(resposta, 'Voltar ao login', status_code=403)

    def test_500_grava_no_log_o_mesmo_codigo_mostrado_na_tela(self):
        import re
        from django.test import RequestFactory
        from core.views_erro import erro_interno

        with self.assertLogs('oficina.erros', level='ERROR') as log:
            resposta = erro_interno(RequestFactory().get('/financeiro/'))

        referencia = re.search(r'Ref\. <strong>([0-9A-F]{4}-[0-9A-F]{2})</strong>', resposta.content.decode())
        self.assertIsNotNone(referencia)
        self.assertIn(f'ref={referencia.group(1)}', log.output[0])
        self.assertIn('/financeiro/', log.output[0])

    def test_link_publico_cita_o_nome_da_oficina(self):
        with self.settings(OFICINA_NOME='Oficina Teste'):
            resposta = self.client.get('/a/link-quebrado/')

        self.assertContains(resposta, 'Peça um novo para Oficina Teste.', status_code=404)

class SessaoTests(TestCase):
    def setUp(self):
        self.usuario = CustomUser.objects.create_user(
            username='atendente', password='senha-forte-123', role='recepcionista',
        )

    def test_cookie_de_sessao_acaba_ao_fechar_o_navegador(self):
        resposta = self.client.post(
            reverse('accounts:login'), {'username': 'atendente', 'password': 'senha-forte-123'},
        )

        cookie = resposta.cookies['sessionid']
        self.assertEqual(cookie['expires'], '')
        self.assertEqual(cookie['max-age'], '')

    def test_sair_encerra_a_sessao(self):
        self.client.force_login(self.usuario)

        self.client.post(reverse('accounts:logout'))

        resposta = self.client.get('/clientes/')
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('accounts:login'), resposta['Location'])

    def test_paginas_logadas_nao_ficam_no_cache_do_navegador(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get('/clientes/')

        self.assertIn('no-store', resposta['Cache-Control'])
        self.assertIn('private', resposta['Cache-Control'])
