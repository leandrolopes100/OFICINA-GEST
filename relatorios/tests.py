from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import CustomUser
from clientes.models import Cliente
from estoque.models import Produto
from financeiro.models import Lancamento
from orcamentos.models import TipoServico
from ordens_servico.models import ItemOSPeca, ItemOSServico, OrdemServico
from veiculos.models import Marca, Modelo, Veiculo

from .lucro import calcular_lucro_do_mes

DIA = date(2026, 10, 15)


class CenarioLucroTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = CustomUser.objects.create_user(username='admin', password='senha-forte-123', role='admin')
        cls.cliente = Cliente.objects.create(nome='João da Silva', cpf_cnpj='529.982.247-25')
        marca = Marca.objects.create(nome='Volkswagen')
        modelo = Modelo.objects.create(marca=marca, nome='Gol')
        cls.veiculo = Veiculo.objects.create(
            cliente=cls.cliente, marca=marca, modelo=modelo,
            ano_fabricacao=2020, ano_modelo=2021, cor='Prata', placa='ABC1D23',
        )
        cls.tipo_servico = TipoServico.objects.create(nome='Troca de óleo', preco_padrao=Decimal('80'))
        cls.produto = Produto.objects.create(
            codigo='OL-01', nome='Óleo 5W30', preco_custo=Decimal('20'), preco_venda=Decimal('45'),
        )

    def criar_os(self, status='entregue', custo_unitario=Decimal('20'), custo_estimado=False, preco_peca='45'):
        ordem = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, status=status, defeito_relatado='Barulho',
        )
        ItemOSServico.objects.create(
            ordem_servico=ordem, tipo_servico=self.tipo_servico, descricao='Troca de óleo',
            quantidade=Decimal('1'), preco_unitario=Decimal('80'),
        )
        ItemOSPeca.objects.create(
            ordem_servico=ordem, produto=self.produto, descricao='Óleo 5W30',
            quantidade=Decimal('4'), preco_unitario=Decimal(preco_peca),
            custo_unitario=custo_unitario, custo_estimado=custo_estimado,
        )
        ordem.recalcular_totais()
        return ordem

    def lancar(self, tipo, valor, categoria='servico', ordem=None, taxa='0', data=DIA, status='pago'):
        return Lancamento.objects.create(
            tipo=tipo, categoria=categoria, ordem_servico=ordem, descricao='x', valor=Decimal(valor),
            valor_taxa=Decimal(taxa), data_competencia=data,
            data_pagamento=data if status == 'pago' else None, status=status,
        )

    def montar_cenario(self):
        ordem = self.criar_os()
        self.lancar('receita', '260.00', ordem=ordem, taxa='7.80')
        self.lancar('receita', '100.00', categoria='venda_peca')
        self.lancar('despesa', '50.00', categoria='aluguel')
        self.lancar('despesa', '500.00', categoria='fornecedor')
        self.lancar('despesa', '999.00', categoria='aluguel', data=DIA - timedelta(days=40))
        self.lancar('despesa', '999.00', categoria='salario', status='pendente')
        self.criar_os(status='concluida')
        return ordem


