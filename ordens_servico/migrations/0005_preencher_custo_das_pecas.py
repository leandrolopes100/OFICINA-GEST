from django.db import migrations


def _escolher_saida(item, disponiveis):
    mesmo_produto = [mov for mov in disponiveis if mov.produto_id == item.produto_id]
    for mov in mesmo_produto:
        if mov.quantidade == item.quantidade:
            return mov
    return mesmo_produto[0] if mesmo_produto else None


def preencher_custos(apps, schema_editor):
    OrdemServico = apps.get_model('ordens_servico', 'OrdemServico')
    ItemOSPeca = apps.get_model('ordens_servico', 'ItemOSPeca')
    MovimentacaoEstoque = apps.get_model('estoque', 'MovimentacaoEstoque')

    for ordem in OrdemServico.objects.filter(status__in=['concluida', 'entregue']).iterator():
        saidas = list(MovimentacaoEstoque.objects.filter(
            tipo='saida', ordem_servico__isnull=True, observacao__startswith=f'OS-{ordem.numero} —',
        ))
        for mov in saidas:
            mov.ordem_servico_id = ordem.pk
        MovimentacaoEstoque.objects.bulk_update(saidas, ['ordem_servico'])

        disponiveis = list(saidas)
        itens = list(ItemOSPeca.objects.filter(ordem_servico=ordem).select_related('produto'))
        for item in itens:
            mov = _escolher_saida(item, disponiveis) if item.quantidade > 0 else None
            if mov is not None:
                disponiveis.remove(mov)
                item.custo_unitario = mov.custo_unitario
                item.custo_estimado = False
            else:
                item.custo_unitario = item.produto.preco_custo
                item.custo_estimado = item.quantidade > 0
        ItemOSPeca.objects.bulk_update(itens, ['custo_unitario', 'custo_estimado'])


class Migration(migrations.Migration):

    dependencies = [
        ('ordens_servico', '0004_itemospeca_custo_estimado_itemospeca_custo_unitario'),
        ('estoque', '0004_movimentacaoestoque_ordem_servico'),
    ]

    operations = [
        migrations.RunPython(preencher_custos, migrations.RunPython.noop),
    ]
