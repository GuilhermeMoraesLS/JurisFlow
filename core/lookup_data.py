"""
Módulo de consulta de dados históricos oficiais para cálculos previdenciários.

Fornece valores de salário mínimo e teto do INSS por competência,
essenciais para validação e limitação de benefícios previdenciários.
"""

from datetime import date
from typing import Dict, Tuple


# Histórico de Salário Mínimo Nacional
# Formato: {ano: [(mes_inicio, valor), ...]}
# Se houver apenas uma tupla, o valor é válido para todo o ano
HISTORICO_SALARIO_MINIMO: Dict[int, list] = {
    2022: [(1, 1212.00)],  # R$ 1.212,00 (todo o ano)
    2023: [
        (1, 1302.00),  # R$ 1.302,00 (Janeiro a Abril)
        (5, 1320.00),  # R$ 1.320,00 (Maio a Dezembro)
    ],
    2024: [(1, 1412.00)],  # R$ 1.412,00 (todo o ano)
    2025: [(1, 1518.00)],  # R$ 1.518,00 (todo o ano)
}


# Histórico do Teto do INSS (Limite Máximo de Benefício)
# Formato: {ano: [(mes_inicio, valor), ...]}
HISTORICO_TETO_INSS: Dict[int, list] = {
    2022: [(1, 7087.22)],  # R$ 7.087,22
    2023: [
        (1, 7507.49),  # R$ 7.507,49 (Janeiro a Abril)
        (5, 7786.02),  # R$ 7.786,02 (Maio a Dezembro)
    ],
    2024: [(1, 7786.02)],  # R$ 7.786,02 (reajuste ficou igual)
    2025: [(1, 8157.41)],  # R$ 8.157,41 (estimado)
}


def obter_salario_minimo(data_competencia: date) -> float:
    """
    Retorna o valor do salário mínimo vigente na data especificada.

    Args:
        data_competencia: Data do mês de competência do benefício.

    Returns:
        Valor do salário mínimo nacional em Reais.

    Raises:
        ValueError: Se não houver dados para o ano solicitado.

    Exemplo:
        >>> from datetime import date
        >>> obter_salario_minimo(date(2023, 3, 1))
        1302.0
        >>> obter_salario_minimo(date(2023, 7, 15))
        1320.0
        >>> obter_salario_minimo(date(2024, 12, 1))
        1412.0
    """
    ano = data_competencia.year
    mes = data_competencia.month

    # Verifica se há dados para o ano
    if ano not in HISTORICO_SALARIO_MINIMO:
        # Se for ano futuro sem dados, retorna o último valor conhecido
        ultimo_ano_conhecido = max(HISTORICO_SALARIO_MINIMO.keys())
        if ano > ultimo_ano_conhecido:
            ultimo_valor = HISTORICO_SALARIO_MINIMO[ultimo_ano_conhecido][-1][1]
            return ultimo_valor
        else:
            raise ValueError(
                f"Não há dados de salário mínimo para o ano {ano}. "
                f"Anos disponíveis: {sorted(HISTORICO_SALARIO_MINIMO.keys())}"
            )

    # Busca o valor vigente no mês específico
    valores_ano = HISTORICO_SALARIO_MINIMO[ano]

    # Percorre os valores do ano em ordem reversa para pegar o mais recente válido
    valor_vigente = valores_ano[0][1]  # Fallback para o primeiro valor do ano

    for mes_inicio, valor in valores_ano:
        if mes >= mes_inicio:
            valor_vigente = valor
        else:
            break  # Já passou do mês válido

    return valor_vigente


