"""
ordens_servico/views.py — todas as views em CBV
"""
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Q, Exists, OuterRef
from core.utils import calcular_taxa, periodo_do_request, registrar_historico

from core.whatsapp import formatar_telefone_exibicao, motivo_sem_whatsapp
from .models import OrdemServico, ItemOSServico, ItemOSPeca
from .whatsapp import (
    ACOMPANHAMENTO, PRONTO, TIPOS_MENSAGEM, link_whatsapp_ordem, motivo_bloqueio_envio,
    url_publica_ordem,
)
from .forms import (
    OrdemServicoForm,
    ItemOSServicoFormSet,
    ItemOSPecaFormSet,
    AtualizarStatusForm,
)

_CACHE_KEY_PRECOS = 'precos_data_v1'
_CACHE_TTL = 300


def _precos_data():
    """
    Retorna dicts Python com preços de serviços e produtos.
    Usar com o filtro |json_script no template para evitar auto-escape.
    Resultado cacheado por 5 minutos.
    """
    resultado = cache.get(_CACHE_KEY_PRECOS)
    if resultado is not None:
        return resultado

    from orcamentos.models import TipoServico
    from estoque.models import Produto

    servicos = {
        str(ts.pk): {'preco': float(ts.preco_padrao), 'nome': ts.nome}
        for ts in TipoServico.objects.filter(ativo=True).only('pk', 'nome', 'preco_padrao')
    }
    produtos = {
        str(p.pk): {'preco': float(p.preco_venda), 'nome': p.nome}
        for p in Produto.objects.filter(ativo=True).only('pk', 'nome', 'preco_venda')
    }
    resultado = (servicos, produtos)
    cache.set(_CACHE_KEY_PRECOS, resultado, _CACHE_TTL)
    return resultado


# ---------------------------------------------------------------------------
# Lista e detalhe
# ---------------------------------------------------------------------------

_STATUS_ATIVOS          = ['aberta', 'em_andamento', 'aguardando']
_STATUS_REQUER_PAGAMENTO = ['concluida', 'entregue']


class OrdemServicoListView(LoginRequiredMixin, ListView):
    model = OrdemServico
    template_name = 'ordens_servico/lista.html'
    context_object_name = 'ordens'
    paginate_by = 20

    def get_queryset(self):
        from financeiro.models import Lancamento

        # Anota cada OS com tem_pagamento=True/False via subquery (sem N+1)
        qs = OrdemServico.objects.select_related(
            'cliente', 'veiculo', 'mecanico'
        ).annotate(
            tem_pagamento=Exists(
                Lancamento.objects.filter(
                    ordem_servico_id=OuterRef('pk'),
                    tipo='receita',
                    status='pago',
                )
            )
        ).order_by('-data_abertura')

        q             = self.request.GET.get('q', '').strip()
        status        = self.request.GET.get('status', '')
        sem_pagamento = self.request.GET.get('sem_pagamento', '')
        de, ate = periodo_do_request(self.request)

        if q:
            termo_codigo = q.upper().removeprefix('OS-').replace('-', '').replace(' ', '')
            filtro = Q(cliente__nome__icontains=q)
            if termo_codigo:
                filtro |= Q(numero__icontains=termo_codigo) | Q(veiculo__placa__icontains=termo_codigo)
            qs = qs.filter(filtro)
        if de:
            qs = qs.filter(data_abertura__date__gte=de)
        if ate:
            qs = qs.filter(data_abertura__date__lte=ate)
        if status == 'abertas':
            qs = qs.filter(status__in=_STATUS_ATIVOS)
        elif status:
            qs = qs.filter(status=status)

        if sem_pagamento == '1':
            qs = qs.filter(status__in=_STATUS_REQUER_PAGAMENTO, tem_pagamento=False)

        return qs

    def get_context_data(self, **kwargs):
        from financeiro.models import Lancamento

        ctx  = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        ctx['status_choices']          = OrdemServico.STATUS_CHOICES
        ctx['status_atual']            = self.request.GET.get('status', '')
        ctx['busca']                   = self.request.GET.get('q', '')
        ctx['sem_pagamento_filtro']    = self.request.GET.get('sem_pagamento', '')
        de, ate = periodo_do_request(self.request)
        ctx['data_de']  = de.isoformat() if de else ''
        ctx['data_ate'] = ate.isoformat() if ate else ''
        ctx['hoje']                    = hoje
        ctx['status_ativos']           = _STATUS_ATIVOS
        ctx['statuses_requer_pagamento'] = _STATUS_REQUER_PAGAMENTO

        ctx['total_atrasadas'] = OrdemServico.objects.filter(
            data_previsao__lt=hoje,
            status__in=_STATUS_ATIVOS,
        ).count()

        # Contador global de OS finalizadas sem pagamento (independe dos filtros)
        ctx['pendentes_pagamento'] = OrdemServico.objects.filter(
            status__in=_STATUS_REQUER_PAGAMENTO,
        ).exclude(
            pk__in=Lancamento.objects.filter(
                tipo='receita', status='pago'
            ).values('ordem_servico_id')
        ).count()

        return ctx


