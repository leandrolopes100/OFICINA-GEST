from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def parse_mes_ano(request, hoje):
    """Valida e retorna (mes, ano) da query string, com fallback seguro."""
    try:
        mes = int(request.GET.get('mes', hoje.month))
        ano = int(request.GET.get('ano', hoje.year))
    except (ValueError, TypeError):
        return hoje.month, hoje.year
    if not (1 <= mes <= 12):
        mes = hoje.month
    if not (2000 <= ano <= 2100):
        ano = hoje.year
    return mes, ano


def calcular_taxa(valor, forma_pagamento):
    """Calcula o valor monetário da taxa de uma forma de pagamento."""
    if forma_pagamento and forma_pagamento.taxa > 0:
        return (valor * forma_pagamento.taxa / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    return Decimal('0')


def registrar_historico(*, orcamento=None, ordem_servico=None,
                        tipo='outro', descricao, usuario=None):
    """
    Registra um evento de auditoria no Historico.
    Sempre envolto em try/except — falhas aqui nunca interrompem o fluxo principal.
    """
    try:
        from core.models import Historico
        Historico.objects.create(
            orcamento=orcamento,
            ordem_servico=ordem_servico,
            tipo=tipo,
            descricao=descricao,
            usuario=usuario,
        )
    except Exception:
        pass


def rate_limit_ajax(max_calls: int = 30, window: int = 60):
    """
    Decorator para endpoints AJAX que limita requisições por usuário (ou IP).
    Retorna HTTP 429 quando o limite é excedido.

    Uso:
        @login_required
        @rate_limit_ajax(max_calls=30, window=60)
        def minha_view_ajax(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            identifier = (
                str(request.user.pk)
                if request.user.is_authenticated
                else request.META.get('REMOTE_ADDR', 'anon')
            )
            cache_key = f'rl:{view_func.__name__}:{identifier}'
            count = cache.get(cache_key, 0)
            if count >= max_calls:
                return JsonResponse(
                    {'error': 'Muitas requisições. Aguarde alguns instantes.'},
                    status=429,
                )
            cache.set(cache_key, count + 1, window)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
