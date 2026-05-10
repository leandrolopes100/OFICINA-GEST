from django import forms
from veiculos.models import Veiculo


class VeiculoChoiceField(forms.ModelChoiceField):
    """
    Campo de veículo com queryset mínimo para renderização (desempenho),
    mas que valida contra todos os veículos ativos ao receber o POST.
    Isso permite que o AJAX popule e submeta qualquer veículo ativo do cliente
    sem depender do queryset inicial de renderização.
    """

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return Veiculo.objects.get(pk=int(value), ativo=True)
        except (ValueError, TypeError, Veiculo.DoesNotExist):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'],
                code='invalid_choice',
                params={'value': value},
            )