class OrdemServicoDetailView(LoginRequiredMixin, DetailView):
    model = OrdemServico
    template_name = 'ordens_servico/detalhe.html'
    context_object_name = 'os'

    def get_queryset(self):
        return OrdemServico.objects.select_related(
            'cliente', 'veiculo', 'mecanico', 'orcamento', 'criado_por'
        ).prefetch_related('itens_servico__tipo_servico', 'itens_peca__produto')

    def get_context_data(self, **kwargs):
        from orcamentos.models import TipoServico
        from estoque.models import Produto

        ctx = super().get_context_data(**kwargs)
        ctx['status_form']   = AtualizarStatusForm(initial={'status': self.object.status})
        ctx['itens_servico'] = self.object.itens_servico.all()
        ctx['itens_peca']    = self.object.itens_peca.all()

        # Busca uma vez, reutiliza para JSON e para template (evita 2 queries duplicadas)
        tipos_servico = list(
            TipoServico.objects.filter(ativo=True).order_by('nome').only('pk', 'nome', 'preco_padrao')
        )
        produtos_list = list(
            Produto.objects.filter(ativo=True).order_by('nome').only('pk', 'nome', 'preco_venda')
        )
        ctx['tipos_servico_data'] = json.dumps(
            {str(t.pk): {'nome': t.nome, 'preco': str(t.preco_padrao)} for t in tipos_servico},
            ensure_ascii=False,
        )
        ctx['produtos_data'] = json.dumps(
            {str(p.pk): {'nome': p.nome, 'preco': str(p.preco_venda)} for p in produtos_list},
            ensure_ascii=False,
        )
        ctx['tipos_servico'] = tipos_servico
        ctx['produtos']      = produtos_list

        try:
            from financeiro.models import FormaPagamento, Lancamento
            ctx['formas_pagamento'] = FormaPagamento.objects.filter(ativo=True)
            lancamentos = Lancamento.objects.filter(
                ordem_servico=self.object,
                tipo='receita',
            ).order_by('data_competencia')
            ctx['lancamentos']    = lancamentos
            pagamento_pago        = lancamentos.filter(status='pago').first()
            ctx['pagamento_pago'] = pagamento_pago
            ctx['ja_pago']        = pagamento_pago is not None
        except Exception:
            ctx['formas_pagamento'] = []
            ctx['lancamentos']      = []
            ctx['pagamento_pago']   = None
            ctx['ja_pago']          = False

        ctx['historico_list'] = self.object.historico.select_related('usuario')[:15]

        sem_whatsapp = motivo_sem_whatsapp(self.object.cliente)
        ctx['motivo_bloqueio_acompanhamento'] = (
            motivo_bloqueio_envio(self.object, ACOMPANHAMENTO) or sem_whatsapp
        )
        ctx['motivo_bloqueio_pronto'] = motivo_bloqueio_envio(self.object, PRONTO) or sem_whatsapp
        ctx['url_acompanhamento'] = (
            url_publica_ordem(self.request, self.object)
            if self.object.link_visivel_ao_cliente else ''
        )
        return ctx


# ---------------------------------------------------------------------------
# Criação e edição (com inline formsets)
# ---------------------------------------------------------------------------

