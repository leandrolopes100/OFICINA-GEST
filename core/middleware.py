from django.utils.cache import add_never_cache_headers


class SemCacheParaUsuarioLogadoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(resposta)
        return resposta
