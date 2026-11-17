from core.versao import versao_sistema


def versao(request):
    usuario = getattr(request, 'user', None)
    if not (usuario and usuario.is_authenticated):
        return {}
    return {'versao_sistema': versao_sistema()}
