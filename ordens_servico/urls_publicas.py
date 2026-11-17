from django.urls import re_path

from . import views_publicas

app_name = 'acompanhamento_publico'

urlpatterns = [
    re_path(
        r'^(?P<token>[A-Za-z0-9_-]{32,64})/$',
        views_publicas.AcompanhamentoPublicoView.as_view(),
        name='detalhe',
    ),
]
