import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def ip_do_cliente(request):
    cabecalho = settings.IP_CLIENTE_CABECALHO
    valor = request.META.get(cabecalho, '') if cabecalho != 'REMOTE_ADDR' else ''
    if cabecalho == 'HTTP_X_FORWARDED_FOR':
        valor = valor.split(',')[-1]
    candidato = valor.strip() or request.META.get('REMOTE_ADDR', '')
    try:
        return str(ipaddress.ip_address(candidato))
    except ValueError:
        return None


def excedeu_limite(request, escopo, maximo, janela_segundos):
    chave = f'rl-publico:{escopo}:{ip_do_cliente(request) or "desconhecido"}'
    cache.add(chave, 0, janela_segundos)
    try:
        total = cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, janela_segundos)
        total = 1
    return total > maximo


def proteger(resposta):
    resposta['X-Robots-Tag'] = 'noindex, nofollow'
    resposta['Referrer-Policy'] = 'no-referrer'
    resposta['Cache-Control'] = 'no-store'
    return resposta


def muitas_requisicoes():
    return proteger(HttpResponse(
        'Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.',
        status=429, content_type='text/plain; charset=utf-8',
    ))
