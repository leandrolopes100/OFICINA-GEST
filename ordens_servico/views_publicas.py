from django.shortcuts import get_object_or_404, render
from django.views import View

from core.publico import excedeu_limite, muitas_requisicoes, proteger
from core.whatsapp import identidade_oficina, montar_link_whatsapp
from .models import OrdemServico
from .whatsapp import STATUS_PARA_CLIENTE


class AcompanhamentoPublicoView(View):
    template_name = 'ordens_servico/publico/acompanhamento.html'

    def get(self, request, token):
        if excedeu_limite(request, 'acompanhamento', maximo=60, janela_segundos=60):
            return muitas_requisicoes()
        ordem = get_object_or_404(
            OrdemServico.objects.select_related('cliente', 'veiculo__marca', 'veiculo__modelo'),
            token_publico=token,
        )
        oficina = identidade_oficina()
        whatsapp_oficina_url = ''
        if oficina['whatsapp']:
            whatsapp_oficina_url = montar_link_whatsapp(
                oficina['whatsapp'], f'Olá! Tenho uma dúvida sobre a OS-{ordem.numero}.',
            )

        if not ordem.link_visivel_ao_cliente:
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
