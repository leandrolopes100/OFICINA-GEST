import json

from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from estoque.models import Produto
from .models import Orcamento, TipoServico, TransicaoStatusInvalida
from .forms import OrcamentoForm, ItemServicoFormSet, ItemPecaFormSet, TipoServicoForm
from .whatsapp import (
    link_whatsapp_orcamento, motivo_bloqueio_envio, motivo_sem_whatsapp, url_publica_orcamento,
)
from core.mixins import RoleRequiredMixin
from core.utils import periodo_do_request, registrar_historico
from core.whatsapp import formatar_telefone_exibicao

_CACHE_KEY_TIPOS = 'lookup_tipos_servico_json_v1'
_CACHE_KEY_PRODUTOS = 'lookup_produtos_json_v1'
_CACHE_TTL = 300


def _build_lookup_json(ctx):
    tipos_json = cache.get(_CACHE_KEY_TIPOS)
    if tipos_json is None:
        tipos_json = json.dumps(
            {str(t.id): {'nome': t.nome, 'preco': str(t.preco_padrao)}
             for t in TipoServico.objects.filter(ativo=True)},
            ensure_ascii=False,
        )
        cache.set(_CACHE_KEY_TIPOS, tipos_json, _CACHE_TTL)

    produtos_json = cache.get(_CACHE_KEY_PRODUTOS)
    if produtos_json is None:
        produtos_json = json.dumps(
            {str(p.id): {'nome': p.nome, 'preco': str(p.preco_venda)}
             for p in Produto.objects.filter(ativo=True)},
            ensure_ascii=False,
        )
        cache.set(_CACHE_KEY_PRODUTOS, produtos_json, _CACHE_TTL)

    ctx['tipos_servico_json'] = tipos_json
    ctx['produtos_json'] = produtos_json


class OrcamentoListView(LoginRequiredMixin, ListView):
    model = Orcamento
    template_name = 'orcamentos/orcamento_list.html'
    context_object_name = 'orcamentos'
    paginate_by = 20

    def get_queryset(self):
        from ordens_servico.models import OrdemServico

        # Anota cada orçamento com tem_os=True/False usando subquery (sem N+1)
        qs = (
            Orcamento.objects
            .select_related('cliente', 'veiculo')
            .annotate(tem_os=Exists(OrdemServico.objects.filter(orcamento_id=OuterRef('pk'))))
            .order_by('-data_criacao')
        )

        status = self.request.GET.get('status', '')
        q      = self.request.GET.get('q', '').strip()
        aguardando_os = self.request.GET.get('aguardando_os', '')
        de, ate = periodo_do_request(self.request)

        if status:
            qs = qs.filter(status=status)
        if q:
            termo_codigo = q.upper().removeprefix('ORC-').replace('-', '').replace(' ', '')
            filtro = Q(cliente__nome__icontains=q)
            if termo_codigo:
                filtro |= Q(numero__icontains=termo_codigo) | Q(veiculo__placa__icontains=termo_codigo)
            qs = qs.filter(filtro)
        if de:
            qs = qs.filter(data_criacao__date__gte=de)
        if ate:
            qs = qs.filter(data_criacao__date__lte=ate)
        if aguardando_os in ('1', 'cliente'):
            qs = qs.filter(status='aprovado', tem_os=False)
        if aguardando_os == 'cliente':
            qs = qs.filter(respostas_cliente__decisao='aprovado').distinct()

        return qs

    def get_context_data(self, **kwargs):
        from ordens_servico.models import OrdemServico

        ctx = super().get_context_data(**kwargs)
        ctx['status_choices']  = Orcamento.STATUS_CHOICES
        ctx['status_filter']   = self.request.GET.get('status', '')
        ctx['q']               = self.request.GET.get('q', '').strip()
        ctx['aguardando_os']   = self.request.GET.get('aguardando_os', '')
        de, ate = periodo_do_request(self.request)
        ctx['data_de']  = de.isoformat() if de else ''
        ctx['data_ate'] = ate.isoformat() if ate else ''
        filtros = self.request.GET.copy()
        filtros.pop('page', None)
        ctx['filtros_querystring'] = filtros.urlencode()

        # Contador global (independe dos filtros ativos) para o card de alerta
        ctx['pendentes_os'] = (
            Orcamento.objects
            .filter(status='aprovado')
            .exclude(pk__in=OrdemServico.objects.values('orcamento_id'))
            .count()
        )
        return ctx


