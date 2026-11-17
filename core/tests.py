from django.test import SimpleTestCase

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