class OrdemServicoCreateView(LoginRequiredMixin, CreateView):
    model = OrdemServico
    form_class = OrdemServicoForm
    template_name = 'ordens_servico/form.html'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('cliente'):
            initial['cliente'] = self.request.GET.get('cliente')
        return initial

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        post = self.request.POST or None
        ctx['formset_srv']    = ItemOSServicoFormSet(post, prefix='srv')
        ctx['formset_peca']   = ItemOSPecaFormSet(post, prefix='peca')
        ctx['titulo']         = 'Nova Ordem de Serviço'
        ctx['veiculo_inicial'] = self.request.GET.get('veiculo', '')
        ctx['servicos_data'], ctx['produtos_data'] = _precos_data()
        return ctx

    def form_valid(self, form):
        ctx     = self.get_context_data(form=form)
        fs_srv  = ctx['formset_srv']
        fs_peca = ctx['formset_peca']

        if fs_srv.is_valid() and fs_peca.is_valid():
            form.instance.criado_por = self.request.user
            self.object = form.save()
            fs_srv.instance  = self.object
            fs_peca.instance = self.object
            fs_srv.save()
            fs_peca.save()
            self.object.recalcular_totais()
            messages.success(self.request, f'OS {self.object.numero} aberta com sucesso!')
            registrar_historico(ordem_servico=self.object, tipo='criacao',
                                descricao='OS aberta.', usuario=self.request.user)
            return redirect(self.get_success_url())

        # Exibe erros de estoque como messages (padrão do sistema)
        for peca_form in fs_peca.forms:
            for error in peca_form.errors.get('quantidade', []):
                messages.error(self.request, error)

        return self.render_to_response(ctx)

    def get_success_url(self):
        return reverse('ordens_servico:os_detalhe', kwargs={'pk': self.object.pk})


class OrdemServicoUpdateView(LoginRequiredMixin, UpdateView):
    model = OrdemServico
    form_class = OrdemServicoForm
    template_name = 'ordens_servico/form.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.pode_editar:
            messages.error(request, 'Esta OS não pode mais ser editada.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': obj.pk}))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        post = self.request.POST or None
        ctx['formset_srv']    = ItemOSServicoFormSet(post, instance=self.object, prefix='srv')
        ctx['formset_peca']   = ItemOSPecaFormSet(post, instance=self.object, prefix='peca')
        ctx['os']             = self.object
        ctx['titulo']         = f'Editar OS-{self.object.numero}'
        ctx['servicos_data'], ctx['produtos_data'] = _precos_data()
        return ctx

    def form_valid(self, form):
        ctx     = self.get_context_data(form=form)
        fs_srv  = ctx['formset_srv']
        fs_peca = ctx['formset_peca']

        if fs_srv.is_valid() and fs_peca.is_valid():
            form.save()
            fs_srv.save()
            fs_peca.save()
            self.object.recalcular_totais()
            messages.success(self.request, f'OS {self.object.numero} atualizada!')
            registrar_historico(ordem_servico=self.object, tipo='edicao',
                                descricao='OS editada.', usuario=self.request.user)
            return redirect(self.get_success_url())

        # Exibe erros de estoque como messages (padrão do sistema)
        for peca_form in fs_peca.forms:
            for error in peca_form.errors.get('quantidade', []):
                messages.error(self.request, error)

        return self.render_to_response(ctx)

    def get_success_url(self):
        return reverse('ordens_servico:os_detalhe', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Ações de status (POST-only)
# ---------------------------------------------------------------------------

class AtualizarStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from django.db import transaction
        from estoque.models import MovimentacaoEstoque

        os   = get_object_or_404(OrdemServico, pk=pk)
        form = AtualizarStatusForm(request.POST)
        if not form.is_valid():
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        novo_status     = form.cleaned_data['status']
        status_anterior = os.get_status_display()

        if not os.pode_mudar_para(novo_status):
            status_labels = dict(OrdemServico.STATUS_CHOICES)
            messages.error(
                request,
                f'Transição inválida: não é possível mudar de '
                f'"{os.get_status_display()}" para '
                f'"{status_labels.get(novo_status, novo_status)}".',
            )
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        # ── Conclusão: valida estoque e gera movimentações de saída ──
        if novo_status == 'concluida':
            itens_peca = os.itens_peca.select_related('produto').all()

            # Pré-checagem: identifica todos os produtos com estoque insuficiente
            insuficientes = [
                item for item in itens_peca
                if item.produto.estoque_atual < item.quantidade
            ]
            if insuficientes:
                lista = '; '.join(
                    f'{i.produto.nome} '
                    f'(disponível: {float(i.produto.estoque_atual):g} '
                    f'{i.produto.get_unidade_display()}, '
                    f'necessário: {float(i.quantidade):g})'
                    for i in insuficientes
                )
                messages.error(
                    request,
                    f'Não é possível concluir a OS: estoque insuficiente — {lista}.'
                )
                return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

            # Cria movimentações de saída e atualiza status em transação única
            try:
                with transaction.atomic():
                    for item in itens_peca:
                        if item.quantidade > 0:
                            MovimentacaoEstoque.objects.create(
                                produto=item.produto,
                                tipo='saida',
                                quantidade=item.quantidade,
                                custo_unitario=item.produto.preco_custo,
                                observacao=(
                                    f'OS-{os.numero} — {os.cliente.nome} '
                                    f'({item.descricao})'
                                ),
                                usuario=request.user,
                            )
                    os.registrar_mudanca_status(novo_status)
                    os.save()
                n_pecas = itens_peca.count()
                messages.success(
                    request,
                    f'OS {os.numero} concluída com sucesso! '
                    f'Estoque de {n_pecas} produto(s) atualizado.'
                )
                registrar_historico(
                    ordem_servico=os, tipo='status',
                    descricao=(
                        f'Status: {status_anterior} → Concluída. '
                        f'Estoque de {n_pecas} produto(s) baixado.'
                    ),
                    usuario=request.user,
                )
            except ValueError as exc:
                messages.error(request, f'Erro ao movimentar estoque: {exc}')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        # ── Demais transições de status ──
        os.registrar_mudanca_status(novo_status)
        os.save()
        messages.success(request, f'Status atualizado: {os.get_status_display()}')
        registrar_historico(
            ordem_servico=os, tipo='status',
            descricao=f'Status: {status_anterior} → {os.get_status_display()}.',
            usuario=request.user,
        )
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))


