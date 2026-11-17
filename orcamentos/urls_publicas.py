from django.urls import re_path

from . import views_publicas

app_name = 'orcamento_publico'

_TOKEN = r'(?P<token>[A-Za-z0-9_-]{32,64})'

urlpatterns = [
    re_path(rf'^{_TOKEN}/$', views_publicas.OrcamentoPublicoView.as_view(), name='detalhe'),
    re_path(rf'^{_TOKEN}/pdf/$', views_publicas.OrcamentoPublicoPdfView.as_view(), name='pdf'),
]
