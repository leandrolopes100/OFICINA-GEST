from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from core.publico import excedeu_limite, muitas_requisicoes, proteger
from core.whatsapp import identidade_oficina, montar_link_whatsapp
from .models import OrdemServico
from .whatsapp import STATUS_PARA_CLIENTE


def _obter_ordem(token):
    return get_object_or_404(
        OrdemServico.objects.select_related('cliente', 'veiculo__marca', 'veiculo__modelo', 'mecanico'),
        token_publico=token,
    )


def _whatsapp_oficina(oficina, ordem):
    if not oficina['whatsapp']:
        return ''
    return montar_link_whatsapp(oficina['whatsapp'], f'Olá! Tenho uma dúvida sobre a OS-{ordem.numero}.')


def _indisponivel(request, oficina, whatsapp_oficina_url):
    return proteger(render(
        request, 'orcamentos/publico/indisponivel.html',
        {
            'oficina': oficina,
            'whatsapp_oficina_url': whatsapp_oficina_url,
            'mensagem': 'O prazo de consulta deste serviço terminou. '
                        'Fale com a oficina se precisar de alguma informação.',
        },
        status=410,
    ))


class AcompanhamentoPublicoView(View):
    template_name = 'ordens_servico/publico/acompanhamento.html'

    def get(self, request, token):
        if excedeu_limite(request, 'acompanhamento', maximo=60, janela_segundos=60):
            return muitas_requisicoes()
        ordem = _obter_ordem(token)
        oficina = identidade_oficina()
        whatsapp_oficina_url = _whatsapp_oficina(oficina, ordem)
        if not ordem.link_visivel_ao_cliente:
            return _indisponivel(request, oficina, whatsapp_oficina_url)

        contexto = {
            'ordem': ordem,
            'oficina': oficina,
            'situacao': STATUS_PARA_CLIENTE[ordem.status],
            'etapas': ordem.etapas_acompanhamento,
            'itens_servico': ordem.itens_servico.all(),
            'itens_peca': ordem.itens_peca.all(),
            'whatsapp_oficina_url': whatsapp_oficina_url,
        }
        return proteger(render(request, self.template_name, contexto))


class AcompanhamentoPublicoDocumentoView(View):
    template_name = 'ordens_servico/publico/documento.html'

    def get(self, request, token):
        if excedeu_limite(request, 'acompanhamento', maximo=60, janela_segundos=60):
            return muitas_requisicoes()
        ordem = _obter_ordem(token)
        oficina = identidade_oficina()
        whatsapp_oficina_url = _whatsapp_oficina(oficina, ordem)
        if not ordem.link_visivel_ao_cliente:
            return _indisponivel(request, oficina, whatsapp_oficina_url)

        contexto = {
            'ordem': ordem,
            'oficina': oficina,
            'situacao': STATUS_PARA_CLIENTE[ordem.status],
            'whatsapp_oficina_url': whatsapp_oficina_url,
        }
        return proteger(render(request, self.template_name, contexto))


class AcompanhamentoPublicoPdfView(View):
    def get(self, request, token):
        if excedeu_limite(request, 'acompanhamento-pdf', maximo=20, janela_segundos=60):
            return muitas_requisicoes()
        from .pdf import gerar_pdf_os
        ordem = _obter_ordem(token)
        if not ordem.link_visivel_ao_cliente:
            raise Http404
        disposicao = 'attachment' if request.GET.get('baixar') else 'inline'
        resposta = HttpResponse(gerar_pdf_os(ordem, para_cliente=True), content_type='application/pdf')
        resposta['Content-Disposition'] = f'{disposicao}; filename="OS-{ordem.numero}.pdf"'
        return proteger(resposta)
