import re
from urllib.parse import quote

from django.conf import settings

_NAO_DIGITO = re.compile(r'\D')


def _normalizar(numero):
    digitos = _NAO_DIGITO.sub('', numero or '')
    if digitos.startswith('00'):
        digitos = digitos[2:]
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        digitos = digitos[2:]
    if len(digitos) in (11, 12) and digitos.startswith('0'):
        digitos = digitos[1:]

    if len(digitos) not in (10, 11) or digitos[0] == '0' or digitos[1] == '0':
        return None
    if len(digitos) == 11 and digitos[2] != '9':
        return None
    if len(digitos) == 10 and digitos[2] not in '2345':
        return None
    return '55' + digitos


def normalizar_telefone_whatsapp(*numeros):
    for numero in numeros:
        normalizado = _normalizar(numero)
        if normalizado:
            return normalizado
    return None


def formatar_telefone_exibicao(telefone_normalizado):
    if not telefone_normalizado:
        return ''
    local = telefone_normalizado[2:]
    ddd, resto = local[:2], local[2:]
    return f'({ddd}) {resto[:-4]}-{resto[-4:]}'


def montar_link_whatsapp(telefone_normalizado, texto):
    return f'https://wa.me/{telefone_normalizado}?text={quote(texto)}'


def identidade_oficina():
    return {
        'nome': settings.OFICINA_NOME,
        'logo': settings.OFICINA_LOGO,
        'whatsapp': normalizar_telefone_whatsapp(settings.OFICINA_WHATSAPP),
    }