class OrcamentoDetailView(LoginRequiredMixin, DetailView):
    model = Orcamento
    template_name = 'orcamentos/orcamento_detail.html'
    context_object_name = 'orcamento'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['itens_servico']  = self.object.itens_servico.select_related('tipo_servico')
        ctx['itens_peca']     = self.object.itens_peca.select_related('produto')
        ctx['historico_list'] = self.object.historico.select_related('usuario')[:15]
        ctx['resposta_cliente'] = self.object.respostas_cliente.first()
        ctx['motivo_bloqueio_envio'] = motivo_bloqueio_envio(self.object)
        ctx['motivo_sem_whatsapp'] = ctx['motivo_bloqueio_envio'] or motivo_sem_whatsapp(self.object.cliente)
        ctx['url_publica'] = (
            url_publica_orcamento(self.request, self.object)
            if self.object.link_visivel_ao_cliente else ''
        )
        return ctx


class OrcamentoCreateView(LoginRequiredMixin, CreateView):
    model = Orcamento
    form_class = OrcamentoForm
    template_name = 'orcamentos/orcamento_form.html'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('cliente'):
            initial['cliente'] = self.request.GET.get('cliente')
        return initial

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        post = self.request.POST or None
        ctx['formset_servico'] = ItemServicoFormSet(post, prefix='servico')
        ctx['formset_peca']    = ItemPecaFormSet(post, prefix='peca')
        ctx['veiculo_inicial'] = self.request.GET.get('veiculo', '')
        _build_lookup_json(ctx)
        return ctx

    def form_valid(self, form):
        ctx        = self.get_context_data(form=form)
        fs_servico = ctx['formset_servico']
        fs_peca    = ctx['formset_peca']
        if fs_servico.is_valid() and fs_peca.is_valid():
            form.instance.criado_por = self.request.user
            self.object = form.save()
            fs_servico.instance = self.object
            fs_servico.save()
            fs_peca.instance = self.object
            fs_peca.save()
            self.object.recalcular_totais()
            messages.success(self.request, f'Orçamento {self.object} criado com sucesso!')
            registrar_historico(orcamento=self.object, tipo='criacao',
                                descricao='Orçamento criado.',
                                usuario=self.request.user)
            return redirect(self.get_success_url())
        messages.error(self.request, 'Corrija os erros nos itens de serviço ou peças antes de salvar.')
        return self.render_to_response(ctx)

    def get_success_url(self):
        return reverse_lazy('orcamentos:detail', kwargs={'pk': self.object.pk})


class OrcamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = Orcamento
    form_class = OrcamentoForm
    template_name = 'orcamentos/orcamento_form.html'

    def dispatch(self, request, *args, **kwargs):
        orc = self.get_object()
        if not orc.pode_editar:
            messages.error(
                request,
                f'O orçamento ORC-{orc.numero} não pode ser editado '
                f'pois está com status "{orc.get_status_display()}".'
            )
            return redirect(reverse('orcamentos:detail', kwargs={'pk': orc.pk}))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        post = self.request.POST or None
        ctx['formset_servico'] = ItemServicoFormSet(post, instance=self.object, prefix='servico')
        ctx['formset_peca']    = ItemPecaFormSet(post, instance=self.object, prefix='peca')
        _build_lookup_json(ctx)
        return ctx

    def form_valid(self, form):
        ctx        = self.get_context_data(form=form)
        fs_servico = ctx['formset_servico']
        fs_peca    = ctx['formset_peca']
        if fs_servico.is_valid() and fs_peca.is_valid():
            novo_status = form.cleaned_data.get('status')
            if novo_status == 'aprovado' and not form.instance.data_aprovacao:
                form.instance.data_aprovacao = timezone.now()
            elif novo_status != 'aprovado':
                form.instance.data_aprovacao = None
            with transaction.atomic():
                atual = Orcamento.objects.select_for_update().get(pk=form.instance.pk)
                if not atual.pode_editar:
                    messages.error(
                        self.request,
                        f'O orçamento ORC-{atual.numero} mudou para "{atual.get_status_display()}" '
                        'enquanto você editava. As alterações não foram salvas.',
                    )
                    return redirect(reverse('orcamentos:detail', kwargs={'pk': atual.pk}))
                self.object = form.save()
                fs_servico.save()
                fs_peca.save()
                self.object.recalcular_totais()
            messages.success(self.request, 'Orçamento atualizado com sucesso!')
            registrar_historico(orcamento=self.object, tipo='edicao',
                                descricao='Orçamento editado.',
                                usuario=self.request.user)
            return redirect(self.get_success_url())
        messages.error(self.request, 'Corrija os erros nos itens de serviço ou peças antes de salvar.')
        return self.render_to_response(ctx)

    def get_success_url(self):
        return reverse_lazy('orcamentos:detail', kwargs={'pk': self.object.pk})


class _TransicaoStatusView(LoginRequiredMixin, View):
    metodo = None
    rotulo = None
    nivel_mensagem = messages.SUCCESS
    texto_sucesso = None

    def post(self, request, pk):
        orc = get_object_or_404(Orcamento, pk=pk)
        try:
            status_anterior = getattr(orc, self.metodo)()
        except TransicaoStatusInvalida as erro:
            messages.error(request, str(erro))
            return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))
        messages.add_message(request, self.nivel_mensagem, self.texto_sucesso.format(orc=orc))
        registrar_historico(orcamento=orc, tipo='status',
                            descricao=f'Status: {status_anterior} → {self.rotulo}.',
                            usuario=request.user)
        return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))


class OrcamentoAprovarView(_TransicaoStatusView):
    metodo = 'aprovar'
    rotulo = 'Aprovado'
    texto_sucesso = 'Orçamento {orc} aprovado!'


class OrcamentoReprovarView(_TransicaoStatusView):
    metodo = 'reprovar'
    rotulo = 'Reprovado'
    nivel_mensagem = messages.WARNING
    texto_sucesso = 'Orçamento {orc} reprovado.'


class OrcamentoEnviarView(_TransicaoStatusView):
    metodo = 'marcar_enviado'
    rotulo = 'Enviado ao Cliente'
    nivel_mensagem = messages.INFO
    texto_sucesso = 'Orçamento {orc} marcado como enviado ao cliente.'


class OrcamentoEnviarWhatsAppView(LoginRequiredMixin, View):
    def post(self, request, pk):
        orc = get_object_or_404(Orcamento.objects.select_related('cliente', 'veiculo__modelo'), pk=pk)
        url_detalhe = reverse('orcamentos:detail', kwargs={'pk': pk})

        motivo = motivo_bloqueio_envio(orc) or motivo_sem_whatsapp(orc.cliente)
        if motivo:
            messages.error(request, f'Não foi possível enviar pelo WhatsApp. {motivo}')
            return redirect(url_detalhe)

        orc.garantir_link_publico()
        try:
            status_anterior = orc.marcar_enviado()
        except TransicaoStatusInvalida as erro:
            messages.error(request, str(erro))
            return redirect(url_detalhe)

        telefone, url_whatsapp = link_whatsapp_orcamento(request, orc)
        descricao = f'Link do orçamento enviado pelo WhatsApp para {formatar_telefone_exibicao(telefone)}.'
        if status_anterior != orc.get_status_display():
            descricao = f'Status: {status_anterior} → Enviado ao Cliente. ' + descricao
        registrar_historico(orcamento=orc, tipo='status', descricao=descricao, usuario=request.user)
        return redirect(url_whatsapp)


