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
