"""
Módulo de cálculo trabalhista determinístico.

Implementa regras da CLT para cálculo de verbas rescisórias sem uso de IA.
Todos os cálculos são baseados em fórmulas matemáticas precisas.
"""

from datetime import date
from typing import Dict, Any

from dateutil.relativedelta import relativedelta

from models.schemas import DadosTrabalhistasExtraidos


def calcular_remuneracao_total(dados: DadosTrabalhistasExtraidos) -> float:
    """
    Calcula a remuneração total do trabalhador (salário base + adicionais).

    Args:
        dados: Objeto contendo dados extraídos da reclamação trabalhista.

    Returns:
        Valor total da remuneração (salário base + todos os adicionais).

    Exemplo:
        >>> dados = DadosTrabalhistasExtraidos(
        ...     salario_base=2000.0,
        ...     adicionais=Adicionais(insalubridade=400.0, noturno=200.0)
        ... )
        >>> calcular_remuneracao_total(dados)
        2600.0
    """
    remuneracao = dados.salario_base if dados.salario_base else 0.0

    if dados.adicionais:
        if dados.adicionais.insalubridade:
            remuneracao += dados.adicionais.insalubridade
        if dados.adicionais.periculosidade:
            remuneracao += dados.adicionais.periculosidade
        if dados.adicionais.noturno:
            remuneracao += dados.adicionais.noturno

    return remuneracao


