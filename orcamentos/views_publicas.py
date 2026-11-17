from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from core.publico import excedeu_limite, ip_do_cliente, muitas_requisicoes, proteger
from core.utils import registrar_historico
from core.whatsapp import identidade_oficina, montar_link_whatsapp
from .forms import RespostaClienteForm
from .models import ConteudoAlterado, LinkIndisponivel, Orcamento, RespostaCliente

_ACOES = (RespostaCliente.APROVADO, RespostaCliente.RECUSADO)


def _obter_orcamento(token):
    return get_object_or_404(
        Orcamento.objects.select_related('cliente', 'veiculo', 'veiculo__marca', 'veiculo__modelo'),
        token_publico=token,
    )


class OrcamentoPublicoView(View):
    template_name = 'orcamentos/publico/orcamento.html'

    def dispatch(self, request, *args, **kwargs):
        if excedeu_limite(request, 'orcamento', maximo=60, janela_segundos=60):
            return muitas_requisicoes()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, token):
        return self._renderizar(request, _obter_orcamento(token))

    def post(self, request, token):
        if excedeu_limite(request, 'orcamento-resposta', maximo=10, janela_segundos=300):
            return muitas_requisicoes()
        orcamento = _obter_orcamento(token)
        url_pagina = reverse('orcamento_publico:detalhe', kwargs={'token': token})

        acao = request.POST.get('acao')
        if acao not in _ACOES:
            return redirect(url_pagina)

        form = RespostaClienteForm(
            request.POST, prefix=acao,
            exige_confirmacao=(acao == RespostaCliente.APROVADO),
        )
        if not form.is_valid():
            return self._renderizar(request, orcamento, form_invalido=(acao, form), status=400)

        nome = form.cleaned_data['nome']
        motivo = form.cleaned_data['motivo']
        try:
            orcamento.registrar_resposta_cliente(
                decisao=acao,
                nome=nome,
                motivo=motivo,
                hash_visto=form.cleaned_data['hash_conteudo'],
                ip=ip_do_cliente(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except LinkIndisponivel:
            messages.warning(request, 'Este orçamento não está mais aguardando resposta.')
            return redirect(url_pagina)
        except ConteudoAlterado:
            messages.warning(
                request,
                'A oficina atualizou este orçamento enquanto você o visualizava. '
                'Confira os valores abaixo antes de responder.',
            )
            return redirect(url_pagina)

        if acao == RespostaCliente.APROVADO:
            descricao = f'Status: Enviado ao Cliente → Aprovado pelo cliente via link. Nome informado: {nome}.'
            messages.success(request, 'Orçamento aprovado! A oficina já foi avisada.')
        else:
            descricao = f'Status: Enviado ao Cliente → Recusado pelo cliente via link. Nome informado: {nome}.'
            if motivo:
                descricao += f' Motivo: {motivo}'
            messages.info(request, 'Sua resposta foi registrada. Obrigado!')
        registrar_historico(orcamento=orcamento, tipo='status', descricao=descricao)
        return redirect(url_pagina)

    def _renderizar(self, request, orcamento, form_invalido=None, status=200):
        oficina = identidade_oficina()
        if not orcamento.link_visivel_ao_cliente:
            return proteger(render(
                request, 'orcamentos/publico/indisponivel.html',
                {'oficina': oficina, 'whatsapp_oficina_url': self._whatsapp_oficina(oficina, orcamento)},
                status=410,
            ))

        forms = {}
        if orcamento.aceita_resposta_cliente:
            hash_atual = orcamento.hash_conteudo()
            for acao in _ACOES:
                forms[acao] = RespostaClienteForm(prefix=acao, initial={'hash_conteudo': hash_atual})
            if form_invalido:
                forms[form_invalido[0]] = form_invalido[1]

        contexto = {
            'orcamento': orcamento,
            'oficina': oficina,
            'itens_servico': orcamento.itens_servico.all(),
            'itens_peca': orcamento.itens_peca.all(),
            'resposta': orcamento.respostas_cliente.first(),
            'form_aprovar': forms.get(RespostaCliente.APROVADO),
            'form_recusar': forms.get(RespostaCliente.RECUSADO),
            'recusa_aberta': bool(form_invalido and form_invalido[0] == RespostaCliente.RECUSADO),
            'whatsapp_oficina_url': self._whatsapp_oficina(oficina, orcamento),
        }
        return proteger(render(request, self.template_name, contexto, status=status))

    @staticmethod
    def _whatsapp_oficina(oficina, orcamento):
        if not oficina['whatsapp']:
            return ''
        return montar_link_whatsapp(
            oficina['whatsapp'],
            f'Olá! Tenho uma dúvida sobre o orçamento ORC-{orcamento.numero}.',
        )


class OrcamentoPublicoPdfView(View):
    def get(self, request, token):
        if excedeu_limite(request, 'orcamento-pdf', maximo=20, janela_segundos=60):
            return muitas_requisicoes()
        from .pdf import gerar_pdf_orcamento
        orcamento = _obter_orcamento(token)
        if not orcamento.link_visivel_ao_cliente:
            raise Http404
        resposta = HttpResponse(gerar_pdf_orcamento(orcamento), content_type='application/pdf')
        resposta['Content-Disposition'] = f'inline; filename="orcamento-{orcamento.numero}.pdf"'
        return proteger(resposta)
