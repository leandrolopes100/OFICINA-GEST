from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser

from .forms import ProdutoForm
from .models import MovimentacaoEstoque, Produto


def dados_produto(**extras):
    dados = {
        'codigo': 'FL-01', 'nome': 'Filtro de óleo', 'unidade': 'un',
        'preco_custo': '1.00', 'margem_lucro': '1400', 'preco_venda': '15.00',
        'estoque_minimo': '0', 'estoque_maximo': '0', 'ativo': 'on',
    }
    dados.update(extras)
    return dados


class MargemLucroFormTests(TestCase):
    def test_margem_acima_de_999_e_aceita(self):
        form = ProdutoForm(data=dados_produto())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['margem_lucro'], Decimal('1400.00'))

    def test_margem_calculada_pelo_preco_de_venda_e_aceita(self):
        form = ProdutoForm(data=dados_produto(
            preco_custo='0.01', preco_venda='250.00', margem_lucro='2499900.00',
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_margem_com_muitas_casas_decimais_e_arredondada(self):
        form = ProdutoForm(data=dados_produto(margem_lucro='33.3333333'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['margem_lucro'], Decimal('33.33'))

    def test_margem_negativa_continua_aceita(self):
        form = ProdutoForm(data=dados_produto(margem_lucro='-20', preco_venda='0.80'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_margem_acima_do_limite_mostra_mensagem_clara(self):
        form = ProdutoForm(data=dados_produto(margem_lucro='100000000'))
        self.assertFalse(form.is_valid())
        self.assertIn('A margem máxima aceita é 99.999.999,99%.', form.errors['margem_lucro'])

    def test_preco_resultante_acima_do_limite_mostra_mensagem_clara(self):
        form = ProdutoForm(data=dados_produto(preco_custo='1000000', margem_lucro='10000'))
        self.assertFalse(form.is_valid())
        self.assertIn('acima do limite', form.errors['margem_lucro'][0])

    def test_campo_aceita_qualquer_casa_decimal_no_navegador(self):
        self.assertEqual(ProdutoForm().fields['margem_lucro'].widget.attrs['step'], 'any')


class MargemLucroViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(
            username='estoquista', password='senha-forte-123', role='admin',
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_cadastro_com_margem_alta_salva(self):
        resposta = self.client.post(reverse('estoque:create'), dados_produto())
        produto = Produto.objects.get(codigo='FL-01')
        self.assertRedirects(resposta, reverse('estoque:detail', args=[produto.pk]))
        self.assertEqual(produto.margem_lucro, Decimal('1400.00'))

    def test_edicao_com_margem_alta_salva(self):
        produto = Produto.objects.create(codigo='FL-01', nome='Filtro de óleo', preco_custo=Decimal('1'))
        resposta = self.client.post(
            reverse('estoque:update', args=[produto.pk]),
            dados_produto(margem_lucro='5000', preco_venda='51.00'),
        )
        self.assertRedirects(resposta, reverse('estoque:detail', args=[produto.pk]))
        produto.refresh_from_db()
        self.assertEqual(produto.margem_lucro, Decimal('5000.00'))


class EntradaComMargemAltaTests(TestCase):
    def test_entrada_recalcula_preco_com_margem_alta(self):
        produto = Produto.objects.create(
            codigo='FL-01', nome='Filtro', preco_custo=Decimal('1'), margem_lucro=Decimal('1400'),
        )
        MovimentacaoEstoque.objects.create(
            produto=produto, tipo='entrada', quantidade=Decimal('1'), custo_unitario=Decimal('2'),
        )
        produto.refresh_from_db()
        self.assertEqual(produto.preco_venda, Decimal('30.00'))

    def test_entrada_que_estouraria_preco_registra_sem_recalcular(self):
        produto = Produto.objects.create(
            codigo='FL-01', nome='Filtro', preco_custo=Decimal('1'),
            preco_venda=Decimal('1000'), margem_lucro=Decimal('99999900'),
        )
        movimentacao = MovimentacaoEstoque.objects.create(
            produto=produto, tipo='entrada', quantidade=Decimal('3'), custo_unitario=Decimal('500'),
        )
        produto.refresh_from_db()
        self.assertTrue(movimentacao.preco_venda_nao_recalculado)
        self.assertEqual(produto.estoque_atual, Decimal('3'))
        self.assertEqual(produto.preco_custo, Decimal('500'))
        self.assertEqual(produto.preco_venda, Decimal('1000'))


class PaginacaoMovimentacoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(
            username='estoquista', password='senha-forte-123', role='admin',
        )
        produto = Produto.objects.create(codigo='FL-01', nome='Filtro')
        for _ in range(23):
            MovimentacaoEstoque.objects.create(
                produto=produto, tipo='entrada', quantidade=Decimal('1'), custo_unitario=Decimal('0'),
            )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_primeira_pagina_mostra_20_e_contador(self):
        resposta = self.client.get(reverse('estoque:movimentacao_list'))
        self.assertEqual(len(resposta.context['movimentacoes']), 20)
        self.assertContains(resposta, 'Mostrando 1–20 de 23 movimentações')
        self.assertContains(resposta, '?page=2')

    def test_segunda_pagina_mostra_o_restante(self):
        resposta = self.client.get(reverse('estoque:movimentacao_list'), {'page': 2})
        self.assertEqual(len(resposta.context['movimentacoes']), 3)
        self.assertContains(resposta, 'Mostrando 21–23 de 23 movimentações')