class EntregarOSView(LoginRequiredMixin, View):
    def post(self, request, pk):
        os = get_object_or_404(OrdemServico, pk=pk)
        if os.status != 'concluida':
            messages.error(request, 'Não é possível entregar esta OS no status atual.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        km_saida = request.POST.get('km_saida', '').strip()
        if km_saida:
            try:
                os.km_saida = int(km_saida)
            except ValueError:
                messages.error(request, 'KM de saída inválido.')
                return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        os.registrar_mudanca_status('entregue')
        os.save()
        messages.success(request, f'OS {os.numero} marcada como entregue!')
        km_info = f' — KM saída: {os.km_saida:,}' if os.km_saida else ''
        registrar_historico(ordem_servico=os, tipo='entrega',
                            descricao=f'Veículo entregue ao cliente{km_info}.',
                            usuario=request.user)
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))


class CancelarOSView(LoginRequiredMixin, View):
    def post(self, request, pk):
        os = get_object_or_404(OrdemServico, pk=pk)
        if not os.pode_mudar_para('cancelada'):
            messages.error(request, 'Não é possível cancelar esta OS no status atual.')
        else:
            status_anterior = os.get_status_display()
            os.registrar_mudanca_status('cancelada')
            os.save()
            messages.success(request, f'OS {os.numero} cancelada.')
            registrar_historico(ordem_servico=os, tipo='status',
                                descricao=f'Status: {status_anterior} → Cancelada.',
                                usuario=request.user)
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))


class OSEnviarWhatsAppView(LoginRequiredMixin, View):
    def post(self, request, pk, tipo):
        os = get_object_or_404(OrdemServico.objects.select_related('cliente', 'veiculo__modelo'), pk=pk)
        url_detalhe = reverse('ordens_servico:os_detalhe', kwargs={'pk': pk})
        if tipo not in TIPOS_MENSAGEM:
            return redirect(url_detalhe)

        motivo = motivo_bloqueio_envio(os, tipo) or motivo_sem_whatsapp(os.cliente)
        if motivo:
            messages.error(request, f'Não foi possível enviar pelo WhatsApp. {motivo}')
            return redirect(url_detalhe)

        os.garantir_link_publico()
        telefone, url_whatsapp = link_whatsapp_ordem(request, os, tipo)
        assunto = 'Aviso de veículo pronto' if tipo == PRONTO else 'Link de acompanhamento'
        registrar_historico(
            ordem_servico=os, tipo='outro', usuario=request.user,
            descricao=f'{assunto} enviado pelo WhatsApp para {formatar_telefone_exibicao(telefone)}.',
        )
        return redirect(url_whatsapp)


