from django.urls import re_path

from . import views_publicas

app_name = 'acompanhamento_publico'

_TOKEN = r'(?P<token>[A-Za-z0-9_-]{32,64})'

urlpatterns = [
    re_path(rf'^{_TOKEN}/$', views_publicas.AcompanhamentoPublicoView.as_view(), name='detalhe'),
    re_path(rf'^{_TOKEN}/os/$', views_publicas.AcompanhamentoPublicoDocumentoView.as_view(), name='documento'),
    re_path(rf'^{_TOKEN}/pdf/$', views_publicas.AcompanhamentoPublicoPdfView.as_view(), name='pdf'),
]