def obter_teto_inss(data_competencia: date) -> float:
    """
    Retorna o valor do teto do INSS vigente na data especificada.

    O teto é o limite máximo que um benefício previdenciário pode pagar.
    Utilizado para validar se a RMI informada está dentro dos limites legais.

    Args:
        data_competencia: Data do mês de competência do benefício.

    Returns:
        Valor do teto do INSS em Reais.

    Raises:
        ValueError: Se não houver dados para o ano solicitado.

    Exemplo:
        >>> from datetime import date
        >>> obter_teto_inss(date(2023, 2, 1))
        7507.49
        >>> obter_teto_inss(date(2023, 8, 1))
        7786.02
        >>> obter_teto_inss(date(2024, 6, 1))
        7786.02
    """
    ano = data_competencia.year
    mes = data_competencia.month

    # Verifica se há dados para o ano
    if ano not in HISTORICO_TETO_INSS:
        # Se for ano futuro sem dados, retorna o último valor conhecido
        ultimo_ano_conhecido = max(HISTORICO_TETO_INSS.keys())
        if ano > ultimo_ano_conhecido:
            ultimo_valor = HISTORICO_TETO_INSS[ultimo_ano_conhecido][-1][1]
            return ultimo_valor
        else:
            raise ValueError(
                f"Não há dados de teto do INSS para o ano {ano}. "
                f"Anos disponíveis: {sorted(HISTORICO_TETO_INSS.keys())}"
            )

    # Busca o valor vigente no mês específico
    valores_ano = HISTORICO_TETO_INSS[ano]

    # Percorre os valores do ano em ordem reversa para pegar o mais recente válido
    valor_vigente = valores_ano[0][1]  # Fallback para o primeiro valor do ano

    for mes_inicio, valor in valores_ano:
        if mes >= mes_inicio:
            valor_vigente = valor
        else:
            break  # Já passou do mês válido

    return valor_vigente


def obter_faixa_salario_minimo(data_inicio: date, data_fim: date) -> Dict[str, float]:
    """
    Retorna todos os valores de salário mínimo vigentes em um período.

    Útil para cálculos que precisam considerar reajustes durante o período
    de atraso do benefício.

    Args:
        data_inicio: Data inicial do período.
        data_fim: Data final do período.

    Returns:
        Dicionário {competência_str: valor_salario_minimo}
        Exemplo: {"01/2023": 1302.0, "05/2023": 1320.0, ...}

    Exemplo:
        >>> from datetime import date
        >>> from dateutil.relativedelta import relativedelta
        >>> faixa = obter_faixa_salario_minimo(date(2023, 1, 1), date(2023, 12, 31))
        >>> len(faixa)
        12
        >>> faixa["01/2023"]
        1302.0
        >>> faixa["06/2023"]
        1320.0
    """
    from dateutil.relativedelta import relativedelta

    faixa_valores = {}
    data_atual = data_inicio.replace(day=1)  # Primeiro dia do mês

    while data_atual <= data_fim:
        competencia = data_atual.strftime("%m/%Y")
        valor_sm = obter_salario_minimo(data_atual)
        faixa_valores[competencia] = valor_sm

        # Avança para o próximo mês
        data_atual = data_atual + relativedelta(months=1)

    return faixa_valores


def obter_faixa_teto_inss(data_inicio: date, data_fim: date) -> Dict[str, float]:
    """
    Retorna todos os valores de teto do INSS vigentes em um período.

    Args:
        data_inicio: Data inicial do período.
        data_fim: Data final do período.

    Returns:
        Dicionário {competência_str: valor_teto_inss}
        Exemplo: {"01/2023": 7507.49, "05/2023": 7786.02, ...}

    Exemplo:
        >>> from datetime import date
        >>> from dateutil.relativedelta import relativedelta
        >>> faixa = obter_faixa_teto_inss(date(2023, 1, 1), date(2023, 12, 31))
        >>> len(faixa)
        12
        >>> faixa["01/2023"]
        7507.49
        >>> faixa["06/2023"]
        7786.02
    """
    from dateutil.relativedelta import relativedelta

    faixa_valores = {}
    data_atual = data_inicio.replace(day=1)  # Primeiro dia do mês

    while data_atual <= data_fim:
        competencia = data_atual.strftime("%m/%Y")
        valor_teto = obter_teto_inss(data_atual)
        faixa_valores[competencia] = valor_teto

        # Avança para o próximo mês
        data_atual = data_atual + relativedelta(months=1)

    return faixa_valores


