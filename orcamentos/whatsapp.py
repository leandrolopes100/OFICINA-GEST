from django.urls import reverse

from core.templatetags.oficina_tags import currency
from core.whatsapp import (
    identidade_oficina, montar_link_whatsapp, motivo_sem_whatsapp, telefone_whatsapp_cliente,
)


def motivo_bloqueio_envio(orcamento):
    if orcamento.status not in orcamento.STATUS_EM_ABERTO:
        return f'Orçamento com status "{orcamento.get_status_display()}" não pode ser enviado.'
    if orcamento.validade_vencida:
        return (
            f'A validade venceu em {orcamento.data_validade:%d/%m/%Y}. '
            'Edite o orçamento e atualize a validade antes de enviar.'
        )
    return ''


def url_publica_orcamento(request, orcamento):
    return request.build_absolute_uri(
        reverse('orcamento_publico:detalhe', kwargs={'token': orcamento.token_publico})
    )


def montar_mensagem_orcamento(orcamento, url_publica):
    primeiro_nome = (orcamento.cliente.nome or '').split(' ')[0].title()
    veiculo = orcamento.veiculo
    return (
        f'Olá, {primeiro_nome}!\n\n'
        f'Segue o orçamento ORC-{orcamento.numero} da {identidade_oficina()["nome"]} '
        f'para o veículo {veiculo.modelo.nome} placa {veiculo.placa}.\n\n'
        f'Total: {currency(orcamento.total)}\n'
        f'Válido até: {orcamento.data_validade:%d/%m/%Y}\n\n'
        f'Para ver os detalhes e aprovar, acesse:\n{url_publica}'
    )


def link_whatsapp_orcamento(request, orcamento):
    telefone = telefone_whatsapp_cliente(orcamento.cliente)
    if not telefone:
        return None, None
    texto = montar_mensagem_orcamento(orcamento, url_publica_orcamento(request, orcamento))
    return telefone, montar_link_whatsapp(telefone, texto)