def calcular_rescisao(dados: DadosTrabalhistasExtraidos) -> Dict[str, Any]:
    """
    Calcula valores estimados de verbas rescisórias trabalhistas.

    Args:
        dados: Objeto contendo dados extraídos da reclamação trabalhista.

    Returns:
        Dicionário contendo:
        - status: "sucesso" ou "erro"
        - tempo_servico: Duração do vínculo empregatício
        - memoria_calculo: Detalhamento de cada verba calculada
        - remuneracao_base_calculo: Salário base + adicionais
        - total_estimado: Soma das verbas rescisórias
        - multa_477_valor: Valor da multa do Art. 477 (atraso no pagamento)
        - multa_467_valor: Valor da multa do Art. 467 (verbas incontroversas)
        - total_geral: Soma de tudo (verbas + multas)
        - observacoes: Avisos e notas sobre os cálculos
        - erro: Mensagem de erro (se aplicável)

    Exemplo:
        >>> from models.schemas import DadosTrabalhistasExtraidos
        >>> from datetime import date
        >>> dados = DadosTrabalhistasExtraidos(
        ...     data_admissao=date(2020, 1, 1),
        ...     data_dispensa=date(2023, 1, 1),
        ...     salario_base=2000.0,
        ...     verbas_requeridas=["fgts", "multa_40", "aviso_previo"],
        ...     multa_477_requerida=True
        ... )
        >>> resultado = calcular_rescisao(dados)
        >>> print(f"Total: R$ {resultado['total_geral']:.2f}")
    """
    # Validações iniciais
    if dados.data_admissao is None or dados.data_dispensa is None:
        return {
            "status": "erro",
            "erro": "Datas de admissão e dispensa são obrigatórias para realizar o cálculo.",
            "total_estimado": 0.0,
            "total_geral": 0.0
        }

    if dados.salario_base is None or dados.salario_base <= 0:
        return {
            "status": "erro",
            "erro": "Salário base inválido ou não informado.",
            "total_estimado": 0.0,
            "total_geral": 0.0
        }

    # Calcula remuneração total para base de cálculo
    remuneracao_total = calcular_remuneracao_total(dados)

    # Calcula tempo de serviço
    delta = relativedelta(dados.data_dispensa, dados.data_admissao)
    meses_trabalhados = (delta.years * 12) + delta.months
    dias_extras = delta.days

    # Ajusta meses considerando dias extras (proporcional)
    if dias_extras > 0:
        meses_trabalhados += dias_extras / 30.0

    # Inicializa memória de cálculo
    memoria_calculo = {}
    observacoes = []
    total_estimado = 0.0

    # 1. FGTS (8% sobre salário base por mês trabalhado)
    if "fgts" in dados.verbas_requeridas:
        fgts_estimado = dados.salario_base * 0.08 * meses_trabalhados
        memoria_calculo["fgts"] = {
            "descricao": "FGTS acumulado estimado (8% × salário × meses)",
            "formula": f"{dados.salario_base} × 0.08 × {meses_trabalhados:.2f}",
            "valor": round(fgts_estimado, 2)
        }
        total_estimado += fgts_estimado
    else:
        fgts_estimado = 0.0

    # 2. Multa 40% sobre FGTS (rescisão sem justa causa)
    if "multa_40" in dados.verbas_requeridas:
        # Calcula sobre o FGTS estimado, mesmo que não esteja nas verbas
        fgts_base = fgts_estimado if fgts_estimado > 0 else (dados.salario_base * 0.08 * meses_trabalhados)
        multa_40 = fgts_base * 0.40
        memoria_calculo["multa_40_fgts"] = {
            "descricao": "Multa de 40% sobre FGTS (demissão sem justa causa)",
            "formula": f"{fgts_base:.2f} × 0.40",
            "valor": round(multa_40, 2)
        }
        total_estimado += multa_40

    # 3. Aviso Prévio (1 salário base)
    if "aviso_previo" in dados.verbas_requeridas:
        aviso_previo = dados.salario_base
        memoria_calculo["aviso_previo"] = {
            "descricao": "Aviso prévio indenizado (1 salário base)",
            "formula": f"{dados.salario_base}",
            "valor": round(aviso_previo, 2)
        }
        total_estimado += aviso_previo

    # 4. Férias Proporcionais (salário/12 × meses trabalhados no ano)
    if "ferias_proporcionais" in dados.verbas_requeridas:
        # Simplificação: considera meses trabalhados no último ano aquisitivo
        meses_ano_atual = min(meses_trabalhados % 12, 12)
        ferias_proporcionais = (dados.salario_base / 12) * meses_ano_atual
        ferias_com_terco = ferias_proporcionais * 1.333  # + 1/3 constitucional
        memoria_calculo["ferias_proporcionais"] = {
            "descricao": "Férias proporcionais + 1/3 constitucional",
            "formula": f"({dados.salario_base} / 12 × {meses_ano_atual:.2f}) × 1.333",
            "valor": round(ferias_com_terco, 2)
        }
        total_estimado += ferias_com_terco

    # 5. 13º Salário Proporcional
    if "decimo_terceiro" in dados.verbas_requeridas:
        meses_ano_atual = min(meses_trabalhados % 12, 12)
        decimo_terceiro = (dados.salario_base / 12) * meses_ano_atual
        memoria_calculo["decimo_terceiro"] = {
            "descricao": "13º salário proporcional",
            "formula": f"{dados.salario_base} / 12 × {meses_ano_atual:.2f}",
            "valor": round(decimo_terceiro, 2)
        }
        total_estimado += decimo_terceiro

    # 6. MULTA DO ART. 477 CLT (Atraso no pagamento das verbas rescisórias)
    multa_477_valor = 0.0
    if dados.multa_477_requerida:
        multa_477_valor = remuneracao_total
        memoria_calculo["multa_477_clt"] = {
            "descricao": "Multa do Art. 477 CLT (atraso no pagamento - 1 remuneração)",
            "formula": f"Salário base ({dados.salario_base}) + Adicionais = {remuneracao_total}",
            "valor": round(multa_477_valor, 2)
        }
        observacoes.append("Multa do Art. 477 aplicada: atraso no pagamento das verbas rescisórias.")

    # 7. MULTA DO ART. 467 CLT (Verbas incontroversas - 50% sobre verbas não pagas)
    multa_467_valor = 0.0
    if dados.multa_467_requerida:
        # Identifica verbas rescisórias calculadas (base para a multa de 50%)
        verbas_incontroversas = 0.0

        # Soma apenas verbas rescisórias típicas (não inclui FGTS e multa 40%)
        if "aviso_previo" in memoria_calculo:
            verbas_incontroversas += memoria_calculo["aviso_previo"]["valor"]

        if "ferias_proporcionais" in memoria_calculo:
            verbas_incontroversas += memoria_calculo["ferias_proporcionais"]["valor"]

        if "decimo_terceiro" in memoria_calculo:
            verbas_incontroversas += memoria_calculo["decimo_terceiro"]["valor"]

        # Aplica 50% sobre as verbas incontroversas
        multa_467_valor = verbas_incontroversas * 0.50

        memoria_calculo["multa_467_clt"] = {
            "descricao": "Multa do Art. 467 CLT (50% sobre verbas incontroversas)",
            "formula": f"(Aviso Prévio + Férias + 13º) × 0.50 = {verbas_incontroversas:.2f} × 0.50",
            "valor": round(multa_467_valor, 2)
        }
        observacoes.append("Multa do Art. 467 aplicada: 50% sobre verbas incontroversas não pagas.")

    # TOTAL GERAL (Verbas + Multas CLT)
    total_geral = total_estimado + multa_477_valor + multa_467_valor

    # Adiciona observações relevantes
    if meses_trabalhados < 1:
        observacoes.append("Atenção: Tempo de serviço inferior a 1 mês. Alguns cálculos podem ser proporcionais.")

    if dados.adicionais and (dados.adicionais.insalubridade or dados.adicionais.periculosidade or dados.adicionais.noturno):
        observacoes.append(
            f"Remuneração total considerada (salário + adicionais): R$ {remuneracao_total:.2f}"
        )

    if dados.justificativa_demissao and "justa causa" in dados.justificativa_demissao.lower():
        observacoes.append("ALERTA: Em demissão por justa causa, várias verbas rescisórias NÃO são devidas.")

    # Adiciona informações sobre verbas não calculadas
    verbas_calculadas_keys = [k for k in memoria_calculo.keys() if not k.startswith("multa_")]
    verbas_nao_calculadas = [v for v in dados.verbas_requeridas if v not in ["fgts", "multa_40", "aviso_previo", "ferias_proporcionais", "decimo_terceiro", "saldo_salario"]]

    if verbas_nao_calculadas:
        observacoes.append(f"Verbas requeridas não calculadas automaticamente: {', '.join(verbas_nao_calculadas)}")

    # Monta resultado final
    return {
        "status": "sucesso",
        "tempo_servico": {
            "anos": delta.years,
            "meses": delta.months,
            "dias": delta.days,
            "meses_totais": round(meses_trabalhados, 2)
        },
        "salario_base": dados.salario_base,
        "remuneracao_base_calculo": round(remuneracao_total, 2),
        "memoria_calculo": memoria_calculo,
        "total_estimado": round(total_estimado, 2),
        "multa_477_valor": round(multa_477_valor, 2),
        "multa_467_valor": round(multa_467_valor, 2),
        "total_geral": round(total_geral, 2),
        "observacoes": observacoes,
        "verbas_requeridas": dados.verbas_requeridas,
        "data_calculo": date.today().isoformat()
    }