class LucroDoMesTests(CenarioLucroTestCase):
    def test_resultado_em_cascata(self):
        self.montar_cenario()
        lucro = calcular_lucro_do_mes(10, 2026)
        self.assertEqual(lucro.receita_os, Decimal('260.00'))
        self.assertEqual(lucro.receita_sem_os, Decimal('100.00'))
        self.assertEqual(lucro.faturamento, Decimal('360.00'))
        self.assertEqual(lucro.custo_pecas, Decimal('80.00'))
        self.assertEqual(lucro.taxas, Decimal('7.80'))
        self.assertEqual(lucro.lucro_bruto, Decimal('272.20'))
        self.assertEqual(lucro.despesas, Decimal('50.00'))
        self.assertEqual(lucro.lucro_liquido, Decimal('222.20'))
        self.assertEqual(lucro.compras_de_pecas, Decimal('500.00'))

    def test_linha_da_os_e_avisos(self):
        ordem = self.montar_cenario()
        lucro = calcular_lucro_do_mes(10, 2026)
        [linha] = lucro.linhas
        self.assertEqual(linha.ordem, ordem)
        self.assertEqual(linha.lucro, Decimal('172.20'))
        self.assertEqual(linha.margem, Decimal('66.2'))
        self.assertEqual(lucro.qtd_receitas_sem_os, 1)
        self.assertEqual(lucro.qtd_a_receber, 1)
        self.assertEqual(lucro.valor_a_receber, Decimal('260.00'))

    def test_linha_bate_com_o_card_da_os(self):
        ordem = self.montar_cenario()
        [linha] = calcular_lucro_do_mes(10, 2026).linhas
        self.assertEqual(linha.lucro, ordem.resultado().lucro)

    def test_custo_estimado_e_abaixo_do_custo_sinalizados(self):
        estimada = self.criar_os(custo_estimado=True)
        prejuizo = self.criar_os(custo_unitario=Decimal('60'))
        self.lancar('receita', '260.00', ordem=estimada)
        self.lancar('receita', '260.00', ordem=prejuizo)
        lucro = calcular_lucro_do_mes(10, 2026)
        self.assertEqual(lucro.qtd_custo_estimado, 1)
        self.assertEqual(lucro.qtd_abaixo_do_custo, 1)

    def test_mes_sem_movimento(self):
        lucro = calcular_lucro_do_mes(1, 2020)
        self.assertEqual(lucro.faturamento, Decimal('0'))
        self.assertIsNone(lucro.margem_bruta)
        self.assertEqual(lucro.linhas, [])

    def test_quantidade_de_consultas_nao_cresce_com_o_numero_de_os(self):
        def consultas():
            with CaptureQueriesContext(connection) as contexto:
                calcular_lucro_do_mes(10, 2026)
            return len(contexto.captured_queries)

        self.lancar('receita', '260.00', ordem=self.criar_os())
        com_uma = consultas()
        for _ in range(4):
            self.lancar('receita', '260.00', ordem=self.criar_os())
        self.assertEqual(consultas(), com_uma)

    def test_tela_so_para_admin(self):
        self.montar_cenario()
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 10, 'ano': 2026})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '222,20')
        self.assertContains(resposta, 'Investido em estoque')
        for papel in ('recepcionista', 'mecanico'):
            with self.subTest(papel=papel):
                usuario = CustomUser.objects.create_user(username=papel, password='senha-forte-123', role=papel)
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(reverse('relatorios:lucro')).status_code, 403)

    def test_ordenacao_invalida_cai_no_padrao(self):
        self.montar_cenario()
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 10, 'ano': 2026, 'ordem': 'x'})
        self.assertEqual(resposta.context['ordem'], 'margem')

    def test_dashboard_mostra_lucro_do_mes_so_para_admin(self):
        from django.utils import timezone
        ordem = self.criar_os()
        self.lancar('receita', '260.00', ordem=ordem, taxa='7.80', data=timezone.localdate())
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:dashboard'))
        self.assertContains(resposta, 'Lucro do Mês')
        self.assertContains(resposta, '172,20')
        for papel in ('recepcionista', 'mecanico'):
            with self.subTest(papel=papel):
                usuario = CustomUser.objects.create_user(username=papel, password='senha-forte-123', role=papel)
                self.client.force_login(usuario)
                resposta = self.client.get(reverse('relatorios:dashboard'))
                self.assertEqual(resposta.status_code, 200)
                self.assertNotContains(resposta, 'Lucro do Mês')

    def test_os_cancelada_com_receita_tem_custo_zero_no_relatorio_e_no_card(self):
        ordem = self.criar_os(status='cancelada')
        self.lancar('receita', '100.00', ordem=ordem)
        [linha] = calcular_lucro_do_mes(10, 2026).linhas
        self.assertEqual(linha.custo_pecas, Decimal('0'))
        self.assertEqual(linha.lucro, ordem.resultado().lucro)

    def test_composicao_soma_100_por_cento_do_faturamento(self):
        self.montar_cenario()
        partes = calcular_lucro_do_mes(10, 2026).composicao()
        self.assertEqual([p['nome'] for p in partes], ['Peças', 'Taxas de cartão', 'Despesas da oficina', 'Lucro líquido'])
        self.assertEqual(sum(p['valor'] for p in partes), Decimal('360.00'))
        self.assertAlmostEqual(float(sum(p['percentual'] for p in partes)), 100.0, delta=0.2)

    def test_composicao_no_prejuizo_mostra_so_custos(self):
        ordem = self.criar_os()
        self.lancar('receita', '260.00', ordem=ordem)
        self.lancar('despesa', '1000.00', categoria='aluguel')
        lucro = calcular_lucro_do_mes(10, 2026)
        self.assertTrue(lucro.prejuizo)
        self.assertEqual(lucro.valor_prejuizo, Decimal('820.00'))
        partes = lucro.composicao()
        self.assertNotIn('Lucro líquido', [p['nome'] for p in partes])
        self.assertEqual(sum(p['valor'] for p in partes), Decimal('1080.00'))
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 10, 'ano': 2026})
        self.assertContains(resposta, 'Mês no prejuízo')
        self.assertContains(resposta, '820,00')

    def test_mes_sem_movimento_nao_mostra_barra(self):
        self.assertEqual(calcular_lucro_do_mes(1, 2020).composicao(), [])
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 1, 'ano': 2020})
        self.assertNotContains(resposta, 'Para onde foi o faturamento')
        self.assertContains(resposta, 'Imprimir / PDF')


