import logging
import secrets
import sys

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import requires_csrf_token

from .publico import proteger
from .whatsapp import identidade_oficina

logger = logging.getLogger('oficina.erros')

PREFIXOS_PUBLICOS = ('/o/', '/a/')

ATALHOS = [
    ('Ordens de serviço', '/ordens-servico/', 'bi-clipboard2-check'),
    ('Orçamentos', '/orcamentos/', 'bi-file-earmark-text'),
    ('Clientes', '/clientes/', 'bi-people'),
    ('Veículos', '/veiculos/', 'bi-car-front'),
]

ERROS = {
    400: {
        'titulo': 'Pedido inválido',
        'mensagem': 'O endereço ou os dados enviados vieram num formato que o sistema não aceita. '
                    'Volte à página anterior e tente de novo.',
        'mensagem_publica': 'Não foi possível abrir este link. Confira se ele foi copiado inteiro '
                            'ou peça um novo para {oficina}.',
        'icone': 'bi-exclamation-diamond',
    },
    403: {
        'titulo': 'Acesso restrito',
        'mensagem': 'Seu usuário não tem permissão para abrir esta página. '
                    'Se precisar dela, peça ao administrador do sistema para ajustar seu perfil.',
        'mensagem_publica': 'Este link não pode ser aberto. Peça um novo para {oficina}.',
        'icone': 'bi-shield-lock',
    },
    'csrf': {
        'titulo': 'Formulário expirado',
        'mensagem': 'A página ficou aberta por muito tempo ou a sessão terminou, então o envio foi recusado. '
                    'Abra a página de novo e repita o envio.',
        'mensagem_publica': 'A página ficou aberta por muito tempo. Abra o link de novo e repita o envio.',
        'icone': 'bi-hourglass-bottom',
    },
    404: {
        'titulo': 'Página não encontrada',
        'mensagem': 'Este endereço não existe ou o registro foi removido. Confira o endereço abaixo.',
        'mensagem_publica': 'Este link não existe ou já expirou. Peça um novo para {oficina}.',
        'icone': 'bi-signpost-split',
    },
    429: {
        'titulo': 'Muitas tentativas',
        'mensagem': 'Foram muitas tentativas em pouco tempo. Aguarde alguns minutos e tente de novo.',
        'mensagem_publica': 'Foram muitas tentativas em pouco tempo. Aguarde alguns minutos e tente de novo.',
        'icone': 'bi-stopwatch',
    },
    500: {
        'titulo': 'Erro no sistema',
        'mensagem': 'O sistema encontrou um erro ao abrir esta página e o problema foi registrado. '
                    'Tente de novo em instantes. Se continuar, avise o suporte informando o código abaixo.',
        'mensagem_publica': 'Não foi possível abrir esta página agora. Tente de novo em instantes '
                            'ou fale com {oficina}.',
        'icone': 'bi-wrench-adjustable',
    },
}


def _eh_publico(request):
    return request.path.startswith(PREFIXOS_PUBLICOS)


def _contexto(chave, codigo, **extra):
    return {**ERROS[chave], 'codigo': codigo, **extra}


def _contexto_publico(chave, codigo, **extra):
    oficina = identidade_oficina()
    whatsapp = f'https://wa.me/{oficina["whatsapp"]}' if oficina['whatsapp'] else None
    contexto = _contexto(chave, codigo, oficina=oficina, whatsapp_oficina_url=whatsapp, **extra)
    contexto['mensagem_publica'] = contexto['mensagem_publica'].format(oficina=oficina['nome'] or 'a oficina')
    return contexto


def _renderizar(request, chave, codigo, **extra):
    if _eh_publico(request):
        resposta = render(request, 'erro/publico.html', _contexto_publico(chave, codigo, **extra), status=codigo)
        return proteger(resposta)
    contexto = _contexto(chave, codigo, **extra)
    if request.user.is_authenticated:
        contexto['atalhos'] = ATALHOS
    return render(request, 'erro/interno.html', contexto, status=codigo)


def pagina_de_erro(request, chave, codigo):
    return _renderizar(request, chave, codigo)


def _nomes_dos_perfis(perfis):
    from accounts.models import CustomUser
    nomes = dict(CustomUser.ROLE_CHOICES)
    return [nomes.get(perfil, perfil) for perfil in perfis]


def _endereco_de_volta(request):
    origem = request.META.get('HTTP_REFERER', '')
    seguro = url_has_allowed_host_and_scheme(
        origem, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    )
    return origem if seguro else '/'


@requires_csrf_token
def requisicao_invalida(request, exception=None):
    return _renderizar(request, 400, 400)


@requires_csrf_token
def sem_permissao(request, exception=None):
    extra = {}
    if request.user.is_authenticated:
        extra['usuario_atual'] = request.user.get_username()
        extra['perfil_atual'] = request.user.get_role_display()
        extra['perfis_exigidos'] = _nomes_dos_perfis(getattr(exception, 'perfis_permitidos', []))
    return _renderizar(request, 403, 403, **extra)


@requires_csrf_token
def nao_encontrada(request, exception=None):
    return _renderizar(request, 404, 404, endereco=request.path)


def falha_csrf(request, reason=''):
    if request.path == settings.LOGIN_URL:
        botao = ('Voltar ao login', reverse('accounts:login'))
    else:
        botao = ('Abrir a página de novo', _endereco_de_volta(request))
    return _renderizar(request, 'csrf', 403, botao_csrf=botao)


def erro_interno(request):
    hexa = secrets.token_hex(3).upper()
    referencia = f'{hexa[:4]}-{hexa[4:]}'
    logger.error('Erro 500 ref=%s %s %s', referencia, request.method, request.path, exc_info=sys.exc_info())
    if _eh_publico(request):
        conteudo = loader.get_template('erro/publico.html').render(
            _contexto_publico(500, 500, referencia=referencia)
        )
        return proteger(HttpResponse(conteudo, status=500))
    conteudo = loader.get_template('erro/interno.html').render(
        _contexto(500, 500, referencia=referencia, recarregar=True)
    )
    return HttpResponse(conteudo, status=500)
