from django.urls import reverse

from core.templatetags.oficina_tags import currency
from core.whatsapp import identidade_oficina, montar_link_whatsapp, telefone_whatsapp_cliente

ACOMPANHAMENTO = 'acompanhamento'
PRONTO = 'pronto'
TIPOS_MENSAGEM = (ACOMPANHAMENTO, PRONTO)

STATUS_PARA_CLIENTE = {
    'aberta': 'Recebido pela oficina',
    'em_andamento': 'Em serviço',
    'aguardando': 'Aguardando peça/aprovação',
    'concluida': 'Pronto para retirada',
    'entregue': 'Entregue',
    'cancelada': 'Cancelado',
}


def motivo_bloqueio_envio(ordem, tipo):
    if ordem.status == 'cancelada':
        return 'A OS está cancelada.'
    if tipo == PRONTO and ordem.status != 'concluida':
        return 'O aviso de pronto só pode ser enviado com a OS concluída.'
    if ordem.status == 'entregue' and ordem.token_publico and not ordem.link_visivel_ao_cliente:
        return (
            f'O link expirou {ordem.DIAS_LINK_APOS_ENCERRAMENTO} dias após a entrega. '
            'Gere um novo link para enviar.'
        )
    return ''


def url_publica_ordem(request, ordem):
    return request.build_absolute_uri(
        reverse('acompanhamento_publico:detalhe', kwargs={'token': ordem.token_publico})
    )


def montar_mensagem_ordem(ordem, tipo, url_publica):
    primeiro_nome = (ordem.cliente.nome or '').split(' ')[0].title()
    veiculo = f'{ordem.veiculo.modelo.nome} placa {ordem.veiculo.placa}'
    oficina = identidade_oficina()['nome']
    if tipo == PRONTO:
        return (
            f'Olá, {primeiro_nome}!\n\n'
            f'Seu {veiculo} está pronto para retirada na {oficina}.\n\n'
            f'Total: {currency(ordem.total)}\n\n'
            f'Detalhes do serviço (OS-{ordem.numero}):\n{url_publica}'
        )
    return (
        f'Olá, {primeiro_nome}!\n\n'
        f'Você pode acompanhar o serviço do seu {veiculo} na {oficina} pelo link abaixo.\n\n'
        f'OS-{ordem.numero} · Situação atual: {STATUS_PARA_CLIENTE[ordem.status]}\n\n'
        f'{url_publica}'
    )


def link_whatsapp_ordem(request, ordem, tipo):
    telefone = telefone_whatsapp_cliente(ordem.cliente)
    if not telefone:
        return None, None
    texto = montar_mensagem_ordem(ordem, tipo, url_publica_ordem(request, ordem))
    return telefone, montar_link_whatsapp(telefone, texto)