class ExportarLucroExcelTests(CenarioLucroTestCase):
    def baixar(self, usuario=None, **params):
        from io import BytesIO
        from openpyxl import load_workbook
        self.client.force_login(usuario or self.admin)
        resposta = self.client.get(reverse('relatorios:lucro_excel'), {'mes': 10, 'ano': 2026, **params})
        livro = load_workbook(BytesIO(resposta.content)) if resposta.status_code == 200 else None
        return resposta, livro

    def valores(self, aba):
        return {aba.cell(row=r, column=1).value: aba.cell(row=r, column=2).value for r in range(1, aba.max_row + 1)}

    def test_arquivo_e_resumo_batem_com_o_calculo(self):
        self.montar_cenario()
        resposta, livro = self.baixar()
        self.assertEqual(
            resposta['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertEqual(resposta['Content-Disposition'], 'attachment; filename="lucratividade_2026-10.xlsx"')
        self.assertEqual(livro.sheetnames, ['Resumo', 'Lucro por OS', 'Avisos'])
        resumo = self.valores(livro['Resumo'])
        self.assertEqual(resumo['Faturamento'], 360.0)
        self.assertEqual(resumo['(−) Custo das peças'], -80.0)
        self.assertAlmostEqual(resumo['Lucro bruto'], 272.20, places=2)
        self.assertEqual(resumo['Aluguel'], -50.0)
        self.assertAlmostEqual(resumo['Lucro líquido'], 222.20, places=2)
        self.assertEqual(resumo['Investido em estoque (compras de peças pagas no mês)'], 500.0)

    def test_aba_de_os_tem_valores_numericos_e_total_com_formula(self):
        ordem = self.montar_cenario()
        _, livro = self.baixar()
        aba = livro['Lucro por OS']
        self.assertEqual(aba['A6'].value, f'OS-{ordem.numero}')
        self.assertEqual(aba['B6'].value, 'João da Silva')
        self.assertEqual(aba['D6'].value, 260.0)
        self.assertAlmostEqual(aba['G6'].value, 172.20, places=2)
        self.assertAlmostEqual(aba['H6'].value, 0.662, places=3)
        self.assertEqual(aba['D6'].number_format, '"R$" #,##0.00;[Red]-"R$" #,##0.00')
        self.assertEqual(aba['A7'].value, 'Total das OS')
        self.assertEqual(aba['G7'].value, '=SUM(G6:G6)')
        self.assertEqual(aba.freeze_panes, 'A6')

    def test_respeita_a_ordenacao_da_tela(self):
        primeira = self.criar_os(custo_unitario=Decimal('60'))
        segunda = self.criar_os()
        self.lancar('receita', '260.00', ordem=primeira)
        self.lancar('receita', '260.00', ordem=segunda)
        _, livro = self.baixar(ordem='lucro')
        self.assertEqual(livro['Lucro por OS']['A6'].value, f'OS-{segunda.numero}')
        _, livro = self.baixar(ordem='margem')
        self.assertEqual(livro['Lucro por OS']['A6'].value, f'OS-{primeira.numero}')

    def test_mes_sem_movimento_e_sem_avisos(self):
        _, livro = self.baixar(mes=1, ano=2020)
        self.assertEqual(livro.sheetnames, ['Resumo', 'Lucro por OS'])
        self.assertIn('Nenhuma OS recebida', livro['Lucro por OS']['A6'].value)

    def test_prejuizo_aparece_no_resumo(self):
        ordem = self.criar_os()
        self.lancar('receita', '260.00', ordem=ordem)
        self.lancar('despesa', '1000.00', categoria='aluguel')
        _, livro = self.baixar()
        textos = [c.value for linha in livro['Resumo'].iter_rows() for c in linha if isinstance(c.value, str)]
        self.assertTrue(any('Mês no prejuízo' in t and '820,00' in t for t in textos))

    def test_so_admin_exporta(self):
        for papel in ('recepcionista', 'mecanico'):
            with self.subTest(papel=papel):
                usuario = CustomUser.objects.create_user(username=papel, password='senha-forte-123', role=papel)
                resposta, _ = self.baixar(usuario)
                self.assertEqual(resposta.status_code, 403)

    def test_tela_tem_botao_de_exportar_com_o_mes_e_a_ordem(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 10, 'ano': 2026, 'ordem': 'lucro'})
        self.assertContains(resposta, f'{reverse("relatorios:lucro_excel")}?mes=10&ano=2026&ordem=lucro')


class PaginacaoLucroPorOSTests(CenarioLucroTestCase):
    def setUp(self):
        self.ordens = []
        for _ in range(25):
            ordem = self.criar_os()
            self.lancar('receita', '260.00', ordem=ordem)
            self.ordens.append(ordem)
        self.client.force_login(self.admin)

    def pagina(self, **params):
        return self.client.get(reverse('relatorios:lucro'), {'mes': 10, 'ano': 2026, 'ordem': 'data', **params})

    def test_vinte_por_pagina_e_total_de_todas_as_paginas(self):
        primeira = self.pagina()
        self.assertEqual(len(primeira.context['page_obj']), 20)
        self.assertContains(primeira, 'Mostrando 1–20 de 25 OS')
        self.assertContains(primeira, '(todas as páginas)')
        self.assertContains(primeira, '6.500,00')
        segunda = self.pagina(page=2)
        self.assertEqual(len(segunda.context['page_obj']), 5)
        self.assertContains(segunda, f'OS-{self.ordens[-1].numero}')
        self.assertNotContains(segunda, f'>OS-{self.ordens[0].numero}<')

    def test_links_de_pagina_mantem_mes_ano_e_ordem(self):
        self.assertContains(self.pagina(), 'href="?mes=10&amp;ano=2026&amp;ordem=data&amp;page=2"')

    def test_pagina_invalida_nao_quebra(self):
        self.assertEqual(self.pagina(page='abc').context['page_obj'].number, 1)
        self.assertEqual(self.pagina(page=99).context['page_obj'].number, 2)

    def test_poucas_os_nao_mostram_paginacao(self):
        resposta = self.client.get(reverse('relatorios:lucro'), {'mes': 1, 'ano': 2020})
        self.assertNotContains(resposta, 'aria-label="Paginação"')

    def test_excel_continua_com_todas_as_os(self):
        from io import BytesIO
        from openpyxl import load_workbook
        resposta = self.client.get(reverse('relatorios:lucro_excel'), {'mes': 10, 'ano': 2026, 'page': 2})
        aba = load_workbook(BytesIO(resposta.content))['Lucro por OS']
        self.assertEqual(aba['A31'].value, 'Total das OS')
        self.assertEqual(aba['D31'].value, '=SUM(D6:D30)')