class OrcamentoNovoLinkView(LoginRequiredMixin, View):
    def post(self, request, pk):
        orc = get_object_or_404(Orcamento, pk=pk)
        motivo = motivo_bloqueio_envio(orc)
        if motivo:
            messages.error(request, f'Não foi possível gerar o link. {motivo}')
            return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))
        tinha_link = bool(orc.token_publico)
        orc.regenerar_link_publico()
        try:
            status_anterior = orc.marcar_enviado()
        except TransicaoStatusInvalida as erro:
            messages.error(request, str(erro))
            return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))
        if tinha_link:
            messages.success(request, 'Novo link gerado. O link anterior deixou de funcionar.')
            descricao = 'Novo link do cliente gerado; o link anterior foi invalidado.'
        else:
            messages.success(request, 'Link do cliente gerado. Copie e envie ao cliente.')
            descricao = 'Link do cliente gerado.'
        if status_anterior != orc.get_status_display():
            descricao = f'Status: {status_anterior} → Enviado ao Cliente. ' + descricao
        registrar_historico(orcamento=orc, tipo='status', descricao=descricao, usuario=request.user)
        return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))


class OrcamentoGerarOSView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from ordens_servico.models import OrdemServico, ItemOSServico, ItemOSPeca
        orc = get_object_or_404(Orcamento, pk=pk, status='aprovado')
        if _orcamento_tem_os(orc):
            messages.warning(request, 'Já existe uma OS para este orçamento.')
            return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': orc.ordem_servico.pk}))

        # Garante que o veículo do orçamento pertence ao cliente do orçamento
        if orc.veiculo.cliente_id != orc.cliente_id:
            messages.error(
                request,
                f'Não é possível gerar a OS: o veículo {orc.veiculo.placa} não pertence '
                f'ao cliente {orc.cliente.nome}. Corrija o orçamento antes de continuar.'
            )
            return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))
        with transaction.atomic():
            os_obj = OrdemServico.objects.create(
                orcamento=orc,
                cliente=orc.cliente,
                veiculo=orc.veiculo,
                criado_por=request.user,
                km_entrada=orc.km_entrada,
                defeito_relatado='Gerado a partir do orçamento ' + str(orc),
                desconto_valor=orc.desconto_valor,
            )
            for item in orc.itens_servico.all():
                ItemOSServico.objects.create(
                    ordem_servico=os_obj,
                    tipo_servico=item.tipo_servico,
                    descricao=item.descricao,
                    quantidade=item.quantidade,
                    preco_unitario=item.preco_unitario,
                )
            for item in orc.itens_peca.all():
                ItemOSPeca.objects.create(
                    ordem_servico=os_obj,
                    produto=item.produto,
                    descricao=item.descricao,
                    quantidade=item.quantidade,
                    preco_unitario=item.preco_unitario,
                )
            os_obj.recalcular_totais()
        messages.success(request, f'Ordem de Serviço {os_obj} criada com sucesso!')
        registrar_historico(orcamento=orc, tipo='os_gerada',
                            descricao=f'OS-{os_obj.numero} gerada a partir deste orçamento.',
                            usuario=request.user)
        registrar_historico(ordem_servico=os_obj, tipo='criacao',
                            descricao=f'OS criada a partir do orçamento ORC-{orc.numero}.',
                            usuario=request.user)
        return redirect(reverse('ordens_servico:os_detalhe', kwargs={'pk': os_obj.pk}))


_STATUS_SEGUROS = frozenset({'rascunho', 'reprovado', 'expirado', 'cancelado'})


def _orcamento_tem_os(orcamento):
    """Verifica se o orçamento gerou uma OS (OneToOne SET_NULL)."""
    try:
        return orcamento.ordem_servico is not None
    except Exception:
        return False


