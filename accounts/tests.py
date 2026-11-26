from django.test import TestCase
from django.urls import reverse

from .models import CustomUser


class TelaDeLoginTests(TestCase):
    def setUp(self):
        self.url = reverse('accounts:login')

    def test_tela_mostra_marca_e_campos(self):
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'OFICINA<span class="marca-destaque">GEST</span>', html=False)
        self.assertContains(resposta, 'name="username"')
        self.assertContains(resposta, 'name="password"')
        self.assertNotContains(resposta, 'Usuário ou senha incorretos.')

    def test_senha_errada_mostra_aviso_e_mantem_usuario(self):
        CustomUser.objects.create_user(username='mecanico', password='senha-certa-123')

        resposta = self.client.post(self.url, {'username': 'mecanico', 'password': 'errada'})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Usuário ou senha incorretos.')
        self.assertContains(resposta, 'value="mecanico"')

    def test_login_valido_entra_no_sistema(self):
        CustomUser.objects.create_user(username='mecanico', password='senha-certa-123')

        resposta = self.client.post(self.url, {'username': 'mecanico', 'password': 'senha-certa-123'})

        self.assertEqual(resposta.status_code, 302)
