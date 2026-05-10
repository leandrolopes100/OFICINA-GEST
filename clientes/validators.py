from django.core.exceptions import ValidationError


def _validar_cpf(cpf: str) -> bool:
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    if (soma * 10 % 11) % 10 != int(cpf[9]):
        return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    return (soma * 10 % 11) % 10 == int(cpf[10])


def _validar_cnpj(cnpj: str) -> bool:
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False
    for i, pesos in enumerate([[5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                                [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]]):
        soma = sum(int(cnpj[j]) * pesos[j] for j in range(len(pesos)))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[12 + i]):
            return False
    return True


def validar_cpf_cnpj(valor: str) -> None:
    """Validator Django para campos CPF/CNPJ (detecta pelo tamanho dos dígitos)."""
    digitos = ''.join(filter(str.isdigit, valor or ''))
    if len(digitos) == 11:
        if not _validar_cpf(valor):
            raise ValidationError('CPF inválido. Verifique os dígitos informados.')
    elif len(digitos) == 14:
        if not _validar_cnpj(valor):
            raise ValidationError('CNPJ inválido. Verifique os dígitos informados.')
    else:
        raise ValidationError('Informe um CPF (11 dígitos) ou CNPJ (14 dígitos) válido.')
