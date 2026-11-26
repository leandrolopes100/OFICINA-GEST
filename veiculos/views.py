from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.utils.text import Truncator
from .models import Veiculo, Marca, Modelo
from .forms import VeiculoForm, MarcaForm, ModeloForm
from core.utils import rate_limit_ajax
from ordens_servico.models import OrdemServico


class VeiculoListView(LoginRequiredMixin, ListView):
    model = Veiculo
    template_name = 'veiculos/veiculo_list.html'
    context_object_name = 'veiculos'
    paginate_by = 20

    def get_queryset(self):
        status = self.request.GET.get('status', 'ativos')
        base   = Veiculo.objects.select_related('cliente', 'marca', 'modelo')

        if status == 'inativos':
            qs = base.filter(ativo=False)
        else:                          # 'ativos' é o padrão seguro
            qs = base.filter(ativo=True)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(placa__icontains=q)        |
                Q(cliente__nome__icontains=q) |
                Q(marca__nome__icontains=q)   |
                Q(modelo__nome__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q']              = self.request.GET.get('q', '')
        ctx['status_filtro']  = self.request.GET.get('status', 'ativos')
        ctx['total_inativos'] = Veiculo.objects.filter(ativo=False).count()
        return ctx


class VeiculoDetailView(LoginRequiredMixin, DetailView):
    model = Veiculo
    template_name = 'veiculos/veiculo_detail.html'
    context_object_name = 'veiculo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['orcamentos'] = self.object.orcamentos.order_by('-data_criacao')[:5]
        ctx['historico'] = OrdemServico.historico_do_veiculo(self.object)
        return ctx


class VeiculoHistoricoPdfView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from .pdf import gerar_pdf_historico_veiculo
        veiculo = get_object_or_404(Veiculo.objects.select_related('cliente', 'marca', 'modelo'), pk=pk)
        resposta = HttpResponse(gerar_pdf_historico_veiculo(veiculo), content_type='application/pdf')
        resposta['Content-Disposition'] = f'inline; filename="historico-{veiculo.placa}.pdf"'
        return resposta


class VeiculoCreateView(LoginRequiredMixin, CreateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/veiculo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente_id'] = self.request.GET.get('cliente')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Veículo cadastrado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('veiculos:detail', kwargs={'pk': self.object.pk})


class VeiculoUpdateView(LoginRequiredMixin, UpdateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/veiculo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente_id'] = None
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Veículo atualizado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('veiculos:detail', kwargs={'pk': self.object.pk})


def _veiculo_tem_historico(veiculo):
    return veiculo.orcamentos.exists() or veiculo.ordens_servico.exists()


class VeiculoDeleteView(LoginRequiredMixin, View):
    def _get_veiculo(self, pk):
        return get_object_or_404(Veiculo, pk=pk)

    def get(self, request, pk):
        veiculo      = self._get_veiculo(pk)
        tem_historico = _veiculo_tem_historico(veiculo)
        return render(request, 'veiculos/veiculo_confirm_delete.html', {
            'veiculo':       veiculo,
            'tem_historico': tem_historico,
            'n_orcamentos':  veiculo.orcamentos.count(),
            'n_os':          veiculo.ordens_servico.count(),
        })

    def post(self, request, pk):
        veiculo = self._get_veiculo(pk)
        acao    = request.POST.get('acao')

        tem_historico = _veiculo_tem_historico(veiculo)

        if acao == 'excluir':
            if tem_historico:
                messages.error(
                    request,
                    'Exclusão bloqueada: o veículo possui registros vinculados. '
                    'Use a opção Inativar.'
                )
                return redirect('veiculos:delete', pk=pk)
            try:
                placa = veiculo.placa
                veiculo.delete()
                messages.success(request, f'Veículo {placa} excluído permanentemente.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não foi possível excluir: existem registros vinculados a este veículo.'
                )
            return redirect('veiculos:list')

        elif acao == 'inativar':
            veiculo.ativo = False
            veiculo.save(update_fields=['ativo'])
            messages.success(
                request,
                f'Veículo {veiculo.placa} inativado. '
                'Ele não aparecerá em novas OS ou orçamentos.'
            )
            return redirect('veiculos:list')

        messages.error(request, 'Ação inválida.')
        return redirect('veiculos:list')


class VeiculoReativarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        veiculo = get_object_or_404(Veiculo, pk=pk, ativo=False)
        veiculo.ativo = True
        veiculo.save(update_fields=['ativo'])
        messages.success(request, f'Veículo {veiculo.placa} reativado com sucesso!')
        return redirect(f"{reverse_lazy('veiculos:list')}?status=ativos")


class MarcaListView(LoginRequiredMixin, ListView):
    model = Marca
    template_name = 'veiculos/marca_list.html'
    context_object_name = 'marcas'
    paginate_by = 20

    def get_queryset(self):
        return (
            Marca.objects
            .prefetch_related('modelos')
            .annotate(n_veiculos=Count('veiculo'))
            .order_by('nome')
        )


class MarcaCreateView(LoginRequiredMixin, CreateView):
    model = Marca
    form_class = MarcaForm
    template_name = 'veiculos/marca_form.html'
    success_url = reverse_lazy('veiculos:marca_list')

    def form_valid(self, form):
        messages.success(self.request, 'Marca cadastrada!')
        return super().form_valid(form)


class ModeloCreateView(LoginRequiredMixin, View):
    """Recebe POST do modal da página de marcas e cria um novo modelo."""

    def post(self, request):
        from django.db import IntegrityError
        marca_id = request.POST.get('marca', '').strip()
        nome     = request.POST.get('nome', '').strip()

        if not marca_id or not nome:
            messages.error(request, 'Informe a marca e o nome do modelo.')
            return redirect(reverse('veiculos:marca_list'))

        try:
            marca = Marca.objects.get(pk=marca_id)
        except Marca.DoesNotExist:
            messages.error(request, 'Marca inválida.')
            return redirect(reverse('veiculos:marca_list'))

        try:
            Modelo.objects.create(marca=marca, nome=nome)
            messages.success(request, f'Modelo "{nome}" adicionado à marca {marca.nome}.')
        except IntegrityError:
            messages.error(
                request,
                f'O modelo "{nome}" já existe para a marca {marca.nome}.'
            )

        return redirect(reverse('veiculos:marca_list'))


class ModeloDeleteView(LoginRequiredMixin, View):
    """Remove um modelo se não houver veículos vinculados."""

    def post(self, request, pk):
        modelo = get_object_or_404(Modelo, pk=pk)
        n_veiculos = modelo.veiculo_set.count()

        if n_veiculos > 0:
            messages.error(
                request,
                f'Não é possível excluir "{modelo.nome}": '
                f'há {n_veiculos} veículo(s) cadastrado(s) com este modelo.'
            )
        else:
            nome_marca  = modelo.marca.nome
            nome_modelo = modelo.nome
            modelo.delete()
            messages.success(
                request,
                f'Modelo "{nome_modelo}" ({nome_marca}) excluído com sucesso.'
            )

        return redirect(reverse('veiculos:marca_list'))


@login_required
@rate_limit_ajax(max_calls=60, window=60)
def veiculos_por_cliente_ajax(request, cliente_pk):
    veiculos = Veiculo.objects.filter(cliente_id=cliente_pk, ativo=True).select_related('modelo')
    ultimas = OrdemServico.ultimas_visitas(veiculos)
    data = []
    for veiculo in veiculos:
        ordem = ultimas.get(veiculo.id)
        data.append({
            'id': veiculo.id,
            'text': str(veiculo),
            'ultima_visita': {
                'data': timezone.localtime(ordem.data_abertura).strftime('%d/%m/%Y'),
                'numero': ordem.numero,
                'km': f'{ordem.km_entrada:,}'.replace(',', '.'),
                'relatado': Truncator(ordem.defeito_relatado).chars(120),
                'url': reverse('veiculos:detail', args=[veiculo.id]),
            } if ordem else None,
        })
    return JsonResponse({'results': data})


@login_required
@rate_limit_ajax(max_calls=60, window=60)
def modelos_por_marca_ajax(request, marca_pk):
    modelos = Modelo.objects.filter(marca_id=marca_pk).order_by('nome')
    data = [{'id': m.id, 'text': m.nome} for m in modelos]
    return JsonResponse({'results': data})