class OrcamentoDeleteView(LoginRequiredMixin, View):

    def _checar_admin(self, request):
        """Retorna True se o usuário é admin, caso contrário redireciona."""
        if getattr(request.user, 'role', None) != 'admin':
            messages.error(request, 'Apenas administradores podem excluir orçamentos.')
            return False
        return True

    def get(self, request, pk):
        if not self._checar_admin(request):
            return redirect(reverse('orcamentos:list'))
        orcamento  = get_object_or_404(Orcamento, pk=pk)
        tem_os     = _orcamento_tem_os(orcamento)
        return render(request, 'orcamentos/orcamento_confirm_delete.html', {
            'orcamento':    orcamento,
            'tem_os':       tem_os,
            'status_seguro': orcamento.status in _STATUS_SEGUROS,
        })

    def post(self, request, pk):
        if not self._checar_admin(request):
            return redirect(reverse('orcamentos:list'))
        orcamento = get_object_or_404(Orcamento, pk=pk)
        acao      = request.POST.get('acao')

        if acao == 'excluir':
            numero = orcamento.numero
            if orcamento.respostas_cliente.exists():
                messages.error(
                    request,
                    f'O orçamento ORC-{numero} tem resposta registrada pelo cliente e não pode ser '
                    'excluído, pois ela é o comprovante da decisão. Cancele o orçamento em vez de excluir.',
                )
                return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))
            orcamento.delete()          # CASCADE remove itens; SET_NULL desvincula OS
            messages.success(request, f'Orçamento ORC-{numero} excluído permanentemente.')
            return redirect(reverse('orcamentos:list'))

        elif acao == 'cancelar':
            orcamento.status = 'cancelado'
            orcamento.save(update_fields=['status'])
            messages.success(request, f'Orçamento ORC-{orcamento.numero} cancelado.')
            registrar_historico(orcamento=orcamento, tipo='status',
                                descricao='Status alterado para Cancelado.',
                                usuario=request.user)
            return redirect(reverse('orcamentos:detail', kwargs={'pk': pk}))

        messages.error(request, 'Ação inválida.')
        return redirect(reverse('orcamentos:list'))


class OrcamentoPdfView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from .pdf import gerar_pdf_orcamento
        orc       = get_object_or_404(Orcamento, pk=pk)
        pdf_bytes = gerar_pdf_orcamento(orc)
        response  = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="orcamento-{orc.numero}.pdf"'
        return response


class OrcamentoPrintView(LoginRequiredMixin, DetailView):
    """Página HTML formatada para impressão / salvar como PDF pelo browser."""
    model               = Orcamento
    template_name       = 'orcamentos/orcamento_print.html'
    context_object_name = 'orcamento'

    def get_queryset(self):
        return Orcamento.objects.select_related(
            'cliente', 'veiculo', 'veiculo__modelo', 'criado_por',
        ).prefetch_related(
            'itens_servico__tipo_servico',
            'itens_peca__produto',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['itens_servico'] = self.object.itens_servico.select_related('tipo_servico')
        ctx['itens_peca']    = self.object.itens_peca.select_related('produto')
        return ctx


class TipoServicoListView(LoginRequiredMixin, ListView):
    model = TipoServico
    template_name = 'orcamentos/tipo_servico_list.html'
    context_object_name = 'tipos'


class TipoServicoCreateView(LoginRequiredMixin, CreateView):
    model = TipoServico
    form_class = TipoServicoForm
    template_name = 'orcamentos/tipo_servico_form.html'
    success_url = reverse_lazy('orcamentos:tipo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de serviço cadastrado!')
        return super().form_valid(form)


class TipoServicoUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoServico
    form_class = TipoServicoForm
    template_name = 'orcamentos/tipo_servico_form.html'
    success_url = reverse_lazy('orcamentos:tipo_list')
