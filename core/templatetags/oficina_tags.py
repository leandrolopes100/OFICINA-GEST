from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def currency(value):
    try:
        return f'R$ {Decimal(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return value


@register.filter
def cpf_cnpj(value):
    if not value:
        return ''
    v = ''.join(filter(str.isdigit, str(value)))
    if len(v) == 11:
        return f'{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}'
    elif len(v) == 14:
        return f'{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}'
    return value


@register.filter
def status_badge(status):
    badges = {
        'rascunho': 'secondary',
        'enviado': 'info',
        'aprovado': 'success',
        'reprovado': 'danger',
        'expirado': 'warning',
        'cancelado': 'dark',
        'aberta': 'primary',
        'em_andamento': 'warning',
        'aguardando': 'info',
        'concluida': 'success',
        'entregue': 'success',
        'pendente': 'warning',
        'pago': 'success',
        'vencido': 'danger',
    }
    return badges.get(status, 'secondary')


@register.simple_tag
def get_status_display(obj, field='status'):
    return getattr(obj, f'get_{field}_display', lambda: '')()
