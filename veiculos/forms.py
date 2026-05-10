import re
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import Veiculo, Marca, Modelo


# ── Regex de placa ────────────────────────────────────────────────────────────
_RE_PLACA_ANTIGA   = re.compile(r'^[A-Z]{3}[0-9]{4}$')          # ABC1234
_RE_PLACA_MERCOSUL = re.compile(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$') # ABC1D23

# ── Regex de chassi (VIN) — sem I, O, Q ───────────────────────────────────────
_RE_CHASSI = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')


def _validar_renavam(digits: str) -> bool:
    """Valida o dígito verificador de um RENAVAM com 9 ou 11 dígitos."""
    if len(digits) == 9:
        digits = '00' + digits          # normaliza para 11 dígitos
    if len(set(digits)) == 1:           # ex: 11111111111 — inválido
        return False
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma  = sum(int(digits[i]) * pesos[i] for i in range(10))
    resto = soma % 11
    digito_esperado = 0 if resto < 2 else 11 - resto
    return digito_esperado == int(digits[10])


class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = [
            'cliente', 'marca', 'modelo',
            'ano_fabricacao', 'ano_modelo', 'cor',
            'placa', 'renavam', 'chassi', 'combustivel',
            'km_atual', 'km_proxima_revisao', 'data_proxima_revisao',
            'observacoes', 'ativo',
        ]
        widgets = {
            'data_proxima_revisao': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        cliente_id = kwargs.pop('cliente_id', None)
        super().__init__(*args, **kwargs)
        if cliente_id:
            from clientes.models import Cliente
            self.fields['cliente'].initial = cliente_id
        self.fields['placa'].widget.attrs.update({
            'data-mask': 'placa',
            'placeholder': 'ABC-1234 ou ABC1D23',
        })
        self.fields['renavam'].widget.attrs.update({
            'placeholder': '11 dígitos',
            'maxlength': '11',
        })
        self.fields['chassi'].widget.attrs.update({
            'placeholder': '17 caracteres alfanuméricos',
            'maxlength': '17',
            'style': 'text-transform:uppercase',
        })
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('cliente', css_class='col-md-12')),
            Row(
                Column('marca', css_class='col-md-4'),
                Column('modelo', css_class='col-md-4'),
                Column('combustivel', css_class='col-md-4'),
            ),
            Row(
                Column('ano_fabricacao', css_class='col-md-3'),
                Column('ano_modelo', css_class='col-md-3'),
                Column('cor', css_class='col-md-3'),
                Column('placa', css_class='col-md-3'),
            ),
            Row(
                Column('renavam', css_class='col-md-4'),
                Column('chassi', css_class='col-md-4'),
                Column('km_atual', css_class='col-md-4'),
            ),
            Row(
                Column('km_proxima_revisao', css_class='col-md-4'),
                Column('data_proxima_revisao', css_class='col-md-4'),
                Column('ativo', css_class='col-md-4'),
            ),
            'observacoes',
            Submit('submit', 'Salvar Veículo', css_class='btn btn-primary'),
        )

    # ── Placa ─────────────────────────────────────────────────────────────────
    def clean_placa(self):
        placa = self.cleaned_data.get('placa', '')
        # Normaliza: maiúsculas e remove hífen/espaços antes de validar
        placa = placa.upper().replace('-', '').replace(' ', '')

        if not (_RE_PLACA_ANTIGA.match(placa) or _RE_PLACA_MERCOSUL.match(placa)):
            raise forms.ValidationError(
                'Placa inválida. Informe no formato antigo (ABC-1234) '
                'ou Mercosul (ABC1D23).'
            )
        # Armazena sem hífen e em maiúsculas para consistência no banco
        return placa

    # ── RENAVAM ───────────────────────────────────────────────────────────────
    def clean_renavam(self):
        renavam = self.cleaned_data.get('renavam', '').strip()
        if not renavam:
            return renavam  # campo opcional — vazio é aceito

        digits = ''.join(filter(str.isdigit, renavam))

        if len(digits) not in (9, 11):
            raise forms.ValidationError(
                f'RENAVAM deve ter 9 ou 11 dígitos numéricos '
                f'(informado: {len(digits)} dígito(s)).'
            )

        if not _validar_renavam(digits):
            raise forms.ValidationError(
                'RENAVAM inválido — o dígito verificador não confere. '
                'Verifique se o número foi digitado corretamente.'
            )

        return digits  # armazena apenas dígitos

    # ── Chassi (VIN) ──────────────────────────────────────────────────────────
    def clean_chassi(self):
        chassi = self.cleaned_data.get('chassi', '').strip().upper()
        if not chassi:
            return chassi  # campo opcional — vazio é aceito

        if len(chassi) != 17:
            raise forms.ValidationError(
                f'O chassi deve ter exatamente 17 caracteres '
                f'(informado: {len(chassi)}).'
            )

        if not _RE_CHASSI.match(chassi):
            raise forms.ValidationError(
                'Chassi inválido. Use apenas letras (exceto I, O e Q) '
                'e dígitos (0-9).'
            )

        return chassi  # armazena em maiúsculas

    # ── Consistência entre anos ───────────────────────────────────────────────
    def clean(self):
        cleaned    = super().clean()
        ano_fab    = cleaned.get('ano_fabricacao')
        ano_modelo = cleaned.get('ano_modelo')

        if ano_fab and ano_modelo and ano_modelo < ano_fab:
            self.add_error(
                'ano_modelo',
                'O ano do modelo não pode ser anterior ao ano de fabricação.'
            )
        return cleaned


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ['nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].widget.attrs['class'] = 'form-control'


class ModeloForm(forms.ModelForm):
    class Meta:
        model = Modelo
        fields = ['marca', 'nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'
