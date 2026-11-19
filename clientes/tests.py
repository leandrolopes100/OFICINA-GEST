from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser

from .models import Cliente


class PaginacaoClientesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = CustomUser.objects.create_user(username='admin', password='senha-forte-123', role='admin')
        Cliente.objects.bulk_create(
            Cliente(nome=f'Silva & Filhos {i:02d}', cpf_cnpj=f'000.000.000-{i:02d}') for i in range(25)
        )
        Cliente.objects.create(nome='Outro Cliente', cpf_cnpj='999.999.999-99')

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_vinte_por_pagina_com_total(self):
        resposta = self.client.get(reverse('clientes:list'))
        self.assertEqual(len(resposta.context['page_obj']), 20)
        self.assertContains(resposta, 'Mostrando 1–20 de 26 clientes')

    def test_busca_com_e_comercial_sobrevive_a_troca_de_pagina(self):
        resposta = self.client.get(reverse('clientes:list'), {'q': 'Silva & Filhos'})
        self.assertContains(resposta, 'href="?q=Silva+%26+Filhos&amp;page=2"')

        pagina2 = self.client.get(reverse('clientes:list'), {'q': 'Silva & Filhos', 'page': 2})
        nomes = [c.nome for c in pagina2.context['page_obj']]
        self.assertEqual(len(nomes), 5)
        self.assertTrue(all(n.startswith('Silva & Filhos') for n in nomes))

    def test_link_nao_duplica_page(self):
        resposta = self.client.get(reverse('clientes:list'), {'page': 2})
        self.assertContains(resposta, 'href="?page=1"')
        self.assertNotContains(resposta, 'page=2&amp;page')