class OSNovoLinkView(LoginRequiredMixin, View):
    def post(self, request, pk):
        os = get_object_or_404(OrdemServico, pk=pk)
        url_detalhe = reverse('ordens_servico:os_detalhe', kwargs={'pk': pk})
        if os.status == 'cancelada':
            messages.error(request, 'Não é possível gerar link para uma OS cancelada.')
            return redirect(url_detalhe)
        tinha_link = bool(os.token_publico)
        os.regenerar_link_publico()
        if tinha_link:
            messages.success(request, 'Novo link gerado. O link anterior deixou de funcionar.')
            descricao = 'Novo link de acompanhamento gerado; o link anterior foi invalidado.'
        else:
            messages.success(request, 'Link de acompanhamento gerado. Copie e envie ao cliente.')
            descricao = 'Link de acompanhamento gerado.'
        registrar_historico(ordem_servico=os, tipo='outro', descricao=descricao, usuario=request.user)
        return redirect(url_detalhe)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

class OSPdfView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from .pdf import gerar_pdf_os
        os_obj    = get_object_or_404(OrdemServico, pk=pk)
        pdf_bytes = gerar_pdf_os(os_obj)
        response  = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="OS-{os_obj.numero}.pdf"'
        return response


class OSPrintView(LoginRequiredMixin, DetailView):
    """Página HTML formatada para impressão / salvar como PDF pelo browser."""
    model            = OrdemServico
    template_name    = 'ordens_servico/os_print.html'
    context_object_name = 'os'

    def get_queryset(self):
        return OrdemServico.objects.select_related(
            'cliente', 'veiculo', 'veiculo__modelo',
            'mecanico', 'orcamento', 'criado_por',
        ).prefetch_related(
            'itens_servico__tipo_servico',
            'itens_peca__produto',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            from financeiro.models import Lancamento
            ctx['pagamento'] = Lancamento.objects.filter(
                ordem_servico=self.object,
                tipo='receita',
                status='pago',
            ).select_related('forma_pagamento').first()
        except Exception:
            ctx['pagamento'] = None
        return ctx


# ---------------------------------------------------------------------------
# Pagamento
# ---------------------------------------------------------------------------

class RegistrarPagamentoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from financeiro.models import Lancamento, FormaPagamento

        os        = get_object_or_404(OrdemServico, pk=pk)
        valor_str = request.POST.get('valor_pago', '').replace(',', '.')
        forma_id  = request.POST.get('forma_pagamento', '').strip()
        obs       = request.POST.get('observacao', '')

        # Forma de pagamento obrigatória — validação backend independente do frontend
        if not forma_id:
            messages.error(request, 'Selecione uma forma de pagamento para confirmar o recebimento.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            valor = Decimal(valor_str)
            if valor <= 0:
                raise ValueError
        except (Exception, ValueError):
            messages.error(request, 'Informe um valor de pagamento válido e maior que zero.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            forma = FormaPagamento.objects.get(pk=forma_id, ativo=True)
        except FormaPagamento.DoesNotExist:
            messages.error(request, 'Forma de pagamento inválida ou inativa.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            lancamento = Lancamento.objects.filter(
                ordem_servico=os, tipo='receita',
            ).first()

            hoje       = timezone.now().date()
            valor_taxa = calcular_taxa(valor, forma)

            if not lancamento:
                Lancamento.objects.create(
                    tipo='receita',
                    categoria='servico',
                    forma_pagamento=forma,
                    descricao=f'OS-{os.numero} — {os.cliente.nome}',
                    valor=valor,
                    valor_taxa=valor_taxa,
                    data_competencia=hoje,
                    data_vencimento=hoje,
                    data_pagamento=hoje,
                    status='pago',
                    ordem_servico=os,
                    observacoes=obs,
                )
            else:
                lancamento.data_pagamento  = hoje
                lancamento.status          = 'pago'
                lancamento.valor           = valor
                lancamento.valor_taxa      = valor_taxa
                lancamento.forma_pagamento = forma   # sempre atualiza — agora obrigatória
                if obs:
                    lancamento.observacoes = obs
                lancamento.save()

            messages.success(request, f'Pagamento de R$ {valor:.2f} registrado com sucesso!')
            registrar_historico(
                ordem_servico=os, tipo='pagamento',
                descricao=(
                    f'Pagamento de R$ {valor:.2f} registrado'
                    f'{f" via {forma.nome}" if forma else ""}.'
                ),
                usuario=request.user,
            )

        except Exception as exc:
            messages.warning(request, f'Erro ao registrar lançamento financeiro: {exc}')

        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Adição rápida de itens direto do detalhe da OS
# ---------------------------------------------------------------------------

class AdicionarServicoView(LoginRequiredMixin, View):
    """Adiciona um ItemOSServico à OS sem precisar ir para a página de edição."""

    def post(self, request, pk):
        os = get_object_or_404(OrdemServico, pk=pk)

        if not os.pode_editar:
            messages.error(request, 'Não é possível adicionar itens a uma OS neste status.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        from orcamentos.models import TipoServico

        tipo_id    = request.POST.get('tipo_servico', '').strip()
        descricao  = request.POST.get('descricao', '').strip()
        quantidade = request.POST.get('quantidade', '').strip()
        preco_str  = request.POST.get('preco_unitario', '').strip().replace(',', '.')

        if not descricao:
            messages.error(request, 'A descrição do serviço é obrigatória.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            qtd = Decimal(quantidade)
            if qtd <= 0:
                raise ValueError
        except Exception:
            messages.error(request, 'Quantidade inválida — deve ser maior que zero.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            preco = Decimal(preco_str)
            if preco < 0:
                raise ValueError
        except Exception:
            messages.error(request, 'Preço unitário inválido.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        # [C-03] tipo_servico é FK NOT NULL — requer seleção obrigatória nesta view
        if not tipo_id:
            messages.error(request, 'Selecione um tipo de serviço do catálogo.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            tipo = TipoServico.objects.get(pk=int(tipo_id), ativo=True)
        except (TipoServico.DoesNotExist, ValueError):
            messages.error(request, 'Tipo de serviço inválido ou inativo.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        ItemOSServico.objects.create(
            ordem_servico=os,
            tipo_servico=tipo,
            descricao=descricao,
            quantidade=qtd,
            preco_unitario=preco,
        )
        os.recalcular_totais()
        messages.success(request, f'Serviço "{descricao}" adicionado com sucesso!')
        registrar_historico(ordem_servico=os, tipo='item_add',
                            descricao=f'Serviço adicionado: {descricao} × {float(qtd):g}.',
                            usuario=request.user)
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))


class AdicionarPecaView(LoginRequiredMixin, View):
    """Adiciona um ItemOSPeca à OS sem precisar ir para a página de edição."""

    def post(self, request, pk):
        os = get_object_or_404(OrdemServico, pk=pk)

        if not os.pode_editar:
            messages.error(request, 'Não é possível adicionar itens a uma OS neste status.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        from estoque.models import Produto

        produto_id = request.POST.get('produto', '').strip()
        descricao  = request.POST.get('descricao', '').strip()
        quantidade = request.POST.get('quantidade', '').strip()
        preco_str  = request.POST.get('preco_unitario', '').strip().replace(',', '.')

        if not produto_id:
            messages.error(request, 'Selecione um produto.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            produto = Produto.objects.get(pk=int(produto_id), ativo=True)
        except (Produto.DoesNotExist, ValueError):
            messages.error(request, 'Produto inválido ou inativo.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        if not descricao:
            descricao = produto.nome

        try:
            qtd = Decimal(quantidade)
            if qtd <= 0:
                raise ValueError
        except Exception:
            messages.error(request, 'Quantidade inválida — deve ser maior que zero.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        try:
            preco = Decimal(preco_str)
            if preco < 0:
                raise ValueError
        except Exception:
            messages.error(request, 'Preço unitário inválido.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        # Valida estoque disponível antes de adicionar o item
        if produto.estoque_atual < qtd:
            messages.error(
                request,
                f'Estoque insuficiente para "{produto.nome}": '
                f'disponível {float(produto.estoque_atual):g} '
                f'{produto.get_unidade_display()}, '
                f'solicitado {float(qtd):g}.'
            )
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))

        ItemOSPeca.objects.create(
            ordem_servico=os,
            produto=produto,
            descricao=descricao,
            quantidade=qtd,
            preco_unitario=preco,
        )
        os.recalcular_totais()
        messages.success(request, f'Peça "{descricao}" adicionada com sucesso!')
        registrar_historico(
            ordem_servico=os, tipo='item_add',
            descricao=f'Peça adicionada: {descricao} × {float(qtd):g} {produto.get_unidade_display()}.',
            usuario=request.user,
        )
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': pk}))