def validar_rmi(
    rmi: float,
    data_competencia: date,
    permitir_acima_teto: bool = False
) -> Tuple[bool, str]:
    """
    Valida se a RMI está dentro dos limites legais (salário mínimo e teto).

    Args:
        rmi: Renda Mensal Inicial a ser validada.
        data_competencia: Data de competência do benefício.
        permitir_acima_teto: Se True, não valida o limite superior.

    Returns:
        Tupla (valido: bool, mensagem: str)

    Exemplo:
        >>> from datetime import date
        >>> validar_rmi(800.0, date(2024, 1, 1))
        (False, 'RMI (R$ 800,00) está abaixo do salário mínimo vigente (R$ 1.412,00).')
        >>> validar_rmi(1500.0, date(2024, 1, 1))
        (True, 'RMI válida.')
        >>> validar_rmi(9000.0, date(2024, 1, 1), permitir_acima_teto=False)
        (False, 'RMI (R$ 9.000,00) está acima do teto do INSS (R$ 7.786,02).')
    """
    salario_minimo = obter_salario_minimo(data_competencia)
    teto_inss = obter_teto_inss(data_competencia)

    # Valida limite inferior (salário mínimo)
    if rmi < salario_minimo:
        return (
            False,
            f"RMI (R$ {rmi:,.2f}) está abaixo do salário mínimo vigente (R$ {salario_minimo:,.2f}).".replace(',', '_').replace('.', ',').replace('_', '.')
        )

    # Valida limite superior (teto do INSS)
    if not permitir_acima_teto and rmi > teto_inss:
        return (
            False,
            f"RMI (R$ {rmi:,.2f}) está acima do teto do INSS (R$ {teto_inss:,.2f}).".replace(',', '_').replace('.', ',').replace('_', '.')
        )

    return (True, "RMI válida.")


# Função auxiliar para adicionar novos valores (uso interno/manutenção)
def adicionar_salario_minimo(ano: int, mes_inicio: int, valor: float) -> None:
    """
    Adiciona um novo valor de salário mínimo ao histórico.

    ATENÇÃO: Esta função é para manutenção do sistema.
    Use apenas para atualizar dados oficiais após publicação no DOU.

    Args:
        ano: Ano de vigência.
        mes_inicio: Mês de início da vigência (1-12).
        valor: Valor do salário mínimo em Reais.

    Exemplo:
        >>> adicionar_salario_minimo(2026, 1, 1600.00)
    """
    if ano not in HISTORICO_SALARIO_MINIMO:
        HISTORICO_SALARIO_MINIMO[ano] = []

    HISTORICO_SALARIO_MINIMO[ano].append((mes_inicio, valor))

    # Ordena por mês de início
    HISTORICO_SALARIO_MINIMO[ano].sort(key=lambda x: x[0])


def adicionar_teto_inss(ano: int, mes_inicio: int, valor: float) -> None:
    """
    Adiciona um novo valor de teto do INSS ao histórico.

    ATENÇÃO: Esta função é para manutenção do sistema.
    Use apenas para atualizar dados oficiais após publicação no DOU.

    Args:
        ano: Ano de vigência.
        mes_inicio: Mês de início da vigência (1-12).
        valor: Valor do teto em Reais.

    Exemplo:
        >>> adicionar_teto_inss(2026, 1, 8500.00)
    """
    if ano not in HISTORICO_TETO_INSS:
        HISTORICO_TETO_INSS[ano] = []

    HISTORICO_TETO_INSS[ano].append((mes_inicio, valor))

    # Ordena por mês de início
    HISTORICO_TETO_INSS[ano].sort(key=lambda x: x[0])